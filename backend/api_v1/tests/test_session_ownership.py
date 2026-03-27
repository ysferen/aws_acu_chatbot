import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from api_v1.models import ChatMessage, ChatSession


class SessionOwnershipTests(TestCase):
    def _seed_session_for_client(self, client: Client):
        response = client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "Seed", "stream": False}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        session_id = response.json()["data"]["session"]["id"]
        return ChatSession.objects.get(id=session_id)

    def test_anonymous_can_read_own_session_messages(self):
        client = Client()
        chat_session = self._seed_session_for_client(client)

        response = client.get(f"/api/v1/sessions/{chat_session.id}/messages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["session_id"], chat_session.id)

    def test_anonymous_cannot_read_other_anonymous_session(self):
        owner_client = Client()
        chat_session = self._seed_session_for_client(owner_client)

        other_client = Client()
        response = other_client.get(f"/api/v1/sessions/{chat_session.id}/messages")
        self.assertEqual(response.status_code, 401)

        other_client.post(
            "/api/v1/chat",
            data=json.dumps({"question": "other", "stream": False}),
            content_type="application/json",
        )
        response_after_cookie = other_client.get(f"/api/v1/sessions/{chat_session.id}/messages")
        self.assertEqual(response_after_cookie.status_code, 404)
        self.assertEqual(response_after_cookie.json()["error"]["code"], "NOT_FOUND")

    def test_student_cannot_read_other_student_session(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="owner", password="pass12345")
        intruder = user_model.objects.create_user(username="intruder", password="pass12345")

        owner_session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)
        ChatMessage.objects.create(session=owner_session, role=ChatMessage.ROLE_USER, content="hi")

        intruder_client = Client()
        intruder_client.force_login(intruder)

        response = intruder_client.get(f"/api/v1/sessions/{owner_session.id}/messages")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_student_can_read_own_session(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="owner2", password="pass12345")

        owner_session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)
        ChatMessage.objects.create(session=owner_session, role=ChatMessage.ROLE_USER, content="hello")

        owner_client = Client()
        owner_client.force_login(owner)
        response = owner_client.get(f"/api/v1/sessions/{owner_session.id}/messages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["session_id"], owner_session.id)

    def test_cursor_pagination_asc_moves_to_next_page(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_owner", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)

        m1 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m1")
        m2 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m2")
        m3 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m3")

        client = Client()
        client.force_login(owner)

        first_page = client.get(f"/api/v1/sessions/{session.id}/messages?limit=2&order=asc")
        self.assertEqual(first_page.status_code, 200)
        first_data = first_page.json()["data"]
        first_ids = [item["id"] for item in first_data["messages"]]
        self.assertEqual(first_ids, [m1.id, m2.id])
        self.assertTrue(first_data["pagination"]["has_more"])
        self.assertEqual(first_data["pagination"]["next_cursor"], m2.id)

        second_page = client.get(
            f"/api/v1/sessions/{session.id}/messages?limit=2&order=asc&cursor={first_data['pagination']['next_cursor']}"
        )
        self.assertEqual(second_page.status_code, 200)
        second_data = second_page.json()["data"]
        second_ids = [item["id"] for item in second_data["messages"]]
        self.assertEqual(second_ids, [m3.id])
        self.assertFalse(second_data["pagination"]["has_more"])
        self.assertIsNone(second_data["pagination"]["next_cursor"])

    def test_cursor_pagination_desc_moves_to_next_page(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_owner_desc", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)

        m1 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m1")
        m2 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m2")
        m3 = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m3")

        client = Client()
        client.force_login(owner)

        first_page = client.get(f"/api/v1/sessions/{session.id}/messages?limit=2&order=desc")
        self.assertEqual(first_page.status_code, 200)
        first_data = first_page.json()["data"]
        first_ids = [item["id"] for item in first_data["messages"]]
        self.assertEqual(first_ids, [m3.id, m2.id])
        self.assertTrue(first_data["pagination"]["has_more"])
        self.assertEqual(first_data["pagination"]["next_cursor"], m2.id)

        second_page = client.get(
            f"/api/v1/sessions/{session.id}/messages?limit=2&order=desc&cursor={first_data['pagination']['next_cursor']}"
        )
        self.assertEqual(second_page.status_code, 200)
        second_data = second_page.json()["data"]
        second_ids = [item["id"] for item in second_data["messages"]]
        self.assertEqual(second_ids, [m1.id])
        self.assertFalse(second_data["pagination"]["has_more"])
        self.assertIsNone(second_data["pagination"]["next_cursor"])

    def test_invalid_cursor_returns_validation_error(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_owner_invalid", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)
        ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m1")

        client = Client()
        client.force_login(owner)

        response = client.get(f"/api/v1/sessions/{session.id}/messages?limit=2&order=asc&cursor=msg_invalid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_limit_validation_bounds(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_limit_owner", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)
        ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m1")

        client = Client()
        client.force_login(owner)

        too_small = client.get(f"/api/v1/sessions/{session.id}/messages?limit=0")
        self.assertEqual(too_small.status_code, 400)
        self.assertEqual(too_small.json()["error"]["code"], "VALIDATION_ERROR")

        too_large = client.get(f"/api/v1/sessions/{session.id}/messages?limit=101")
        self.assertEqual(too_large.status_code, 400)
        self.assertEqual(too_large.json()["error"]["code"], "VALIDATION_ERROR")

    def test_invalid_order_returns_validation_error(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_order_owner", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)
        ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content="m1")

        client = Client()
        client.force_login(owner)

        response = client.get(f"/api/v1/sessions/{session.id}/messages?order=sideways")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")

    def test_cursor_pagination_no_duplicates_or_skips_in_asc(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_walk_asc", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)

        expected_ids = []
        for idx in range(1, 8):
            msg = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=f"m{idx}")
            expected_ids.append(msg.id)

        client = Client()
        client.force_login(owner)

        collected_ids = []
        cursor = None
        while True:
            url = f"/api/v1/sessions/{session.id}/messages?limit=3&order=asc"
            if cursor:
                url = f"{url}&cursor={cursor}"
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            payload = response.json()["data"]

            page_ids = [item["id"] for item in payload["messages"]]
            collected_ids.extend(page_ids)

            if not payload["pagination"]["has_more"]:
                self.assertIsNone(payload["pagination"]["next_cursor"])
                break

            cursor = payload["pagination"]["next_cursor"]
            self.assertEqual(cursor, page_ids[-1])

        self.assertEqual(collected_ids, expected_ids)
        self.assertEqual(len(collected_ids), len(set(collected_ids)))

    def test_cursor_pagination_no_duplicates_or_skips_in_desc(self):
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="cursor_walk_desc", password="pass12345")
        session = ChatSession.objects.create(owner_type=ChatSession.OWNER_STUDENT, owner_user=owner)

        created_ids = []
        for idx in range(1, 8):
            msg = ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=f"m{idx}")
            created_ids.append(msg.id)

        expected_ids = list(reversed(created_ids))

        client = Client()
        client.force_login(owner)

        collected_ids = []
        cursor = None
        while True:
            url = f"/api/v1/sessions/{session.id}/messages?limit=3&order=desc"
            if cursor:
                url = f"{url}&cursor={cursor}"
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            payload = response.json()["data"]

            page_ids = [item["id"] for item in payload["messages"]]
            collected_ids.extend(page_ids)

            if not payload["pagination"]["has_more"]:
                self.assertIsNone(payload["pagination"]["next_cursor"])
                break

            cursor = payload["pagination"]["next_cursor"]
            self.assertEqual(cursor, page_ids[-1])

        self.assertEqual(collected_ids, expected_ids)
        self.assertEqual(len(collected_ids), len(set(collected_ids)))
