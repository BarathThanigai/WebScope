from passlib.context import CryptContext


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password is required.")
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    if not password or not hashed_password:
        return False
    return password_context.verify(password, hashed_password)
