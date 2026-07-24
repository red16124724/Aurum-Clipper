import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { Icons } from "./Icons.jsx";

// Linear interpolation between the two keyframes bracketing t — mirrors the
// backend's ffmpeg crop-x/y/zoom expressions (app/clipper.py::_crop_filter)
// exactly, so the live preview here matches the eventual render.
function interpAt(keyframes, t) {
  const norm = (k) => ({ pos_x: k.pos_x, pos_y: k.pos_y, zoom: k.zoom ?? 100 });
  if (!keyframes.length) return { pos_x: 50, pos_y: 50, zoom: 100 };
  const pts = [...keyframes].sort((a, b) => a.time - b.time);
  if (t <= pts[0].time) return norm(pts[0]);
  const last = pts[pts.length - 1];
  if (t >= last.time) return norm(last);
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (t >= a.time && t <= b.time) {
      const f = b.time > a.time ? (t - a.time) / (b.time - a.time) : 0;
      const az = a.zoom ?? 100, bz = b.zoom ?? 100;
      return { pos_x: a.pos_x + (b.pos_x - a.pos_x) * f, pos_y: a.pos_y + (b.pos_y - a.pos_y) * f, zoom: az + (bz - az) * f };
    }
  }
  return norm(last);
}

function upsertKeyframe(keyframes, time, pos) {
  const EPS = 0.05;
  const idx = keyframes.findIndex((k) => Math.abs(k.time - time) < EPS);
  const kf = {
    time: Math.max(0, +time.toFixed(2)),
    pos_x: Math.round(pos.pos_x * 10) / 10,
    pos_y: Math.round(pos.pos_y * 10) / 10,
    zoom: Math.round(Math.max(40, Math.min(100, pos.zoom ?? 100)) * 10) / 10,
  };
  const next = idx >= 0 ? keyframes.map((k, i) => (i === idx ? kf : k)) : [...keyframes, kf];
  return next.sort((a, b) => a.time - b.time);
}

const fmt = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;

// Reframe Editor — opens the clip's original (uncropped) source segment in a
// dedicated timeline so the crop position AND size can be manually keyframed.
// Saving re-renders this ONE clip immediately (per the confirmed workflow
// choice); interpolation between points is smooth/linear (also confirmed),
// not a discrete jump.
export default function ReframeEditor({ clipId, clip, targetAspect, initialKeyframes, onClose, onSaved }) {
  const videoRef = useRef(null);
  const [keyframes, setKeyframes] = useState(
    initialKeyframes && initialKeyframes.length ? initialKeyframes : [{ time: 0, pos_x: 50, pos_y: 50, zoom: 100 }]
  );
  const [curTime, setCurTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [natural, setNatural] = useState(null); // { w, h } of the source video
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const dragRef = useRef(null);
  const resizeRef = useRef(null);
  const stageRef = useRef(null);

  const duration = Math.max(0.1, clip.end - clip.start);
  const srcUrl = api.clipSourceUrl(clipId, clip.index);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    const onMeta = () => { setNatural({ w: v.videoWidth, h: v.videoHeight }); v.currentTime = clip.start; };
    const onTime = () => {
      let rel = v.currentTime - clip.start;
      if (rel >= duration) { v.pause(); setPlaying(false); rel = duration; v.currentTime = clip.start + duration; }
      if (rel < 0) rel = 0;
      setCurTime(rel);
    };
    const onPause = () => setPlaying(false);
    v.addEventListener("loadedmetadata", onMeta);
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("pause", onPause);
    if (v.readyState >= 1) onMeta();
    return () => { v.removeEventListener("loadedmetadata", onMeta); v.removeEventListener("timeupdate", onTime); v.removeEventListener("pause", onPause); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipId, clip.index]);

  function seek(rel) {
    const clamped = Math.max(0, Math.min(duration, rel));
    setCurTime(clamped);
    const v = videoRef.current;
    if (v) { try { v.currentTime = clip.start + clamped; } catch { /* not seekable yet */ } }
  }

  function togglePlay() {
    const v = videoRef.current;
    if (!v) return;
    if (playing) { v.pause(); setPlaying(false); }
    else { if (curTime >= duration - 0.05) seek(0); v.play(); setPlaying(true); }
  }

  const current = useMemo(() => interpAt(keyframes, curTime), [keyframes, curTime]);

  // Crop-box geometry, mirroring ffmpeg's scale(force_original_aspect_ratio
  // =increase) + fractional crop: the base box covers one full axis; zoom
  // then shrinks BOTH axes by the same factor (a tighter, more zoomed-in
  // crop), and pan slides that (possibly shrunk) box across the leftover span.
  const box = useMemo(() => {
    if (!natural || !natural.w || !natural.h) return null;
    const videoAspect = natural.w / natural.h;
    const zoomFrac = Math.max(0.4, Math.min(1, (current.zoom ?? 100) / 100));
    let baseW, baseH;
    if (targetAspect < videoAspect) { baseW = (targetAspect / videoAspect) * 100; baseH = 100; }
    else { baseW = 100; baseH = (videoAspect / targetAspect) * 100; }
    const width = baseW * zoomFrac, height = baseH * zoomFrac;
    const spanX = 100 - width, spanY = 100 - height;
    const left = spanX > 0.01 ? (current.pos_x / 100) * spanX : (100 - width) / 2;
    const top = spanY > 0.01 ? (current.pos_y / 100) * spanY : (100 - height) / 2;
    return { left, top, width, height };
  }, [natural, targetAspect, current]);

  function onBoxPointerDown(e) {
    if (!box || !stageRef.current) return;
    e.preventDefault();
    const rect = stageRef.current.getBoundingClientRect();
    dragRef.current = { rect, box, zoom: current.zoom ?? 100, startX: e.clientX, startY: e.clientY };
    window.addEventListener("pointermove", onBoxPointerMove);
    window.addEventListener("pointerup", onBoxPointerUp);
  }
  function onBoxPointerMove(e) {
    const d = dragRef.current;
    if (!d) return;
    const dxPct = ((e.clientX - d.startX) / d.rect.width) * 100;
    const dyPct = ((e.clientY - d.startY) / d.rect.height) * 100;
    const spanX = 100 - d.box.width, spanY = 100 - d.box.height;
    const newLeft = Math.max(0, Math.min(spanX, d.box.left + dxPct));
    const newTop = Math.max(0, Math.min(spanY, d.box.top + dyPct));
    const pos_x = spanX > 0.01 ? (newLeft / spanX) * 100 : 50;
    const pos_y = spanY > 0.01 ? (newTop / spanY) * 100 : 50;
    setKeyframes((kfs) => upsertKeyframe(kfs, curTime, { pos_x, pos_y, zoom: d.zoom }));
  }
  function onBoxPointerUp() {
    dragRef.current = null;
    window.removeEventListener("pointermove", onBoxPointerMove);
    window.removeEventListener("pointerup", onBoxPointerUp);
  }

  // Corner handles resize the box (zoom) around its OWN centre — dragging
  // outward enlarges it (zoom -> 100, less tight); dragging inward shrinks it
  // (zoom -> 40, more zoomed-in). Position (pos_x/pos_y) stays untouched.
  function onCornerPointerDown(e) {
    if (!box || !stageRef.current) return;
    e.preventDefault(); e.stopPropagation();
    const rect = stageRef.current.getBoundingClientRect();
    const centerX = rect.left + ((box.left + box.width / 2) / 100) * rect.width;
    const centerY = rect.top + ((box.top + box.height / 2) / 100) * rect.height;
    const startDist = Math.max(1, Math.hypot(e.clientX - centerX, e.clientY - centerY));
    resizeRef.current = {
      centerX, centerY, startDist,
      startZoom: current.zoom ?? 100, pos_x: current.pos_x, pos_y: current.pos_y,
    };
    window.addEventListener("pointermove", onCornerPointerMove);
    window.addEventListener("pointerup", onCornerPointerUp);
  }
  function onCornerPointerMove(e) {
    const d = resizeRef.current;
    if (!d) return;
    const dist = Math.hypot(e.clientX - d.centerX, e.clientY - d.centerY);
    const zoom = Math.max(40, Math.min(100, d.startZoom * (dist / d.startDist)));
    setKeyframes((kfs) => upsertKeyframe(kfs, curTime, { pos_x: d.pos_x, pos_y: d.pos_y, zoom }));
  }
  function onCornerPointerUp() {
    resizeRef.current = null;
    window.removeEventListener("pointermove", onCornerPointerMove);
    window.removeEventListener("pointerup", onCornerPointerUp);
  }

  useEffect(() => () => {
    window.removeEventListener("pointermove", onBoxPointerMove);
    window.removeEventListener("pointerup", onBoxPointerUp);
    window.removeEventListener("pointermove", onCornerPointerMove);
    window.removeEventListener("pointerup", onCornerPointerUp);
  }, []);

  function addKeyframeHere() { setKeyframes((kfs) => upsertKeyframe(kfs, curTime, current)); }
  function removeKeyframe(time) { setKeyframes((kfs) => (kfs.length > 1 ? kfs.filter((k) => Math.abs(k.time - time) > 0.001) : kfs)); }

  async function save() {
    setSaving(true); setError("");
    try {
      const res = await api.reframeClip(clipId, clip.index, keyframes);
      onSaved(clip.index, res.url, keyframes);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }

  const onKeyframe = keyframes.some((k) => Math.abs(k.time - curTime) < 0.05);

  return (
    <div className="reframe-editor">
      <div className="reframe-head">
        <h2><Icons.crop /> Reframe — {clip.title}</h2>
        <button className="btn btn-ghost" onClick={onClose}>← Back to review</button>
      </div>

      <div className="reframe-body">
        <div className="reframe-stage-wrap">
          <div className="reframe-stage" ref={stageRef} style={{ aspectRatio: natural ? `${natural.w} / ${natural.h}` : "16 / 9" }}>
            <video ref={videoRef} src={srcUrl} playsInline preload="metadata" />
            {box && (
              <div className="reframe-box" style={{ left: box.left + "%", top: box.top + "%", width: box.width + "%", height: box.height + "%" }}
                onPointerDown={onBoxPointerDown}>
                <span className="reframe-box-corner tl" onPointerDown={onCornerPointerDown} />
                <span className="reframe-box-corner tr" onPointerDown={onCornerPointerDown} />
                <span className="reframe-box-corner bl" onPointerDown={onCornerPointerDown} />
                <span className="reframe-box-corner br" onPointerDown={onCornerPointerDown} />
              </div>
            )}
            {!natural && <div className="w2-preview-empty">Loading source…</div>}
          </div>

          <div className="reframe-controls">
            <button className="btn btn-ghost" onClick={togglePlay}>{playing ? "Pause" : "Play"}</button>
            <input type="range" className="range" min={0} max={duration} step={0.05} value={curTime} onChange={(e) => seek(+e.target.value)} />
            <span className="reframe-time">{fmt(curTime)} / {fmt(duration)}</span>
          </div>

          <div className="reframe-timeline">
            {keyframes.map((k) => (
              <button key={k.time} className={"reframe-kf" + (Math.abs(k.time - curTime) < 0.05 ? " active" : "")}
                style={{ left: (k.time / duration) * 100 + "%" }}
                title={`Keyframe @ ${fmt(k.time)} — click to jump`}
                onClick={() => seek(k.time)} />
            ))}
            <div className="reframe-timeline-track" onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              seek(((e.clientX - r.left) / r.width) * duration);
            }} />
          </div>

          <div className="row" style={{ gap: 10, marginTop: 10 }}>
            <button className="btn btn-ghost" onClick={addKeyframeHere} disabled={onKeyframe}>+ Keyframe here</button>
            <button className="btn btn-ghost" onClick={() => removeKeyframe(curTime)} disabled={!onKeyframe || keyframes.length <= 1}>Delete this keyframe</button>
          </div>
          <div className="note">
            Drag the crop box to move it, or its corner handles to resize (zoom in/out) — both add/update a keyframe
            at the current time. Position and size both pan/zoom smoothly between keyframes.
          </div>
        </div>

        <aside className="reframe-sidebar card">
          <div className="card-h"><h2>Keyframes</h2></div>
          {keyframes.map((k, i) => (
            <div key={i} className="reframe-kf-row" onClick={() => seek(k.time)}>
              <span>{fmt(k.time)}</span>
              <span className="hint">x {Math.round(k.pos_x)}% · y {Math.round(k.pos_y)}% · {Math.round(k.zoom ?? 100)}%</span>
            </div>
          ))}
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary btn-block" style={{ marginTop: 16 }} onClick={save} disabled={saving}>
            {saving ? "Saving & re-rendering…" : "Save & re-render this clip"}
          </button>
        </aside>
      </div>
    </div>
  );
}
