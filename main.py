import csv
import asyncio
import json
from io import StringIO
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import ALLOWED_ORIGINS
from crawler import ConcurrentCrawler
from database import Database, get_database
from models import (
    BrokenLinkRecord,
    CrawlJobResponse,
    CrawlReportResponse,
    CrawlRequest,
    CrawlResponse,
    CrawlStatusResponse,
    PageRecord,
    SiteGraphResponse,
    StatsResponse,
)

app = FastAPI(title="Concurrent Web Crawler")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    get_database().initialize()


@app.get("/")
def root() -> dict[str, str | list[str]]:
    return {
        "message": "Welcome to the WebScope Website Intelligence API",
        "available_endpoints": [
            "/docs",
            "/crawl",
            "/crawl/{job_id}",
            "/crawl/{job_id}/status",
            "/crawl/{job_id}/events",
            "/crawl/{job_id}/broken-links",
            "/crawl/{job_id}/graph",
            "/crawl/{job_id}/report",
            "/crawl/{job_id}/export/csv",
            "/pages",
            "/stats",
            "/health",
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "WebScope Website Intelligence API"}


@app.post("/crawl", response_model=CrawlResponse)
async def crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database),
) -> CrawlResponse:
    job_id = str(uuid4())

    try:
        db.create_job(
            job_id,
            str(request.seed_url),
            request.max_depth,
            request.max_concurrency,
            request.max_pages,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    background_tasks.add_task(
        run_crawl_job,
        job_id,
        str(request.seed_url),
        request.max_depth,
        request.max_concurrency,
        request.max_pages,
        db,
    )

    return CrawlResponse(
        job_id=job_id,
        status="queued",
        message="Crawl job created.",
    )


async def run_crawl_job(
    job_id: str,
    seed_url: str,
    max_depth: int,
    max_concurrency: int,
    max_pages: int,
    db: Database,
) -> None:
    try:
        db.start_job(job_id)

        async def update_progress(progress: dict) -> None:
            await asyncio.to_thread(db.update_job_progress, job_id, **progress)

        crawler = ConcurrentCrawler(
            job_id=job_id,
            seed_url=seed_url,
            max_depth=max_depth,
            max_concurrency=max_concurrency,
            max_pages=max_pages,
            progress_callback=update_progress,
        )
        pages = await crawler.crawl()
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
            current_url=None,
        )
        await asyncio.to_thread(db.complete_job, job_id)
    except ValueError as exc:
        await asyncio.to_thread(db.fail_job, job_id, str(exc))
    except Exception:
        await asyncio.to_thread(db.fail_job, job_id, "Crawler failed unexpectedly")


@app.get("/crawl/{job_id}", response_model=CrawlJobResponse)
def crawl_job(job_id: str, db: Database = Depends(get_database)) -> CrawlJobResponse:
    job = db.get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


@app.get("/crawl/{job_id}/status", response_model=CrawlStatusResponse)
def crawl_status(job_id: str, db: Database = Depends(get_database)) -> CrawlStatusResponse:
    status = db.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return status


@app.get("/crawl/{job_id}/events")
async def crawl_events(
    job_id: str,
    request: Request,
    db: Database = Depends(get_database),
) -> StreamingResponse:
    initial_status = db.get_job_status(job_id)
    if initial_status is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    async def event_stream():
        terminal_statuses = {"completed", "failed", "cancelled"}
        while True:
            if await request.is_disconnected():
                break

            try:
                status = await asyncio.to_thread(db.get_job_status, job_id)
            except Exception:
                break

            if status is None:
                break

            payload = status.model_dump() if hasattr(status, "model_dump") else status.dict()
            yield f"data: {json.dumps(payload)}\n\n"

            if status.status in terminal_statuses:
                break

            await asyncio.sleep(0.75)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/crawl/{job_id}/broken-links", response_model=list[BrokenLinkRecord])
def broken_links(job_id: str, db: Database = Depends(get_database)) -> list[BrokenLinkRecord]:
    if db.get_crawl_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return db.get_broken_links(job_id)


@app.get("/crawl/{job_id}/report", response_model=CrawlReportResponse)
def crawl_report(job_id: str, db: Database = Depends(get_database)) -> CrawlReportResponse:
    report = db.get_report(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return report


@app.get("/crawl/{job_id}/graph", response_model=SiteGraphResponse)
def site_graph(job_id: str, db: Database = Depends(get_database)) -> SiteGraphResponse:
    graph = db.get_site_graph(job_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return graph


@app.get("/crawl/{job_id}/export/csv")
def export_csv(job_id: str, db: Database = Depends(get_database)) -> StreamingResponse:
    if db.get_crawl_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "url",
            "source_url",
            "title",
            "meta_description",
            "h1_tags",
            "canonical_url",
            "status_code",
            "depth",
            "response_time_ms",
            "page_size_kb",
            "word_count",
            "missing_title",
            "missing_description",
            "missing_h1",
            "is_slow",
            "success",
            "link_issue_type",
            "error_type",
            "error",
            "crawled_at",
        ]
    )
    link_issue_map = {issue.url: issue.link_issue_type for issue in db.get_broken_links(job_id)}
    for page in db.get_pages(job_id=job_id):
        writer.writerow(
            [
                page.url,
                page.source_url or "",
                page.title,
                page.meta_description,
                " | ".join(page.h1_tags),
                page.canonical_url or "",
                page.status_code or "",
                page.depth,
                page.response_time_ms,
                page.page_size_kb,
                page.word_count,
                page.missing_title,
                page.missing_description,
                page.missing_h1,
                page.is_slow,
                page.success,
                link_issue_map.get(page.url, ""),
                page.error_type or "",
                page.error or "",
                page.crawled_at,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="webscope-{job_id}.csv"'},
    )


@app.get("/pages", response_model=list[PageRecord])
def pages(
    job_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_database),
) -> list[PageRecord]:
    return db.get_pages(job_id=job_id, limit=limit, offset=offset)


@app.get("/stats", response_model=StatsResponse)
def stats(db: Database = Depends(get_database)) -> StatsResponse:
    return db.get_stats()
