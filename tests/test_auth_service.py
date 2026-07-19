import unittest
from pathlib import Path
from uuid import uuid4

from database import Database
from services.auth import (
    DuplicateEmailError,
    InvalidProviderError,
    UserValidationError,
    create_user,
    email_exists,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    verify_password,
)


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f"test_auth_{uuid4().hex}.db"
        self.db = Database(
            path=self.db_path,
            database_url=None,
            use_sqlite_fallback=True,
        )
        self.db.initialize()

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    def test_hash_and_verify_password(self) -> None:
        hashed = hash_password("correct horse battery staple")

        self.assertNotEqual(hashed, "correct horse battery staple")
        self.assertTrue(verify_password("correct horse battery staple", hashed))
        self.assertFalse(verify_password("wrong password", hashed))

    def test_create_local_user_and_lookup_by_email_and_id(self) -> None:
        user = create_user(
            name="Ada Lovelace",
            email="Ada@Example.com",
            password="safe-password",
            db=self.db,
        )

        self.assertEqual(user.email, "ada@example.com")
        self.assertEqual(user.provider, "local")
        self.assertIsNotNone(user.password_hash)
        self.assertTrue(verify_password("safe-password", user.password_hash))
        self.assertTrue(email_exists("ADA@example.com", db=self.db))
        self.assertEqual(get_user_by_email("ada@example.com", db=self.db), user)
        self.assertEqual(get_user_by_id(user.id, db=self.db), user)

    def test_create_google_user_without_password_hash(self) -> None:
        user = create_user(
            name="Grace Hopper",
            email="grace@example.com",
            provider="google",
            picture_url="https://example.com/grace.png",
            db=self.db,
        )

        self.assertEqual(user.provider, "google")
        self.assertIsNone(user.password_hash)
        self.assertEqual(user.picture_url, "https://example.com/grace.png")

    def test_rejects_duplicate_email(self) -> None:
        create_user(
            name="First User",
            email="duplicate@example.com",
            password="safe-password",
            db=self.db,
        )

        with self.assertRaises(DuplicateEmailError):
            create_user(
                name="Second User",
                email="DUPLICATE@example.com",
                password="other-password",
                db=self.db,
            )

    def test_rejects_invalid_provider_and_missing_required_fields(self) -> None:
        with self.assertRaises(InvalidProviderError):
            create_user(
                name="Invalid Provider",
                email="invalid@example.com",
                password="safe-password",
                provider="github",
                db=self.db,
            )

        with self.assertRaises(UserValidationError):
            create_user(name="", email="missing-name@example.com", password="x", db=self.db)

        with self.assertRaises(UserValidationError):
            create_user(name="Missing Password", email="local@example.com", db=self.db)


if __name__ == "__main__":
    unittest.main()
