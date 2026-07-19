import unittest

from aiohttp import web

from crawler import ConcurrentCrawler


OVERSIZED_BODY = b"x" * (1_500_000 + 1024)


class OversizedResponseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = web.Application()
        self.app.router.add_get("/robots.txt", self._robots)
        self.app.router.add_get("/sitemap.xml", self._missing)
        self.app.router.add_get("/content-length", self._content_length)
        self.app.router.add_get("/streamed", self._streamed)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = self.site._server.sockets
        self.base_url = f"http://127.0.0.1:{sockets[0].getsockname()[1]}"

    async def asyncTearDown(self) -> None:
        await self.runner.cleanup()

    async def _robots(self, request: web.Request) -> web.Response:
        return web.Response(text="User-agent: *\nAllow: /\n", content_type="text/plain")

    async def _missing(self, request: web.Request) -> web.Response:
        return web.Response(status=404)

    async def _content_length(self, request: web.Request) -> web.Response:
        return web.Response(body=OVERSIZED_BODY, content_type="text/html")

    async def _streamed(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        await response.prepare(request)
        for _ in range(24):
            await response.write(b"x" * 65536)
        await response.write_eof()
        return response

    async def test_content_length_over_limit_records_failed_page(self) -> None:
        pages = await self._crawl("/content-length")

        self.assertEqual(len(pages), 1)
        self.assertFalse(pages[0].success)
        self.assertEqual(pages[0].error_type, "response_too_large")
        self.assertEqual(pages[0].status_code, 200)
        self.assertIn("configured size limit", pages[0].error)
        self.assertIn("1,500,000 bytes", pages[0].error)

    async def test_streamed_response_over_limit_records_failed_page(self) -> None:
        pages = await self._crawl("/streamed")

        self.assertEqual(len(pages), 1)
        self.assertFalse(pages[0].success)
        self.assertEqual(pages[0].error_type, "response_too_large")
        self.assertIn("configured size limit", pages[0].error)
        self.assertIn("1,500,000 bytes", pages[0].error)

    async def _crawl(self, path: str):
        crawler = ConcurrentCrawler(
            job_id="oversized-test",
            seed_url=f"{self.base_url}{path}",
            max_depth=0,
            max_concurrency=1,
            max_pages=1,
        )
        return await crawler.crawl()


if __name__ == "__main__":
    unittest.main()
