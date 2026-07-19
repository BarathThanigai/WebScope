from fastapi import Depends, HTTPException, Request, status

from database import Database, get_database
from models import UserRecord
from services.auth.jwt import decode_access_token
from services.auth.users import get_user_by_id


AUTHENTICATION_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired authentication token.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    request: Request,
    db: Database = Depends(get_database),
) -> UserRecord:
    token = _extract_bearer_token(request)
    if token is None:
        raise AUTHENTICATION_ERROR

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise AUTHENTICATION_ERROR from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AUTHENTICATION_ERROR

    user = get_user_by_id(user_id, db=db)
    if user is None:
        raise AUTHENTICATION_ERROR

    return user


def get_current_user_optional(
    request: Request,
    db: Database = Depends(get_database),
) -> UserRecord | None:
    token = _extract_bearer_token(request)
    if token is None:
        return None

    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
