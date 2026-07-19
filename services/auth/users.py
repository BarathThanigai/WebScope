from datetime import datetime, timezone
from uuid import uuid4

from database import Database, get_database
from models import UserProvider, UserRecord
from services.auth.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidProviderError,
    ProviderMismatchError,
    UserValidationError,
)
from services.auth.security import hash_password, verify_password


VALID_PROVIDERS = {"local", "google"}


def create_user(
    *,
    name: str,
    email: str,
    password: str | None = None,
    password_hash: str | None = None,
    provider: UserProvider = "local",
    picture_url: str | None = None,
    db: Database | None = None,
) -> UserRecord:
    database = db or get_database()
    clean_name = _validate_required_text(name, "name")
    clean_email = _normalize_email(email)
    clean_provider = _validate_provider(provider)

    if database.email_exists(clean_email):
        raise DuplicateEmailError("A user with this email already exists.")

    if password and password_hash:
        raise UserValidationError("Provide either password or password_hash, not both.")

    stored_password_hash = password_hash
    if password is not None:
        stored_password_hash = hash_password(password)

    if clean_provider == "local" and not stored_password_hash:
        raise UserValidationError("Local users require a password or password_hash.")

    if clean_provider == "google" and password is not None:
        raise UserValidationError("Google users should not be created with a password.")

    now = _utc_now()
    user = UserRecord(
        id=str(uuid4()),
        name=clean_name,
        email=clean_email,
        password_hash=stored_password_hash,
        provider=clean_provider,
        picture_url=picture_url.strip() if picture_url else None,
        created_at=now,
        updated_at=now,
    )
    return database.create_user(user)


def get_user_by_email(email: str, db: Database | None = None) -> UserRecord | None:
    database = db or get_database()
    return database.get_user_by_email(_normalize_email(email))


def authenticate_user(
    *,
    email: str,
    password: str,
    db: Database | None = None,
) -> UserRecord:
    database = db or get_database()
    clean_email = _normalize_email(email)
    clean_password = _validate_required_text(password, "password")
    user = database.get_user_by_email(clean_email)

    if user is None:
        raise InvalidCredentialsError("Invalid email or password.")
    if user.provider != "local":
        raise ProviderMismatchError("This account uses Google sign-in.")
    if not verify_password(clean_password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password.")

    return user


def get_user_by_id(user_id: str, db: Database | None = None) -> UserRecord | None:
    database = db or get_database()
    clean_user_id = _validate_required_text(user_id, "user_id")
    return database.get_user_by_id(clean_user_id)


def email_exists(email: str, db: Database | None = None) -> bool:
    database = db or get_database()
    return database.email_exists(_normalize_email(email))


def _validate_provider(provider: str) -> UserProvider:
    if provider not in VALID_PROVIDERS:
        raise InvalidProviderError("Provider must be either 'local' or 'google'.")
    return provider  # type: ignore[return-value]


def _normalize_email(email: str) -> str:
    clean_email = _validate_required_text(email, "email").lower()
    if "@" not in clean_email:
        raise UserValidationError("A valid email is required.")
    return clean_email


def _validate_required_text(value: str, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise UserValidationError(f"{field_name} is required.")
    return str(value).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
