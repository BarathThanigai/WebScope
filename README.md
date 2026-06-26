# WebScope

WebScope v1.1 is a full-stack Website Intelligence & Audit Platform for practical SEO checks, website health checks, broken link detection, performance analysis, site graph visualization, and crawl reporting.

It started as a concurrent web crawler and now includes a FastAPI audit backend, SQLite persistence, and a React + Vite dashboard suitable for a portfolio or internship resume project.

## Features

- Concurrent BFS-style crawling with `asyncio` and `aiohttp`
- `robots.txt` checking before page fetches
- Crawl jobs with persistent IDs
- Safety limits: `max_depth <= 3`, `max_concurrency <= 20`, `max_pages <= 200`
- Timeout handling and friendly blocked-site messages
- Broken link detection for failed internal crawl targets and HTTP error pages
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
- React dashboard with Overview, Pages, Broken Links, SEO Issues, Performance, and Site Graph sections

## Recommended Test Sites

Use small crawler-friendly demo sites while testing locally:

```text
https://books.toscrape.com
https://quotes.toscrape.com
```

Avoid crawling large production sites without permission.

## Tech Stack

Backend:

- Python
- FastAPI
- asyncio
- aiohttp
- BeautifulSoup
- SQLite
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
├── database.py          # SQLite schema, migrations, reports, stats
├── models.py            # Pydantic request/response models
├── config.py            # Environment-based CORS config
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
uvicorn main:app --reload
```

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

## Environment Variables

Backend:

```text
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173
```

Frontend:

```text
VITE_API_URL=http://127.0.0.1:8000
```

## API Endpoints

```http
GET /
GET /health
POST /crawl
GET /crawl/{job_id}
GET /crawl/{job_id}/broken-links
GET /crawl/{job_id}/graph
GET /crawl/{job_id}/report
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
FRONTEND_URL=https://your-frontend-domain.vercel.app
ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app
```

SQLite is fine for demos and portfolio deployments. For durable production data on ephemeral hosting, move storage to Postgres or another managed database.

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

## Screenshots

Add screenshots here after running or deploying:

- WebScope overview dashboard
- Pages table
- Broken links tab
- SEO issues tab
- Performance tab
- Site Graph tab
- FastAPI docs

## Roadmap

- Live crawl progress and streaming job status
- Dockerfile and Docker Compose for local full-stack startup
- Persistent production database option such as Postgres
- Scheduled recurring audits and historical report comparison

## Resume Bullets

- Built WebScope, a full-stack website audit platform using FastAPI, React, Vite, SQLite, asyncio, aiohttp, BeautifulSoup, and React Flow.
- Implemented concurrent BFS crawling with robots.txt compliance, bounded crawl limits, crawl job tracking, timeout handling, CSV exports, and graph-ready crawl topology.
- Added SEO metadata extraction, broken link detection, slow page analysis, health scoring, report endpoints, and interactive site graph visualization.
- Designed a responsive React dashboard for audit summaries, broken links, SEO issues, performance reports, site graph exploration, and deployment-ready portfolio presentation.
