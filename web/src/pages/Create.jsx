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

export default function Create() {
  const [step, setStep] = useState(1);
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
  const [numClips, setNumClips] = useState(3);
  const [language, setLanguage] = useState("auto");
  const [device, setDevice] = useState("auto");

  // Background music
  const [tracks, setTracks] = useState([]);
  const [musicTrack, setMusicTrack] = useState("");
  const [musicVolume, setMusicVolume] = useState(35);
  const [musicDuck, setMusicDuck] = useState(70);

  // Generate
  const [busy, setBusy] = useState(false);
  const [snap, setSnap] = useState(null);
  const [clips, setClips] = useState([]);
  const [error, setError] = useState("");
  const closeRef = useRef(null);
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
    return prep;
  }, [source, upPct, upload, prep]);

  async function generate() {
    setError("");
    const payload = {
      aspect_ratio: aspect, fit_mode: fit,
      bar_text: fit === "square" ? (barText.trim() || null) : null,
      num_clips: numClips, device, caption_style: studio.styleId,
      language: language === "auto" ? null : language,
    };
    if (Object.keys(studio.overrides).length) payload.caption_overrides = studio.overrides;
    if (cineActive(studio.cinematic)) payload.cinematic = studio.cinematic;
    if (musicTrack) { payload.music_track = musicTrack; payload.music_volume = musicVolume; payload.music_duck = musicDuck; }
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
      closeRef.current = streamProgress(job_id, (sn) => {
        setSnap(sn);
        if (sn.clips) setClips(sn.clips);
        if (sn.status === "done" || sn.status === "error") {
          setBusy(false);
          if (sn.status === "error") setError(sn.error || sn.message || "Pipeline failed.");
          closeRef.current && closeRef.current();
        }
      }, () => { setBusy(false); setError("Lost connection to the progress stream."); });
    } catch (e) { setBusy(false); setError(e.message); }
  }

  const curStep = STEPS.findIndex(([k]) => k === snap?.stage);
  const done = snap?.status === "done";
  const pct = Math.round((snap?.progress || 0) * 100);

  /* ---------- STEP 1 ---------- */
  if (step === 1) {
    return (
      <div className="card" style={{ maxWidth: 720, margin: "0 auto" }}>
        <span className="eyebrow">Step 1 of 2</span>
        <h2 style={{ margin: "6px 0 18px", fontSize: 22 }}>Add your video</h2>
        <div className="toggle" style={{ marginBottom: 16 }}>
          <button className={source === "url" ? "active" : ""} onClick={() => setSource("url")}>Paste link</button>
          <button className={source === "upload" ? "active" : ""} onClick={() => setSource("upload")}>Upload file</button>
        </div>
        {source === "url" ? (
          <input type="text" placeholder="https://youtube.com/watch?v=…" value={url} onChange={(e) => setUrl(e.target.value)} />
        ) : (
          <div className={"dropzone" + (drag ? " drag" : "")} onClick={() => fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); doUpload(e.dataTransfer.files[0]); }}>
            <input ref={fileRef} type="file" accept="video/*" hidden onChange={(e) => doUpload(e.target.files[0])} />
            <div className="dz-main">{upPct != null ? `Uploading… ${upPct}%` : upload ? `✓ ${upload.filename}` : "Drop a video or click to browse"}</div>
            <div className="dz-sub">MP4 · MOV · WEBM</div>
          </div>
        )}
        {error && <div className="error">{error}</div>}
        <button className="btn btn-primary btn-block" style={{ marginTop: 22 }} disabled={!sourceReady} onClick={() => { setStep(2); startPrep(); }}>
          Continue →
        </button>
      </div>
    );
  }

  /* ---------- STEP 2 ---------- */
  return (
    <>
      <button className="btn btn-ghost" style={{ marginBottom: 16 }} onClick={() => setStep(1)}>← Back to source</button>

      <div className="editor">
        <div className="editor-left">
          <details className="card sect" open>
            <summary className="card-h sect-h"><h2>Output</h2><span className="sect-x" /></summary>
            <div className="row" style={{ flexWrap: "wrap", gap: 18 }}>
              <div><label className="fieldlabel">Aspect</label>
                <div className="toggle">{["9:16", "16:9"].map((a) => <button key={a} className={aspect === a ? "active" : ""} onClick={() => setAspect(a)}>{a}</button>)}</div>
              </div>
              <div><label className="fieldlabel">Fit</label>
                <div className="toggle">{["crop", "square"].map((x) => <button key={x} className={fit === x ? "active" : ""} onClick={() => setFit(x)}>{x[0].toUpperCase() + x.slice(1)}</button>)}</div>
              </div>
              <div><label className="fieldlabel">Clips</label>
                <div className="counter">
                  <button onClick={() => setNumClips((n) => Math.max(1, n - 1))}>−</button>
                  <input type="number" min="1" max="10" value={numClips} onChange={(e) => setNumClips(Math.max(1, Math.min(10, +e.target.value || 1)))} />
                  <button onClick={() => setNumClips((n) => Math.min(10, n + 1))}>+</button>
                </div>
              </div>
            </div>
            {fit === "square" && (
              <div style={{ marginTop: 14 }}><label className="fieldlabel">Title text (top)</label>
                <input type="text" placeholder="Title shown over the square…" value={barText} onChange={(e) => setBarText(e.target.value)} /></div>
            )}
            <div className="grid-2" style={{ marginTop: 14 }}>
              <div><label className="fieldlabel">Caption language</label>
                <select value={language} onChange={(e) => changeLanguage(e.target.value)}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
              <div><label className="fieldlabel">Compute</label>
                <select value={device} onChange={(e) => setDevice(e.target.value)}>
                  {["auto", ...devices.filter((d) => d !== "auto")].filter((v, i, a) => a.indexOf(v) === i).map((d) => <option key={d} value={d}>{d === "cuda" ? "GPU (CUDA)" : d.toUpperCase()}</option>)}
                </select></div>
            </div>
          </details>

          <CaptionStudio studio={studio} language={language} onFontUpload={onFontUpload} />

          <Music tracks={tracks} track={musicTrack} volume={musicVolume} duck={musicDuck}
            onTrack={setMusicTrack} onVolume={setMusicVolume} onDuck={setMusicDuck} onUpload={onMusicUpload} onRefresh={refreshMusic} />
        </div>

        <div className="editor-right">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            aspect={aspect} fit={fit} barText={barText} overrides={studio.overrides} setOverride={studio.setOverride} />

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
            <button className="btn btn-primary btn-block" disabled={busy} onClick={generate}>
              {busy ? <><span className="spinner" /> Working…</> : <><Icons.bolt /> Generate {numClips} clip{numClips > 1 ? "s" : ""}</>}
            </button>
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
      </div>

      {clips.length > 0 && (
        <div className="card" style={{ marginTop: 18 }} ref={clipsRef}>
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
