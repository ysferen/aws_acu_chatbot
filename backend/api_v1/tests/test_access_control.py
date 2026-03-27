import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from api_v1.models import SourceChunk


class AccessControlTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.student = user_model.objects.create_user(username="student", password="pass12345")
        self.staff = user_model.objects.create_user(username="staff", password="pass12345", is_staff=True)
        SourceChunk.objects.create(
            source_id="src_public",
            chunk_id="chunk_1",
            title="Public Source",
            url="https://university.example.edu/public",
            snippet="Public snippet",
            page=1,
            doc_metadata={"source": "seed"},
        )

    def test_chat_allows_anonymous(self):
        client = Client()
        response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "Hello", "stream": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_sources_is_public(self):
        client = Client()
        response = client.get("/api/v1/sources/src_public")
        self.assertEqual(response.status_code, 200)

    def test_ingest_requires_auth(self):
        client = Client()
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")

    def test_ingest_forbids_student(self):
        client = Client()
        client.force_login(self.student)
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")

    def test_ingest_allows_staff(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")
