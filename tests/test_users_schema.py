import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from crawler import CrawledPage
from database import Database


class FakeSession:
    backend = "postgresql"

    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str, params=()):
        self.statements.append(sql)
        return self


class UserSchemaTests(unittest.TestCase):
    def test_sqlite_initialization_creates_users_table_without_affecting_crawls(self) -> None:
        db_path = Path.cwd() / f"test_users_{uuid4().hex}.db"
        try:
            db = Database(path=db_path, database_url=None, use_sqlite_fallback=True)
            db.initialize()

            raw = sqlite3.connect(db_path)
            columns = {
                row[1]: row[2]
                for row in raw.execute("PRAGMA table_info(users)").fetchall()
            }
            indexes = raw.execute("PRAGMA index_list(users)").fetchall()
            raw.close()

            self.assertEqual(columns["id"], "TEXT")
            self.assertEqual(columns["name"], "TEXT")
            self.assertEqual(columns["email"], "TEXT")
            self.assertEqual(columns["password_hash"], "TEXT")
            self.assertEqual(columns["provider"], "TEXT")
            self.assertEqual(columns["picture_url"], "TEXT")
            self.assertEqual(columns["created_at"], "TEXT")
            self.assertEqual(columns["updated_at"], "TEXT")
            self.assertTrue(any(index[2] for index in indexes))

            db.create_job("job", "https://example.com", 1, 1, 1)
            db.save_pages([self._page("job")])
            report = db.get_report("job")

            self.assertIsNotNone(report)
            self.assertEqual(report.total_pages, 1)
        finally:
            db_path.unlink(missing_ok=True)

    def test_postgresql_user_table_ddl_uses_uuid_primary_key(self) -> None:
        db = Database(database_url="postgresql://user:pass@localhost/db")
        session = FakeSession()

        db._create_tables(session)

        ddl = "\n".join(session.statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS users", ddl)
        self.assertIn("id UUID PRIMARY KEY", ddl)
        self.assertIn("email TEXT NOT NULL UNIQUE", ddl)
        self.assertIn("CHECK (provider IN ('local', 'google'))", ddl)

    @staticmethod
    def _page(job_id: str) -> CrawledPage:
        return CrawledPage(
            job_id=job_id,
            url="https://example.com",
            source_url=None,
            title="Example",
            meta_description="Description",
            h1_tags=["Example"],
            canonical_url=None,
            word_count=10,
            page_size_kb=1.0,
            missing_title=False,
            missing_description=False,
            missing_h1=False,
            is_slow=False,
            status_code=200,
            depth=0,
            links=[],
            response_time_ms=100.0,
            success=True,
            crawled_at="2026-07-19T00:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
