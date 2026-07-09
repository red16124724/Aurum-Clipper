import { useEffect, useMemo, useRef, useState } from "react";
import { api, streamProgress } from "../api.js";
import { Icons } from "../components/Icons.jsx";
import { LANGS, parseEmbed, cineActive } from "../caption.js";
import { useStudio } from "../useStudio.js";
import { usePrep } from "../usePrep.js";
import CaptionStudio from "../components/CaptionStudio.jsx";
import PhonePreview from "../components/PhonePreview.jsx";
import Music from "../components/Music.jsx";

const STEPS = [["downloading", "Download"], ["transcribing", "Transcribe"], ["selecting", "Analyze"], ["rendering", "Render"]];

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

export default function Create({ step, setStep }) {
  const [presets, setPresets] = useState([]);
  const [fonts, setFonts] = useState({ bundled: [], multilingual: [], user: [] });
  const [devices, setDevices] = useState(["auto"]);

  // Source
  const [source, setSource] = useState("url");
  const [url, setUrl] = useState("");
  const [upload, setUpload] = useState(null);
  const [upPct, setUpPct] = useState(null);
  const [objUrl, setObjUrl] = useState(null);
  const [drag, setDrag] = useState(false);

  // Output
  const [aspect, setAspect] = useState("9:16");
  const [fit, setFit] = useState("crop");
  const [barText, setBarText] = useState("");
  const [barTextColor, setBarTextColor] = useState("#FFFFFF");
  const [barTextAnim, setBarTextAnim] = useState("none");
  const [numClips, setNumClips] = useState(3);
  const [clipLen, setClipLen] = useState(null);   // target clip length in seconds; null = Auto (adaptive)
  const [language, setLanguage] = useState("auto");
  const [device, setDevice] = useState("auto");

  // Background music
  const [tracks, setTracks] = useState([]);
  const [musicTrack, setMusicTrack] = useState("");
  const [musicVolume, setMusicVolume] = useState(35);
  const [musicDuck, setMusicDuck] = useState(70);
  const [musicStart, setMusicStart] = useState(0);  // seconds into the track to start from (beat-aligned)
  const [musicSuggest, setMusicSuggest] = useState(null);  // {mood,label,emoji,hint} from transcript

  // Signature / watermark
  const [signature, setSignature] = useState({ enabled: false, text: "@theharis.ai", pos_x: 50, pos_y: 92, size: 34, color: "#FFFFFF", opacity: 75 });
  const setSig = (k, v) => setSignature((s) => ({ ...s, [k]: v }));

  // Generate
  const [busy, setBusy] = useState(false);
  const [snap, setSnap] = useState(null);
  const [clips, setClips] = useState([]);
  const [error, setError] = useState("");
  const closeRef = useRef(null);
  const jobRef = useRef(null);
  const fileRef = useRef(null);
  const clipsRef = useRef(null);

  const studio = useStudio(presets, fonts, language);
  const prep = usePrep(device, language);

  // Kick off the background download (URL) or transcript prep (upload).
  function startPrep() {
    if (source === "url" && url.trim()) prep.startUrl(url.trim());
    else if (source === "upload" && upload?.upload_id) prep.startUpload(upload.upload_id);
  }

  // On Step 2 (and when the upload finishes there), prepare in the background so
  // Generate is instant — with live progress shown under the preview.
  useEffect(() => {
    if (step === 2) startPrep();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, source, upload?.upload_id, url]);

  useEffect(() => {
    api.captionStyles().then((p) => setPresets(p || [])).catch(() => {});
    api.fonts().then((f) => setFonts(f || { bundled: [], multilingual: [], user: [] })).catch(() => {});
    api.devices().then((d) => { setDevices(d.devices || ["auto"]); setDevice(d.cuda_available ? "cuda" : "cpu"); }).catch(() => {});
    api.music().then((m) => setTracks(m.tracks || [])).catch(() => {});
    return () => closeRef.current && closeRef.current();
  }, []);

  // As soon as the first clip lands, jump straight to it so the user never has to
  // scroll the whole options column to reach the downloads.
  useEffect(() => {
    if (clips.length === 1) clipsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [clips.length]);

  const refreshMusic = () => api.music().then((m) => setTracks(m.tracks || [])).catch(() => {});
  async function onMusicUpload(file) { const t = await api.uploadMusic(file); await refreshMusic(); return t; }

  // Inject @font-face for previews whenever fonts load.
  useEffect(() => {
    const all = [...(fonts.user || []), ...(fonts.multilingual || []), ...(fonts.bundled || [])];
    let css = "";
    all.forEach((f) => { css += `@font-face{font-family:'${f.family}';src:url('/fonts/${encodeURIComponent(f.file)}');font-display:swap;}`; });
    let el = document.getElementById("cf-fontfaces");
    if (!el) { el = document.createElement("style"); el.id = "cf-fontfaces"; document.head.appendChild(el); }
    el.textContent = css;
  }, [fonts]);

  const media = useMemo(() => {
    if (source === "upload") return objUrl ? { kind: "video", src: objUrl } : null;
    // Once the background download finishes, preview the real downloaded file
    // (accurate frames/captions/cinematic); until then show the link's embed.
    if (prep.downloadId) return { kind: "video", src: `/api/download/${prep.downloadId}/video` };
    return parseEmbed(url.trim());
  }, [source, objUrl, url, prep.downloadId]);

  // Suggest a music mood from the prepared transcript (once it's ready).
  const srcId = (source === "upload" ? upload?.upload_id : prep.downloadId) || null;
  useEffect(() => {
    if (!srcId) { setMusicSuggest(null); return; }
    let alive = true;
    api.musicSuggest(srcId, language === "auto" ? null : language)
      .then((m) => { if (alive && m && m.ready) setMusicSuggest(m); })
      .catch(() => {});
    return () => { alive = false; };
  }, [srcId, language, prep.prep?.phase]);

  async function doUpload(file) {
    if (!file) return;
    setSource("upload"); setUpload(null); setUpPct(0); setError("");
    if (objUrl) URL.revokeObjectURL(objUrl);
    setObjUrl(URL.createObjectURL(file));
    try { const d = await api.upload(file, setUpPct); setUpload({ upload_id: d.upload_id, filename: d.filename || file.name }); setUpPct(null); }
    catch (e) { setError(e.message); setUpPct(null); }
  }

  async function onFontUpload(file) {
    const d = await api.uploadFont(file);
    const fresh = await api.fonts();
    setFonts(fresh);
    return d.family;
  }

  function changeLanguage(v) { setLanguage(v); studio.onLanguageChange(v); prep.relang(v); }

  const sourceReady = source === "upload" ? !!(upload || objUrl) : !!url.trim();

  // What the prep box shows. While an uploaded source file is still streaming to
  // the backend (you can move to Step 2 before it finishes), surface that upload's
  // progress here instead of a blank "Preparing video…". Otherwise show the normal
  // download/transcribe prep state.
  const prepView = useMemo(() => {
    if (source === "upload" && upPct != null && !upload) {
      return { phase: "downloading", pct: upPct,
        message: upPct >= 100 ? "Processing upload…" : "Uploading your video…" };
    }
    return prep.prep;  // the actual download/transcribe STATE (usePrep returns { prep, … })
  }, [source, upPct, upload, prep.prep]);

  async function generate() {
    setError("");
    const payload = {
      aspect_ratio: aspect, fit_mode: fit,
      bar_text: fit === "square" ? (barText.trim() || null) : null,
      bar_text_color: barTextColor, bar_text_anim: barTextAnim,
      num_clips: numClips, device, caption_style: studio.styleId,
      language: language === "auto" ? null : language,
    };
    if (clipLen != null) payload.clip_length = clipLen;
    if (Object.keys(studio.overrides).length) payload.caption_overrides = studio.overrides;
    if (cineActive(studio.cinematic)) payload.cinematic = studio.cinematic;
    if (musicTrack) { payload.music_track = musicTrack; payload.music_volume = musicVolume; payload.music_duck = musicDuck; payload.music_start = musicStart; }
    if (signature.enabled && (signature.text || "").trim()) payload.signature = signature;
    if (source === "upload") {
      if (!upload) { setError("Wait for the upload to finish."); return; }
      payload.upload_id = upload.upload_id; payload.upload_name = upload.filename;
    } else {
      if (!url.trim()) { setError("Paste a video URL."); return; }
      payload.video_url = url.trim();
      // Reuse the file already fetched in the background → skips re-downloading.
      if (prep.downloadId) payload.download_id = prep.downloadId;
    }

    setBusy(true); setClips([]); setSnap({ stage: "queued", progress: 0.02, message: "Starting…", status: "running" });
    try {
      const { job_id } = await api.generate(payload);
      jobRef.current = job_id;
      closeRef.current = streamProgress(job_id, (sn) => {
        setSnap(sn);
        if (sn.clips) setClips(sn.clips);
        if (sn.status === "done" || sn.status === "error" || sn.status === "cancelled") {
          setBusy(false);
          if (sn.status === "error") setError(sn.error || sn.message || "Pipeline failed.");
          closeRef.current && closeRef.current();
        }
      }, () => { setBusy(false); setError("Lost connection to the progress stream."); });
    } catch (e) { setBusy(false); setError(e.message); }
  }

  // Cancel an in-flight render: tell the backend to stop, drop the stream, reset UI.
  function cancelGenerate() {
    if (jobRef.current) api.cancel(jobRef.current).catch(() => {});
    closeRef.current && closeRef.current();
    setBusy(false); setSnap(null); setError("");
  }

  const curStep = STEPS.findIndex(([k]) => k === snap?.stage);
  const done = snap?.status === "done";
  const pct = Math.round((snap?.progress || 0) * 100);

  /* ---------- STEP 1 · Landing ---------- */
  if (step === 1) {
    const uploading = source === "upload" && upPct != null && !upload;
    const fileChosen = source === "upload" && (upload || upPct != null);
    const clearFile = () => {
      setSource("url"); setUpload(null); setUpPct(null);
      if (objUrl) { URL.revokeObjectURL(objUrl); setObjUrl(null); }
    };
    return (
    <>
      <div className="landing">
        <div className="brand-hero">
          <span className="brand-mark"><Icons.bolt /></span>
          <span className="brand-word">ClipForge</span>
        </div>
        <span className="eyebrow">100% local pipeline · no API keys</span>
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
              <button className="cmd-clear" onClick={clearFile} title="Remove">✕</button>
            </div>
          ) : (
            <input
              className="cmd-input"
              type="text"
              placeholder="Paste a YouTube or video link…"
              value={url}
              onChange={(e) => { setSource("url"); setUrl(e.target.value); }}
              onKeyDown={(e) => { if (e.key === "Enter" && sourceReady) { startPrep(); setStep(2); } }}
            />
          )}

          <button className="cmd-go" disabled={!sourceReady} onClick={() => { startPrep(); setStep(2); }}>
            <Icons.bolt /> Generate
          </button>
        </div>

        {error && <div className="error landing-error">{error}</div>}

        <div className="landing-hints">
          <span>Drag &amp; drop a file onto the bar</span>
          <span className="sep">·</span><span>9:16 &amp; 1:1 square</span>
          <span className="sep">·</span><span>19 caption styles</span>
          <span className="sep">·</span><span>background music</span>
        </div>
      </div>

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

  /* ---------- STEP 2 ---------- */
  return (
    <>
      <button className="btn btn-ghost" style={{ marginBottom: 16 }} onClick={() => setStep(1)}>← Back to source</button>

      <div className="editor3">
        {/* LEFT — Captions */}
        <div className="editor-captions">
          <CaptionStudio studio={studio} language={language} onFontUpload={onFontUpload} signature={signature} setSig={setSig} />
        </div>

        {/* CENTER — Live preview + Generate */}
        <div className="editor-center">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            signature={signature} setSig={setSig}
            overrides={studio.overrides} setOverride={studio.setOverride} />

          <div className={"prep prep-" + (prepView.phase || "idle")}>
            <div className="prep-row">
              <span className="prep-msg">
                {["downloading", "transcribing", "downloaded", "idle"].includes(prepView.phase) && <span className="spinner" />}
                {prepView.phase === "ready" && <span className="prep-ok">✓</span>}
                {prepView.phase === "error" && <span className="prep-ok" style={{ color: "var(--danger)" }}>!</span>}
                {prepView.message || "Preparing video…"}
              </span>
              {prepView.pct != null && <span className="prep-pct">{prepView.pct}%</span>}
            </div>
            <div className="track"><div className={"fill" + (prepView.pct == null ? " indeterminate" : "")} style={prepView.pct == null ? {} : { width: prepView.pct + "%" }} /></div>
          </div>

          <div className="card gen-card">
            {busy ? (
              <>
                <div className="gen-busy">
                  <span className="gen-busy-orbit" />
                  <span className="gen-busy-text">Generating clips<span className="gen-dots"><i>.</i><i>.</i><i>.</i></span></span>
                </div>
                <button className="btn btn-cancel btn-block" onClick={cancelGenerate}>Cancel</button>
              </>
            ) : (
              <button className="btn btn-primary btn-block" onClick={generate}><Icons.bolt /> Generate clips</button>
            )}
            {error && <div className="error">{error}</div>}
            {snap && (
              <div style={{ marginTop: 18 }}>
                <div className="steps">
                  {STEPS.map(([k, lbl], i) => (
                    <div key={k} className={"step" + (done || i < curStep ? " done" : i === curStep ? " active" : "")}>
                      <div className="ring">{done || i < curStep ? "✓" : i + 1}</div><div className="lbl">{lbl}</div>
                    </div>
                  ))}
                </div>
                <div className="bar-row"><span className="msg">{busy && <span className="spinner" />}{snap.message}</span><span className="pct">{pct}%</span></div>
                <div className="track"><div className="fill" style={{ width: pct + "%" }} /></div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT — Output settings */}
        <div className="editor-output">
          <details className="card sect" open>
            <summary className="card-h sect-h"><h2>Output</h2><span className="sect-x" /></summary>
            <div className="row" style={{ flexWrap: "wrap", gap: 16 }}>
              <div><label className="fieldlabel">Aspect</label>
                <div className="toggle">{["9:16", "16:9"].map((a) => <button key={a} className={aspect === a ? "active" : ""} onClick={() => setAspect(a)}>{a}</button>)}</div>
              </div>
              <div><label className="fieldlabel">Fit</label>
                <div className="toggle">{["crop", "square"].map((x) => <button key={x} className={fit === x ? "active" : ""} onClick={() => setFit(x)}>{x[0].toUpperCase() + x.slice(1)}</button>)}</div>
              </div>
              <div><label className="fieldlabel">Clips</label>
                <div className="counter">
                  <button onClick={() => setNumClips((n) => Math.max(1, n - 1))}>−</button>
                  <input type="number" min="1" max="100" value={numClips} onChange={(e) => setNumClips(Math.max(1, Math.min(100, +e.target.value || 1)))} />
                  <button onClick={() => setNumClips((n) => Math.min(100, n + 1))}>+</button>
                </div>
              </div>
              <div style={{ width: "100%" }}>
                <label className="fieldlabel">Clip length</label>
                <div className="toggle">
                  {[["Auto", null], ["30s", 30], ["45s", 45], ["60s", 60]].map(([lbl, v]) => (
                    <button key={lbl} className={clipLen === v ? "active" : ""} onClick={() => setClipLen(v)}>{lbl}</button>
                  ))}
                  <button className={clipLen != null && ![30, 45, 60].includes(clipLen) ? "active" : ""}
                    onClick={() => setClipLen((c) => (c != null && ![30, 45, 60].includes(c) ? c : 90))}>Custom</button>
                </div>
                {clipLen != null && ![30, 45, 60].includes(clipLen) && (
                  <div className="counter" style={{ marginTop: 8, width: "fit-content" }}>
                    <input type="number" min="5" max="600" value={clipLen}
                      onChange={(e) => setClipLen(Math.max(5, Math.min(600, +e.target.value || 5)))} />
                    <span style={{ padding: "0 10px", opacity: 0.7 }}>sec</span>
                  </div>
                )}
              </div>
            </div>
            {fit === "square" && (
              <div style={{ marginTop: 14 }}>
                <label className="fieldlabel">Title text (top) — Shift+Enter for a new line</label>
                <textarea className="title-area" placeholder="Title shown over the square…&#10;Second line…" rows={2} maxLength={120}
                  value={barText} onChange={(e) => setBarText(e.target.value)} />
                <div className="row" style={{ gap: 12, marginTop: 10, alignItems: "center" }}>
                  <label className="swatch">Title colour<input type="color" value={barTextColor} onChange={(e) => setBarTextColor(e.target.value)} /></label>
                  <div style={{ flex: 1 }}>
                    <label className="fieldlabel">Animation</label>
                    <select value={barTextAnim} onChange={(e) => setBarTextAnim(e.target.value)}>
                      <option value="none">None</option>
                      <option value="fade">Fade in</option>
                      <option value="slide">Slide up</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
            <div style={{ marginTop: 14, display: "grid", gap: 14 }}>
              <div><label className="fieldlabel">Caption language</label>
                <select value={language} onChange={(e) => changeLanguage(e.target.value)}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div><label className="fieldlabel">Compute</label>
                <select value={device} onChange={(e) => setDevice(e.target.value)}>
                  {["auto", ...devices.filter((d) => d !== "auto")].filter((v, i, a) => a.indexOf(v) === i).map((d) => <option key={d} value={d}>{d === "cuda" ? "GPU (CUDA)" : d.toUpperCase()}</option>)}
                </select></div>
            </div>
          </details>
        </div>

        {/* RIGHT — background music (with beat analysis) lives up here on the right */}
        <div className="editor-musiccol">
          <Music tracks={tracks} track={musicTrack} volume={musicVolume} duck={musicDuck} musicStart={musicStart} suggest={musicSuggest}
            onTrack={(t) => { setMusicTrack(t); setMusicStart(0); }} onVolume={setMusicVolume} onDuck={setMusicDuck} onStart={setMusicStart}
            onUpload={onMusicUpload} onRefresh={refreshMusic} />
        </div>
      </div>

      {/* BOTTOM — generated clips, full width */}
      {clips.length > 0 && (
        <div className="clips-bottom card" ref={clipsRef}>
          <div className="card-h"><h2>Your clips</h2><span className="hint">{clips.length} ready</span></div>
          <div className="clips">
            {clips.map((c) => (
              <div className="clip" key={c.url}>
                <video src={c.url} controls preload="metadata" />
                <div className="meta">
                  <h3>{c.title}</h3>
                  <div className="sub">{(c.end - c.start).toFixed(1)}s · {c.start.toFixed(1)}–{c.end.toFixed(1)}s</div>
                  <div className="acts">
                    <a href={c.url} download={c.filename || ""}>Download</a>
                    <button onClick={() => navigator.clipboard.writeText(location.origin + c.url)}>Copy link</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
