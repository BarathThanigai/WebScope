from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import ALLOWED_ORIGINS
from crawler import ConcurrentCrawler
from database import Database, get_database
from models import CrawlJobResponse, CrawlRequest, CrawlResponse, PageRecord, StatsResponse

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
        "message": "Welcome to the Concurrent Web Crawler API",
        "available_endpoints": ["/docs", "/crawl", "/pages", "/stats", "/health"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Concurrent Web Crawler API"}


@app.post("/crawl", response_model=CrawlResponse)
async def crawl(request: CrawlRequest, db: Database = Depends(get_database)) -> CrawlResponse:
    job_id = str(uuid4())

    try:
        db.create_job(job_id, str(request.seed_url), request.max_depth, request.max_concurrency)
        crawler = ConcurrentCrawler(
            job_id=job_id,
            seed_url=str(request.seed_url),
            max_depth=request.max_depth,
            max_concurrency=request.max_concurrency,
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
    return CrawlResponse(
        job_id=job_id,
        crawled_pages=len(pages),
        total_links_found=sum(len(page.links) for page in pages),
        failed_requests=sum(1 for page in pages if not page.success),
        message=f"Crawl completed. Full results are available at /crawl/{job_id}.",
    )


@app.get("/crawl/{job_id}", response_model=CrawlJobResponse)
def crawl_job(job_id: str, db: Database = Depends(get_database)) -> CrawlJobResponse:
    job = db.get_crawl_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Crawl job not found")
    return job


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
