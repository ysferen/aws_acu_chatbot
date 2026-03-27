from django.contrib import admin

from .models import (
    ChatMessage,
    ChatSession,
    Citation,
    Feedback,
    IngestJob,
    ServiceToken,
    SourceChunk,
)


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "owner_type", "owner_user", "status", "updated_at")
    search_fields = ("id", "owner_user__username", "anonymous_session_key")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "created_at")
    search_fields = ("id", "session__id", "content")


@admin.register(Citation)
class CitationAdmin(admin.ModelAdmin):
    list_display = ("citation_id", "message", "source_id", "chunk_id", "score")
    search_fields = ("citation_id", "source_id", "chunk_id")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "message", "rating", "created_at")
    search_fields = ("id", "session__id", "message__id")


@admin.register(SourceChunk)
class SourceChunkAdmin(admin.ModelAdmin):
    list_display = ("source_id", "chunk_id", "title", "updated_at")
    search_fields = ("source_id", "chunk_id", "title")


@admin.register(ServiceToken)
class ServiceTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "last_used_at")
    search_fields = ("name",)


@admin.register(IngestJob)
class IngestJobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "submitted_by_role", "accepted_count", "created_at")
    search_fields = ("id", "idempotency_key")
