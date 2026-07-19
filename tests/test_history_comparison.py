import unittest
import sqlite3
from pathlib import Path
from uuid import uuid4

from crawler import CrawledPage
from database import Database


def page(
    job_id: str,
    url: str,
    *,
    source_url: str | None = None,
    status_code: int | None = 200,
    success: bool = True,
    response_time_ms: float = 100.0,
    missing_title: bool = False,
    missing_description: bool = False,
    missing_h1: bool = False,
    is_slow: bool = False,
) -> CrawledPage:
    return CrawledPage(
        job_id=job_id,
        url=url,
        source_url=source_url,
        title="" if missing_title else "Page",
        meta_description="" if missing_description else "Description",
        h1_tags=[] if missing_h1 else ["Heading"],
        canonical_url=None,
        word_count=20,
        page_size_kb=12.5,
        missing_title=missing_title,
        missing_description=missing_description,
        missing_h1=missing_h1,
        is_slow=is_slow,
        status_code=status_code,
        depth=0,
        links=[],
        response_time_ms=response_time_ms,
        success=success,
        crawled_at="2026-07-19T00:00:00+00:00",
        error_type=None if success else "http_error",
        error=None if success else "HTTP error",
    )


class CrawlHistoryComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path.cwd() / f"test_history_{uuid4().hex}.db"
        self.db = Database(
            path=self.db_path,
            database_url=None,
            use_sqlite_fallback=True,
        )
        self.db.initialize()

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    def test_history_groups_completed_audits_by_normalized_seed(self) -> None:
        self._create_completed_job("old", "https://www.example.com")
        self._create_completed_job("new", "https://example.com/")
        self.db.create_job("running", "https://example.com", 1, 1, 10)

        history = self.db.get_crawl_history("https://example.com")

        self.assertEqual(history.normalized_seed, "example.com")
        self.assertEqual({audit.job_id for audit in history.audits}, {"old", "new"})
        self.assertTrue(all(audit.completed_at for audit in history.audits))

    def test_compare_completed_audits_reports_metric_directions(self) -> None:
        self._create_completed_job(
            "old",
            "https://example.com",
            pages=[
                page("old", "https://example.com", response_time_ms=1800, missing_description=True, is_slow=True),
                page(
                    "old",
                    "https://example.com/missing",
                    source_url="https://example.com",
                    status_code=404,
                    success=False,
                    response_time_ms=200,
                ),
            ],
        )
        self._create_completed_job(
            "new",
            "https://www.example.com",
            pages=[page("new", "https://example.com", response_time_ms=400)],
        )

        comparison = self.db.compare_audits("old", "new")

        self.assertIsNotNone(comparison)
        metrics = {metric.metric: metric for metric in comparison.metrics}
        self.assertEqual(metrics["health_score"].direction, "improved")
        self.assertEqual(metrics["broken_links_count"].direction, "improved")
        self.assertEqual(metrics["seo_issues_count"].direction, "improved")
        self.assertEqual(metrics["average_response_time_ms"].direction, "improved")
        self.assertEqual(metrics["failed_requests"].old_value, 1)
        self.assertEqual(metrics["failed_requests"].new_value, 0)

    def test_compare_rejects_missing_incomplete_and_unrelated_jobs(self) -> None:
        self._create_completed_job("done", "https://example.com")
        self.db.create_job("running", "https://example.com", 1, 1, 10)
        self._create_completed_job("other", "https://other.example")

        self.assertIsNone(self.db.compare_audits("missing", "done"))

        with self.assertRaisesRegex(ValueError, "completed"):
            self.db.compare_audits("done", "running")

        with self.assertRaisesRegex(ValueError, "same website"):
            self.db.compare_audits("done", "other")

    def test_initialize_migrates_and_repairs_normalized_seed(self) -> None:
        legacy_path = Path.cwd() / f"test_legacy_history_{uuid4().hex}.db"
        try:
            raw = sqlite3.connect(legacy_path)
            raw.execute(
                """
                CREATE TABLE jobs (
                    job_id TEXT PRIMARY KEY,
                    seed_url TEXT NOT NULL,
                    max_depth INTEGER NOT NULL,
                    max_concurrency INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            raw.execute(
                """
                INSERT INTO jobs (
                    job_id, seed_url, max_depth, max_concurrency, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy",
                    "https://www.example.com/path",
                    1,
                    1,
                    "2026-07-19T00:00:00+00:00",
                    "2026-07-19T00:00:01+00:00",
                ),
            )
            raw.commit()
            raw.close()

            legacy_db = Database(
                path=legacy_path,
                database_url=None,
                use_sqlite_fallback=True,
            )
            legacy_db.initialize()

            with legacy_db._connect() as connection:
                connection.execute(
                    "UPDATE jobs SET normalized_seed = seed_url WHERE job_id = ?",
                    ("legacy",),
                )
            legacy_db.initialize()

            raw = sqlite3.connect(legacy_path)
            normalized_seed = raw.execute(
                "SELECT normalized_seed FROM jobs WHERE job_id = ?",
                ("legacy",),
            ).fetchone()[0]
            index_exists = raw.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'index' AND name = 'idx_jobs_normalized_seed'
                """
            ).fetchone()
            raw.close()

            self.assertEqual(normalized_seed, "example.com")
            self.assertIsNotNone(index_exists)
        finally:
            legacy_path.unlink(missing_ok=True)

    def _create_completed_job(
        self,
        job_id: str,
        seed_url: str,
        pages: list[CrawledPage] | None = None,
    ) -> None:
        self.db.create_job(job_id, seed_url, 1, 1, 10)
        pages = pages or [page(job_id, seed_url)]
        self.db.save_pages(pages)
        self.db.update_job_progress(
            job_id,
            pages_crawled=len(pages),
            successful_requests=sum(1 for item in pages if item.success),
            failed_requests=sum(1 for item in pages if not item.success),
        )
        self.db.complete_job(job_id, "queue_exhausted", "success")


if __name__ == "__main__":
    unittest.main()
