import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import main
from database import Database


class AuthRegisterApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f"test_auth_api_{uuid4().hex}.db"
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

    def test_successful_registration_returns_safe_user(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "password": "safe-password",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "Ada Lovelace")
        self.assertEqual(body["email"], "ada@example.com")
        self.assertEqual(body["provider"], "local")
        self.assertIn("id", body)
        self.assertIn("created_at", body)
        self.assertNotIn("password", body)
        self.assertNotIn("password_hash", body)

    def test_duplicate_email_returns_conflict(self) -> None:
        payload = {
            "name": "Ada Lovelace",
            "email": "duplicate@example.com",
            "password": "safe-password",
        }
        first = self.client.post("/auth/register", json=payload)
        second = self.client.post("/auth/register", json=payload)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)

    def test_invalid_email_returns_validation_error(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Ada Lovelace",
                "email": "not-an-email",
                "password": "safe-password",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_short_password_returns_validation_error(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "password": "short",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_whitespace_trimming_and_lowercase_email_normalization(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "name": "  Ada Lovelace  ",
                "email": "  ADA@Example.COM  ",
                "password": "  safe-password  ",
            },
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "Ada Lovelace")
        self.assertEqual(body["email"], "ada@example.com")

        stored_user = self.db.get_user_by_email("ada@example.com")
        self.assertIsNotNone(stored_user)
        self.assertEqual(stored_user.name, "Ada Lovelace")
        self.assertEqual(stored_user.email, "ada@example.com")


if __name__ == "__main__":
    unittest.main()
