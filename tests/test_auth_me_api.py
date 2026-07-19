import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jose import jwt

import main
from config import JWT_ALGORITHM, JWT_SECRET_KEY
from database import Database
from services.auth import create_access_token, create_user


class AuthMeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f"test_auth_me_{uuid4().hex}.db"
        self.db = Database(
            path=self.db_path,
            database_url=None,
            use_sqlite_fallback=True,
        )
        self.db.initialize()
        main.app.dependency_overrides[main.get_database] = lambda: self.db
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.app.dependency_overrides.clear()
        self.db_path.unlink(missing_ok=True)

    def test_auth_me_returns_current_user_for_valid_jwt(self) -> None:
        user = create_user(
            name="Ada Lovelace",
            email="ada@example.com",
            password="safe-password",
            db=self.db,
        )
        token = create_access_token(user.id)

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], user.id)
        self.assertEqual(body["name"], "Ada Lovelace")
        self.assertEqual(body["email"], "ada@example.com")
        self.assertEqual(body["provider"], "local")
        self.assertIsNone(body["picture_url"])
        self.assertIn("created_at", body)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)

    def test_auth_me_rejects_expired_jwt(self) -> None:
        token = jwt.encode(
            {
                "sub": "user-123",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_malformed_jwt(self) -> None:
        response = self.client.get(
            "/auth/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_missing_authorization_header(self) -> None:
        response = self.client.get("/auth/me")

        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_token_for_nonexistent_user(self) -> None:
        token = create_access_token("missing-user-id")

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)

    def test_auth_me_rejects_token_without_subject(self) -> None:
        token = jwt.encode(
            {
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "iat": datetime.now(timezone.utc),
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
