import { useRef } from "react";

function fmt(t) {
  if (t == null || !isFinite(t)) return "0:00";
  t = Math.max(0, t);
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Bottom timeline bar — a visual reference for the source video's duration:
// scrub to move the canvas playhead, and once clips are chosen/rendered their
// time ranges appear as markers. Clip selection itself stays automatic.
export default function Timeline({ duration, currentTime, onSeek, clips }) {
  const trackRef = useRef(null);
  const ready = duration != null && isFinite(duration) && duration > 0;

  function seekFromEvent(e) {
    if (!ready || !trackRef.current) return;
    const r = trackRef.current.getBoundingClientRect();
    const p = e.touches ? e.touches[0] : e;
    const frac = Math.max(0, Math.min(1, (p.clientX - r.left) / r.width));
    onSeek(frac * duration);
  }

  function onDown(e) {
    e.preventDefault();
    seekFromEvent(e);
    const move = (ev) => seekFromEvent(ev);
    const up = () => {
      document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up);
      document.removeEventListener("touchmove", move); document.removeEventListener("touchend", up);
    };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
    document.addEventListener("touchmove", move); document.addEventListener("touchend", up);
  }

  const pct = ready ? Math.max(0, Math.min(100, (currentTime / duration) * 100)) : 0;

  return (
    <div className="timeline">
      <div className="timeline-head">
        <span className="timeline-time">{fmt(currentTime)}</span>
        <span className="timeline-total">{ready ? fmt(duration) : "--:--"}</span>
      </div>
      <div
        ref={trackRef}
        className={"timeline-track" + (ready ? "" : " disabled")}
        onMouseDown={ready ? onDown : undefined}
        onTouchStart={ready ? onDown : undefined}
      >
        <div className="timeline-base" />
        {ready && (clips || []).map((c) => (
          <div
            key={c.index ?? c.url ?? `${c.start}-${c.end}`}
            className="timeline-clip"
            style={{ left: (c.start / duration) * 100 + "%", width: Math.max(0.6, ((c.end - c.start) / duration) * 100) + "%" }}
            title={c.title}
          />
        ))}
        {ready && <div className="timeline-playhead" style={{ left: pct + "%" }} />}
        {!ready && <span className="timeline-empty">Timeline appears once your video loads</span>}
      </div>
    </div>
  );
}
