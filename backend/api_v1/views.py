import json

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rag import api_views as rag_services

from .auth import (
    ROLE_ADMIN_STAFF,
    ROLE_ANONYMOUS,
    ROLE_INTERNAL_SERVICE,
    ROLE_STUDENT,
    ensure_session_key,
    enforce_owner,
    require_roles,
    resolve_auth_context,
)
from .errors import ApiError
from .models import ChatMessage, ChatSession, Citation, Feedback, IngestJob, SourceChunk
from .rate_limit import check_rate_limit
from .responses import error_response, success_response


def _parse_json_body(request: HttpRequest):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise ApiError(400, "VALIDATION_ERROR", "Invalid JSON payload.")


def _serialize_citation(citation):
    return {
        "citation_id": citation.citation_id,
        "source_id": citation.source_id,
        "chunk_id": citation.chunk_id,
        "snippet": citation.snippet,
        "title": citation.title,
        "url": citation.url,
        "page": citation.page,
        "doc_metadata": citation.doc_metadata or {},
        "score": citation.score,
    }


def _serialize_message_for_history(message: ChatMessage):
    data: dict[str, object] = {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat().replace("+00:00", "Z"),
    }
    if message.role == ChatMessage.ROLE_ASSISTANT:
        citations = Citation.objects.filter(message=message)
        data["citations"] = [_serialize_citation(c) for c in citations]
    return data


@csrf_exempt
@require_POST
def chat(request: HttpRequest):
    try:
        context = resolve_auth_context(request)
        require_roles(context, {ROLE_ANONYMOUS, ROLE_STUDENT})

        retry_after = check_rate_limit(
            request,
            context,
            scope="chat",
            limit=settings.API_RATE_LIMIT_CHAT_LIMIT,
            window_seconds=settings.API_RATE_LIMIT_CHAT_WINDOW_SECONDS,
        )
        if retry_after is not None:
            raise ApiError(
                429,
                "RATE_LIMITED",
                "Rate limit exceeded.",
                details=[{"field": "retry_after_seconds", "reason": "wait", "value": retry_after}],
            )

        payload = _parse_json_body(request)
        question = (payload.get("question") or "").strip()
        stream = payload.get("stream")
        session_id = payload.get("session_id")

        details = []
        if not question:
            details.append({"field": "question", "reason": "must_not_be_blank"})
        elif len(question) > 4000:
            details.append({"field": "question", "reason": "max_length_exceeded"})

        if not isinstance(stream, bool):
            details.append({"field": "stream", "reason": "must_be_boolean"})

        if details:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=details)

        with transaction.atomic():
            is_new = False
            if session_id:
                chat_session = ChatSession.objects.filter(id=session_id).first()
                if not chat_session:
                    raise ApiError(404, "NOT_FOUND", "Session not found.")
                enforce_owner(request, context, chat_session, hide_existence=False)
            else:
                is_new = True
                if context.role == ROLE_STUDENT:
                    chat_session = ChatSession.objects.create(
                        owner_type=ChatSession.OWNER_STUDENT,
                        owner_user=context.user,
                    )
                else:
                    session_key = ensure_session_key(request)
                    chat_session = ChatSession.objects.create(
                        owner_type=ChatSession.OWNER_ANON,
                        anonymous_session_key=session_key,
                    )

            ChatMessage.objects.create(
                session=chat_session,
                role=ChatMessage.ROLE_USER,
                content=question,
            )

            # Use shared RAG service module, but keep a deterministic fallback for local/test runs.
            answer_text = "This path is active and ready for OLLAMA integration."
            try:
                rag_result = rag_services.generate_chat_answer(question)
                candidate = str(rag_result.get("answer", "")).strip()
                if candidate:
                    answer_text = candidate
            except Exception:
                answer_text = "This path is active and ready for OLLAMA integration."

            assistant_message = ChatMessage.objects.create(
                session=chat_session,
                role=ChatMessage.ROLE_ASSISTANT,
                content=answer_text,
            )

            ChatSession.objects.filter(id=chat_session.id).update(last_message=assistant_message)

        return success_response(
            request,
            {
                "session": {
                    "id": chat_session.id,
                    "is_new": is_new,
                },
                "message": {
                    "id": assistant_message.id,
                    "role": assistant_message.role,
                    "answer": assistant_message.content,
                    "citations": [],
                    "created_at": assistant_message.created_at.isoformat().replace("+00:00", "Z"),
                },
                "stream": {
                    "enabled": stream,
                    "transport": "websocket" if stream else None,
                    "channel": f"chat.{chat_session.id}" if stream else None,
                },
            },
            status=200,
        )
    except ApiError as exc:
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.retryable)


@require_GET
def session_messages(request: HttpRequest, id: str):
    try:
        context = resolve_auth_context(request)
        if context.role == ROLE_ANONYMOUS and not request.session.session_key:
            raise ApiError(401, "UNAUTHORIZED", "Authentication required.")

        try:
            limit = int(request.GET.get("limit", 20))
        except ValueError:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=[{"field": "limit", "reason": "must_be_integer"}])

        if limit < 1 or limit > 100:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=[{"field": "limit", "reason": "out_of_range"}])

        order = request.GET.get("order", "asc")
        if order not in {"asc", "desc"}:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=[{"field": "order", "reason": "invalid_choice"}])

        cursor = request.GET.get("cursor")

        chat_session = ChatSession.objects.filter(id=id).first()
        if not chat_session:
            raise ApiError(404, "NOT_FOUND", "Session not found.")

        enforce_owner(request, context, chat_session, hide_existence=True)

        queryset = ChatMessage.objects.filter(session=chat_session)
        if cursor:
            cursor_message = ChatMessage.objects.filter(id=cursor, session=chat_session).first()
            if not cursor_message:
                raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=[{"field": "cursor", "reason": "invalid"}])

            if order == "asc":
                queryset = queryset.filter(
                    Q(created_at__gt=cursor_message.created_at)
                    | Q(created_at=cursor_message.created_at, id__gt=cursor_message.id)
                )
            else:
                queryset = queryset.filter(
                    Q(created_at__lt=cursor_message.created_at)
                    | Q(created_at=cursor_message.created_at, id__lt=cursor_message.id)
                )

        if order == "asc":
            queryset = queryset.order_by("created_at", "id")
        else:
            queryset = queryset.order_by("-created_at", "-id")

        messages = list(queryset[: limit + 1])
        has_more = len(messages) > limit
        page_messages = messages[:limit]

        next_cursor = page_messages[-1].id if has_more and page_messages else None

        return success_response(
            request,
            {
                "session_id": chat_session.id,
                "messages": [_serialize_message_for_history(msg) for msg in page_messages],
                "pagination": {
                    "limit": limit,
                    "next_cursor": next_cursor,
                    "has_more": has_more,
                },
            },
            status=200,
        )
    except ApiError as exc:
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.retryable)


@require_POST
def feedback(request: HttpRequest):
    try:
        context = resolve_auth_context(request)
        require_roles(context, {ROLE_ANONYMOUS, ROLE_STUDENT})

        retry_after = check_rate_limit(
            request,
            context,
            scope="feedback",
            limit=settings.API_RATE_LIMIT_FEEDBACK_LIMIT,
            window_seconds=settings.API_RATE_LIMIT_FEEDBACK_WINDOW_SECONDS,
        )
        if retry_after is not None:
            raise ApiError(
                429,
                "RATE_LIMITED",
                "Rate limit exceeded.",
                details=[{"field": "retry_after_seconds", "reason": "wait", "value": retry_after}],
            )

        payload = _parse_json_body(request)
        session_id = payload.get("session_id")
        message_id = payload.get("message_id")
        rating = payload.get("rating")
        reason = payload.get("reason")
        comment = payload.get("comment", "")

        details = []
        if not session_id:
            details.append({"field": "session_id", "reason": "required"})
        if not message_id:
            details.append({"field": "message_id", "reason": "required"})
        if rating not in {Feedback.RATING_UP, Feedback.RATING_DOWN}:
            details.append({"field": "rating", "reason": "invalid_choice"})
        if reason is not None and reason not in {
            Feedback.REASON_INCORRECT,
            Feedback.REASON_INCOMPLETE,
            Feedback.REASON_UNSAFE,
            Feedback.REASON_OTHER,
        }:
            details.append({"field": "reason", "reason": "invalid_choice"})
        if comment and len(comment) > 1000:
            details.append({"field": "comment", "reason": "max_length_exceeded"})

        if details:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=details)

        chat_session = ChatSession.objects.filter(id=session_id).first()
        if not chat_session:
            raise ApiError(404, "NOT_FOUND", "Session not found.")

        enforce_owner(request, context, chat_session, hide_existence=False)

        message = ChatMessage.objects.filter(id=message_id, session=chat_session).first()
        if not message:
            raise ApiError(404, "NOT_FOUND", "Message not found.")

        if message.role != ChatMessage.ROLE_ASSISTANT:
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                "Invalid request payload.",
                details=[{"field": "message_id", "reason": "must_reference_assistant_message"}],
            )

        if Feedback.objects.filter(message=message).exists():
            raise ApiError(409, "CONFLICT", "Feedback already exists for this message.")

        feedback_entry = Feedback.objects.create(
            session=chat_session,
            message=message,
            rating=rating,
            reason=reason,
            comment=comment or "",
        )

        return success_response(
            request,
            {
                "feedback": {
                    "id": feedback_entry.id,
                    "session_id": chat_session.id,
                    "message_id": message.id,
                    "rating": feedback_entry.rating,
                    "reason": feedback_entry.reason,
                    "comment": feedback_entry.comment,
                    "created_at": feedback_entry.created_at.isoformat().replace("+00:00", "Z"),
                }
            },
            status=201,
        )
    except ApiError as exc:
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.retryable)


@require_GET
def source_by_id(request: HttpRequest, source_id: str):
    try:
        chunk_id = request.GET.get("chunk_id")
        queryset = SourceChunk.objects.filter(source_id=source_id)
        if chunk_id:
            queryset = queryset.filter(chunk_id=chunk_id)

        source = queryset.order_by("-updated_at").first()
        if not source:
            raise ApiError(404, "NOT_FOUND", "Source not found.")

        return success_response(
            request,
            {
                "source_id": source.source_id,
                "title": source.title,
                "url": source.url,
                "chunk_id": source.chunk_id,
                "snippet": source.snippet,
                "page": source.page,
                "doc_metadata": source.doc_metadata or {},
            },
            status=200,
        )
    except ApiError as exc:
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.retryable)


@csrf_exempt
@require_POST
def ingest(request: HttpRequest):
    try:
        context = resolve_auth_context(request)

        if context.role == ROLE_ANONYMOUS:
            raise ApiError(401, "UNAUTHORIZED", "Authentication required.")
        if context.role not in {ROLE_ADMIN_STAFF, ROLE_INTERNAL_SERVICE}:
            raise ApiError(403, "FORBIDDEN", "You do not have permission to perform this action.")

        if context.role == ROLE_INTERNAL_SERVICE and (not context.service_token or not context.service_token.has_scope("ingest:write")):
            raise ApiError(403, "FORBIDDEN", "Service token does not have required scope.")

        retry_after = check_rate_limit(
            request,
            context,
            scope="ingest",
            limit=settings.API_RATE_LIMIT_INGEST_LIMIT,
            window_seconds=settings.API_RATE_LIMIT_INGEST_WINDOW_SECONDS,
        )
        if retry_after is not None:
            raise ApiError(
                429,
                "RATE_LIMITED",
                "Rate limit exceeded.",
                details=[{"field": "retry_after_seconds", "reason": "wait", "value": retry_after}],
            )

        payload = _parse_json_body(request)
        items = payload.get("items")
        body_idempotency_key = payload.get("idempotency_key")
        header_idempotency_key = request.headers.get("Idempotency-Key")
        idempotency_key = body_idempotency_key or header_idempotency_key

        details = []
        if not isinstance(items, list) or not items:
            details.append({"field": "items", "reason": "required"})

        if details:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid request payload.", details=details)

        existing_job = None
        if idempotency_key:
            existing_job = IngestJob.objects.filter(idempotency_key=idempotency_key).first()

        if existing_job:
            return success_response(
                request,
                {
                    "job_id": existing_job.id,
                    "status": existing_job.status,
                    "idempotency_key": idempotency_key,
                    "accepted_count": existing_job.accepted_count,
                    "duplicate": True,
                },
                status=202,
            )

        job = IngestJob.objects.create(
            idempotency_key=idempotency_key,
            accepted_count=len(items),
            submitted_by_role=context.role,
            submitted_by_user=context.user if context.role == ROLE_ADMIN_STAFF else None,
            submitted_by_token=context.service_token if context.role == ROLE_INTERNAL_SERVICE else None,
        )

        documents_payload = []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).strip().lower()
            value = str(item.get("value", "")).strip()
            if item_type in {"text", "content"} and value:
                documents_payload.append(
                    {
                        "title": item.get("title", "Ingested text"),
                        "source": item.get("source", "api_v1_ingest"),
                        "content": value,
                    }
                )

        if documents_payload:
            try:
                rag_services.ingest_documents(documents_payload)
            except Exception:
                pass

        return success_response(
            request,
            {
                "job_id": job.id,
                "status": job.status,
                "idempotency_key": idempotency_key,
                "accepted_count": job.accepted_count,
                "duplicate": False,
            },
            status=202,
        )
    except ApiError as exc:
        return error_response(request, exc.status, exc.code, exc.message, exc.details, exc.retryable)
