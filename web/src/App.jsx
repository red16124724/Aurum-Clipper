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

export default function App() {
  const [page, setPage] = useState("create");
  const [step, setStep] = useState(1);
  const [device, setDevice] = useState(null);
  const [online, setOnline] = useState(null);

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
  // are HIDDEN (via the .is-landing class), not unmounted. Crucially, <Create>
  // stays mounted at the SAME tree position across the landing→editor switch, so
  // its source/url/upload state survives (re-mounting it would wipe the pasted URL).
  const chromeless = page === "create" && step === 1;
  const t = TITLES[page];

  return (
    <div className={"shell" + (chromeless ? " is-landing" : "")}>
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
              onClick={() => { setPage(n.id); if (n.id === "create") setStep(1); }}
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
          <div>
            <h1>{t.h}</h1>
            <div className="sub">{t.sub}</div>
          </div>
          <div className="topbar-right">
            <span className={"badge " + (online ? "ok" : online === false ? "warn" : "")}>
              <span className="dot" />
              {online == null ? "Connecting…" : online ? `Backend · ${(device || "ready").toUpperCase()}` : "Backend offline"}
            </span>
          </div>
        </header>

        <div className="content">
          {/* Orbs are ALWAYS in the tree (hidden via CSS off the landing) so that
              <Create> never changes sibling-index — otherwise toggling them would
              remount Create and wipe its in-flight download/prep state. */}
          <div className="landing-orbs" aria-hidden="true">
            <span className="orb orb-1" />
            <span className="orb orb-2" />
            <span className="orb orb-3" />
            <span className="orb orb-4" />
          </div>
          {page === "create" && <Create key="create" step={step} setStep={setStep} />}
          {page === "library" && <Library />}
          {page === "settings" && <Settings />}
        </div>
      </div>
    </div>
  );
}
