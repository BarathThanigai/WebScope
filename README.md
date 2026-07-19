# WebScope

WebScope is a full-stack Website Intelligence & Audit Platform that enables authenticated users to perform asynchronous website audits with real-time progress monitoring, AI-powered audit summaries, SEO and performance analysis, interactive site graph visualization, and exportable reports through a modern responsive dashboard.

It combines a high-performance asynchronous crawler, Redis-backed background job processing, PostgreSQL persistence, secure JWT authentication, and a React + Vite frontend to deliver production-style website intelligence and monitoring.

## Features

- Concurrent BFS-style crawling with `asyncio` and `aiohttp`
- `robots.txt` checking before page fetches
- WebScopeBot User-Agent, polite crawl delay, retry/backoff for temporary failures, and sitemap.xml discovery
- Failure reason classification for robots blocks, timeouts, connection errors, rate limits, and HTTP errors
- Crawl jobs with persistent IDs
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
- Interactive site graph endpoint and React Flow visualization
- CSV export per crawl job
- React dashboard with Overview, Pages, Link Issues, SEO Issues, Performance, and Site Graph sections

## Recommended Test Sites

Use crawler-friendly demo websites while testing locally:

```text
https://books.toscrape.com
https://quotes.toscrape.com
```

Avoid crawling large production websites without permission.

WebScope only audits publicly crawlable content and respects `robots.txt`, authentication boundaries, and anti-bot protections.

---

# Tech Stack

### Backend

- Python
- FastAPI
- asyncio
- aiohttp
- BeautifulSoup
- PostgreSQL primary database
- Optional SQLite local fallback
- Pydantic
- OpenAI Python SDK
- JWT Authentication
- bcrypt
- python-jose

### Frontend

- React
- Vite
- React Flow
- Plain CSS

---

# Architecture

```text
.
├── main.py              # FastAPI routes, CORS, health checks, exports
├── crawler.py           # Concurrent crawler, robots.txt, SEO extraction
├── database.py          # SQLite/PostgreSQL persistence, migrations, reports, stats
├── models.py            # Pydantic request/response models
├── config.py            # Environment-based CORS config
├── requirements.txt     # Backend dependencies
├── .env.example         # Backend env sample
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example
    └── src/
        ├── auth/
        │   ├── AuthContext.jsx
        │   └── AuthPages.jsx
        ├── api.js
        ├── main.jsx
        └── styles.css
```

## Local Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

PostgreSQL is the primary database. Set `DATABASE_URL` in `.env` before starting the backend. For local-only development without PostgreSQL, set `USE_SQLITE_FALLBACK=true` to use SQLite at `crawler.db`.

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

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
```

Database behavior:

- `DATABASE_URL` is required by default.
- Set `DATABASE_URL` to a PostgreSQL database for local or production use.
- For local SQLite development only, set `USE_SQLITE_FALLBACK=true`.
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

## API Endpoints

### Authentication

```http
POST /auth/register
POST /auth/login
GET /auth/me
```

### Crawl

```http
GET /
GET /health
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
```

### General

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
  "crawled_pages": 50,
  "total_links_found": 420,
  "failed_requests": 0,
  "slow_pages": 2,
  "seo_issues": 8,
  "health_score": 92,
  "message": "Crawl completed. Full results are available at /crawl/2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7."
}
```

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
DATABASE_URL=
USE_SQLITE_FALLBACK=false

REDIS_URL=
USE_RQ=true

JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

AI_PROVIDER=nvidia
AI_API_KEY=
AI_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=meta/llama-3.1-8b-instruct
AI_TIMEOUT_SECONDS=90

FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173
```

### Frontend

```text
VITE_API_URL=http://127.0.0.1:8000
```

---

## Deployment

### Backend

- Render
- Railway
- Docker

### Database

- PostgreSQL (Neon, Render PostgreSQL, Supabase)

### Queue

- Upstash Redis / Redis Cloud

### Frontend

- Vercel
- Render Static Site

---

## Roadmap

- Live crawl progress and streaming job status
- Dockerfile and Docker Compose for local full-stack startup
- Persistent production database option such as Postgres
- Scheduled recurring audits and historical report comparison
