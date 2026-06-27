export default function Hero({ onLaunch }) {
  return (
    <section className="landing-hero" id="top">
      <div className="hero-content">
        <span className="hero-badge">Website Intelligence & Audit Platform</span>
        <h1>Understand Your Website in Minutes, Not Hours.</h1>
        <p className="hero-subheading">
          Crawl your website, uncover SEO issues, detect link problems, analyze performance,
          and visualize your entire site structure from one intelligent platform.
        </p>
        <div className="landing-actions">
          <button className="primary hero-primary" onClick={onLaunch}>Start Free Audit</button>
          <a className="hero-secondary" href="https://github.com/BarathThanigai/Concurrent_Web_Crawler">View GitHub</a>
        </div>
      </div>
      <div className="hero-preview-card" aria-label="WebScope dashboard preview">
        <div className="preview-card-header">
          <div>
            <span>Health Score</span>
            <strong>96%</strong>
          </div>
          <span className="score-pill">Excellent</span>
        </div>

        <div className="preview-metrics">
          <div><span>Link Issues</span><strong>1</strong></div>
          <div><span>SEO Issues</span><strong>4</strong></div>
          <div><span>Slow Pages</span><strong>5</strong></div>
          <div><span>Avg Response</span><strong>586ms</strong></div>
        </div>

        <div className="mini-site-graph" aria-hidden="true">
          <svg viewBox="0 0 320 160" role="img">
            <path d="M72 80 L154 38 L154 122 L248 80" />
            <path d="M154 38 L248 80 L154 122" />
          </svg>
          <span className="graph-node node-a"></span>
          <span className="graph-node node-b"></span>
          <span className="graph-node node-c"></span>
          <span className="graph-node node-d warning"></span>
        </div>
      </div>
    </section>
  );
}
