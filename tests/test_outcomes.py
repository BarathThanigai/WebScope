import unittest
from uuid import uuid4
from pathlib import Path

from crawler import CrawledPage
from database import Database
from services.crawl_tasks import classify_crawl_outcome


def page(success: bool) -> CrawledPage:
    return CrawledPage(
        job_id="job",
        url="https://example.com",
        source_url=None,
        title="",
        meta_description="",
        h1_tags=[],
        canonical_url=None,
        word_count=0,
        page_size_kb=0,
        missing_title=True,
        missing_description=True,
        missing_h1=True,
        is_slow=False,
        status_code=200 if success else None,
        depth=0,
        links=[],
        response_time_ms=0,
        success=success,
        crawled_at="2026-07-12T00:00:00+00:00",
        error_type=None if success else "connection_error",
        error=None if success else "Connection failed",
    )


class CrawlOutcomeTests(unittest.TestCase):
    def test_classifies_success(self) -> None:
        self.assertEqual(classify_crawl_outcome([page(True)]), "success")

    def test_classifies_partial_success(self) -> None:
        self.assertEqual(classify_crawl_outcome([page(True), page(False)]), "partial_success")

    def test_classifies_failed_when_no_pages_succeed(self) -> None:
        self.assertEqual(classify_crawl_outcome([page(False)]), "failed")

    def test_failed_outcome_keeps_completed_execution_status(self) -> None:
        db_path = Path.cwd() / f"test_outcome_{uuid4().hex}.db"
        try:
            db = Database(
                path=db_path,
                database_url=None,
                use_sqlite_fallback=True,
            )
            db.initialize()
            db.create_job("job", "https://bad.example", 0, 1, 1)
            db.complete_job(
                "job",
                "seed_url_unreachable",
                "failed",
                "Audit failed: the seed URL was unreachable.",
                "https://bad.example",
            )

            status = db.get_job_status("job")

            self.assertIsNotNone(status)
            self.assertEqual(status.status, "completed")
            self.assertEqual(status.outcome, "failed")
            self.assertEqual(status.completion_reason, "seed_url_unreachable")
            self.assertEqual(status.current_url, "https://bad.example")
            self.assertIn("seed URL", status.error_message)
        finally:
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
