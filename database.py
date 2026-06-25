import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from crawler import CrawledPage
from models import CrawlJobResponse, PageRecord, StatsResponse

DATABASE_PATH = Path(__file__).with_name("crawler.db")


class Database:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path

    def initialize(self) -> None:
        with self._connect() as connection:
            self._migrate_legacy_pages_table(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    seed_url TEXT NOT NULL,
                    max_depth INTEGER NOT NULL,
                    max_concurrency INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status_code INTEGER,
                    depth INTEGER NOT NULL,
                    links TEXT NOT NULL,
                    response_time_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    error TEXT,
                    crawled_at TEXT NOT NULL,
                    UNIQUE(job_id, url),
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                )
                """
            )
            self._ensure_legacy_job(connection)

    def create_job(
        self, job_id: str, seed_url: str, max_depth: int, max_concurrency: int
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, seed_url, max_depth, max_concurrency, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, seed_url, max_depth, max_concurrency, self._utc_now()),
            )

    def complete_job(self, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET completed_at = ? WHERE job_id = ?",
                (self._utc_now(), job_id),
            )

    def save_pages(self, pages: list[CrawledPage]) -> None:
        if not pages:
            return

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO pages (
                    job_id, url, title, status_code, depth, links,
                    response_time_ms, success, error, crawled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, url) DO UPDATE SET
                    title = excluded.title,
                    status_code = excluded.status_code,
                    depth = excluded.depth,
                    links = excluded.links,
                    response_time_ms = excluded.response_time_ms,
                    success = excluded.success,
                    error = excluded.error,
                    crawled_at = excluded.crawled_at
                """,
                [
                    (
                        page.job_id,
                        page.url,
                        page.title,
                        page.status_code,
                        page.depth,
                        json.dumps(page.links),
                        page.response_time_ms,
                        int(page.success),
                        page.error,
                        page.crawled_at,
                    )
                    for page in pages
                ],
            )

    def get_pages(
        self,
        job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PageRecord]:
        params: list[str | int] = []
        where = ""
        if job_id:
            where = "WHERE job_id = ?"
            params.append(job_id)

        pagination = ""
        if limit is not None:
            pagination = "LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT job_id, url, title, status_code, depth, links,
                       response_time_ms, success, error, crawled_at
                FROM pages
                {where}
                ORDER BY id
                {pagination}
                """,
                tuple(params),
            ).fetchall()

        return [self._row_to_page(row) for row in rows]

    def get_crawl_job(self, job_id: str) -> CrawlJobResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT job_id, seed_url, max_depth, max_concurrency, started_at, completed_at
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return CrawlJobResponse(
            job_id=row["job_id"],
            seed_url=row["seed_url"],
            max_depth=row["max_depth"],
            max_concurrency=row["max_concurrency"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            pages=self.get_pages(job_id),
        )

    def get_stats(self) -> StatsResponse:
        pages = self.get_pages()
        total_pages = len(pages)
        total_links = sum(len(page.links) for page in pages)
        failed_requests = sum(1 for page in pages if not page.success)
        average_response_time_ms = (
            sum(page.response_time_ms for page in pages) / total_pages if total_pages else 0.0
        )

        return StatsResponse(
            total_pages_crawled=total_pages,
            total_links_found=total_links,
            failed_requests=failed_requests,
            average_response_time=average_response_time_ms / 1000,
            average_response_time_ms=average_response_time_ms,
        )

    def _migrate_legacy_pages_table(self, connection: sqlite3.Connection) -> None:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pages'"
        ).fetchone()
        if table is None:
            return

        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(pages)").fetchall()
        }
        if {"job_id", "response_time_ms", "crawled_at"}.issubset(columns):
            return

        connection.execute("ALTER TABLE pages RENAME TO pages_legacy")
        connection.execute(
            """
            CREATE TABLE pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                status_code INTEGER,
                depth INTEGER NOT NULL,
                links TEXT NOT NULL,
                response_time_ms REAL NOT NULL,
                success INTEGER NOT NULL,
                error TEXT,
                crawled_at TEXT NOT NULL,
                UNIQUE(job_id, url)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pages (
                job_id, url, title, status_code, depth, links,
                response_time_ms, success, error, crawled_at
            )
            SELECT
                'legacy', url, title, status_code, depth, links,
                response_time * 1000, success, error, created_at
            FROM pages_legacy
            """
        )

    def _ensure_legacy_job(self, connection: sqlite3.Connection) -> None:
        legacy_page = connection.execute(
            "SELECT 1 FROM pages WHERE job_id = 'legacy' LIMIT 1"
        ).fetchone()
        if legacy_page is None:
            return

        connection.execute(
            """
            INSERT OR IGNORE INTO jobs (
                job_id, seed_url, max_depth, max_concurrency, started_at, completed_at
            )
            VALUES ('legacy', 'legacy data', 0, 0, ?, ?)
            """,
            (self._utc_now(), self._utc_now()),
        )

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> PageRecord:
        return PageRecord(
            job_id=row["job_id"],
            url=row["url"],
            title=row["title"],
            status_code=row["status_code"],
            depth=row["depth"],
            links=json.loads(row["links"]),
            response_time_ms=row["response_time_ms"],
            success=bool(row["success"]),
            error=row["error"],
            crawled_at=row["crawled_at"],
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


database = Database()


def get_database() -> Database:
    return database
