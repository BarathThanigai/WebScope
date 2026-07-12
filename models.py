from pydantic import AnyHttpUrl, BaseModel, Field


class CrawlRequest(BaseModel):
    seed_url: AnyHttpUrl
    max_depth: int = Field(ge=0, le=3)
    max_concurrency: int = Field(ge=1, le=20)
    max_pages: int = Field(default=50, ge=1, le=200)


class PageRecord(BaseModel):
    job_id: str
    url: str
    source_url: str | None = None
    title: str
    meta_description: str
    h1_tags: list[str]
    canonical_url: str | None = None
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


class CrawlResponse(BaseModel):
    job_id: str
    status: str
    message: str


class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    pages_crawled: int
    pages_discovered: int
    successful_requests: int
    failed_requests: int
    current_depth: int
    current_url: str | None = None
    started_at: str
    completed_at: str | None = None
    error_message: str | None = None


class CrawlJobResponse(BaseModel):
    job_id: str
    seed_url: str
    max_depth: int
    max_concurrency: int
    max_pages: int
    started_at: str
    completed_at: str | None
    pages: list[PageRecord]


class StatsResponse(BaseModel):
    total_pages_crawled: int
    total_links_found: int
    failed_requests: int
    average_response_time: float
    average_response_time_ms: float


class BrokenLinkRecord(BaseModel):
    job_id: str
    source_url: str | None = None
    url: str
    status_code: int | None
    link_issue_type: str
    error_type: str | None = None
    error: str | None = None
    depth: int
    crawled_at: str


class JobPerformanceStats(BaseModel):
    average_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float


class CrawlReportResponse(BaseModel):
    job_id: str
    total_pages: int
    total_links: int
    broken_links_count: int
    link_issues_count: int
    link_issues_by_type: dict[str, int]
    slow_pages_count: int
    skipped_by_robots_count: int
    timeout_count: int
    failed_by_reason: dict[str, int]
    missing_titles_count: int
    missing_descriptions_count: int
    missing_h1_count: int
    seo_issues_count: int
    average_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    health_score: int
    top_10_slowest_pages: list[PageRecord]


class SiteGraphNode(BaseModel):
    id: str
    url: str
    title: str
    depth: int
    status_code: int | None
    success: bool
    is_slow: bool
    has_seo_issue: bool


class SiteGraphEdge(BaseModel):
    source: str
    target: str


class SiteGraphResponse(BaseModel):
    job_id: str
    nodes: list[SiteGraphNode]
    edges: list[SiteGraphEdge]
