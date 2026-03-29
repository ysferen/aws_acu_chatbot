# Backend API Notes (v1)

## Auth/access matrix

| Endpoint | anonymous | student | admin/staff | internal_service |
| --- | ---: | ---: | ---: | ---: |
| `POST /api/v1/chat` | ✅ | ✅ | ❌ | ❌ |
| `GET /api/v1/sessions/{id}/messages` | ✅ owner only | ✅ owner only | ❌ | ❌ |
| `POST /api/v1/feedback` | ✅ owner + assistant message only | ✅ owner + assistant message only | ❌ | ❌ |
| `GET /api/v1/sources/{source_id}` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/ingest` | ❌ | ❌ | ✅ | ✅ (`ingest:write`) |

## Standard status codes

- `200` successful read/answer responses.
- `201` feedback created.
- `202` ingest accepted (`duplicate=true` for idempotent replay).
- `400` validation error.
- `401` unauthorized.
- `403` forbidden.
- `404` not found.
- `409` conflict.
- `429` rate limited (retry hint in details).

## Canonical error envelope

```json
{
  "ok": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded.",
    "details": [{"field": "retry_after_seconds", "reason": "wait", "value": 22}],
    "retryable": false
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2026-03-24T12:00:00Z"
  }
}
```

Full contract: `backend/README_API_CONTRACT_V1.md` and `backend/openapi.v1.yaml`.

## Rate limit env knobs

- `API_RATE_LIMIT_CHAT_LIMIT` (default `10`)
- `API_RATE_LIMIT_CHAT_WINDOW_SECONDS` (default `60`)
- `API_RATE_LIMIT_FEEDBACK_LIMIT` (default `30`)
- `API_RATE_LIMIT_FEEDBACK_WINDOW_SECONDS` (default `60`)
- `API_RATE_LIMIT_INGEST_LIMIT` (default `5`)
- `API_RATE_LIMIT_INGEST_WINDOW_SECONDS` (default `60`)
