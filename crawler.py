import asyncio
import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup


@dataclass(slots=True)
class CrawledPage:
    job_id: str
    url: str
    source_url: str | None
    title: str
    meta_description: str
    h1_tags: list[str]
    canonical_url: str | None
    word_count: int
    page_size_kb: float
    missing_title: bool
    missing_description: bool
    missing_h1: bool
    is_slow: bool
    status_code: int | None
    depth: int
    links: list[str]
    response_time_ms: float
    success: bool
    crawled_at: str
    error: str | None = None


class ConcurrentCrawler:
    def __init__(
        self,
        job_id: str,
        seed_url: str,
        max_depth: int,
        max_concurrency: int,
        max_pages: int,
        timeout_seconds: int = 15,
    ) -> None:
        self.job_id = job_id
        self.seed_url = self._normalize_url(seed_url)
        self.max_depth = max_depth
        self.max_concurrency = max_concurrency
        self.max_pages = max_pages
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.seed_host = urlparse(self.seed_url).netloc.lower()
        self.user_agent = "WebScopeAuditBot/1.0"

        if not self.seed_host:
            raise ValueError("seed_url must be an absolute URL")

    async def crawl(self) -> list[CrawledPage]:
        queue: deque[tuple[str, int, str | None]] = deque([(self.seed_url, 0, None)])
        seen = {self.seed_url}
        results: list[CrawledPage] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        headers = {"User-Agent": self.user_agent}
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            robots = await self._load_robots_parser(session)

            while queue and len(results) < self.max_pages:
                current_depth = queue[0][1]
                batch: list[tuple[str, int, str | None]] = []

                # Processing one depth layer at a time keeps traversal BFS-style.
                while (
                    queue
                    and queue[0][1] == current_depth
                    and len(results) + len(batch) < self.max_pages
                ):
                    batch.append(queue.popleft())

                pages = await asyncio.gather(
                    *(
                        self._fetch_page(session, semaphore, robots, url, depth)
                        if source_url is None
                        else self._fetch_page(session, semaphore, robots, url, depth, source_url)
                        for url, depth, source_url in batch
                    )
                )
                results.extend(pages)

                for page in pages:
                    if not page.success or page.depth >= self.max_depth:
                        continue

                    for link in page.links:
                        if link not in seen:
                            seen.add(link)
                            queue.append((link, page.depth + 1, page.url))

        return results

    async def _fetch_page(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        robots: urllib.robotparser.RobotFileParser,
        url: str,
        depth: int,
        source_url: str | None = None,
    ) -> CrawledPage:
        async with semaphore:
            if not robots.can_fetch(self.user_agent, url):
                return self._failed_page(url, depth, source_url, "Blocked by robots.txt")

            started_at = time.perf_counter()
            try:
                async with session.get(url, allow_redirects=True) as response:
                    content_type = response.headers.get("content-type", "")
                    body = await response.text(errors="ignore") if "text/html" in content_type else ""
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    metadata = self._parse_html(body, str(response.url))

                    return CrawledPage(
                        job_id=self.job_id,
                        url=url,
                        source_url=source_url,
                        title=metadata["title"],
                        meta_description=metadata["meta_description"],
                        h1_tags=metadata["h1_tags"],
                        canonical_url=metadata["canonical_url"],
                        word_count=metadata["word_count"],
                        page_size_kb=round(len(body.encode("utf-8")) / 1024, 2),
                        missing_title=not metadata["title"],
                        missing_description=not metadata["meta_description"],
                        missing_h1=len(metadata["h1_tags"]) == 0,
                        is_slow=elapsed_ms > 1000,
                        status_code=response.status,
                        depth=depth,
                        links=metadata["links"],
                        response_time_ms=round(elapsed_ms, 2),
                        success=response.status < 400,
                        crawled_at=self._utc_now(),
                    )
            except asyncio.TimeoutError:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                return self._failed_page(url, depth, source_url, "Request timed out", elapsed_ms)
            except aiohttp.ClientError as exc:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                return self._failed_page(url, depth, source_url, str(exc), elapsed_ms)

    async def _load_robots_parser(
        self, session: aiohttp.ClientSession
    ) -> urllib.robotparser.RobotFileParser:
        robots_url = f"{urlparse(self.seed_url).scheme}://{self.seed_host}/robots.txt"
        parser = urllib.robotparser.RobotFileParser(robots_url)

        try:
            async with session.get(robots_url, allow_redirects=True) as response:
                if response.status < 400:
                    parser.parse((await response.text(errors="ignore")).splitlines())
                else:
                    parser.parse([])
        except (aiohttp.ClientError, asyncio.TimeoutError):
            # If robots.txt cannot be fetched, proceed as allowed rather than failing the crawl.
            parser.parse([])

        return parser

    def _failed_page(
        self,
        url: str,
        depth: int,
        source_url: str | None,
        error: str,
        response_time_ms: float = 0.0,
    ) -> CrawledPage:
        return CrawledPage(
            job_id=self.job_id,
            url=url,
            source_url=source_url,
            title="",
            meta_description="",
            h1_tags=[],
            canonical_url=None,
            word_count=0,
            page_size_kb=0.0,
            missing_title=True,
            missing_description=True,
            missing_h1=True,
            is_slow=response_time_ms > 1000,
            status_code=None,
            depth=depth,
            links=[],
            response_time_ms=round(response_time_ms, 2),
            success=False,
            crawled_at=self._utc_now(),
            error=error or "Request failed",
        )

    def _parse_html(self, html: str, base_url: str) -> dict:
        if not html:
            return {
                "title": "",
                "meta_description": "",
                "h1_tags": [],
                "canonical_url": None,
                "word_count": 0,
                "links": [],
            }

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        meta_description = (
            description_tag.get("content", "").strip() if description_tag else ""
        )
        h1_tags = [tag.get_text(" ", strip=True) for tag in soup.find_all("h1")]
        canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
        canonical_url = (
            self._safe_normalize(urljoin(base_url, canonical_tag.get("href", "")))
            if canonical_tag
            else None
        )
        for script_or_style in soup(["script", "style", "noscript"]):
            script_or_style.decompose()
        word_count = len(soup.get_text(" ", strip=True).split())
        links = self._extract_internal_links(soup.find_all("a", href=True), base_url)
        return {
            "title": title,
            "meta_description": meta_description,
            "h1_tags": h1_tags,
            "canonical_url": canonical_url,
            "word_count": word_count,
            "links": sorted(links),
        }

    def _extract_internal_links(self, anchors: Iterable, base_url: str) -> set[str]:
        links: set[str] = set()

        for anchor in anchors:
            try:
                normalized = self._normalize_url(urljoin(base_url, anchor["href"]))
            except ValueError:
                continue

            parsed = urlparse(normalized)

            if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == self.seed_host:
                links.add(normalized)

        return links

    @staticmethod
    def _normalize_url(url: str) -> str:
        parsed = urlparse(urldefrag(url.strip())[0])
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("URLs must use http or https")

        normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
        return normalized.geturl().rstrip("/")

    @classmethod
    def _safe_normalize(cls, url: str) -> str | None:
        try:
            return cls._normalize_url(url)
        except ValueError:
            return None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
