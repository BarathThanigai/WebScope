# Concurrent Web Crawler

A deployed-ready full-stack web crawler built with FastAPI, React, Vite, asyncio, aiohttp, BeautifulSoup, and SQLite.

## Features

- Concurrent BFS-style crawling with `asyncio` and `aiohttp`
- `robots.txt` checking before page fetches
- Crawl job IDs with full job detail lookup
- SQLite storage for jobs and crawled pages
- Response time tracking in milliseconds
- Paginated and job-filtered page results
- React dashboard with crawl form, summary metrics, job details, stats, and page table
- CORS and environment-based frontend origin configuration

## Project Structure

```text
.
├── main.py
├── crawler.py
├── database.py
├── models.py
├── config.py
├── requirements.txt
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        └── styles.css
```

## Local Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FRONTEND_URL="http://localhost:5173"
uvicorn main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## Local Frontend Setup

```powershell
cd frontend
npm install
$env:VITE_API_URL="http://127.0.0.1:8000"
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

- `FRONTEND_URL`: allowed frontend origin. Defaults to `http://localhost:5173`.
- `ALLOWED_ORIGINS`: optional comma-separated list of allowed CORS origins.

Frontend:

- `VITE_API_URL`: backend API base URL. Defaults to `http://127.0.0.1:8000`.

## API Usage

### Health Check

```http
GET /health
```

### Start a Crawl

```http
POST /crawl
Content-Type: application/json

{
  "seed_url": "https://example.com",
  "max_depth": 2,
  "max_concurrency": 10
}
```

Limits:

- `max_depth`: 0 to 3
- `max_concurrency`: 1 to 20

Sample response:

```json
{
  "job_id": "2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7",
  "crawled_pages": 4,
  "total_links_found": 12,
  "failed_requests": 0,
  "message": "Crawl completed. Full results are available at /crawl/2f5b8cc8-0f2b-4f2d-a514-6566b4dfc9e7."
}
```

### Get Crawl Details

```http
GET /crawl/{job_id}
```

### Get Pages

```http
GET /pages?limit=50&offset=0
GET /pages?job_id={job_id}&limit=100&offset=0
```

### Get Stats

```http
GET /stats
```

## Architecture

The backend keeps crawling, persistence, request models, and API routes separate:

- `crawler.py`: concurrency, BFS depth traversal, robots.txt checks, HTML parsing, timeout handling
- `database.py`: SQLite schema, migrations, job storage, page queries, aggregate stats
- `models.py`: Pydantic request and response models
- `main.py`: FastAPI routes, CORS, health checks, endpoint orchestration
- `config.py`: environment-based deployment settings

The frontend is a Vite React app with a single dashboard-oriented interface. It talks to the API through `VITE_API_URL`, making it portable across local development, Vercel, Render Static Sites, and other hosts.

## Deployment

### Backend on Render

1. Create a new Render Web Service.
2. Connect this repository.
3. Use Python as the runtime.
4. Set the build command:

```bash
pip install -r requirements.txt
```

5. Set the start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

6. Add environment variables:

```text
FRONTEND_URL=https://your-frontend-domain.vercel.app
ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app
```

SQLite works for demos and portfolio deployments. For persistent production data on ephemeral hosts, move storage to a managed database.

### Frontend on Vercel

1. Import the repository in Vercel.
2. Set the root directory to `frontend`.
3. Set the build command:

```bash
npm run build
```

4. Set the output directory:

```text
dist
```

5. Add environment variable:

```text
VITE_API_URL=https://your-render-backend.onrender.com
```

### Frontend on Render Static Site

1. Create a new Render Static Site.
2. Set the root directory to `frontend`.
3. Set the build command:

```bash
npm install && npm run build
```

4. Set the publish directory:

```text
dist
```

5. Add `VITE_API_URL` pointing to the deployed backend.

## Sample Screenshots

Add screenshots here after deploying or running locally:

- Dashboard crawl form and summary cards
- Job details table
- Stats page
- FastAPI docs at `/docs`
