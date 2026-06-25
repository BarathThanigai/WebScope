import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const emptyStats = {
  total_pages_crawled: 0,
  total_links_found: 0,
  failed_requests: 0,
  average_response_time_ms: 0,
};

function formatMs(value) {
  return `${Number(value || 0).toFixed(1)} ms`;
}

function App() {
  const [activeView, setActiveView] = useState("dashboard");
  const [seedUrl, setSeedUrl] = useState("https://example.com");
  const [maxDepth, setMaxDepth] = useState(1);
  const [maxConcurrency, setMaxConcurrency] = useState(5);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [stats, setStats] = useState(emptyStats);
  const [pages, setPages] = useState([]);
  const [currentJob, setCurrentJob] = useState(null);
  const [jobSearch, setJobSearch] = useState("");

  useEffect(() => {
    refreshStats();
    refreshPages();
  }, []);

  const currentJobAverage = useMemo(() => {
    if (!currentJob?.pages?.length) return 0;
    const total = currentJob.pages.reduce((sum, page) => sum + page.response_time_ms, 0);
    return total / currentJob.pages.length;
  }, [currentJob]);

  async function request(path, options) {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || "The API request failed.");
    }

    return data;
  }

  async function refreshStats() {
    try {
      setStats(await request("/stats"));
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshPages(jobId = "") {
    try {
      const params = new URLSearchParams({ limit: "100", offset: "0" });
      if (jobId) params.set("job_id", jobId);
      setPages(await request(`/pages?${params.toString()}`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadJob(jobId) {
    if (!jobId) return;

    try {
      setError("");
      const job = await request(`/crawl/${jobId}`);
      setCurrentJob(job);
      setJobSearch(job.job_id);
      setPages(job.pages);
      setActiveView("job");
    } catch (err) {
      setError(err.message);
    }
  }

  async function startCrawl(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("Crawl in progress. This can take a moment on larger sites.");

    try {
      const result = await request("/crawl", {
        method: "POST",
        body: JSON.stringify({
          seed_url: seedUrl,
          max_depth: Number(maxDepth),
          max_concurrency: Number(maxConcurrency),
        }),
      });

      setSummary(result);
      setMessage(result.message);
      await loadJob(result.job_id);
      await refreshStats();
    } catch (err) {
      setError(err.message);
      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  const tableRows = activeView === "job" && currentJob ? currentJob.pages : pages;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">FastAPI + React</p>
          <h1>Concurrent Web Crawler</h1>
        </div>
        <nav className="nav">
          <button className={activeView === "dashboard" ? "active" : ""} onClick={() => setActiveView("dashboard")}>
            Dashboard
          </button>
          <button className={activeView === "job" ? "active" : ""} onClick={() => setActiveView("job")}>
            Job Details
          </button>
          <button className={activeView === "stats" ? "active" : ""} onClick={() => setActiveView("stats")}>
            Stats
          </button>
        </nav>
      </header>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      {activeView === "dashboard" && (
        <>
          <section className="panel">
            <form className="crawl-form" onSubmit={startCrawl}>
              <label>
                Seed URL
                <input value={seedUrl} onChange={(event) => setSeedUrl(event.target.value)} placeholder="https://example.com" />
              </label>
              <label>
                Max depth
                <input type="number" min="0" max="3" value={maxDepth} onChange={(event) => setMaxDepth(event.target.value)} />
              </label>
              <label>
                Max concurrency
                <input type="number" min="1" max="20" value={maxConcurrency} onChange={(event) => setMaxConcurrency(event.target.value)} />
              </label>
              <button className="primary" disabled={loading}>
                {loading ? "Crawling..." : "Start Crawl"}
              </button>
            </form>
          </section>

          <SummaryCards
            crawled={summary?.crawled_pages ?? stats.total_pages_crawled}
            links={summary?.total_links_found ?? stats.total_links_found}
            failed={summary?.failed_requests ?? stats.failed_requests}
            average={currentJob ? currentJobAverage : stats.average_response_time_ms}
          />

          <PagesTable pages={tableRows} title="Recent Crawled Pages" />
        </>
      )}

      {activeView === "job" && (
        <>
          <section className="panel job-search">
            <label>
              Crawl job ID
              <input value={jobSearch} onChange={(event) => setJobSearch(event.target.value)} placeholder="Paste a job ID" />
            </label>
            <button className="primary" onClick={() => loadJob(jobSearch)}>
              Load Job
            </button>
          </section>

          {currentJob && (
            <section className="job-meta">
              <div><span>Seed</span>{currentJob.seed_url}</div>
              <div><span>Depth</span>{currentJob.max_depth}</div>
              <div><span>Concurrency</span>{currentJob.max_concurrency}</div>
              <div><span>Pages</span>{currentJob.pages.length}</div>
            </section>
          )}

          <PagesTable pages={tableRows} title="Job Page Details" />
        </>
      )}

      {activeView === "stats" && (
        <>
          <SummaryCards
            crawled={stats.total_pages_crawled}
            links={stats.total_links_found}
            failed={stats.failed_requests}
            average={stats.average_response_time_ms}
          />
          <section className="panel">
            <div className="section-header">
              <h2>API Stats</h2>
              <button onClick={refreshStats}>Refresh</button>
            </div>
            <p className="muted">Stats are calculated from all stored crawl results in SQLite.</p>
          </section>
        </>
      )}
    </main>
  );
}

function SummaryCards({ crawled, links, failed, average }) {
  return (
    <section className="cards">
      <Metric label="Pages crawled" value={crawled} />
      <Metric label="Links found" value={links} />
      <Metric label="Failed requests" value={failed} />
      <Metric label="Avg response" value={formatMs(average)} />
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function PagesTable({ pages, title }) {
  return (
    <section className="panel">
      <div className="section-header">
        <h2>{title}</h2>
        <span className="muted">{pages.length} rows</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>URL</th>
              <th>Title</th>
              <th>Status</th>
              <th>Depth</th>
              <th>Time</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {pages.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty">No crawled pages yet.</td>
              </tr>
            ) : (
              pages.map((page) => (
                <tr key={`${page.job_id}-${page.url}`}>
                  <td className="url-cell" title={page.url}>{page.url}</td>
                  <td>{page.title || "Untitled"}</td>
                  <td>{page.status_code ?? "N/A"}</td>
                  <td>{page.depth}</td>
                  <td>{formatMs(page.response_time_ms)}</td>
                  <td>
                    <span className={page.success ? "pill success" : "pill failed"}>
                      {page.success ? "Success" : page.error || "Failed"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
