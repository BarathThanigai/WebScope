from services.auth.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidProviderError,
    ProviderMismatchError,
    UserValidationError,
)
from services.auth.dependencies import get_current_user, get_current_user_optional
from services.auth.jwt import (
    access_token_expires_in_seconds,
    create_access_token,
    decode_access_token,
)
from services.auth.security import hash_password, verify_password
from services.auth.users import (
    authenticate_user,
    create_user,
    email_exists,
    get_user_by_email,
    get_user_by_id,
)

__all__ = [
    "DuplicateEmailError",
    "InvalidCredentialsError",
    "InvalidProviderError",
    "ProviderMismatchError",
    "UserValidationError",
    "access_token_expires_in_seconds",
    "authenticate_user",
    "create_user",
    "create_access_token",
    "decode_access_token",
    "email_exists",
    "get_current_user",
    "get_current_user_optional",
    "get_user_by_email",
    "get_user_by_id",
    "hash_password",
    "verify_password",
]
