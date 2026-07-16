# WebScope

WebScope v1.1 is a full-stack Website Intelligence & Audit Platform for practical SEO checks, website health checks, link issue detection, performance analysis, site graph visualization, and crawl reporting.

It started as a concurrent web crawler and now includes a FastAPI audit backend, PostgreSQL persistence, optional SQLite local fallback, and a React + Vite dashboard suitable for a portfolio or internship resume project.

## Features

- Concurrent BFS-style crawling with `asyncio` and `aiohttp`
- `robots.txt` checking before page fetches
- WebScopeBot User-Agent, polite crawl delay, retry/backoff for temporary failures, and sitemap.xml discovery
- Failure reason classification for robots blocks, timeouts, connection errors, rate limits, and HTTP errors
- Asynchronous crawl jobs with persistent IDs and status tracking
- Production-style live crawl monitor with SSE updates, heartbeat events, phases, queue depth, worker counts, crawl speed, ETA, and cancellation
- Safety limits: `max_depth <= 3`, `max_concurrency <= 20`, `max_pages <= 200`
- Timeout handling and friendly blocked-site messages
- Link issue classification for true broken links, crawler-inaccessible URLs, server errors, rate limits, and redirect issues
- SEO metadata extraction:
  - title
  - meta description
  - H1 tags
  - canonical URL
  - word count
  - page size in KB
  - missing title, description, and H1 flags
- Performance analysis:
  - response time in milliseconds
  - slow page flag for pages over 1000 ms
  - average, min, and max response time per crawl job
- Crawl report endpoint with health score and top 10 slowest pages
- AI-powered audit summary endpoint using NVIDIA's OpenAI-compatible API
- Interactive site graph endpoint and React Flow visualization
- CSV export per crawl job
- React dashboard with Overview, Pages, Link Issues, SEO Issues, Performance, Site Graph, and AI Summary sections

## Recommended Test Sites

Use small crawler-friendly demo sites while testing locally:

```text
https://books.toscrape.com
https://quotes.toscrape.com
```

Avoid crawling large production sites without permission.
WebScope audits publicly crawlable pages only and does not bypass `robots.txt`, anti-bot protections, authentication, or JavaScript-only rendering.

## Tech Stack

Backend:

- Python
- FastAPI
- asyncio
- aiohttp
- BeautifulSoup
- PostgreSQL primary database
- Optional SQLite local fallback
- Redis + RQ background workers for crawl execution
- OpenAI Python SDK for OpenAI-compatible AI providers
- Pydantic

Frontend:

- React
- Vite
- React Flow
- Plain CSS

## Architecture

```text
.
├── main.py              # FastAPI routes, CORS, health checks, exports
├── crawler.py           # Concurrent crawler, robots.txt, SEO extraction
├── database.py          # SQLite/PostgreSQL persistence, migrations, reports, stats
├── models.py            # Pydantic request/response models
├── config.py            # Environment-based CORS config
├── services/
│   ├── ai/
│   │   ├── provider.py        # Provider abstraction and config loading
│   │   ├── nvidia_provider.py # NVIDIA OpenAI-compatible implementation
│   │   ├── prompts.py         # Audit summary prompt construction
│   │   └── schemas.py         # AI response validation models
│   ├── queue.py         # Redis connection and RQ crawls queue
│   └── crawl_tasks.py   # Crawl task execution logic
├── worker.py            # RQ worker entrypoint
├── requirements.txt     # Backend dependencies
├── .env.example         # Backend env sample
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example     # Frontend env sample
    └── src/
        ├── main.jsx
        └── styles.css
```

## Local Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

PostgreSQL is the primary database. Set `DATABASE_URL` in `.env` before starting the backend. For local-only development without PostgreSQL, set `USE_SQLITE_FALLBACK=true` to use SQLite at `crawler.db`.

RQ is the recommended crawl execution mode. Set `USE_RQ=true` and `REDIS_URL=redis://localhost:6379` in `.env`.

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Redis and RQ Worker Setup

WebScope enqueues crawl jobs into Redis Queue by default. FastAPI creates the database job record, pushes the crawl task to the `crawls` queue, and returns immediately. A separate worker process executes the crawl and updates PostgreSQL/SQLite progress for SSE and polling.

Install Redis locally:

- Windows: use Docker, WSL, or Memurai-compatible Redis.
- macOS: `brew install redis`
- Ubuntu/WSL: `sudo apt install redis-server`

Run Redis locally with Docker:

```bash
docker run --name webscope-redis -p 6379:6379 redis:7
```

Or start an installed Redis service:

```bash
redis-server
```

Set the Redis URL in `.env`:

```text
REDIS_URL=redis://localhost:6379
```

Start the prepared worker in a separate terminal:

```powershell
python worker.py
```

Worker selection is automatic:

- Windows uses `rq.SimpleWorker`, which avoids Unix-only process forking.
- Linux, macOS, and Render production workers use `rq.Worker`.

Start FastAPI in another terminal:

```powershell
uvicorn main:app --reload
```

The worker listens on the `crawls` queue. For local emergency use only, set `USE_RQ=false` to run crawls in the web process with FastAPI background tasks.

Test queued crawl execution:

1. Start Redis.
2. Start `python worker.py`.
3. Start `uvicorn main:app --reload`.
4. Submit `POST /crawl` from `/docs` or the React dashboard.
5. Watch `GET /crawl/{job_id}/status`, `GET /crawl/{job_id}/events`, and `GET /queue/health`.

Queue health endpoint:

```http
GET /queue/health
```

Returns Redis connectivity, queue name, queued jobs, started jobs, and failed jobs.

## Local Frontend Setup

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

Production build:

```powershell
npm run build
npm run preview
```

## Docker Setup

Run the full stack with Docker Compose:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`

The frontend container serves the Vite production build through Nginx and proxies `/api` requests to the backend container. Set `DATABASE_URL` for PostgreSQL. SQLite is available only when `USE_SQLITE_FALLBACK=true`.

## Environment Variables

Backend:

```text
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173
DATABASE_PATH=crawler.db
DATABASE_URL=postgresql://user:password@host:5432/webscope?sslmode=require
USE_SQLITE_FALLBACK=false
REDIS_URL=redis://localhost:6379
USE_RQ=true
AI_PROVIDER=nvidia
AI_API_KEY=
AI_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=z-ai/glm-5.2
AI_TIMEOUT_SECONDS=90
```

Database behavior:

- `DATABASE_URL` is required by default.
- Set `DATABASE_URL` to a PostgreSQL database for local or production use.
- For local SQLite development only, set `USE_SQLITE_FALLBACK=true`.
- `USE_RQ=true` is recommended for production so crawls run outside the FastAPI web process.
- `REDIS_URL` is required when `USE_RQ=true`.
- `AI_API_KEY` is required only when generating AI summaries. Never expose it to the frontend.
- `AI_PROVIDER=nvidia` uses NVIDIA's OpenAI-compatible API through the official OpenAI Python SDK.
- Neon/Supabase-style PostgreSQL example:

```text
DATABASE_URL=postgresql://webscope_user:strong_password@ep-example.us-east-1.aws.neon.tech/webscope?sslmode=require
```

Neon/Supabase setup:

1. Create a PostgreSQL project/database.
2. Copy the pooled or direct connection string.
3. Add `?sslmode=require` if your provider requires SSL and it is not already included.
4. Set the value as `DATABASE_URL` in `.env` locally or in your deployment provider.

Frontend:

```text
VITE_API_URL=http://127.0.0.1:8000
```

## AI Summary Provider

WebScope's AI layer is isolated under `services/ai`. The FastAPI route loads the existing crawl report, sends only aggregate audit metrics to the configured provider, validates the returned JSON with Pydantic, and returns a clean summary to the dashboard.

NVIDIA setup:

```text
AI_PROVIDER=nvidia
AI_API_KEY=your-nvidia-api-key
AI_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=z-ai/glm-5.2
AI_TIMEOUT_SECONDS=90
```

The prompt does not send raw HTML, all pages, or page URLs. It sends compact report metrics: health score, page/link counts, SEO issue counts, link issue summary, failed request reasons, response-time stats, and at most 5 top slow page examples without URLs. Output is capped to a concise JSON response.

The NVIDIA provider uses a 90-second timeout by default, retries once for timeouts or temporary 5xx provider failures, and does not retry authentication, rate-limit, or invalid-model errors.

Connectivity test:

```powershell
python scripts/test_nvidia_connectivity.py
```

The test prints provider, model, latency, and success status. It never prints `AI_API_KEY`.

To swap providers, add another implementation of the `AIProvider` interface under `services/ai`, then update `get_ai_provider()` in `services/ai/provider.py` to select it from `AI_PROVIDER`.

## API Endpoints

```http
GET /
GET /health
GET /queue/health
POST /crawl
GET /crawl/{job_id}
GET /crawl/{job_id}/status
GET /crawl/{job_id}/events
POST /crawl/{job_id}/cancel
GET /crawl/{job_id}/broken-links
GET /crawl/{job_id}/graph
GET /crawl/{job_id}/report
POST /crawl/{job_id}/ai-summary
GET /crawl/{job_id}/export/csv
GET /pages?job_id={job_id}&limit=50&offset=0
GET /stats
```

### Start a Crawl

```http
POST /crawl
Content-Type: application/json

{
  "seed_url": "https://books.toscrape.com",
  "max_depth": 1,
  "max_concurrency": 8,
  "max_pages": 50
}
```

Sample response:

```json
{
  "job_id": "2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7",
  "status": "queued",
  "message": "Crawl job created."
}
```

The crawl continues in the background. Subscribe to live progress with Server-Sent Events:

```http
GET /crawl/{job_id}/events
Accept: text/event-stream
```

Each SSE message contains the same JSON shape as the status endpoint, including monitor fields for crawl phase, audit outcome, queued URLs, active workers, crawl speed, and completion reason:

```text
data: {"job_id":"...","status":"running","outcome":null,"phase":"crawling","pages_crawled":12,"pages_discovered":43,"successful_requests":11,"failed_requests":1,"queued_urls":31,"active_workers":4,"pages_per_second":2.4,"current_depth":1,"current_url":"https://books.toscrape.com/catalogue/page-2.html","started_at":"2026-07-12T10:00:00+00:00","completed_at":null,"completion_reason":null,"error_message":null}
```

The stream sends updates about every 750 ms, includes named `heartbeat` events to keep hosted connections alive, and closes automatically when the job reaches `completed`, `failed`, or `cancelled`. Clients can fall back to polling:

```http
GET /crawl/{job_id}/status
```

Sample status response:

```json
{
  "job_id": "2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7",
  "status": "running",
  "outcome": null,
  "phase": "crawling",
  "pages_crawled": 12,
  "pages_discovered": 43,
  "successful_requests": 11,
  "failed_requests": 1,
  "queued_urls": 31,
  "active_workers": 4,
  "pages_per_second": 2.4,
  "current_depth": 1,
  "current_url": "https://books.toscrape.com/catalogue/page-2.html",
  "started_at": "2026-07-12T10:00:00+00:00",
  "completed_at": null,
  "completion_reason": null,
  "error_message": null
}
```

Valid execution states are `queued`, `running`, `completed`, `failed`, and `cancelled`. Audit outcome is reported separately as `success`, `partial_success`, or `failed`.

Outcome rules:

- `success`: at least one successful page and no failed requests
- `partial_success`: at least one successful page and one or more failed requests
- `failed`: zero successful pages

Supported crawl phases are `queued`, `checking_robots`, `discovering_sitemap`, `crawling`, `generating_report`, `completed`, `failed`, and `cancelled`.

Completion reasons include `page_limit_reached`, `queue_exhausted`, `max_depth_reached`, `seed_url_unreachable`, `cancelled_by_user`, and `failed`.

If the seed URL cannot be reached and no pages succeed, the execution status is still `completed`, but the audit outcome is `failed`, the completion reason is `seed_url_unreachable`, and `error_message` contains a user-facing reason.

To cancel an active crawl:

```http
POST /crawl/{job_id}/cancel
```

Cancellation is cooperative: WebScope stops scheduling new pages, lets active requests finish safely, saves partial results, and then marks the job as `cancelled`. Reports, page results, graph data, and CSV export remain available through their existing endpoints after a crawl has produced data.

## Deployment

### Backend on Render

1. Create a Render Web Service.
2. Connect this repository.
3. Runtime: Python.
4. Build command:

```bash
pip install -r requirements.txt
```

5. Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

6. Environment variables:

```text
FRONTEND_URL=https://your-frontend-domain.vercel.app
ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app
DATABASE_URL=postgresql://user:password@host:5432/webscope?sslmode=require
USE_SQLITE_FALLBACK=false
```

For production, use a managed PostgreSQL database such as Render PostgreSQL, Neon, or Supabase. If `DATABASE_URL` is missing and `USE_SQLITE_FALLBACK` is not `true`, the backend raises a clear startup error instead of silently using local storage.

### Frontend on Vercel

1. Import the repository in Vercel.
2. Set root directory to `frontend`.
3. Build command:

```bash
npm run build
```

4. Output directory:

```text
dist
```

5. Environment variable:

```text
VITE_API_URL=https://your-render-backend.onrender.com
```

### Frontend on Render Static Site

1. Create a Render Static Site.
2. Set root directory to `frontend`.
3. Build command:

```bash
npm install && npm run build
```

4. Publish directory:

```text
dist
```

5. Set `VITE_API_URL` to the deployed backend URL.

## Site Graph

```http
GET /crawl/{job_id}/graph
```

Returns graph-ready crawl data with nodes and edges:

```json
{
  "job_id": "2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7",
  "nodes": [
    {
      "id": "page-0",
      "url": "https://books.toscrape.com",
      "title": "All products | Books to Scrape - Sandbox",
      "depth": 0,
      "status_code": 200,
      "success": true,
      "is_slow": false,
      "has_seo_issue": false
    }
  ],
  "edges": [
    {
      "source": "page-0",
      "target": "page-1"
    }
  ]
}
```

The frontend uses React Flow for zoom, pan, fit view, minimap, and click-to-inspect page details. Graph nodes are styled by audit state: normal, slow, SEO issue, or failed.

## Roadmap

- WebSocket collaboration mode for multi-user audit sessions
- Docker image hardening and deployment templates
- Scheduled recurring audits and historical report comparison

## Copyright

Copyright © 2026 Barath.

All Rights Reserved.

This repository is intended for portfolio and evaluation purposes only.
No permission is granted to use, copy, modify, distribute, or create derivative works from this software without prior written permission from the author.
