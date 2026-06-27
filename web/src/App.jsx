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

  // The Create landing (step 1) is a clean, full-screen page with NO app chrome —
  // the sidebar + topbar only appear once you start (step 2) or open another page.
  const chromeless = page === "create" && step === 1;
  if (chromeless) {
    return (
      <div className="landing-shell">
        <div className="landing-orbs" aria-hidden="true">
          <span className="orb orb-1" />
          <span className="orb orb-2" />
          <span className="orb orb-3" />
          <span className="orb orb-4" />
        </div>
        <Create step={step} setStep={setStep} />
      </div>
    );
  }

  const t = TITLES[page];
  return (
    <div className="shell">
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
          {page === "create" && <Create step={step} setStep={setStep} />}
          {page === "library" && <Library />}
          {page === "settings" && <Settings />}
        </div>
      </div>
    </div>
  );
}
