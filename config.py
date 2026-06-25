import os


def _split_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ALLOWED_ORIGINS = _split_origins(os.getenv("ALLOWED_ORIGINS", FRONTEND_URL))
