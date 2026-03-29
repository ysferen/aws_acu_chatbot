import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from api_v1.models import Feedback, IngestJob, SourceChunk


def _assert_iso_utc_timestamp(value: str):
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert value.endswith("Z")


def _assert_error_envelope_shape(test_case: TestCase, payload: dict):
    test_case.assertEqual(set(payload.keys()), {"ok", "error", "meta"})
    test_case.assertFalse(payload["ok"])
    test_case.assertEqual(set(payload["error"].keys()), {"code", "message", "details", "retryable"})
    test_case.assertIsInstance(payload["error"]["code"], str)
    test_case.assertIsInstance(payload["error"]["message"], str)
    test_case.assertIsInstance(payload["error"]["details"], list)
    test_case.assertIsInstance(payload["error"]["retryable"], bool)
    test_case.assertEqual(set(payload["meta"].keys()), {"request_id", "timestamp"})
    test_case.assertIsInstance(payload["meta"]["request_id"], str)
    test_case.assertTrue(payload["meta"]["request_id"])
    _assert_iso_utc_timestamp(payload["meta"]["timestamp"])


class ErrorEnvelopeContractTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.student = user_model.objects.create_user(username="student_contract", password="pass12345")
        self.staff = user_model.objects.create_user(username="staff_contract", password="pass12345", is_staff=True)

        SourceChunk.objects.create(
            source_id="src_contract",
            chunk_id="chunk_1",
            title="Source",
            url="https://example.edu/source",
            snippet="snippet",
            page=1,
            doc_metadata={"k": "v"},
        )

    def test_error_400_schema_chat_validation(self):
        client = Client()
        response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "hello", "stream": "not_bool"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        _assert_error_envelope_shape(self, payload)
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")

    def test_error_401_schema_ingest_anonymous(self):
        client = Client()
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps(
                {
                    "idempotency_key": "key-contract-401",
                    "items": [{"type": "url", "value": "https://example.edu/a"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        payload = response.json()
        _assert_error_envelope_shape(self, payload)
        self.assertEqual(payload["error"]["code"], "UNAUTHORIZED")

    def test_error_403_schema_ingest_student_forbidden(self):
        client = Client()
        client.force_login(self.student)
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps(
                {
                    "idempotency_key": "key-contract-403",
                    "items": [{"type": "url", "value": "https://example.edu/b"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        payload = response.json()
        _assert_error_envelope_shape(self, payload)
        self.assertEqual(payload["error"]["code"], "FORBIDDEN")

    def test_error_404_schema_source_not_found(self):
        client = Client()
        response = client.get("/api/v1/sources/src_missing")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        _assert_error_envelope_shape(self, payload)
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")

    def test_error_409_schema_feedback_duplicate(self):
        client = Client()
        chat_response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "seed", "stream": False}),
            content_type="application/json",
        )
        self.assertEqual(chat_response.status_code, 200)
        session_id = chat_response.json()["data"]["session"]["id"]
        message_id = chat_response.json()["data"]["message"]["id"]

        first_feedback = client.post(
            "/api/v1/feedback",
            data=json.dumps({"session_id": session_id, "message_id": message_id, "rating": Feedback.RATING_UP}),
            content_type="application/json",
        )
        self.assertEqual(first_feedback.status_code, 201)

        duplicate_feedback = client.post(
            "/api/v1/feedback",
            data=json.dumps({"session_id": session_id, "message_id": message_id, "rating": Feedback.RATING_DOWN}),
            content_type="application/json",
        )
        self.assertEqual(duplicate_feedback.status_code, 409)
        payload = duplicate_feedback.json()
        _assert_error_envelope_shape(self, payload)
        self.assertEqual(payload["error"]["code"], "CONFLICT")


class RequestTracingTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username="staff_trace", password="pass12345", is_staff=True)

    def test_success_uses_incoming_x_request_id(self):
        client = Client()
        response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "trace", "stream": False}),
            content_type="application/json",
            HTTP_X_REQUEST_ID="req-from-test-123",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["request_id"], "req-from-test-123")
        _assert_iso_utc_timestamp(payload["meta"]["timestamp"])

    def test_error_generates_request_id_when_missing_header(self):
        client = Client()
        response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "", "stream": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        _assert_error_envelope_shape(self, payload)
        self.assertTrue(payload["meta"]["request_id"].startswith("req_"))


class IngestIdempotencyContractTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username="staff_ingest_contract", password="pass12345", is_staff=True)

    def test_ingest_duplicate_idempotency_returns_duplicate_true_with_202(self):
        client = Client()
        client.force_login(self.staff)

        first = client.post(
            "/api/v1/ingest",
            data=json.dumps(
                {
                    "idempotency_key": "dup-key-1",
                    "items": [{"type": "url", "value": "https://example.edu/1"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.json()["data"]["duplicate"], False)

        second = client.post(
            "/api/v1/ingest",
            data=json.dumps(
                {
                    "idempotency_key": "dup-key-1",
                    "items": [{"type": "url", "value": "https://example.edu/1"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 202)
        self.assertEqual(second.json()["data"]["duplicate"], True)
        self.assertEqual(IngestJob.objects.filter(idempotency_key="dup-key-1").count(), 1)
