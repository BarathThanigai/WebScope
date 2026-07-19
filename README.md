# WebScope

WebScope is a full-stack Website Intelligence & Audit Platform that enables authenticated users to perform asynchronous website audits with real-time progress monitoring, AI-powered audit summaries, SEO and performance analysis, interactive site graph visualization, and exportable reports through a modern responsive dashboard.

It combines a high-performance asynchronous crawler, Redis-backed background job processing, PostgreSQL persistence, secure JWT authentication, and a React + Vite frontend to deliver production-style website intelligence and monitoring.

## Features

- Concurrent BFS-style crawling with `asyncio` and `aiohttp`
- `robots.txt` compliance and sitemap.xml discovery
- WebScopeBot User-Agent, polite crawl delays, retry/backoff, and failure classification
- Asynchronous crawl jobs with Redis Queue (RQ)
- Real-time crawl monitoring with Server-Sent Events (SSE)
- Production-style crawl monitor with phases, queue depth, worker counts, crawl speed, ETA, and cancellation
- User-configurable crawl settings (`max_depth`, `max_concurrency`, and `max_pages`)
- Secure JWT authentication
- User registration and login
- Protected dashboard for authenticated users
- AI-powered audit summaries using NVIDIA's OpenAI-compatible API
- SEO analysis
  - Title
  - Meta description
  - H1 tags
  - Canonical URL
  - Word count
  - Page size
  - Missing SEO metadata detection
- Performance analysis
  - Response time
  - Slow page detection
  - Average, minimum, and maximum response times
- Link issue detection and classification
- Interactive website graph visualization with React Flow
- Website health scoring
- CSV export
- Modern responsive dashboard with:
  - Overview
  - Pages
  - Link Issues
  - SEO Issues
  - Performance
  - Site Graph
  - AI Summary

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
- PostgreSQL
- SQLite (development fallback)
- Redis
- Redis Queue (RQ)
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
├── main.py
├── crawler.py
├── database.py
├── models.py
├── config.py
├── worker.py
├── services/
│
├── ai/
│   ├── provider.py
│   ├── nvidia_provider.py
│   ├── prompts.py
│   └── schemas.py
│
├── auth/
│   ├── router.py
│   ├── users.py
│   ├── jwt.py
│   ├── security.py
│   ├── dependencies.py
│   ├── exceptions.py
│   └── schemas.py
│
├── queue.py
├── crawl_tasks.py
│
├── requirements.txt
├── .env.example
│
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

---

## API Endpoints

### Authentication

```http
POST /auth/register
POST /auth/login
GET /auth/me
```

### Crawl

```http
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
GET /
GET /health
GET /queue/health
GET /pages
GET /stats
```

---

## Environment Variables

### Backend

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

- Google OAuth login
- User-owned audit history
- Audit comparison and change tracking
- Scheduled recurring audits
- Team workspaces and shared audits
- Docker deployment improvements
- Additional AI providers (Gemini, Groq, OpenRouter)

---

## Copyright

Copyright © 2026 Barath.

All Rights Reserved.

This repository is intended for portfolio and evaluation purposes only.
No permission is granted to use, copy, modify, distribute, or create derivative works from this software without prior written permission from the author.