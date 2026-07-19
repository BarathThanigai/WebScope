import csv
import asyncio
import json
from io import StringIO
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import ALLOWED_ORIGINS
from database import Database, get_database
from models import (
    AISummaryResponse,
    AuditComparisonResponse,
    BrokenLinkRecord,
    CrawlHistoryResponse,
    CrawlJobResponse,
    CrawlReportResponse,
    CrawlRequest,
    CrawlResponse,
    CrawlStatusResponse,
    PageRecord,
    SiteGraphResponse,
    StatsResponse,
)
from services.ai.provider import AIProviderError, get_ai_provider
from services.crawl_tasks import run_crawl_job
from services.queue import CRAWL_QUEUE_NAME, USE_RQ, crawl_queue, redis_connection

try:
    from rq.job import Job
    from rq.registry import FailedJobRegistry, StartedJobRegistry
except ImportError:
    Job = None
    FailedJobRegistry = None
    StartedJobRegistry = None

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
            "/crawl/{job_id}/cancel",
            "/crawl/{job_id}/broken-links",
            "/crawl/{job_id}/graph",
            "/crawl/{job_id}/report",
            "/crawl/{job_id}/ai-summary",
            "/crawl/{job_id}/export/csv",
            "/audits/history",
            "/audits/compare",
            "/pages",
            "/stats",
            "/health",
            "/queue/health",
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

    if USE_RQ:
        try:
            rq_job = crawl_queue.enqueue(
                run_crawl_job,
                job_id,
                str(request.seed_url),
                request.max_depth,
                request.max_concurrency,
                request.max_pages,
                job_timeout="30m",
                result_ttl=3600,
                failure_ttl=86400,
            )
            db.set_rq_job_id(job_id, rq_job.id)
        except Exception as exc:
            db.fail_job(job_id, "Failed to enqueue crawl job")
            raise HTTPException(
                status_code=503,
                detail="Unable to enqueue crawl job. Please try again later.",
            ) from exc
    else:
        background_tasks.add_task(
            run_crawl_job,
            job_id,
            str(request.seed_url),
            request.max_depth,
            request.max_concurrency,
            request.max_pages,
        )

    return CrawlResponse(
        job_id=job_id,
        status="queued",
        message="Crawl job created.",
    )


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


@app.post("/crawl/{job_id}/cancel", response_model=CrawlStatusResponse)
def cancel_crawl(job_id: str, db: Database = Depends(get_database)) -> CrawlStatusResponse:
    status = db.get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    if status.status not in {"completed", "failed", "cancelled"}:
        db.request_job_cancel(job_id)
        if USE_RQ:
            removed_from_queue = _cancel_queued_rq_job(db.get_rq_job_id(job_id))
            if removed_from_queue:
                db.cancel_job(job_id)

    updated_status = db.get_job_status(job_id)
    if updated_status is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return updated_status


@app.get("/queue/health")
def queue_health() -> dict[str, int | str | bool]:
    queued_jobs = 0
    started_jobs = 0
    failed_jobs = 0
    redis_connected = False

    try:
        redis_connected = bool(redis_connection.ping())
        queued_jobs = crawl_queue.count
        if StartedJobRegistry is not None:
            started_jobs = len(
                StartedJobRegistry(CRAWL_QUEUE_NAME, connection=redis_connection).get_job_ids()
            )
        if FailedJobRegistry is not None:
            failed_jobs = len(
                FailedJobRegistry(CRAWL_QUEUE_NAME, connection=redis_connection).get_job_ids()
            )
    except Exception:
        redis_connected = False

    return {
        "redis_connected": redis_connected,
        "queue_name": CRAWL_QUEUE_NAME,
        "queued_jobs": queued_jobs,
        "started_jobs": started_jobs,
        "failed_jobs": failed_jobs,
    }


def _cancel_queued_rq_job(rq_job_id: str | None) -> bool:
    if not rq_job_id or Job is None:
        return False

    try:
        job = Job.fetch(rq_job_id, connection=redis_connection)
        status = job.get_status(refresh=True)
        status_value = getattr(status, "value", str(status))
        if status_value in {"queued", "deferred", "scheduled"}:
            job.cancel()
            job.delete()
            return True
    except Exception:
        return False
    return False


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
            yield f"event: heartbeat\ndata: {json.dumps({'job_id': job_id})}\n\n"

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


@app.get("/audits/history", response_model=CrawlHistoryResponse)
def audit_history(
    seed_url: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Database = Depends(get_database),
) -> CrawlHistoryResponse:
    return db.get_crawl_history(seed_url, limit)


@app.get("/audits/compare", response_model=AuditComparisonResponse)
def compare_audits(
    old_job_id: str = Query(..., min_length=1),
    new_job_id: str = Query(..., min_length=1),
    db: Database = Depends(get_database),
) -> AuditComparisonResponse:
    try:
        comparison = db.compare_audits(old_job_id, new_job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if comparison is None:
        raise HTTPException(status_code=404, detail="One or both crawl jobs were not found")
    return comparison


@app.post("/crawl/{job_id}/ai-summary", response_model=AISummaryResponse)
def crawl_ai_summary(
    job_id: str,
    db: Database = Depends(get_database),
) -> AISummaryResponse:
    report = db.get_report(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    try:
        summary = get_ai_provider().generate_summary(report)
    except AIProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error_type": exc.error_type, "message": exc.public_message},
        ) from exc

    return AISummaryResponse(**summary.model_dump())


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
