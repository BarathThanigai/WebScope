import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from crawler import CrawledPage
from models import (
    BrokenLinkRecord,
    CrawlJobResponse,
    CrawlReportResponse,
    PageRecord,
    SiteGraphEdge,
    SiteGraphNode,
    SiteGraphResponse,
    StatsResponse,
)

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
                    max_pages INTEGER NOT NULL DEFAULT 50,
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
            self._ensure_schema_columns(connection)
            self._ensure_legacy_job(connection)

    def create_job(
        self,
        job_id: str,
        seed_url: str,
        max_depth: int,
        max_concurrency: int,
        max_pages: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, seed_url, max_depth, max_concurrency, max_pages, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, seed_url, max_depth, max_concurrency, max_pages, self._utc_now()),
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
                    job_id, url, source_url, title, meta_description, h1_tags,
                    canonical_url, word_count, page_size_kb, missing_title,
                    missing_description, missing_h1, is_slow, status_code, depth,
                    links, response_time_ms, success, error, crawled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, url) DO UPDATE SET
                    source_url = excluded.source_url,
                    title = excluded.title,
                    meta_description = excluded.meta_description,
                    h1_tags = excluded.h1_tags,
                    canonical_url = excluded.canonical_url,
                    word_count = excluded.word_count,
                    page_size_kb = excluded.page_size_kb,
                    missing_title = excluded.missing_title,
                    missing_description = excluded.missing_description,
                    missing_h1 = excluded.missing_h1,
                    is_slow = excluded.is_slow,
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
                        page.source_url,
                        page.title,
                        page.meta_description,
                        json.dumps(page.h1_tags),
                        page.canonical_url,
                        page.word_count,
                        page.page_size_kb,
                        int(page.missing_title),
                        int(page.missing_description),
                        int(page.missing_h1),
                        int(page.is_slow),
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
                SELECT job_id, url, source_url, title, meta_description, h1_tags,
                       canonical_url, word_count, page_size_kb, missing_title,
                       missing_description, missing_h1, is_slow, status_code, depth,
                       links, response_time_ms, success, error, crawled_at
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
                SELECT job_id, seed_url, max_depth, max_concurrency, max_pages,
                       started_at, completed_at
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
            max_pages=row["max_pages"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            pages=self.get_pages(job_id),
        )

    def get_broken_links(self, job_id: str) -> list[BrokenLinkRecord]:
        pages = self.get_pages(job_id)
        return [
            BrokenLinkRecord(
                job_id=page.job_id,
                source_url=page.source_url,
                url=page.url,
                status_code=page.status_code,
                error=page.error,
                depth=page.depth,
                crawled_at=page.crawled_at,
            )
            for page in pages
            if page.source_url and (not page.success or (page.status_code or 0) >= 400)
        ]

    def get_report(self, job_id: str) -> CrawlReportResponse | None:
        if self.get_crawl_job(job_id) is None:
            return None

        pages = self.get_pages(job_id)
        total_pages = len(pages)
        total_links = sum(len(page.links) for page in pages)
        broken_links_count = len(self.get_broken_links(job_id))
        slow_pages = [page for page in pages if page.is_slow]
        missing_titles = sum(1 for page in pages if page.missing_title)
        missing_descriptions = sum(1 for page in pages if page.missing_description)
        missing_h1 = sum(1 for page in pages if page.missing_h1)
        response_times = [page.response_time_ms for page in pages]
        average_response_time_ms = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        return CrawlReportResponse(
            job_id=job_id,
            total_pages=total_pages,
            total_links=total_links,
            broken_links_count=broken_links_count,
            slow_pages_count=len(slow_pages),
            missing_titles_count=missing_titles,
            missing_descriptions_count=missing_descriptions,
            missing_h1_count=missing_h1,
            seo_issues_count=missing_titles + missing_descriptions + missing_h1,
            average_response_time_ms=average_response_time_ms,
            min_response_time_ms=min(response_times) if response_times else 0.0,
            max_response_time_ms=max(response_times) if response_times else 0.0,
            health_score=self._health_score(pages, broken_links_count),
            top_10_slowest_pages=sorted(
                pages, key=lambda page: page.response_time_ms, reverse=True
            )[:10],
        )

    def get_site_graph(self, job_id: str) -> SiteGraphResponse | None:
        if self.get_crawl_job(job_id) is None:
            return None

        pages = self.get_pages(job_id)
        url_to_id = {page.url: f"page-{index}" for index, page in enumerate(pages)}
        nodes = [
            SiteGraphNode(
                id=url_to_id[page.url],
                url=page.url,
                title=page.title,
                depth=page.depth,
                status_code=page.status_code,
                success=page.success,
                is_slow=page.is_slow,
                has_seo_issue=page.missing_title
                or page.missing_description
                or page.missing_h1,
            )
            for page in pages
        ]

        seen_edges: set[tuple[str, str]] = set()
        edges: list[SiteGraphEdge] = []
        for page in pages:
            source = url_to_id[page.url]
            for link in page.links:
                target = url_to_id.get(link)
                if target is None or target == source:
                    continue
                edge_key = (source, target)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append(SiteGraphEdge(source=source, target=target))

        return SiteGraphResponse(job_id=job_id, nodes=nodes, edges=edges)

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
                job_id, seed_url, max_depth, max_concurrency, max_pages,
                started_at, completed_at
            )
            VALUES ('legacy', 'legacy data', 0, 0, 0, ?, ?)
            """,
            (self._utc_now(), self._utc_now()),
        )

    def _ensure_schema_columns(self, connection: sqlite3.Connection) -> None:
        job_columns = self._table_columns(connection, "jobs")
        if "max_pages" not in job_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN max_pages INTEGER NOT NULL DEFAULT 50")

        page_columns = self._table_columns(connection, "pages")
        columns = {
            "source_url": "TEXT",
            "meta_description": "TEXT NOT NULL DEFAULT ''",
            "h1_tags": "TEXT NOT NULL DEFAULT '[]'",
            "canonical_url": "TEXT",
            "word_count": "INTEGER NOT NULL DEFAULT 0",
            "page_size_kb": "REAL NOT NULL DEFAULT 0",
            "missing_title": "INTEGER NOT NULL DEFAULT 0",
            "missing_description": "INTEGER NOT NULL DEFAULT 0",
            "missing_h1": "INTEGER NOT NULL DEFAULT 0",
            "is_slow": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, definition in columns.items():
            if name not in page_columns:
                connection.execute(f"ALTER TABLE pages ADD COLUMN {name} {definition}")

    @staticmethod
    def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
        return {
            row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})")
        }

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> PageRecord:
        return PageRecord(
            job_id=row["job_id"],
            url=row["url"],
            source_url=row["source_url"],
            title=row["title"],
            meta_description=row["meta_description"],
            h1_tags=json.loads(row["h1_tags"]),
            canonical_url=row["canonical_url"],
            word_count=row["word_count"],
            page_size_kb=row["page_size_kb"],
            missing_title=bool(row["missing_title"]),
            missing_description=bool(row["missing_description"]),
            missing_h1=bool(row["missing_h1"]),
            is_slow=bool(row["is_slow"]),
            status_code=row["status_code"],
            depth=row["depth"],
            links=json.loads(row["links"]),
            response_time_ms=row["response_time_ms"],
            success=bool(row["success"]),
            error=row["error"],
            crawled_at=row["crawled_at"],
        )

    @staticmethod
    def _health_score(pages: list[PageRecord], broken_links_count: int) -> int:
        if not pages:
            return 0

        issue_count = (
            broken_links_count
            + sum(1 for page in pages if page.is_slow)
            + sum(1 for page in pages if page.missing_title)
            + sum(1 for page in pages if page.missing_description)
            + sum(1 for page in pages if page.missing_h1)
        )
        possible_issues = len(pages) * 5
        return max(0, round(100 - (issue_count / possible_issues * 100)))

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
