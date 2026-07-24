import { Icons } from "../../components/Icons.jsx";

// Social handles shown on the landing — brand colour drives the hover glow/fill.
const SOCIALS = [
  {
    label: "Instagram", href: "https://www.instagram.com/theharis.ai/", color: "#E1306C",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
        <rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" />
        <circle cx="17.3" cy="6.7" r="1.1" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    label: "TikTok", href: "https://www.tiktok.com/@theharis.ai", color: "#FE2C55",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M16.5 3c.3 2.2 1.6 3.6 3.8 3.85v2.6c-1.3.05-2.5-.32-3.8-1.02v5.93c0 3.6-2.62 5.74-5.6 5.74A5.36 5.36 0 0 1 5.5 14.6c0-3.02 2.5-5.2 5.6-4.9v2.74c-.4-.13-.8-.2-1.2-.2-1.3 0-2.36 1.05-2.36 2.36 0 1.3 1.06 2.36 2.36 2.36 1.4 0 2.5-1.02 2.5-2.6V3h2.6z" />
      </svg>
    ),
  },
  {
    label: "LinkedIn", href: "https://www.linkedin.com/in/ai-haris/", color: "#0A66C2",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M20.4 3H3.6a.6.6 0 0 0-.6.6v16.8a.6.6 0 0 0 .6.6h16.8a.6.6 0 0 0 .6-.6V3.6a.6.6 0 0 0-.6-.6zM8.3 18.3H5.5V9.7h2.8v8.6zM6.9 8.5a1.63 1.63 0 1 1 0-3.26 1.63 1.63 0 0 1 0 3.26zm11.4 9.8h-2.8v-4.18c0-1 0-2.28-1.4-2.28-1.4 0-1.6 1.08-1.6 2.2v4.26H9.7V9.7h2.7v1.18h.04a2.96 2.96 0 0 1 2.66-1.46c2.85 0 3.38 1.87 3.38 4.3v4.58z" />
      </svg>
    ),
  },
  {
    label: "YouTube", href: "https://www.youtube.com/@harisailab", color: "#FF0000",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M23 12s0-3.2-.4-4.7a2.5 2.5 0 0 0-1.77-1.77C19.27 5.1 12 5.1 12 5.1s-7.27 0-8.83.43A2.5 2.5 0 0 0 1.4 7.3C1 8.8 1 12 1 12s0 3.2.4 4.7a2.5 2.5 0 0 0 1.77 1.77C4.73 18.9 12 18.9 12 18.9s7.27 0 8.83-.43a2.5 2.5 0 0 0 1.77-1.77C23 15.2 23 12 23 12z" />
        <path d="M9.75 15.3V8.7L15.5 12z" fill="#fff" />
      </svg>
    ),
  },
];

// Screen 1 — Video Input. Only a URL paste or a file upload; nothing else to
// decide here. Choosing either lights up "Continue", which is the sole way
// forward (auto-advance to Screen 2 the moment a source is picked).
export default function Screen1Input({
  source, setSource, url, setUrl, upload, upPct, drag, setDrag, fileRef,
  doUpload, onClear, sourceReady, error, onContinue,
}) {
  const uploading = source === "upload" && upPct != null && !upload;
  const fileChosen = source === "upload" && (upload || upPct != null);

  return (
    <>
      <div className="landing">
        <div className="brand-hero">
          <span className="brand-mark"><Icons.bolt /></span>
          <span className="brand-word">ClipForge</span>
          <span className="brand-by-hero">by Haris AI</span>
        </div>
        <span className="eyebrow"><span className="eyebrow-dot" />100% local pipeline · no API keys</span>
        <h1 className="landing-title">Turn any video into <span className="grad">captioned shorts</span></h1>
        <p className="landing-sub">
          Paste a link or drop a file — ClipForge finds the best moments, reframes them
          vertical, and burns on styled captions, right on your own machine.
        </p>

        <div
          className={"cmdbar" + (drag ? " drag" : "")}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); doUpload(e.dataTransfer.files[0]); }}
        >
          <input ref={fileRef} type="file" accept="video/*" hidden onChange={(e) => doUpload(e.target.files[0])} />
          <button className="cmd-upload" onClick={() => fileRef.current?.click()} title="Upload a video file">
            <Icons.upload /><span>Upload</span>
          </button>

          {fileChosen ? (
            <div className="cmd-file">
              <span className="cmd-file-name">{uploading ? `Uploading… ${upPct}%` : `✓ ${upload?.filename}`}</span>
              <button className="cmd-clear" onClick={onClear} title="Remove">✕</button>
            </div>
          ) : (
            <input
              className="cmd-input"
              type="text"
              placeholder="Paste a YouTube or video link…"
              value={url}
              onChange={(e) => { setSource("url"); setUrl(e.target.value); }}
              onKeyDown={(e) => { if (e.key === "Enter" && sourceReady) onContinue(); }}
            />
          )}

          <button className="cmd-go" disabled={!sourceReady} onClick={onContinue}>
            <Icons.bolt /> Continue
          </button>
        </div>

        {error && <div className="error landing-error">{error}</div>}

        <div className="landing-hints">
          {["Drag & drop a file onto the bar", "9:16, 16:9 & 1:1 square", "19 caption styles", "Manual reframe & keyframes"].map((h) => (
            <span className="hint-chip" key={h}><span className="hc-check"><Icons.check /></span>{h}</span>
          ))}
        </div>
      </div>

      <section className="landing-more">
        <div className="landing-section">
          <span className="eyebrow">How it works</span>
          <h2 className="landing-h2">From link to posted clip in 5 steps</h2>
          <div className="how-steps">
            {[
              ["Paste a link or upload", "YouTube, a downloaded file — anything with a video track."],
              ["Pick your settings", "Aspect ratio, GPU/CPU, caption language — that's all you decide up front."],
              ["Style your captions & effects", "Pick a preset or fully customise fonts, colours, glow, gradients."],
              ["Review every rendered clip", "All clips render automatically — reframe any that need a better crop."],
              ["Download & post", "Finished vertical/square/landscape clips, ready for Reels, Shorts, TikTok."],
            ].map(([t, d], i) => (
              <div className="how-step" key={t}>
                <span className="how-step-n">{i + 1}</span>
                <div><h3>{t}</h3><p>{d}</p></div>
              </div>
            ))}
          </div>
        </div>

        <div className="landing-section">
          <span className="eyebrow">What you can do</span>
          <h2 className="landing-h2">Everything a short-form editor needs — done locally</h2>
          <div className="feature-grid">
            {[
              [<Icons.create />, "19+ caption styles", "Hormozi-style, karaoke, word-reveal & more — or build and save your own."],
              [<Icons.crop />, "Manual reframe & keyframes", "Drag the crop box across time so the important part of the shot is never cut off."],
              [<Icons.film />, "Cinematic effects", "Colour grades, glow, vignette, film grain, gradients & letterboxing."],
              [<Icons.bolt />, "Auto-picked best moments", "Topic-aware clip selection finds natural start/end points, not mid-sentence cuts."],
              [<Icons.download />, "Background music", "Auto-suggested mood tracks that duck under your voice automatically."],
              [<Icons.settings />, "100% local, GPU or CPU", "Runs on your own machine — no API keys, nothing uploaded anywhere."],
            ].map(([icon, t, d]) => (
              <div className="feature-card" key={t}>
                <span className="feature-ico">{icon}</span>
                <h3>{t}</h3><p>{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="landing-social">
        {SOCIALS.map((s) => (
          <a key={s.label} className="soc" href={s.href} target="_blank" rel="noreferrer"
            title={s.label} aria-label={s.label} style={{ "--soc": s.color }}>
            {s.icon}
          </a>
        ))}
      </footer>
    </>
  );
}
