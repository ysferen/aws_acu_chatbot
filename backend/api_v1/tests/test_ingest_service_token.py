import json

from django.test import Client, TestCase

from api_v1.models import ServiceToken


class IngestServiceTokenTests(TestCase):
    def test_ingest_with_valid_service_token(self):
        raw = "svc-token-123"
        ServiceToken.objects.create(
            name="ingest-worker",
            token_hash=ServiceToken.hash_raw_token(raw),
            scopes=["ingest:write"],
            is_active=True,
        )

        client = Client()
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["accepted_count"], 1)

    def test_ingest_rejects_invalid_service_token(self):
        client = Client()
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")

    def test_ingest_rejects_service_token_without_scope(self):
        raw = "svc-token-no-scope"
        ServiceToken.objects.create(
            name="readonly-worker",
            token_hash=ServiceToken.hash_raw_token(raw),
            scopes=["source:read"],
            is_active=True,
        )

        client = Client()
        response = client.post(
            "/api/v1/ingest",
            data=json.dumps({"items": [{"type": "url", "value": "https://example.edu"}]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "FORBIDDEN")
