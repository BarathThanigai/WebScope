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


class ResponseTooLargeError(Exception):
    """Raised when a response exceeds the crawler's configured body limit."""


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
        crawl_delay_seconds: float = 0.2,
        max_retries: int = 2,
        max_body_bytes: int = 1_500_000,
        progress_callback: Callable[[dict], Awaitable[None] | None] | None = None,
        page_batch_callback: Callable[[list[CrawledPage]], Awaitable[None] | None] | None = None,
        should_cancel: Callable[[], Awaitable[bool] | bool] | None = None,
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
        self.max_body_bytes = max_body_bytes
        self.progress_callback = progress_callback
        self.page_batch_callback = page_batch_callback
        self.should_cancel = should_cancel
        self.completion_reason = "queue_exhausted"
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._internal_url_cache: dict[str, bool] = {}
        self._normalize_cache: dict[str, str | None] = {}

        if not self.seed_host:
            raise ValueError("seed_url must be an absolute URL")

    async def crawl(self) -> list[CrawledPage]:
        queue: deque[tuple[str, int, str | None]] = deque([(self.seed_url, 0, None)])
        seen = {self.seed_url}
        results: list[CrawledPage] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)
        crawl_started_at = time.perf_counter()
        successful_requests = 0
        failed_requests = 0

        headers = {"User-Agent": self.user_agent}
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrency,
            limit_per_host=self.max_concurrency,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        timeout = aiohttp.ClientTimeout(
            total=self.timeout.total,
            connect=min(5, self.timeout.total or 5),
            sock_connect=min(5, self.timeout.total or 5),
            sock_read=min(10, self.timeout.total or 10),
        )
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers,
        ) as session:
            await self._emit_progress(
                phase="checking_robots",
                pages_crawled=0,
                pages_discovered=len(seen),
                successful_requests=0,
                failed_requests=0,
                queued_urls=len(queue),
                active_workers=0,
                pages_per_second=0,
                current_depth=0,
                current_url=self.seed_url,
            )
            robots = await self._load_robots_parser(session)
            self.crawl_delay_seconds = robots.crawl_delay(self.user_agent) or self.crawl_delay_seconds
            await self._emit_progress(
                phase="discovering_sitemap",
                pages_crawled=0,
                pages_discovered=len(seen),
                successful_requests=0,
                failed_requests=0,
                queued_urls=len(queue),
                active_workers=0,
                pages_per_second=0,
                current_depth=0,
                current_url=self.seed_url,
            )
            for sitemap_url in await self._discover_sitemap_urls(session, robots):
                if sitemap_url not in seen:
                    seen.add(sitemap_url)
                    queue.append((sitemap_url, 0, None))
            await self._emit_progress(
                phase="crawling",
                pages_crawled=0,
                pages_discovered=len(seen),
                successful_requests=0,
                failed_requests=0,
                queued_urls=len(queue),
                active_workers=0,
                pages_per_second=0,
                current_depth=0,
                current_url=self.seed_url,
            )

            while queue and len(results) < self.max_pages:
                if await self._should_cancel():
                    self.completion_reason = "cancelled_by_user"
                    break

                current_depth = queue[0][1]
                batch: list[tuple[str, int, str | None]] = []

                # Processing one depth layer at a time keeps traversal BFS-style.
                while (
                    queue
                    and queue[0][1] == current_depth
                    and len(results) + len(batch) < self.max_pages
                    and len(batch) < self.max_concurrency
                ):
                    batch.append(queue.popleft())

                if batch:
                    await self._emit_progress(
                        phase="crawling",
                        pages_crawled=len(results),
                        pages_discovered=len(seen),
                        successful_requests=successful_requests,
                        failed_requests=failed_requests,
                        queued_urls=len(queue),
                        active_workers=min(len(batch), self.max_concurrency),
                        pages_per_second=self._pages_per_second(len(results), crawl_started_at),
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
                successful_requests += sum(1 for page in pages if page.success)
                failed_requests += sum(1 for page in pages if not page.success)
                await self._emit_page_batch(pages)

                if await self._should_cancel():
                    self.completion_reason = "cancelled_by_user"
                else:
                    for page in pages:
                        if not page.success or page.depth >= self.max_depth:
                            continue

                        for link in page.links:
                            if link not in seen and self._is_probably_page_url(link):
                                seen.add(link)
                                queue.append((link, page.depth + 1, page.url))

                await self._emit_progress(
                    phase="crawling",
                    pages_crawled=len(results),
                    pages_discovered=len(seen),
                    successful_requests=successful_requests,
                    failed_requests=failed_requests,
                    queued_urls=len(queue),
                    active_workers=0,
                    pages_per_second=self._pages_per_second(len(results), crawl_started_at),
                    current_depth=current_depth,
                    current_url=pages[-1].url if pages else None,
                )

                if self.completion_reason == "cancelled_by_user":
                    break

        if self.completion_reason != "cancelled_by_user":
            if len(results) >= self.max_pages:
                self.completion_reason = "page_limit_reached"
            elif results and max(page.depth for page in results) >= self.max_depth:
                self.completion_reason = "max_depth_reached"
            else:
                self.completion_reason = "queue_exhausted"

        return results

    async def _emit_progress(self, **progress: object) -> None:
        if self.progress_callback is None:
            return

        result = self.progress_callback(progress)
        if result is not None:
            await result

    async def _emit_page_batch(self, pages: list[CrawledPage]) -> None:
        if not pages or self.page_batch_callback is None:
            return

        result = self.page_batch_callback(pages)
        if result is not None:
            await result

    async def _should_cancel(self) -> bool:
        if self.should_cancel is None:
            return False

        result = self.should_cancel()
        if result is not None and hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)

    def _pages_per_second(self, pages_crawled: int, started_at: float) -> float:
        elapsed = max(time.perf_counter() - started_at, 0.001)
        return round(pages_crawled / elapsed, 2)

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
                        if self._content_length_exceeds_limit(response):
                            elapsed_ms = (time.perf_counter() - started_at) * 1000
                            return self._failed_page(
                                url,
                                depth,
                                source_url,
                                "response_too_large",
                                self._response_too_large_message(response.content_length),
                                elapsed_ms,
                                response.status,
                            )

                        content_type = response.headers.get("content-type", "")
                        is_html = self._is_html_content_type(content_type)
                        body = await self._read_limited_text(response) if is_html else ""
                        elapsed_ms = (time.perf_counter() - started_at) * 1000

                        if self._should_retry(response.status, attempt):
                            await asyncio.sleep(2**attempt)
                            continue

                        metadata = (
                            self._parse_html(body, str(response.url))
                            if is_html
                            else self._empty_metadata()
                        )
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
                except ResponseTooLargeError as exc:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    return self._failed_page(
                        url,
                        depth,
                        source_url,
                        "response_too_large",
                        str(exc),
                        elapsed_ms,
                    )
                except aiohttp.ClientPayloadError as exc:
                    elapsed_ms = (time.perf_counter() - started_at) * 1000
                    return self._failed_page(
                        url,
                        depth,
                        source_url,
                        "connection_error",
                        str(exc) or "Response payload could not be read",
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
        if self.seed_host in self._robots_cache:
            return self._robots_cache[self.seed_host]

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

        self._robots_cache[self.seed_host] = parser
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
            normalized = self._safe_normalize_cached(element.text.strip())
            if (
                normalized
                and self._is_internal_url(normalized)
                and self._is_probably_page_url(normalized)
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
        status_code: int | None = None,
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
            status_code=status_code,
            depth=depth,
            links=[],
            response_time_ms=round(response_time_ms, 2),
            success=False,
            crawled_at=self._utc_now(),
            error_type=error_type,
            error=error or "Request failed",
        )

    async def _read_limited_text(self, response: aiohttp.ClientResponse) -> str:
        chunks: list[bytes] = []
        total_bytes = 0
        async for chunk in response.content.iter_chunked(65536):
            total_bytes += len(chunk)
            if total_bytes > self.max_body_bytes:
                raise ResponseTooLargeError(self._response_too_large_message(total_bytes))
            chunks.append(chunk)

        charset = response.charset or "utf-8"
        return b"".join(chunks).decode(charset, errors="ignore")

    def _content_length_exceeds_limit(self, response: aiohttp.ClientResponse) -> bool:
        return response.content_length is not None and response.content_length > self.max_body_bytes

    def _response_too_large_message(self, observed_bytes: int | None = None) -> str:
        limit_mb = self.max_body_bytes / (1024 * 1024)
        if observed_bytes is None:
            return (
                "Response body exceeded the configured size limit of "
                f"{limit_mb:.2f} MB ({self.max_body_bytes:,} bytes)."
            )

        observed_mb = observed_bytes / (1024 * 1024)
        return (
            f"Response body was {observed_mb:.2f} MB ({observed_bytes:,} bytes), "
            f"which exceeds the configured size limit of {limit_mb:.2f} MB "
            f"({self.max_body_bytes:,} bytes)."
        )

    @staticmethod
    def _is_html_content_type(content_type: str) -> bool:
        media_type = content_type.split(";", 1)[0].strip().lower()
        return media_type in {
            "text/html",
            "application/xhtml+xml",
        }

    @staticmethod
    def _empty_metadata() -> dict:
        return {
            "title": "",
            "meta_description": "",
            "h1_tags": [],
            "canonical_url": None,
            "word_count": 0,
            "links": [],
        }

    def _parse_html(self, html: str, base_url: str) -> dict:
        if not html:
            return self._empty_metadata()

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
                normalized = self._normalize_url_cached(urljoin(base_url, anchor["href"]))
            except ValueError:
                continue

            if (
                normalized
                and self._is_internal_url(normalized)
                and self._is_probably_page_url(normalized)
            ):
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

    def _normalize_url_cached(self, url: str) -> str | None:
        if url not in self._normalize_cache:
            self._normalize_cache[url] = self._safe_normalize(url)
        return self._normalize_cache[url]

    def _safe_normalize_cached(self, url: str) -> str | None:
        return self._normalize_url_cached(url)

    def _is_internal_url(self, url: str) -> bool:
        if url in self._internal_url_cache:
            return self._internal_url_cache[url]

        parsed = urlparse(url)
        is_internal = parsed.scheme in {"http", "https"} and parsed.netloc.lower() == self.seed_host
        self._internal_url_cache[url] = is_internal
        return is_internal

    @staticmethod
    def _is_probably_page_url(url: str) -> bool:
        path = urlparse(url).path.lower()
        blocked_extensions = (
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
            ".mp4", ".webm", ".mov", ".avi", ".mp3", ".wav", ".ogg",
            ".woff", ".woff2", ".ttf", ".otf", ".eot",
            ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
            ".exe", ".dmg", ".pkg", ".msi", ".deb", ".rpm",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        )
        return not path.endswith(blocked_extensions)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
