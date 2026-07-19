import unittest

from services.auth import create_access_token, decode_access_token


class AuthJwtTests(unittest.TestCase):
    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token("user-123")
        payload = decode_access_token(token)

        self.assertEqual(payload["sub"], "user-123")
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

    def test_decode_invalid_access_token_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            decode_access_token("not-a-real-token")


if __name__ == "__main__":
    unittest.main()
