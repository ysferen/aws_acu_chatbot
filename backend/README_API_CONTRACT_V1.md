# University Chatbot Backend — v1 API Contract (MVP)

## Assumptions

- API base path is `/api/v1`.
- Runtime is container-first: backend runs in Docker and reaches Ollama/vector services via container networking.
- Contract is transport-agnostic for implementation details, but payloads and status behavior are fixed.
- Content domain is university information for current and prospective students.
- No additional public endpoints are introduced beyond the required five.
- Timestamps are ISO-8601 UTC strings (example: `2026-03-23T10:12:31Z`).
- Every response includes observability metadata (`request_id`, `timestamp`).

## Auth/session model

### Auth matrix by endpoint

| Endpoint | anonymous | student | admin/staff | internal_service |
|---|---:|---:|---:|---:|
| `POST /chat` | ✅ | ✅ | ❌ | ❌ |
| `GET /sessions/{id}/messages` | ✅ owner only | ✅ owner only | ❌ | ❌ |
| `POST /feedback` | ✅ owner + assistant message only | ✅ owner + assistant message only | ❌ | ❌ |
| `GET /sources/{source_id}` | ✅ | ✅ | ✅ | ✅ |
| `POST /ingest` | ❌ | ❌ | ✅ | ✅ (`ingest:write`) |

### Authentication mechanism (v1)

- Primary web auth: Django session cookie.
- Role resolution server-side (`anonymous`, `student`, `admin`, `internal`).
- Internal/admin automation may use a server-issued credential mapped to `internal` role.

### Session model

```json
{
  "id": "ses_01HZZ...",
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T10:12:31Z",
  "owner_type": "anonymous",
  "owner_id": null,
  "status": "active",
  "last_message_id": "msg_01J0..."
}
```

Validation:
- `id`: server-generated opaque string.
- `owner_type`: one of `anonymous|student`.
- `owner_id`: required when `owner_type=student`; null when anonymous.

### Message model

```json
{
  "id": "msg_01J0...",
  "session_id": "ses_01HZZ...",
  "role": "assistant",
  "content": "The library opens at 8 AM on weekdays.",
  "citations": [
    {
      "citation_id": "cit_01",
      "source_id": "src_7f8a",
      "chunk_id": "chunk_0031",
      "snippet": "Library opening hours are 08:00-22:00 Monday-Friday.",
      "score": 0.91,
      "page": 2,
      "title": "Library Services Handbook",
      "url": "https://university.example.edu/library/services"
    }
  ],
  "created_at": "2026-03-23T10:12:31Z"
}
```

Validation:
- `role`: one of `user|assistant|system`.
- `citations` required (empty array allowed) on assistant messages.

## Data/citation schema

### Citation model (traceable)

```json
{
  "citation_id": "cit_01",
  "source_id": "src_7f8a",
  "chunk_id": "chunk_0031",
  "snippet": "Library opening hours are 08:00-22:00 Monday-Friday.",
  "title": "Library Services Handbook",
  "url": "https://university.example.edu/library/services",
  "page": 2,
  "doc_metadata": {
    "file_name": "library_services_handbook.pdf",
    "source": "catalog:handbook",
    "chunk_start": 1200,
    "chunk_end": 1540
  },
  "score": 0.91
}
```

Traceability rules:
- `source_id` must be resolvable via `GET /sources/{source_id}`.
- `chunk_id` + `source_id` must uniquely identify the cited chunk.
- `snippet` must be a substring or normalized excerpt of the cited chunk.

### Feedback model

```json
{
  "id": "fb_01J1...",
  "session_id": "ses_01HZZ...",
  "message_id": "msg_01J0...",
  "rating": "down",
  "reason": "incorrect",
  "comment": "Office hour listed was outdated.",
  "created_at": "2026-03-23T10:14:00Z"
}
```

Validation:
- `rating`: `up|down`.
- `reason` optional; if present one of `incorrect|incomplete|unsafe|other`.
- `comment` optional, max 1000 chars.

### Source drill-down model

```json
{
  "source_id": "src_7f8a",
  "title": "Library Services Handbook",
  "url": "https://university.example.edu/library/services",
  "chunk_id": "chunk_0031",
  "snippet": "Library opening hours are 08:00-22:00 Monday-Friday.",
  "page": 2,
  "doc_metadata": {
    "file_name": "library_services_handbook.pdf",
    "document_type": "policy_pdf",
    "source": "catalog:handbook",
    "ingest_id": "ing_01K...",
    "published_at": "2025-09-01"
  }
}
```

## Cross-cutting response envelope and errors

Success envelope:

```json
{
  "ok": true,
  "meta": {
    "request_id": "req_0b7db920d9f44b7e",
    "timestamp": "2026-03-23T10:12:31Z"
  },
  "request_id": "req_0b7db920d9f44b7e",
  "timestamp": "2026-03-23T10:12:31Z",
  "data": {}
}
```

Notes:
- `meta.request_id` is always present.
- If `X-Request-Id` is supplied, that value is echoed in `meta.request_id`; otherwise server generates `req_<hex>`.
- `meta.timestamp` is ISO-8601 UTC.
- Top-level `request_id` and `timestamp` are retained for backward compatibility.

Error envelope:

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload.",
    "details": [
      {
        "field": "question",
        "reason": "required"
      }
    ],
    "retryable": false
  },
  "meta": {
    "request_id": "req_0b7db920d9f44b7e",
    "timestamp": "2026-03-23T10:12:31Z"
  }
}
```

Standard status/code matrix:
- `200` `OK` (chat, sessions, sources)
- `201` `CREATED` (feedback)
- `202` `ACCEPTED` (ingest; duplicates return `duplicate=true`)
- `400` `VALIDATION_ERROR`
- `401` `UNAUTHORIZED`
- `403` `FORBIDDEN`
- `404` `NOT_FOUND`
- `409` `CONFLICT`
- `429` `RATE_LIMITED` (details include `retry_after_seconds`)
- `500` `INTERNAL_ERROR`
- `504` `UPSTREAM_TIMEOUT`

## Endpoint contracts

### 1) POST /chat

Purpose:
- Accept a user question, create/reuse a session, generate answer, and return structured citations.

Request schema:

```json
{
  "question": "What are the tuition payment deadlines?",
  "session_id": "ses_01HZZ...",
  "stream": false,
  "client_message_id": "cmsg_001"
}
```

Field rules:
- `question` required, trimmed length 1..4000.
- `session_id` optional:
  - omitted/null => create new session.
  - provided => must exist and caller must own/access it.
- `stream` required boolean.
- `client_message_id` optional (idempotency for client retries).

Response schema (`200`):

```json
{
  "request_id": "req_1",
  "timestamp": "2026-03-23T11:00:00Z",
  "data": {
    "session": {
      "id": "ses_01HZZ...",
      "is_new": false
    },
    "message": {
      "id": "msg_01J0...",
      "role": "assistant",
      "answer": "Tuition is due by the 15th day of each semester.",
      "citations": [
        {
          "citation_id": "cit_01",
          "source_id": "src_aa11",
          "chunk_id": "chunk_0009",
          "snippet": "Payment deadline is the 15th day of the semester.",
          "title": "Student Finance Policy",
          "url": "https://university.example.edu/finance/policy",
          "page": 4,
          "doc_metadata": {
            "file_name": "finance_policy.pdf",
            "source": "policy_repo",
            "chunk_start": 330,
            "chunk_end": 520
          },
          "score": 0.93
        }
      ],
      "created_at": "2026-03-23T11:00:00Z"
    },
    "stream": {
      "enabled": false,
      "transport": null
    }
  }
}
```

Streaming behavior (`stream=true`):
- Still returns `200` with final `answer` + `citations` in payload.
- Partial tokens/events are delivered over WebSocket channel associated with `request_id`.
- Server includes stream metadata:

```json
{
  "enabled": true,
  "transport": "websocket",
  "channel": "chat.req_1"
}
```

Status codes:
- `200` success.
- `400` invalid payload.
- `401` unauthenticated where required by policy.
- `403` session ownership/role violation.
- `404` referenced session missing.
- `409` duplicate `client_message_id` conflict (when payload mismatch).
- `429` rate limited.
- `504` LLM/vector upstream timeout.

Error example (`400`):

```json
{
  "request_id": "req_1",
  "timestamp": "2026-03-23T11:00:00Z",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload.",
    "details": [
      {
        "field": "question",
        "reason": "must_not_be_blank"
      }
    ],
    "retryable": false
  }
}
```

Validation + edge cases:
- Empty/whitespace-only `question` rejected.
- Unknown `session_id` rejected with `404`.
- Existing session of another user rejected with `403`.
- If no citations found, return `citations: []` (never null).

---

### 2) GET /sessions/{id}/messages

Purpose:
- Fetch paginated message history for a session.

Request parameters:
- Path: `id` (session id, required).
- Query (all optional):
  - `limit` integer, default `20`, min `1`, max `100`.
  - `cursor` opaque string for forward pagination.
  - `order` enum `asc|desc`, default `asc`.

Response schema (`200`):

```json
{
  "request_id": "req_2",
  "timestamp": "2026-03-23T11:05:00Z",
  "data": {
    "session_id": "ses_01HZZ...",
    "messages": [
      {
        "id": "msg_u1",
        "role": "user",
        "content": "When is orientation week?",
        "created_at": "2026-03-23T10:55:00Z"
      },
      {
        "id": "msg_a1",
        "role": "assistant",
        "content": "Orientation starts on Sept 2.",
        "citations": [
          {
            "citation_id": "cit_99",
            "source_id": "src_ori",
            "chunk_id": "chunk_010",
            "snippet": "Orientation Week begins September 2.",
            "title": "Academic Calendar",
            "url": "https://university.example.edu/calendar",
            "page": 1,
            "doc_metadata": {
              "file_name": "calendar.pdf",
              "source": "calendar_repo",
              "chunk_start": 0,
              "chunk_end": 120
            },
            "score": 0.96
          }
        ],
        "created_at": "2026-03-23T10:55:02Z"
      }
    ],
    "pagination": {
      "limit": 20,
      "next_cursor": "cur_abc",
      "has_more": true
    }
  }
}
```

Status codes:
- `200` success.
- `401` unauthenticated when required.
- `403` not owner of session.
- `404` session not found.
- `400` invalid query params.

Error example (`403`):

```json
{
  "request_id": "req_2",
  "timestamp": "2026-03-23T11:05:00Z",
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have access to this session.",
    "details": [],
    "retryable": false
  }
}
```

Validation + edge cases:
- Invalid cursor format => `400`.
- Empty session history => `200` with `messages: []`.
- `limit > 100` => `400`.

---

### 3) POST /feedback

Purpose:
- Capture user feedback tied to an assistant response.

Request schema:

```json
{
  "session_id": "ses_01HZZ...",
  "message_id": "msg_01J0...",
  "rating": "down",
  "reason": "incorrect",
  "comment": "The deadline appears outdated."
}
```

Field rules:
- `session_id` required.
- `message_id` required and must belong to `session_id`.
- `rating` required `up|down`.
- `reason` optional enum `incorrect|incomplete|unsafe|other`.
- `comment` optional max 1000 chars.

Response schema (`201`):

```json
{
  "request_id": "req_3",
  "timestamp": "2026-03-23T11:10:00Z",
  "data": {
    "feedback": {
      "id": "fb_01",
      "session_id": "ses_01HZZ...",
      "message_id": "msg_01J0...",
      "rating": "down",
      "reason": "incorrect",
      "comment": "The deadline appears outdated.",
      "created_at": "2026-03-23T11:10:00Z"
    }
  }
}
```

Status codes:
- `201` created.
- `400` validation error.
- `401` unauthenticated where required.
- `403` session/message ownership violation.
- `404` session or message not found.
- `409` duplicate feedback on same message by same actor (idempotent upsert not enabled in MVP).

Error example (`409`):

```json
{
  "request_id": "req_3",
  "timestamp": "2026-03-23T11:10:00Z",
  "error": {
    "code": "CONFLICT",
    "message": "Feedback already exists for this message.",
    "details": [
      {
        "field": "message_id",
        "reason": "duplicate_feedback"
      }
    ],
    "retryable": false
  }
}
```

Validation + edge cases:
- Feedback on non-assistant message is rejected (`400`).
- If `rating=up`, `reason` remains optional.
- Empty `comment` is treated as null.

---

### 4) GET /sources/{source_id}

Purpose:
- Retrieve citation drill-down metadata and chunk/snippet details for transparency.

Request parameters:
- Path: `source_id` required.
- Query (optional):
  - `chunk_id` string; if provided, return the specific chunk view.

Response schema (`200`):

```json
{
  "request_id": "req_4",
  "timestamp": "2026-03-23T11:15:00Z",
  "data": {
    "source_id": "src_7f8a",
    "title": "Library Services Handbook",
    "url": "https://university.example.edu/library/services",
    "chunk_id": "chunk_0031",
    "snippet": "Library opening hours are 08:00-22:00 Monday-Friday.",
    "page": 2,
    "doc_metadata": {
      "file_name": "library_services_handbook.pdf",
      "document_type": "policy_pdf",
      "source": "catalog:handbook",
      "ingest_id": "ing_01K...",
      "published_at": "2025-09-01"
    }
  }
}
```

Status codes:
- `200` success.
- `404` source/chunk not found.
- `400` invalid source id format.

Error example (`404`):

```json
{
  "request_id": "req_4",
  "timestamp": "2026-03-23T11:15:00Z",
  "error": {
    "code": "NOT_FOUND",
    "message": "Source not found.",
    "details": [],
    "retryable": false
  }
}
```

Validation + edge cases:
- If `chunk_id` not provided, return canonical/default chunk for source.
- If source exists but chunk does not, return `404` with chunk-specific detail.

---

### 5) POST /ingest (admin/internal)

Purpose:
- Submit internal/admin ingestion work for documents/URLs into retrievable source index.

Request schema:

```json
{
  "idempotency_key": "ing-key-20260323-001",
  "items": [
    {
      "type": "url",
      "value": "https://university.example.edu/admissions/fees",
      "metadata": {
        "title": "Admissions Fees",
        "document_type": "web_page",
        "source": "admissions_site"
      }
    },
    {
      "type": "document",
      "value": "s3://internal-docs/finance_policy.pdf",
      "metadata": {
        "title": "Finance Policy",
        "document_type": "policy_pdf",
        "source": "policy_repo"
      }
    }
  ],
  "options": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "replace_existing": false
  }
}
```

Field rules:
- `idempotency_key` required, 8..128 chars.
- `items` required, 1..100.
- item `type` required: `url|document|text`.
- `value` required non-empty.
- `options` optional; all fields optional.

Response schema (`202`):

```json
{
  "request_id": "req_5",
  "timestamp": "2026-03-23T11:20:00Z",
  "data": {
    "job_id": "job_ing_01",
    "status": "accepted",
    "idempotency_key": "ing-key-20260323-001",
    "accepted_count": 2,
    "duplicate": false
  }
}
```

Idempotency approach:
- Server stores hash of normalized request body keyed by `idempotency_key` for 24h.
- Repeat same key + same payload returns same `job_id` and `duplicate=true` (`202`).
- Same key + different payload returns `409 CONFLICT`.

Status codes:
- `202` accepted.
- `400` validation error.
- `401` unauthenticated.
- `403` insufficient role (`admin|internal` required).
- `409` idempotency key conflict.
- `429` rate limited.

Error example (`403`):

```json
{
  "request_id": "req_5",
  "timestamp": "2026-03-23T11:20:00Z",
  "error": {
    "code": "FORBIDDEN",
    "message": "Admin or internal role required.",
    "details": [],
    "retryable": false
  }
}
```

Validation + edge cases:
- Empty `items` => `400`.
- Invalid URL syntax => `400` with item index detail.
- Oversized batch (`>100`) => `400`.

## Non-functional constraints (minimum)

### Rate limits

- `POST /chat`: 30 requests/minute per session and 60/minute per authenticated user.
- `GET /sessions/{id}/messages`: 120 requests/minute per user/session.
- `POST /feedback`: 60 requests/minute per user/session.
- `GET /sources/{source_id}`: 120 requests/minute per IP/user.
- `POST /ingest`: 10 requests/minute per admin/internal principal.

On exceed: return `429 RATE_LIMITED` with optional `retry_after_seconds` in `error.details`.

### Timeout/retry behavior

- API gateway/request timeout target: 30s.
- `POST /chat` upstream budget:
  - vector retrieval: 5s,
  - LLM generation: 20s,
  - response assembly: 5s.
- Upstream transient failures may be retried internally up to 2 times with exponential backoff (for idempotent retrieval calls only).
- Client retries:
  - safe for `GET`.
  - for `POST /chat`, provide `client_message_id` for idempotent retry.
  - for `POST /ingest`, use `idempotency_key`.

### Observability fields

- Required in all responses: `request_id`, `timestamp`.
- Recommended request headers:
  - `X-Request-Id` (optional client-provided correlation id).
  - `Idempotency-Key` (optional alias for ingest/chat idempotency; body value wins if both present).
- Server logs should include: route, status_code, latency_ms, role, session_id (if present), model_name (for chat), and job_id (for ingest).

### Backward-compatible versioning strategy

- Path versioning: `/api/v1`.
- v1-compatible changes (no version bump):
  - add optional request fields,
  - add optional response fields,
  - add new enum values only when clients can safely ignore unknown values.
- Breaking changes require `/api/v2`.
- Deprecation notice window target: minimum 90 days before v1 breaking sunset.

## OpenAPI-style summary table

| Method | Path | Auth | Request Body | Success | Common Errors |
|---|---|---|---|---|---|
| POST | `/api/v1/chat` | anonymous/student | `question`, optional `session_id`, `stream`, optional `client_message_id` | `200` answer + citations + session info | `400,401,403,404,409,429,504` |
| GET | `/api/v1/sessions/{id}/messages` | session owner (anonymous/student) | none (query: `limit,cursor,order`) | `200` paginated messages | `400,401,403,404` |
| POST | `/api/v1/feedback` | anonymous/student | `session_id,message_id,rating`, optional `reason,comment` | `201` feedback object | `400,401,403,404,409` |
| GET | `/api/v1/sources/{source_id}` | anonymous/student | none (optional `chunk_id`) | `200` source drill-down | `400,404` |
| POST | `/api/v1/ingest` | admin/internal | `idempotency_key,items`, optional `options` | `202` accepted with `job_id` | `400,401,403,409,429` |
