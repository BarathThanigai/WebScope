import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import "reactflow/dist/style.css";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const emptyReport = {
  total_pages: 0,
  total_links: 0,
  broken_links_count: 0,
  slow_pages_count: 0,
  missing_titles_count: 0,
  missing_descriptions_count: 0,
  missing_h1_count: 0,
  seo_issues_count: 0,
  average_response_time_ms: 0,
  min_response_time_ms: 0,
  max_response_time_ms: 0,
  health_score: 0,
  top_10_slowest_pages: [],
};

function formatMs(value) {
  return `${Number(value || 0).toFixed(1)} ms`;
}

function App() {
  const [seedUrl, setSeedUrl] = useState("https://books.toscrape.com");
  const [maxDepth, setMaxDepth] = useState(1);
  const [maxConcurrency, setMaxConcurrency] = useState(8);
  const [maxPages, setMaxPages] = useState(50);
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(emptyReport);
  const [brokenLinks, setBrokenLinks] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState(null);
  const [jobSearch, setJobSearch] = useState("");

  useEffect(() => {
    setMessage("Recommended test sites: https://books.toscrape.com and https://quotes.toscrape.com");
  }, []);

  const pages = job?.pages || [];
  const seoIssuePages = useMemo(
    () => pages.filter((page) => page.missing_title || page.missing_description || page.missing_h1),
    [pages],
  );
  const slowPages = useMemo(() => pages.filter((page) => page.is_slow), [pages]);
  const topIssues = useMemo(
    () => [
      { label: "Broken links", value: report.broken_links_count },
      { label: "Slow pages", value: report.slow_pages_count },
      { label: "Missing titles", value: report.missing_titles_count },
      { label: "Missing descriptions", value: report.missing_descriptions_count },
      { label: "Missing H1 tags", value: report.missing_h1_count },
    ].filter((issue) => issue.value > 0),
    [report],
  );

  async function request(path, options) {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "The API request failed.");
    return data;
  }

  async function loadJob(jobId) {
    if (!jobId) return;
    setError("");
    const [jobData, reportData, brokenData, graphData] = await Promise.all([
      request(`/crawl/${jobId}`),
      request(`/crawl/${jobId}/report`),
      request(`/crawl/${jobId}/broken-links`),
      request(`/crawl/${jobId}/graph`),
    ]);
    setJob(jobData);
    setReport(reportData);
    setBrokenLinks(brokenData);
    setGraph(graphData);
    setSelectedNode(null);
    setJobSearch(jobId);
  }

  async function startCrawl(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("Running audit. Some websites may block crawlers or require JavaScript rendering.");
    try {
      const result = await request("/crawl", {
        method: "POST",
        body: JSON.stringify({
          seed_url: seedUrl,
          max_depth: Number(maxDepth),
          max_concurrency: Number(maxConcurrency),
          max_pages: Number(maxPages),
        }),
      });
      setSummary(result);
      await loadJob(result.job_id);
      setActiveTab("overview");
      setMessage(result.message);
    } catch (err) {
      setError(err.message);
      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  function exportCsv() {
    if (!job?.job_id) return;
    window.open(`${API_URL}/crawl/${job.job_id}/export/csv`, "_blank", "noopener,noreferrer");
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Website Intelligence & Audit Platform</p>
          <h1>WebScope</h1>
          <p className="hero-copy">Audit crawlability, broken links, SEO metadata, and response times from one focused dashboard.</p>
        </div>
        <div className="score-card">
          <span>Health Score</span>
          <strong>{report.health_score}%</strong>
          <p>{job ? "Latest crawl report" : "Run a crawl to score a site"}</p>
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}
      {message && <div className="alert info">{message}</div>}

      <section className="panel">
        <form className="crawl-form" onSubmit={startCrawl}>
          <label>Seed URL<input value={seedUrl} onChange={(event) => setSeedUrl(event.target.value)} /></label>
          <label>Max depth<input type="number" min="0" max="3" value={maxDepth} onChange={(event) => setMaxDepth(event.target.value)} /></label>
          <label>Concurrency<input type="number" min="1" max="20" value={maxConcurrency} onChange={(event) => setMaxConcurrency(event.target.value)} /></label>
          <label>Max pages<input type="number" min="1" max="200" value={maxPages} onChange={(event) => setMaxPages(event.target.value)} /></label>
          <button className="primary" disabled={loading}>{loading ? "Auditing..." : "Start Audit"}</button>
        </form>
        <p className="crawler-note">Some websites may block crawlers due to robots.txt, anti-bot rules, rate limits, or JavaScript-heavy pages.</p>
      </section>

      <SummaryCards summary={summary} report={report} />

      <section className="toolbar panel">
        <label>Load job ID<input value={jobSearch} onChange={(event) => setJobSearch(event.target.value)} placeholder="Paste an existing crawl job ID" /></label>
        <button onClick={() => loadJob(jobSearch)}>Load Report</button>
        <button className="primary" disabled={!job} onClick={exportCsv}>Export CSV</button>
      </section>

      <nav className="tabs">
        {["overview", "pages", "broken links", "seo issues", "performance", "site graph"].map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>{tab}</button>
        ))}
      </nav>

      {activeTab === "overview" && <Overview report={report} job={job} topIssues={topIssues} />}
      {activeTab === "pages" && <PagesTable pages={pages} title="Crawled Pages" />}
      {activeTab === "broken links" && <BrokenLinksTable links={brokenLinks} />}
      {activeTab === "seo issues" && <SeoIssuesTable pages={seoIssuePages} />}
      {activeTab === "performance" && <Performance report={report} pages={slowPages} />}
      {activeTab === "site graph" && (
        <SiteGraph graph={graph} selectedNode={selectedNode} setSelectedNode={setSelectedNode} />
      )}
    </main>
  );
}

function SummaryCards({ summary, report }) {
  return (
    <section className="cards">
      <Metric label="Pages crawled" value={summary?.crawled_pages ?? report.total_pages} />
      <Metric label="Broken links" value={report.broken_links_count} tone="bad" />
      <Metric label="Slow pages" value={report.slow_pages_count} tone="warn" />
      <Metric label="SEO issues" value={report.seo_issues_count} tone="warn" />
      <Metric label="Total links" value={summary?.total_links_found ?? report.total_links} />
      <Metric label="Avg response" value={formatMs(report.average_response_time_ms)} />
    </section>
  );
}

function Metric({ label, value, tone = "" }) {
  return <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong></article>;
}

function Overview({ report, job, topIssues }) {
  return (
    <section className="overview-grid">
      <div className="panel">
        <div className="section-header"><h2>Crawl Report</h2><span className="muted">{job?.job_id || "No job loaded"}</span></div>
        <div className="report-list">
          <ReportRow label="Total pages" value={report.total_pages} />
          <ReportRow label="Total links" value={report.total_links} />
          <ReportRow label="Broken links" value={report.broken_links_count} />
          <ReportRow label="Missing titles" value={report.missing_titles_count} />
          <ReportRow label="Missing descriptions" value={report.missing_descriptions_count} />
          <ReportRow label="Missing H1 tags" value={report.missing_h1_count} />
        </div>
      </div>
      <div className="panel health-explain">
        <div className="section-header"><h2>Health Score</h2><strong>{report.health_score}%</strong></div>
        <p>
          WebScope scores each crawl by subtracting broken links, slow pages, and missing SEO metadata
          from the ideal site health baseline.
        </p>
        <div className="issue-chips">
          {topIssues.length === 0 ? (
            <span className="chip good">No major issues found</span>
          ) : topIssues.map((issue) => (
            <span className="chip" key={issue.label}>{issue.label}: {issue.value}</span>
          ))}
        </div>
      </div>
      <div className="panel">
        <div className="section-header"><h2>Performance</h2></div>
        <div className="report-list">
          <ReportRow label="Average response" value={formatMs(report.average_response_time_ms)} />
          <ReportRow label="Fastest page" value={formatMs(report.min_response_time_ms)} />
          <ReportRow label="Slowest page" value={formatMs(report.max_response_time_ms)} />
          <ReportRow label="Slow pages" value={report.slow_pages_count} />
        </div>
      </div>
      <div className="panel">
        <div className="section-header"><h2>Slowest Pages</h2></div>
        <div className="mini-list">
          {report.top_10_slowest_pages.length === 0 ? (
            <p className="muted">Run a crawl to see slow pages.</p>
          ) : report.top_10_slowest_pages.slice(0, 5).map((page) => (
            <div className="mini-row" key={page.url}>
              <span title={page.url}>{page.title || page.url}</span>
              <strong>{formatMs(page.response_time_ms)}</strong>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ReportRow({ label, value }) {
  return <div className="report-row"><span>{label}</span><strong>{value}</strong></div>;
}

function PagesTable({ pages, title }) {
  return (
    <section className="panel">
      <div className="section-header"><h2>{title}</h2><span className="muted">{pages.length} rows</span></div>
      <TableShell empty="No pages have been crawled yet." columns={["URL", "Title", "Status", "Depth", "Time", "Audit"]}>
        {pages.map((page) => (
          <tr key={`${page.job_id}-${page.url}`}>
            <td className="url-cell" title={page.url}>{page.url}</td>
            <td>{page.title || "Missing title"}</td>
            <td>{page.status_code ?? "N/A"}</td>
            <td>{page.depth}</td>
            <td>{formatMs(page.response_time_ms)}</td>
            <td><StatusPill page={page} /></td>
          </tr>
        ))}
      </TableShell>
    </section>
  );
}

function BrokenLinksTable({ links }) {
  return (
    <section className="panel">
      <div className="section-header"><h2>Broken Links</h2><span className="muted">{links.length} issues</span></div>
      <TableShell empty="No broken links found for the selected crawl." columns={["Broken URL", "Found on", "Status", "Error"]}>
        {links.map((link) => (
          <tr key={`${link.job_id}-${link.url}`}>
            <td className="url-cell" title={link.url}>{link.url}</td>
            <td className="url-cell" title={link.source_url || ""}>{link.source_url || "Seed URL"}</td>
            <td>{link.status_code ?? "N/A"}</td>
            <td>{link.error || "HTTP error"}</td>
          </tr>
        ))}
      </TableShell>
    </section>
  );
}

function SeoIssuesTable({ pages }) {
  return (
    <section className="panel">
      <div className="section-header"><h2>SEO Issues</h2><span className="muted">{pages.length} pages</span></div>
      <TableShell empty="No title, description, or H1 issues found." columns={["URL", "Title", "Description", "H1", "Word Count"]}>
        {pages.map((page) => (
          <tr key={`${page.job_id}-seo-${page.url}`}>
            <td className="url-cell" title={page.url}>{page.url}</td>
            <td>{page.missing_title ? "Missing" : "Present"}</td>
            <td>{page.missing_description ? "Missing" : "Present"}</td>
            <td>{page.missing_h1 ? "Missing" : `${page.h1_tags.length} found`}</td>
            <td>{page.word_count}</td>
          </tr>
        ))}
      </TableShell>
    </section>
  );
}

function Performance({ report, pages }) {
  return (
    <>
      <section className="cards compact">
        <Metric label="Average response" value={formatMs(report.average_response_time_ms)} />
        <Metric label="Min response" value={formatMs(report.min_response_time_ms)} />
        <Metric label="Max response" value={formatMs(report.max_response_time_ms)} />
      </section>
      <PagesTable pages={pages.length ? pages : report.top_10_slowest_pages} title="Slowest Pages" />
    </>
  );
}

function SiteGraph({ graph, selectedNode, setSelectedNode }) {
  const flowNodes = useMemo(() => {
    const depthCounts = new Map();
    return graph.nodes.map((node) => {
      const siblingIndex = depthCounts.get(node.depth) || 0;
      depthCounts.set(node.depth, siblingIndex + 1);
      return {
        id: node.id,
        position: { x: node.depth * 280, y: siblingIndex * 120 },
        data: { label: node.title || safePath(node.url), page: node },
        className: graphNodeClass(node),
      };
    });
  }, [graph.nodes]);

  const flowEdges = useMemo(
    () => graph.edges.map((edge, index) => ({ id: `edge-${index}`, ...edge })),
    [graph.edges],
  );

  return (
    <section className="graph-layout">
      <div className="panel graph-panel">
        <div className="section-header">
          <h2>Site Graph</h2>
          <span className="muted">{graph.nodes.length} nodes, {graph.edges.length} edges</span>
        </div>
        <div className="graph-canvas">
          {graph.nodes.length === 0 ? (
            <div className="graph-empty">Run or load a crawl to visualize internal links.</div>
          ) : (
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              fitView
              onNodeClick={(_, node) => setSelectedNode(node.data.page)}
            >
              <MiniMap pannable zoomable />
              <Controls />
              <Background gap={18} />
            </ReactFlow>
          )}
        </div>
        <div className="legend">
          <span><i className="legend-dot normal"></i>Normal</span>
          <span><i className="legend-dot slow"></i>Slow</span>
          <span><i className="legend-dot seo"></i>SEO issue</span>
          <span><i className="legend-dot failed"></i>Failed</span>
        </div>
      </div>
      <div className="panel node-detail">
        <div className="section-header"><h2>Page Details</h2></div>
        {selectedNode ? (
          <div className="report-list">
            <ReportRow label="URL" value={selectedNode.url} />
            <ReportRow label="Title" value={selectedNode.title || "Missing title"} />
            <ReportRow label="Depth" value={selectedNode.depth} />
            <ReportRow label="Status" value={selectedNode.status_code ?? "N/A"} />
            <ReportRow label="Slow" value={selectedNode.is_slow ? "Yes" : "No"} />
            <ReportRow label="SEO Issue" value={selectedNode.has_seo_issue ? "Yes" : "No"} />
          </div>
        ) : (
          <p className="muted">Click a graph node to inspect the crawled page.</p>
        )}
      </div>
    </section>
  );
}

function graphNodeClass(node) {
  if (!node.success) return "graph-node failed-node";
  if (node.is_slow) return "graph-node slow-node";
  if (node.has_seo_issue) return "graph-node seo-node";
  return "graph-node normal-node";
}

function safePath(url) {
  try {
    return new URL(url).pathname || url;
  } catch {
    return url;
  }
}

function TableShell({ columns, empty, children }) {
  const rows = React.Children.toArray(children);
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>{rows.length === 0 ? <tr><td className="empty" colSpan={columns.length}>{empty}</td></tr> : rows}</tbody>
      </table>
    </div>
  );
}

function StatusPill({ page }) {
  if (!page.success) return <span className="pill failed">{page.error || "Failed"}</span>;
  if (page.is_slow) return <span className="pill warn">Slow</span>;
  if (page.missing_title || page.missing_description || page.missing_h1) return <span className="pill warn">SEO issue</span>;
  return <span className="pill success">Healthy</span>;
}

createRoot(document.getElementById("root")).render(<App />);
