import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import { Icons } from "./components/Icons.jsx";
import ModelSelectScreen from "./components/ModelSelectScreen.jsx";
import GeminiKeyModal from "./components/GeminiKeyModal.jsx";
import Create from "./pages/Create.jsx";
import Library from "./pages/Library.jsx";
import Settings from "./pages/Settings.jsx";

const WORKFLOW_SUBMENUS = [
  { id: "source", step: 1, label: "Source Video", icon: Icons.video, desc: "Paste URL or upload local video file" },
  { id: "layout", step: 2, label: "Dynamic Split & Layout", icon: Icons.split, desc: "Vertical framing, dynamic AI split screen, and jump-cuts" },
  { id: "captions", step: 3, label: "Captions & Subtitles", icon: Icons.captions, desc: "Select styling presets, custom fonts, and subtitle placement" },
  { id: "effects", step: 4, label: "Cinematic VFX", icon: Icons.wand, desc: "Color grading, glow, vignette, and branding watermark" },
  { id: "music", step: 5, label: "Background Music", icon: Icons.music, desc: "Add soundtrack, speech ducking, and beat synchronization" },
  { id: "review", step: 6, label: "Timeline & Review", icon: Icons.timeline, desc: "Review clips, adjust duration, and inspect transcript" },
  { id: "export", step: 7, label: "Export Video", icon: Icons.export, desc: "Render, download, and reframe your vertical clips" },
];

const WORKSPACE_NAV = [
  { id: "library", label: "Library", icon: Icons.library, desc: "Every clip and project you've generated" },
  { id: "settings", label: "Settings", icon: Icons.settings, desc: "Compute device, Whisper AI models, and cache" },
];

const THEMES = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
];

// Splash while the whisper model is downloading or loading
function ModelSplash({ status }) {
  const pct = status.progress != null ? Math.round(status.progress * 100) : null;
  const failed = status.status === "error";
  return (
    <div className="model-splash" style={{ maxWidth: 520, margin: "0 auto", textAlign: "center" }}>
      <div className="model-splash-mark" style={{
        width: 56,
        height: 56,
        borderRadius: 18,
        background: "linear-gradient(135deg, var(--accent), #ff8a00)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 28,
        color: "#fff",
        marginBottom: 16,
        boxShadow: "0 8px 24px rgba(255, 107, 0, 0.3)",
      }}>
        <Icons.bolt />
      </div>
      <div className="model-splash-title" style={{ fontSize: "1.8rem", fontWeight: 700, marginBottom: 8 }}>
        Aurum Clipper
      </div>
      {failed ? (
        <>
          <div className="model-splash-msg" style={{ color: "var(--danger)", fontWeight: 600, fontSize: "1.1rem" }}>
            Could not start the AI engine.
          </div>
          <div className="model-splash-detail" style={{ color: "var(--muted)", margin: "8px 0 16px" }}>{status.message}</div>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>Retry</button>
        </>
      ) : (
        <>
          <div className="model-splash-msg" style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 12 }}>
            {status.message || "Starting up AI Engine…"}
          </div>
          <div className="track model-splash-track" style={{
            height: 10,
            borderRadius: 5,
            background: "rgba(255,255,255,0.08)",
            overflow: "hidden",
            margin: "12px 0",
          }}>
            <div
              className={"fill" + (pct == null ? " indeterminate" : "")}
              style={{
                height: "100%",
                background: "linear-gradient(90deg, var(--accent), #ff9900)",
                borderRadius: 5,
                transition: "width 0.3s ease",
                ...(pct == null ? {} : { width: `${pct}%` }),
              }}
            />
          </div>
          {pct != null && (
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", color: "var(--muted)", fontWeight: 600, marginBottom: 8 }}>
              <span>Download Progress</span>
              <span style={{ color: "var(--accent)" }}>{pct}%</span>
            </div>
          )}
          {status.status === "downloading" && (
            <div className="model-splash-detail" style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 6 }}>
              One-time download into local cache — saved forever on your device for instant offline use.
            </div>
          )}
        </>
      )}
    </div>
  );
}

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
  const [geminiConfig, setGeminiConfig] = useState({ configured: false, masked_key: null });
  const [geminiModalOpen, setGeminiModalOpen] = useState(false);
  const [isFirstRunOnboard, setIsFirstRunOnboard] = useState(false);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("cf-theme") || "dark"; } catch { return "dark"; }
  });
  const [savedModel, setSavedModel] = useState(() => {
    try { return localStorage.getItem("cf-model-size"); } catch { return null; }
  });
  const [modelStatus, setModelStatus] = useState({ status: "checking", message: "", progress: null });

  const refreshGemini = () => {
    api.getApiKey()
      .then((cfg) => {
        setGeminiConfig(cfg);
        const onboarded = localStorage.getItem("cf-gemini-onboarded");
        if (!cfg.configured && !onboarded) {
          setIsFirstRunOnboard(true);
          setGeminiModalOpen(true);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshGemini();
  }, []);

  // Poll until the whisper model status is known
  useEffect(() => {
    let alive = true;
    let timer;
    async function tick() {
      try {
        const s = await api.modelStatus();
        if (!alive) return;
        setModelStatus(s);
        if (s.status === "ready" || s.status === "error") return;
      } catch { /* server still coming up — keep trying */ }
      if (alive) timer = setTimeout(tick, 400);
    }
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [savedModel]);

  // If a saved model exists and backend is waiting for selection, trigger warmup
  useEffect(() => {
    if (savedModel && modelStatus.status === "unselected") {
      api.warmup("auto", savedModel).catch(() => {});
    }
  }, [savedModel, modelStatus.status]);

  const handleSelectModel = (chosenModel, chosenDevice) => {
    try { localStorage.setItem("cf-model-size", chosenModel); } catch {}
    setSavedModel(chosenModel);
    setModelStatus({ status: "downloading", message: `Initializing ${chosenModel} model...`, progress: 0.0 });
    api.warmup(chosenDevice || "auto", chosenModel).catch((e) => {
      setModelStatus({ status: "error", message: String(e.message || e), progress: null });
    });
  };

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

  const chromeless = false; // Always show sidebar/topbar

  const currentTitle = useMemo(() => {
    if (page === "library") return { h: "Library", sub: "Every clip and project you've generated" };
    if (page === "settings") return { h: "Settings & Engine", sub: "Compute hardware, Google Gemini AI & Whisper models" };
    const activeSubmenu = WORKFLOW_SUBMENUS.find((s) => s.step === step) || WORKFLOW_SUBMENUS[0];
    return { h: activeSubmenu.label, sub: activeSubmenu.desc };
  }, [page, step]);

  // If no model has been selected yet (first run), show the Model Selection Screen!
  if (!savedModel && (modelStatus.status === "unselected" || modelStatus.status === "idle" || modelStatus.status === "checking")) {
    return (
      <div className="shell is-landing">
        <ThemeSwitch theme={theme} setTheme={setTheme} fixed />
        <div className="content" style={{ overflowY: "auto" }}>
          <ModelSelectScreen onSelect={handleSelectModel} />
        </div>
      </div>
    );
  }

  // If model is actively downloading/loading, show the splash with progress
  if (modelStatus.status !== "ready") {
    return (
      <div className={"shell is-landing" + (navOpen ? " nav-open" : "")}>
        <ThemeSwitch theme={theme} setTheme={setTheme} fixed />
        <div className="content"><ModelSplash status={modelStatus} /></div>
      </div>
    );
  }

  return (
    <div className={"shell" + (chromeless ? " is-landing" : "") + (navOpen ? " nav-open" : "")}>
      {/* On the chromeless landing the topbar is hidden, so float the switcher. */}
      {chromeless && <ThemeSwitch theme={theme} setTheme={setTheme} fixed />}

      <div className="nav-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />

      <aside className="sidebar">
        <div className="brand">
          <span className="logo"><Icons.bolt /></span>
          <span className="brand-text">Aurum Clipper<span className="brand-by">Made By RED4724</span></span>
        </div>
        <nav className="nav">
          <div className="nav-section">
            <div className="nav-section-title">Creative Studio</div>
            {WORKFLOW_SUBMENUS.map((item) => {
              const active = page === "create" && step === item.step;
              const isPast = page === "create" && step > item.step;
              return (
                <button
                  key={item.id}
                  className={"nav-item" + (active ? " active" : "") + (isPast ? " done-step" : "")}
                  onClick={() => {
                    setPage("create");
                    setStep(item.step);
                    setNavOpen(false);
                  }}
                  title={item.desc}
                >
                  <item.icon />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.label}</span>
                  <span className="nav-step">{isPast ? "✓" : item.step}</span>
                </button>
              );
            })}
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Workspace</div>
            {WORKSPACE_NAV.map((n) => (
              <button
                key={n.id}
                className={"nav-item" + (page === n.id ? " active" : "")}
                onClick={() => {
                  setPage(n.id);
                  setNavOpen(false);
                }}
                title={n.desc}
              >
                <n.icon />
                <span>{n.label}</span>
              </button>
            ))}
          </div>
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
            <h1>{currentTitle.h}</h1>
            <div className="sub">{currentTitle.sub}</div>
          </div>
          <div className="topbar-right">
            {/* Gemini AI Status Pill / Launcher */}
            <button
              type="button"
              className={"gemini-pill-btn " + (geminiConfig.configured ? "is-active" : "is-pending")}
              onClick={() => {
                setIsFirstRunOnboard(false);
                setGeminiModalOpen(true);
              }}
              title={geminiConfig.configured ? `Google Gemini AI Active (${geminiConfig.masked_key}) — Click to configure` : "Connect Google Gemini API key for AI curation"}
            >
              <span className="gemini-sparkle">✨</span>
              <span>{geminiConfig.configured ? "Gemini AI Active" : "Connect Gemini"}</span>
            </button>

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
          <div style={{ display: page === "create" ? "block" : "none" }}>
            <Create step={step} setStep={setStep} />
          </div>
          {page === "library" && <Library />}
          {page === "settings" && <Settings />}
        </div>
      </div>

      {/* Google Gemini Onboarding & Configuration Modal */}
      <GeminiKeyModal
        isOpen={geminiModalOpen}
        onClose={() => setGeminiModalOpen(false)}
        onKeySaved={() => {
          refreshGemini();
        }}
        isFirstRun={isFirstRunOnboard}
      />
    </div>
  );
}
