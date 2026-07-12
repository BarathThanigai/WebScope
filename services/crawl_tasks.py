import asyncio

from crawler import ConcurrentCrawler
from database import Database


async def run_crawl_job(
    job_id: str,
    seed_url: str,
    max_depth: int,
    max_concurrency: int,
    max_pages: int,
    db: Database,
) -> None:
    """Run a crawl job with the current asyncio background-task behavior."""
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
        await asyncio.to_thread(
            db.update_job_progress,
            job_id,
            phase="generating_report",
            queued_urls=0,
            active_workers=0,
            completion_reason=crawler.completion_reason,
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
            await asyncio.to_thread(db.complete_job, job_id, crawler.completion_reason)
    except ValueError as exc:
        await asyncio.to_thread(db.fail_job, job_id, str(exc))
    except Exception:
        await asyncio.to_thread(db.fail_job, job_id, "Crawler failed unexpectedly")
