import { useTheme } from "../../theme/ThemeContext";

export default function Navbar({ onLaunch }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="landing-navbar">
      <a className="landing-brand" href="#top">WebScope</a>
      <nav className="landing-links" aria-label="Landing navigation">
        <a href="#features">Features</a>
        <a href="#how-it-works">How it works</a>
        <a href="#tech-stack">Tech stack</a>
        <button className="theme-toggle" onClick={toggleTheme}>
          {theme === "dark" ? "Light" : "Dark"} Mode
        </button>
        <button className="primary" onClick={onLaunch}>Launch App</button>
      </nav>
    </header>
  );
}
