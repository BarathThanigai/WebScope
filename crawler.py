import asyncio
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Iterable
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
    error_type: str | None = None
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
        crawl_delay_seconds: float = 0.5,
        max_retries: int = 2,
        progress_callback: Callable[[dict], Awaitable[None] | None] | None = None,
    ) -> None:
        self.job_id = job_id
        self.seed_url = self._normalize_url(seed_url)
        self.max_depth = max_depth
        self.max_concurrency = max_concurrency
        self.max_pages = max_pages
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.seed_host = urlparse(self.seed_url).netloc.lower()
        self.user_agent = "WebScopeBot/1.1 (+https://github.com/webscope-audit)"
        self.crawl_delay_seconds = crawl_delay_seconds
        self.max_retries = max_retries
        self.progress_callback = progress_callback
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0

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
            self.crawl_delay_seconds = robots.crawl_delay(self.user_agent) or self.crawl_delay_seconds
            for sitemap_url in await self._discover_sitemap_urls(session, robots):
                if sitemap_url not in seen:
                    seen.add(sitemap_url)
                    queue.append((sitemap_url, 0, None))
            await self._emit_progress(
                pages_crawled=0,
                pages_discovered=len(seen),
                successful_requests=0,
                failed_requests=0,
                current_depth=0,
                current_url=self.seed_url,
            )

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

                if batch:
                    await self._emit_progress(
                        pages_crawled=len(results),
                        pages_discovered=len(seen),
                        successful_requests=sum(1 for page in results if page.success),
                        failed_requests=sum(1 for page in results if not page.success),
                        current_depth=current_depth,
                        current_url=batch[0][0],
                    )

                pages = await asyncio.gather(
                    *(
                        self._fetch_page(session, semaphore, robots, url, depth, source_url)
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

                await self._emit_progress(
                    pages_crawled=len(results),
                    pages_discovered=len(seen),
                    successful_requests=sum(1 for page in results if page.success),
                    failed_requests=sum(1 for page in results if not page.success),
                    current_depth=current_depth,
                    current_url=pages[-1].url if pages else None,
                )

        return results

    async def _emit_progress(self, **progress: object) -> None:
        if self.progress_callback is None:
            return

        result = self.progress_callback(progress)
        if result is not None:
            await result

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
                return self._failed_page(
                    url,
                    depth,
                    source_url,
                    "blocked_by_robots",
                    "Skipped because robots.txt disallows crawling this URL",
                )

            started_at = time.perf_counter()
            for attempt in range(self.max_retries + 1):
                await self._respect_crawl_delay()
                started_at = time.perf_counter()
                try:
                    async with session.get(url, allow_redirects=True) as response:
                        content_type = response.headers.get("content-type", "")
                        body = (
                            await response.text(errors="ignore")
                            if "text/html" in content_type
                            else ""
                        )
                        elapsed_ms = (time.perf_counter() - started_at) * 1000

                        if self._should_retry(response.status, attempt):
                            await asyncio.sleep(2**attempt)
                            continue

                        metadata = self._parse_html(body, str(response.url))
                        error_type = self._classify_http_status(response.status)

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
                            error_type=error_type,
                            error=self._http_error_message(response.status) if error_type else None,
                        )
                except asyncio.TimeoutError:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    if attempt < self.max_retries:
                        await asyncio.sleep(2**attempt)
                        continue
                    return self._failed_page(
                        url, depth, source_url, "timeout", "Request timed out", elapsed_ms
                    )
                except aiohttp.TooManyRedirects:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    return self._failed_page(
                        url,
                        depth,
                        source_url,
                        "redirect_issue",
                        "Redirect loop or too many redirects",
                        elapsed_ms,
                    )
                except aiohttp.ClientError as exc:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    if attempt < self.max_retries:
                        await asyncio.sleep(2**attempt)
                        continue
                    return self._failed_page(
                        url, depth, source_url, "connection_error", str(exc), elapsed_ms
                    )

            return self._failed_page(
                url,
                depth,
                source_url,
                "connection_error",
                "Request failed after retries",
                (time.perf_counter() - started_at) * 1000,
            )

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

    async def _discover_sitemap_urls(
        self,
        session: aiohttp.ClientSession,
        robots: urllib.robotparser.RobotFileParser,
    ) -> list[str]:
        sitemap_url = f"{urlparse(self.seed_url).scheme}://{self.seed_host}/sitemap.xml"
        if not robots.can_fetch(self.user_agent, sitemap_url):
            return []

        try:
            await self._respect_crawl_delay()
            async with session.get(sitemap_url, allow_redirects=True) as response:
                if response.status >= 400:
                    return []
                xml_text = await response.text(errors="ignore")
        except (aiohttp.ClientError, asyncio.TimeoutError, ET.ParseError):
            return []

        urls: list[str] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        for element in root.iter():
            if not element.tag.endswith("loc") or not element.text:
                continue
            normalized = self._safe_normalize(element.text.strip())
            if (
                normalized
                and self._is_internal_url(normalized)
                and robots.can_fetch(self.user_agent, normalized)
            ):
                urls.append(normalized)

        return sorted(set(urls))

    async def _respect_crawl_delay(self) -> None:
        async with self._request_lock:
            elapsed = time.perf_counter() - self._last_request_at
            wait_time = self.crawl_delay_seconds - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request_at = time.perf_counter()

    def _should_retry(self, status_code: int, attempt: int) -> bool:
        return attempt < self.max_retries and status_code in {408, 429, 500, 502, 503, 504}

    @staticmethod
    def _classify_http_status(status_code: int) -> str | None:
        if status_code == 429:
            return "rate_limited"
        if status_code in {400, 401, 403}:
            return "crawler_inaccessible"
        if status_code >= 400:
            return "http_error"
        return None

    @staticmethod
    def _http_error_message(status_code: int) -> str:
        if status_code == 429:
            return "Rate limited by the server"
        if status_code in {400, 401, 403}:
            return (
                "Crawler could not access this URL due to request restrictions, "
                "cookies, authentication, or anti-bot rules"
            )
        return f"HTTP error {status_code}"

    def _failed_page(
        self,
        url: str,
        depth: int,
        source_url: str | None,
        error_type: str,
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
            error_type=error_type,
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

    def _is_internal_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == self.seed_host

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
