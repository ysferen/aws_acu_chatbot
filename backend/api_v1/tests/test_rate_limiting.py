import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

from api_v1.models import ChatMessage, ChatSession


class RateLimitingTests(TestCase):
    def setUp(self):
        cache.clear()
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(username="staff_rate", password="pass12345", is_staff=True)
        self.student = user_model.objects.create_user(username="student_rate", password="pass12345")

    def _assert_429_contract(self, response):
        self.assertEqual(response.status_code, 429)
        payload = response.json()
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "RATE_LIMITED")
        self.assertIsInstance(payload["error"]["details"], list)
        self.assertTrue(any(item.get("field") == "retry_after_seconds" for item in payload["error"]["details"]))
        self.assertIn("meta", payload)
        self.assertIn("request_id", payload["meta"])
        self.assertIn("timestamp", payload["meta"])

    def test_chat_rate_limit_exceeded_returns_429(self):
        client = Client()

        last_response = None
        for idx in range(11):
            last_response = client.post(
                "/api/v1/chat",
                data=json.dumps({"question": f"q-{idx}", "stream": False}),
                content_type="application/json",
            )

        self._assert_429_contract(last_response)

    def test_feedback_rate_limit_exceeded_returns_429(self):
        client = Client()
        client.force_login(self.student)

        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=self.student)
        messages = [
            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_ASSISTANT, content=f"assistant-{idx}")
            for idx in range(31)
        ]

        for message in messages[:30]:
            response = client.post(
                "/api/v1/feedback",
                data=json.dumps({"session_id": session.id, "message_id": message.id, "rating": "up"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)

        limited = client.post(
            "/api/v1/feedback",
            data=json.dumps({"session_id": session.id, "message_id": messages[30].id, "rating": "up"}),
            content_type="application/json",
        )
        self._assert_429_contract(limited)

    def test_ingest_rate_limit_exceeded_returns_429(self):
        client = Client()
        client.force_login(self.staff)

        for idx in range(5):
            response = client.post(
                "/api/v1/ingest",
                data=json.dumps(
                    {
                        "idempotency_key": f"ing-rate-{idx}",
                        "items": [{"type": "url", "value": f"https://example.edu/{idx}"}],
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 202)

        limited = client.post(
            "/api/v1/ingest",
            data=json.dumps(
                {
                    "idempotency_key": "ing-rate-over",
                    "items": [{"type": "url", "value": "https://example.edu/over"}],
                }
            ),
            content_type="application/json",
        )
        self._assert_429_contract(limited)
