from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from .errors import ApiError
from .models import ChatSession, ServiceToken

ROLE_ANONYMOUS = "anonymous"
ROLE_STUDENT = "student"
ROLE_ADMIN_STAFF = "admin/staff"
ROLE_INTERNAL_SERVICE = "internal_service"


@dataclass
class AuthContext:
    role: str
    user: Optional[object] = None
    service_token: Optional[ServiceToken] = None


def ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _extract_bearer_token(request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header:
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None

    configured_prefix = getattr(settings, "INTERNAL_SERVICE_TOKEN_HEADER_PREFIX", "Bearer")
    if parts[0].lower() not in {"bearer", "token", configured_prefix.lower()}:
        return None

    token = parts[1].strip()
    return token or None


def resolve_auth_context(request) -> AuthContext:
    raw_token = _extract_bearer_token(request)
    if raw_token:
        token_hash = ServiceToken.hash_raw_token(raw_token)
        token = ServiceToken.objects.filter(token_hash=token_hash, is_active=True).first()
        if token:
            token.touch()
            return AuthContext(role=ROLE_INTERNAL_SERVICE, user=None, service_token=token)

    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        if user.is_staff or user.is_superuser:
            return AuthContext(role=ROLE_ADMIN_STAFF, user=user)
        return AuthContext(role=ROLE_STUDENT, user=user)

    return AuthContext(role=ROLE_ANONYMOUS)


def require_roles(context: AuthContext, allowed_roles: set[str]):
    if context.role == ROLE_ANONYMOUS and ROLE_ANONYMOUS not in allowed_roles:
        raise ApiError(401, "UNAUTHORIZED", "Authentication required.")

    if context.role not in allowed_roles:
        raise ApiError(403, "FORBIDDEN", "You do not have permission to perform this action.")


def enforce_owner(request, context: AuthContext, session: ChatSession, hide_existence: bool = False):
    if session.owner_type == ChatSession.OWNER_STUDENT:
        user_id = getattr(context.user, "id", None)
        owner_user = getattr(session, "owner_user", None)
        owner_user_id = getattr(owner_user, "id", None)
        owner_ok = bool(user_id is not None and owner_user_id == user_id)
    else:
        owner_ok = bool(request.session.session_key and session.anonymous_session_key == request.session.session_key)

    if owner_ok:
        return

    if hide_existence:
        raise ApiError(404, "NOT_FOUND", "Resource not found.")

    raise ApiError(403, "FORBIDDEN", "You do not have permission to access this resource.")
