import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import main
from database import Database
from services.auth import create_user, decode_access_token


class AuthLoginApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f"test_auth_login_{uuid4().hex}.db"
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

    def test_successful_login_returns_bearer_token(self) -> None:
        user = create_user(
            name="Ada Lovelace",
            email="ada@example.com",
            password="safe-password",
            db=self.db,
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "  ADA@example.com  ", "password": "  safe-password  "},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(body["expires_in"], 3600)
        self.assertIn("access_token", body)
        self.assertNotIn("password_hash", body)
        self.assertEqual(decode_access_token(body["access_token"])["sub"], user.id)

    def test_wrong_password_returns_unauthorized(self) -> None:
        create_user(
            name="Ada Lovelace",
            email="ada@example.com",
            password="safe-password",
            db=self.db,
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "ada@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_nonexistent_email_returns_unauthorized(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"email": "missing@example.com", "password": "safe-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_google_account_password_login_returns_provider_mismatch(self) -> None:
        create_user(
            name="Grace Hopper",
            email="grace@example.com",
            provider="google",
            db=self.db,
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "grace@example.com", "password": "safe-password"},
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_login_payload_returns_validation_error(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={"email": "not-an-email", "password": ""},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
