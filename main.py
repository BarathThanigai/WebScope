import csv
from io import StringIO
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
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
async def crawl(request: CrawlRequest, db: Database = Depends(get_database)) -> CrawlResponse:
    job_id = str(uuid4())

    try:
        db.create_job(
            job_id,
            str(request.seed_url),
            request.max_depth,
            request.max_concurrency,
            request.max_pages,
        )
        crawler = ConcurrentCrawler(
            job_id=job_id,
            seed_url=str(request.seed_url),
            max_depth=request.max_depth,
            max_concurrency=request.max_concurrency,
            max_pages=request.max_pages,
        )
        pages = await crawler.crawl()
    except ValueError as exc:
        db.complete_job(job_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.complete_job(job_id)
        raise HTTPException(status_code=500, detail="Crawler failed unexpectedly") from exc

    db.save_pages(pages)
    db.complete_job(job_id)
    report = db.get_report(job_id)
    if report is None:
        raise HTTPException(status_code=500, detail="Crawl report could not be generated")

    if not pages:
        message = "Crawl completed, but no pages were reachable. The site may block crawlers."
    elif all(not page.success for page in pages):
        message = (
            "Crawl completed with failed requests. The site may be blocked by robots.txt, "
            "anti-bot rules, timeouts, or JavaScript-only rendering."
        )
    else:
        message = f"Crawl completed. Full results are available at /crawl/{job_id}."

    return CrawlResponse(
        job_id=job_id,
        crawled_pages=len(pages),
        total_links_found=sum(len(page.links) for page in pages),
        failed_requests=sum(1 for page in pages if not page.success),
        slow_pages=report.slow_pages_count,
        seo_issues=report.seo_issues_count,
        health_score=report.health_score,
        message=message,
    )


@app.get("/crawl/{job_id}", response_model=CrawlJobResponse)
def crawl_job(job_id: str, db: Database = Depends(get_database)) -> CrawlJobResponse:
    job = db.get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


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
            "error",
            "crawled_at",
        ]
    )
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
