import { useEffect, useMemo, useRef, useState } from "react";
import { api, streamProgress } from "../api.js";
import { parseEmbed, cineActive } from "../caption.js";
import { useStudio } from "../useStudio.js";
import { usePrep } from "../usePrep.js";
import ReframeEditor from "../components/ReframeEditor.jsx";
import Screen1Input from "./create/Screen1Input.jsx";
import Screen2Settings from "./create/Screen2Settings.jsx";
import Screen3Captions from "./create/Screen3Captions.jsx";
import Screen4Effects from "./create/Screen4Effects.jsx";
import Screen5Music from "./create/Screen5Music.jsx";
import Screen6Review from "./create/Screen5Review.jsx";
import Screen7Export from "./create/Screen6Export.jsx";

// Screen numbers 1-7: Source, Settings, Captions, Effects, Music, Review, Export.
// (Component file names kept as Screen5Review.jsx/Screen6Export.jsx from an
// earlier layout — only the wizard's step NUMBERS shifted when Music became
// its own screen.)
const WIZARD_LABELS = ["Source", "Settings", "Captions", "Effects", "Music", "Review", "Export"];

function targetAspectNum(aspect, fit) {
  if (fit === "square") return 1;
  return aspect === "16:9" ? 16 / 9 : 9 / 16;
}

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
  const [squareCorners, setSquareCorners] = useState("round");

  const outputAspect = fit === "square" ? "1:1" : aspect;
  function setOutputAspect(v) {
    if (v === "1:1") setFit("square");
    else { setFit("crop"); setAspect(v); }
  }

  // Background music
  const [tracks, setTracks] = useState([]);
  const [musicTrack, setMusicTrack] = useState("");
  const [musicVolume, setMusicVolume] = useState(35);
  const [musicDuck, setMusicDuck] = useState(70);
  const [musicStart, setMusicStart] = useState(0);
  const [musicSuggest, setMusicSuggest] = useState(null);

  // Signature / watermark
  const [signature, setSignature] = useState({ enabled: false, text: "@theharis.ai", pos_x: 50, pos_y: 92, size: 34, color: "#FFFFFF", opacity: 75 });
  const setSig = (k, v) => setSignature((s) => ({ ...s, [k]: v }));

  // Generate
  const [busy, setBusy] = useState(false);
  const [snap, setSnap] = useState(null);
  const [clips, setClips] = useState([]);
  const [clipId, setClipId] = useState(null);
  const [error, setError] = useState("");
  const closeRef = useRef(null);
  const jobRef = useRef(null);
  const fileRef = useRef(null);
  const generatedRef = useRef(false);

  // Reframe
  const [reframeTarget, setReframeTarget] = useState(null); // the clip object being reframed
  const reframeCache = useRef({}); // clipId:index -> last keyframes edited this session

  const videoRef = useRef(null);
  const [curTime, setCurTime] = useState(0);
  const [vidDuration, setVidDuration] = useState(null);
  const [transcript, setTranscript] = useState({ ready: false, loading: false, segments: [], duration: null });

  const studio = useStudio(presets, fonts, language);
  const prep = usePrep(device, language);

  function startPrep() {
    if (source === "url" && url.trim()) prep.startUrl(url.trim());
    else if (source === "upload" && upload?.upload_id) prep.startUpload(upload.upload_id);
  }

  // Background download/pre-transcribe kicks off the moment Screen 2 is
  // entered, so it's finished (or well underway) by the time Screen 3/5 need it.
  useEffect(() => {
    if (step >= 2) startPrep();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step >= 2, source, upload?.upload_id, url]);

  useEffect(() => {
    api.captionStyles().then((p) => setPresets(p || [])).catch(() => {});
    api.fonts().then((f) => setFonts(f || { bundled: [], multilingual: [], user: [] })).catch(() => {});
    api.devices().then((d) => { setDevices(d.devices || ["auto"]); setDevice(d.cuda_available ? "cuda" : "cpu"); }).catch(() => {});
    api.music().then((m) => setTracks(m.tracks || [])).catch(() => {});
    return () => closeRef.current && closeRef.current();
  }, []);

  const refreshMusic = () => api.music().then((m) => setTracks(m.tracks || [])).catch(() => {});
  async function onMusicUpload(file) { const t = await api.uploadMusic(file); await refreshMusic(); return t; }

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
    if (prep.downloadId) return { kind: "video", src: `/api/download/${prep.downloadId}/video` };
    return parseEmbed(url.trim());
  }, [source, objUrl, url, prep.downloadId]);

  const srcId = (source === "upload" ? upload?.upload_id : prep.downloadId) || null;
  useEffect(() => {
    if (!srcId) { setMusicSuggest(null); return; }
    let alive = true;
    api.musicSuggest(srcId, language === "auto" ? null : language)
      .then((m) => { if (alive && m && m.ready) setMusicSuggest(m); })
      .catch(() => {});
    return () => { alive = false; };
  }, [srcId, language, prep.prep?.phase]);

  useEffect(() => {
    if (!srcId) { setTranscript({ ready: false, loading: false, segments: [], duration: null }); return; }
    let alive = true;
    setTranscript((t) => ({ ...t, loading: true }));
    api.transcript(srcId, language === "auto" ? null : language)
      .then((d) => { if (alive) setTranscript({ ready: !!d.ready, loading: false, segments: d.segments || [], duration: d.duration ?? null }); })
      .catch(() => { if (alive) setTranscript((t) => ({ ...t, loading: false })); });
    return () => { alive = false; };
  }, [srcId, language, prep.prep?.phase]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) { setVidDuration(null); return; }
    const onTime = () => setCurTime(v.currentTime);
    const onMeta = () => setVidDuration(isFinite(v.duration) ? v.duration : null);
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("loadedmetadata", onMeta);
    if (v.readyState >= 1 && isFinite(v.duration)) setVidDuration(v.duration);
    return () => { v.removeEventListener("timeupdate", onTime); v.removeEventListener("loadedmetadata", onMeta); };
  }, [media]);

  function seekTo(t) {
    if (t == null || !isFinite(t)) return;
    const v = videoRef.current;
    if (v) { try { v.currentTime = Math.max(0, t); } catch { /* not seekable yet */ } }
    setCurTime(t);
  }

  async function doUpload(file) {
    if (!file) { setSource("url"); setUpload(null); setUpPct(null); if (objUrl) { URL.revokeObjectURL(objUrl); setObjUrl(null); } return; }
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

  const prepView = useMemo(() => {
    if (source === "upload" && upPct != null && !upload) {
      return { phase: "downloading", pct: upPct, message: upPct >= 100 ? "Processing upload…" : "Uploading your video…" };
    }
    return prep.prep;
  }, [source, upPct, upload, prep.prep]);

  async function generate() {
    setError("");
    const payload = {
      aspect_ratio: aspect, fit_mode: fit,
      bar_text: fit === "square" ? (barText.trim() || null) : null,
      bar_text_color: barTextColor, bar_text_anim: barTextAnim,
      num_clips: numClips, device, caption_style: studio.styleId,
      language: language === "auto" ? null : language,
      square_corners: squareCorners,
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
      if (prep.downloadId) payload.download_id = prep.downloadId;
    }

    setBusy(true); setClips([]); setSnap({ stage: "queued", progress: 0.02, message: "Starting…", status: "running" });
    try {
      const { job_id } = await api.generate(payload);
      jobRef.current = job_id;
      closeRef.current = streamProgress(job_id, (sn) => {
        setSnap(sn);
        if (sn.clips) setClips(sn.clips);
        if (sn.clip_id) setClipId(sn.clip_id);
        if (sn.status === "done" || sn.status === "error" || sn.status === "cancelled") {
          setBusy(false);
          if (sn.status === "error") setError(sn.error || sn.message || "Pipeline failed.");
          closeRef.current && closeRef.current();
        }
      }, () => { setBusy(false); setError("Lost connection to the progress stream."); });
    } catch (e) { setBusy(false); setError(e.message); }
  }

  function cancelGenerate() {
    if (jobRef.current) api.cancel(jobRef.current).catch(() => {});
    closeRef.current && closeRef.current();
    setBusy(false); setSnap(null); setError("");
    generatedRef.current = false;
  }

  // Screen 6 (Review) — auto-render every clip the instant this screen is entered.
  useEffect(() => {
    if (step === 6 && !generatedRef.current && !busy && clips.length === 0) {
      generatedRef.current = true;
      generate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  function openReframe(clip) {
    setReframeTarget(clip);
  }
  function closeReframe() { setReframeTarget(null); }
  function onReframeSaved(index, newUrl, keyframes) {
    reframeCache.current[`${clipId}:${index}`] = keyframes;
    setClips((cs) => cs.map((c) => (c.index === index ? { ...c, url: newUrl } : c)));
    setReframeTarget(null);
  }

  function restart() {
    setStep(1);
    setSource("url"); setUrl(""); setUpload(null); setUpPct(null);
    if (objUrl) URL.revokeObjectURL(objUrl);
    setObjUrl(null);
    setClips([]); setSnap(null); setError(""); setClipId(null);
    generatedRef.current = false;
    prep.reset();
  }

  if (reframeTarget) {
    const key = `${clipId}:${reframeTarget.index}`;
    return (
      <ReframeEditor
        clipId={clipId}
        clip={reframeTarget}
        targetAspect={targetAspectNum(aspect, fit)}
        initialKeyframes={reframeCache.current[key]}
        onClose={closeReframe}
        onSaved={onReframeSaved}
      />
    );
  }

  const showStepper = step >= 2 && step <= 7;

  return (
    <>
      {step === 1 && (
        <Screen1Input
          source={source} setSource={setSource} url={url} setUrl={setUrl}
          upload={upload} upPct={upPct} drag={drag} setDrag={setDrag} fileRef={fileRef}
          doUpload={doUpload} onClear={() => doUpload(null)} sourceReady={sourceReady} error={error}
          onContinue={() => { startPrep(); setStep(2); }}
        />
      )}

      {step === 2 && (
        <Screen2Settings
          media={media} sourceReady={sourceReady} prepView={prepView}
          outputAspect={outputAspect} setOutputAspect={setOutputAspect}
          squareCorners={squareCorners} setSquareCorners={setSquareCorners}
          barText={barText} setBarText={setBarText} barTextColor={barTextColor} setBarTextColor={setBarTextColor}
          barTextAnim={barTextAnim} setBarTextAnim={setBarTextAnim}
          language={language} changeLanguage={changeLanguage}
          device={device} setDevice={setDevice} devices={devices}
          numClips={numClips} setNumClips={setNumClips} clipLen={clipLen} setClipLen={setClipLen}
          studio={studio} fonts={fonts} aspect={aspect} fit={fit} signature={signature} setSig={setSig} videoRef={videoRef}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
          nextEnabled={!["downloading", "idle"].includes(prepView.phase)}
        />
      )}

      {step === 3 && (
        <Screen3Captions
          studio={studio} language={language} onFontUpload={onFontUpload}
          media={media} prepView={prepView} sourceReady={sourceReady}
          transcript={transcript} curTime={curTime} seekTo={seekTo} videoRef={videoRef} duration={vidDuration}
          aspect={aspect} fit={fit} barText={barText} signature={signature} setSig={setSig}
          onBack={() => setStep(2)} onNext={() => setStep(4)}
        />
      )}

      {step === 4 && (
        <Screen4Effects
          studio={studio} language={language} media={media} sourceReady={sourceReady}
          aspect={aspect} fit={fit} barText={barText} signature={signature} setSig={setSig} videoRef={videoRef}
          onBack={() => setStep(3)} onNext={() => setStep(5)}
        />
      )}

      {step === 5 && (
        <Screen5Music
          tracks={tracks} musicTrack={musicTrack} musicVolume={musicVolume} musicDuck={musicDuck}
          musicStart={musicStart} musicSuggest={musicSuggest}
          onTrack={(t) => { setMusicTrack(t); setMusicStart(0); }} onVolume={setMusicVolume} onDuck={setMusicDuck} onStart={setMusicStart}
          onMusicUpload={onMusicUpload} onRefreshMusic={refreshMusic}
          studio={studio} language={language} media={media} sourceReady={sourceReady}
          aspect={aspect} fit={fit} barText={barText} signature={signature} setSig={setSig} videoRef={videoRef}
          onBack={() => setStep(4)} onNext={() => setStep(6)}
        />
      )}

      {step === 6 && (
        <Screen6Review
          busy={busy} snap={snap} clips={clips} error={error}
          onCancel={cancelGenerate} onOpenReframe={openReframe}
          onBack={() => setStep(5)} onNext={() => setStep(7)}
        />
      )}

      {step === 7 && (
        <Screen7Export clips={clips} onBack={() => setStep(6)} onRestart={restart} />
      )}

      {showStepper && (
        <div className="wizard-steps wizard-steps-bottom">
          {WIZARD_LABELS.slice(1).map((lbl, i) => {
            const n = i + 2;
            return (
              <button key={lbl} type="button" className={"wizard-step" + (step === n ? " active" : step > n ? " done" : "")}
                onClick={() => setStep(n)} title={`Jump to ${lbl}`}>
                <span className="wizard-step-dot">{step > n ? "✓" : n - 1}</span>
                <span className="wizard-step-lbl">{lbl}</span>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}
