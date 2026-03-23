import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def prefixed_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def session_id_default() -> str:
    return prefixed_id("ses")


def message_id_default() -> str:
    return prefixed_id("msg")


def feedback_id_default() -> str:
    return prefixed_id("fb")


def ingest_id_default() -> str:
    return prefixed_id("job_ing")


class ChatSession(models.Model):
    OWNER_ANON = "anonymous"
    OWNER_STUDENT = "student"
    OWNER_CHOICES = [
        (OWNER_ANON, "Anonymous"),
        (OWNER_STUDENT, "Student"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
    ]

    id = models.CharField(primary_key=True, max_length=40, default=session_id_default, editable=False)
    owner_type = models.CharField(max_length=20, choices=OWNER_CHOICES)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    anonymous_session_key = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    last_message = models.ForeignKey(
        "ChatMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner_type", "owner_user"]),
            models.Index(fields=["owner_type", "anonymous_session_key"]),
        ]


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_SYSTEM, "System"),
    ]

    id = models.CharField(primary_key=True, max_length=40, default=message_id_default, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Citation(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="citations")
    citation_id = models.CharField(max_length=64)
    source_id = models.CharField(max_length=64, db_index=True)
    chunk_id = models.CharField(max_length=64)
    snippet = models.TextField()
    title = models.CharField(max_length=255)
    url = models.URLField(max_length=1000)
    page = models.IntegerField(null=True, blank=True)
    doc_metadata = models.JSONField(default=dict, blank=True)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["message", "citation_id"], name="uniq_message_citation_id"),
        ]


class Feedback(models.Model):
    RATING_UP = "up"
    RATING_DOWN = "down"
    RATING_CHOICES = [
        (RATING_UP, "Up"),
        (RATING_DOWN, "Down"),
    ]

    REASON_INCORRECT = "incorrect"
    REASON_INCOMPLETE = "incomplete"
    REASON_UNSAFE = "unsafe"
    REASON_OTHER = "other"
    REASON_CHOICES = [
        (REASON_INCORRECT, "Incorrect"),
        (REASON_INCOMPLETE, "Incomplete"),
        (REASON_UNSAFE, "Unsafe"),
        (REASON_OTHER, "Other"),
    ]

    id = models.CharField(primary_key=True, max_length=40, default=feedback_id_default, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="feedback_entries")
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="feedback_entries")
    rating = models.CharField(max_length=8, choices=RATING_CHOICES)
    reason = models.CharField(max_length=16, choices=REASON_CHOICES, null=True, blank=True)
    comment = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SourceChunk(models.Model):
    source_id = models.CharField(max_length=64, db_index=True)
    chunk_id = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    url = models.URLField(max_length=1000)
    snippet = models.TextField()
    page = models.IntegerField(null=True, blank=True)
    doc_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source_id", "chunk_id"], name="uniq_source_chunk"),
        ]


class ServiceToken(models.Model):
    name = models.CharField(max_length=80, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    @staticmethod
    def hash_raw_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def touch(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])


class IngestJob(models.Model):
    STATUS_ACCEPTED = "accepted"

    id = models.CharField(primary_key=True, max_length=40, default=ingest_id_default, editable=False)
    status = models.CharField(max_length=16, default=STATUS_ACCEPTED)
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    accepted_count = models.IntegerField(default=0)
    submitted_by_role = models.CharField(max_length=32)
    submitted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingest_jobs",
    )
    submitted_by_token = models.ForeignKey(
        ServiceToken,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingest_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
