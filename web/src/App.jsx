import { useEffect, useState } from "react";
import { api } from "./api.js";
import { Icons } from "./components/Icons.jsx";
import Create from "./pages/Create.jsx";
import Library from "./pages/Library.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { id: "create", label: "Create", icon: Icons.create },
  { id: "library", label: "Library", icon: Icons.library },
  { id: "settings", label: "Settings", icon: Icons.settings },
];

const TITLES = {
  create: { h: "Create clips", sub: "Turn any video into captioned vertical shorts" },
  library: { h: "Library", sub: "Every clip you've generated" },
  settings: { h: "Settings", sub: "Compute device & environment" },
};

const THEMES = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
];

// Segmented light/dark switch. Writes the choice to <html data-theme> and
// remembers it across reloads. "dark" is the CSS default, so we clear the attr.
function ThemeSwitch({ theme, setTheme, fixed }) {
  return (
    <div className={"theme-switch" + (fixed ? " theme-switch-fixed" : "")} role="group" aria-label="Theme">
      {THEMES.map((t) => (
        <button key={t.id} className={theme === t.id ? "active" : ""}
          onClick={() => setTheme(t.id)} title={`${t.label} theme`}>{t.label}</button>
      ))}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("create");
  const [step, setStep] = useState(1);
  const [device, setDevice] = useState(null);
  const [online, setOnline] = useState(null);
  const [navOpen, setNavOpen] = useState(false);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("cf-theme") || "dark"; } catch { return "dark"; }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try { localStorage.setItem("cf-theme", theme); } catch { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    let alive = true;
    const ping = () =>
      api.health()
        .then((d) => { if (alive) { setOnline(true); setDevice(d.device); } })
        .catch(() => { if (alive) setOnline(false); });
    ping();
    const t = setInterval(ping, 8000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  // The Create landing (step 1) is a clean, full-screen page: the sidebar + topbar
  // are HIDDEN (via the .is-landing class), not unmounted. <Create> stays mounted
  // across landing→editor so its source/url/upload state survives.
  const chromeless = page === "create" && step === 1;
  const t = TITLES[page];

  const go = (id) => { setPage(id); if (id === "create") setStep(1); setNavOpen(false); };

  return (
    <div className={"shell" + (chromeless ? " is-landing" : "") + (navOpen ? " nav-open" : "")}>
      {/* On the chromeless landing the topbar is hidden, so float the switcher. */}
      {chromeless && <ThemeSwitch theme={theme} setTheme={setTheme} fixed />}

      <div className="nav-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />

      <aside className="sidebar">
        <div className="brand">
          <span className="logo"><Icons.bolt /></span>
          ClipForge
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={"nav-item" + (page === n.id ? " active" : "")}
              onClick={() => go(n.id)}
            >
              <n.icon /> {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          100% local pipeline<br />yt-dlp · faster-whisper · ffmpeg
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <button className="nav-toggle" onClick={() => setNavOpen((o) => !o)} aria-label="Menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="topbar-titles">
            <h1>{t.h}</h1>
            <div className="sub">{t.sub}</div>
          </div>
          <div className="topbar-right">
            <ThemeSwitch theme={theme} setTheme={setTheme} />
            <span className={"badge " + (online ? "ok" : online === false ? "warn" : "")}>
              <span className="dot" />
              {online == null ? "Connecting…" : online ? `Backend · ${(device || "ready").toUpperCase()}` : "Backend offline"}
            </span>
          </div>
        </header>

        <div className="content">
          {/* Orbs are ALWAYS in the tree (hidden via CSS off the landing) so that
              <Create> never changes sibling-index. */}
          <div className="landing-orbs" aria-hidden="true">
            <span className="orb orb-1" />
            <span className="orb orb-2" />
            <span className="orb orb-3" />
            <span className="orb orb-4" />
            <span className="orb orb-5" />
          </div>
          {page === "create" && <Create key="create" step={step} setStep={setStep} />}
          {page === "library" && <Library />}
          {page === "settings" && <Settings />}
        </div>
      </div>
    </div>
  );
}
