import asyncio

from crawler import CrawledPage
from crawler import ConcurrentCrawler
from database import get_database


def run_crawl_job(
    job_id: str,
    seed_url: str,
    max_depth: int,
    max_concurrency: int,
    max_pages: int,
) -> None:
    """RQ-compatible crawl task entrypoint."""
    asyncio.run(
        _run_crawl_job_async(
            job_id=job_id,
            seed_url=seed_url,
            max_depth=max_depth,
            max_concurrency=max_concurrency,
            max_pages=max_pages,
        )
    )


async def _run_crawl_job_async(
    job_id: str,
    seed_url: str,
    max_depth: int,
    max_concurrency: int,
    max_pages: int,
) -> None:
    db = get_database()
    db.initialize()

    try:
        db.start_job(job_id)

        async def update_progress(progress: dict) -> None:
            await asyncio.to_thread(db.update_job_progress, job_id, **progress)

        async def should_cancel() -> bool:
            return await asyncio.to_thread(db.is_cancel_requested, job_id)

        crawler = ConcurrentCrawler(
            job_id=job_id,
            seed_url=seed_url,
            max_depth=max_depth,
            max_concurrency=max_concurrency,
            max_pages=max_pages,
            progress_callback=update_progress,
            should_cancel=should_cancel,
        )
        pages = await crawler.crawl()
        outcome = classify_crawl_outcome(pages)
        completion_reason = crawler.completion_reason
        failed_page = first_failed_page(pages)
        error_message = None
        failed_url = None

        if outcome == "failed":
            completion_reason = "seed_url_unreachable"
            if failed_page is not None:
                failed_url = failed_page.url
                reason = failed_page.error_type or failed_page.error or "request_failed"
                error_message = f"Audit failed: the seed URL was unreachable ({reason})."
            else:
                failed_url = seed_url
                error_message = "Audit failed: the seed URL was unreachable."

        await asyncio.to_thread(
            db.update_job_progress,
            job_id,
            phase="generating_report",
            queued_urls=0,
            active_workers=0,
            completion_reason=completion_reason,
            outcome=outcome,
        )
        await asyncio.to_thread(db.save_pages, pages)
        current_status = await asyncio.to_thread(db.get_job_status, job_id)
        await asyncio.to_thread(
            db.update_job_progress,
            job_id,
            pages_crawled=len(pages),
            pages_discovered=(
                current_status.pages_discovered
                if current_status is not None
                else len(pages)
            ),
            successful_requests=sum(1 for page in pages if page.success),
            failed_requests=sum(1 for page in pages if not page.success),
            current_depth=max((page.depth for page in pages), default=0),
            queued_urls=0,
            active_workers=0,
            current_url=None,
        )
        if crawler.completion_reason == "cancelled_by_user":
            await asyncio.to_thread(db.cancel_job, job_id)
        else:
            await asyncio.to_thread(
                db.complete_job,
                job_id,
                completion_reason,
                outcome,
                error_message,
                failed_url,
            )
    except ValueError as exc:
        await asyncio.to_thread(db.fail_job, job_id, str(exc))
    except Exception:
        await asyncio.to_thread(db.fail_job, job_id, "Crawler failed unexpectedly")


def classify_crawl_outcome(pages: list[CrawledPage]) -> str:
    successful_pages = sum(1 for page in pages if page.success)
    failed_pages = sum(1 for page in pages if not page.success)

    if successful_pages == 0:
        return "failed"
    if failed_pages > 0:
        return "partial_success"
    return "success"


def first_failed_page(pages: list[CrawledPage]) -> CrawledPage | None:
    return next((page for page in pages if not page.success), None)
