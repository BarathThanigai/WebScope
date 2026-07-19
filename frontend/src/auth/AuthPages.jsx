import React, { useState } from "react";
import { useTheme } from "../theme/ThemeContext";

export function LoginPage({ onLogin, onRegister, onHome, login }) {
  const { theme, toggleTheme } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login({ email, password });
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Welcome Back"
      subtitle="Sign in to launch your WebScope audit workspace."
      onHome={onHome}
      theme={theme}
      toggleTheme={toggleTheme}
    >
      <form className="auth-form" onSubmit={submit}>
        {error && <div className="alert error">{error}</div>}
        <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        <button className="primary" disabled={loading}>{loading ? "Signing in..." : "Sign In"}</button>
      </form>
      <p className="auth-switch">New to WebScope? <button onClick={onRegister}>Create an account</button></p>
    </AuthShell>
  );
}

export function RegisterPage({ onRegisterComplete, onLogin, onHome, register }) {
  const { theme, toggleTheme } = useTheme();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({ name, email, password });
      onRegisterComplete();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Create Your Account"
      subtitle="Start with a local WebScope account. Google sign-in is not enabled yet."
      onHome={onHome}
      theme={theme}
      toggleTheme={toggleTheme}
    >
      <form className="auth-form" onSubmit={submit}>
        {error && <div className="alert error">{error}</div>}
        <label>Name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
        <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Password<input type="password" minLength="8" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        <button className="primary" disabled={loading}>{loading ? "Creating account..." : "Create Account"}</button>
      </form>
      <p className="auth-switch">Already have an account? <button onClick={onLogin}>Sign in</button></p>
    </AuthShell>
  );
}

function AuthShell({ title, subtitle, children, onHome, theme, toggleTheme }) {
  return (
    <main className="auth-page">
      <header className="dashboard-topbar auth-topbar">
        <button className="dashboard-brand" onClick={onHome}>WebScope</button>
        <nav className="dashboard-nav" aria-label="Authentication navigation">
          <button onClick={onHome}>Back to Home</button>
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === "dark" ? "Light" : "Dark"} Mode
          </button>
        </nav>
      </header>
      <section className="auth-card panel">
        <p className="eyebrow">Website Intelligence & Audit Platform</p>
        <h1>{title}</h1>
        <p className="hero-copy">{subtitle}</p>
        {children}
      </section>
    </main>
  );
}
