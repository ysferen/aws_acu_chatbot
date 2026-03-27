import uuid
from datetime import datetime, timezone

from django.http import JsonResponse


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_request_id(request) -> str:
    return request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:16]}"


def success_response(request, data, status=200):
    request_id = get_request_id(request)
    timestamp = utc_timestamp()
    return JsonResponse(
        {
            "ok": True,
            "meta": {
                "request_id": request_id,
                "timestamp": timestamp,
            },
            "request_id": request_id,
            "timestamp": timestamp,
            "data": data,
        },
        status=status,
    )


def error_response(request, status: int, code: str, message: str, details=None, retryable=False):
    request_id = get_request_id(request)
    timestamp = utc_timestamp()
    return JsonResponse(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "retryable": retryable,
            },
            "meta": {
                "request_id": request_id,
                "timestamp": timestamp,
            },
        },
        status=status,
    )
