import { useRef, useEffect, useState, useMemo } from "react";

function fmt(t) {
  if (t == null || !isFinite(t)) return "0:00";
  t = Math.max(0, t);
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function fmtMs(t) {
  if (t == null || !isFinite(t)) return "00:00.00";
  t = Math.max(0, t);
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const ms = Math.floor((t % 1) * 100);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms).padStart(2, "0")}`;
}

export default function Timeline({ duration, currentTime, onSeek, clips, videoRef, isPlaying, onTogglePlay }) {
  const trackRef = useRef(null);
  const ready = duration != null && isFinite(duration) && duration > 0;
  const [playingState, setPlayingState] = useState(false);

  // Sync play state from videoRef if provided
  useEffect(() => {
    const v = videoRef?.current;
    if (!v) return;
    const onPlay = () => setPlayingState(true);
    const onPause = () => setPlayingState(false);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    setPlayingState(!v.paused);
    return () => {
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
    };
  }, [videoRef]);

  const activePlaying = isPlaying !== undefined ? isPlaying : playingState;

  function togglePlay() {
    if (onTogglePlay) {
      onTogglePlay();
      return;
    }
    const v = videoRef?.current;
    if (v) {
      if (v.paused) v.play().catch(() => {});
      else v.pause();
    }
  }

  function skip(delta) {
    if (!ready) return;
    const target = Math.max(0, Math.min(duration, (currentTime || 0) + delta));
    if (onSeek) onSeek(target);
    const v = videoRef?.current;
    if (v) v.currentTime = target;
  }

  const dragCleanup = useRef(null);
  useEffect(() => { return () => { if (dragCleanup.current) dragCleanup.current(); }; }, []);

  function seekFromEvent(e) {
    if (!ready || !trackRef.current) return;
    const r = trackRef.current.getBoundingClientRect();
    const p = e.touches ? e.touches[0] : e;
    const frac = Math.max(0, Math.min(1, (p.clientX - r.left) / r.width));
    const target = frac * duration;
    if (onSeek) onSeek(target);
    const v = videoRef?.current;
    if (v) {
      try { v.currentTime = target; } catch { /* not seekable */ }
    }
  }

  function onDown(e) {
    e.preventDefault();
    seekFromEvent(e);
    const move = (ev) => seekFromEvent(ev);
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.removeEventListener("touchmove", move);
      document.removeEventListener("touchend", up);
      dragCleanup.current = null;
    };
    dragCleanup.current = up;
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    document.addEventListener("touchmove", move, { passive: false });
    document.addEventListener("touchend", up);
  }

  const pct = ready ? Math.max(0, Math.min(100, ((currentTime || 0) / duration) * 100)) : 0;

  // Generate pseudo-waveform bars for the audio track
  const waveformBars = useMemo(() => {
    const bars = [];
    const count = 48;
    for (let i = 0; i < count; i++) {
      // Deterministic decorative heights between 4px and 22px
      const h = Math.round(6 + Math.abs(Math.sin(i * 0.45) * 12 + Math.cos(i * 0.8) * 6));
      bars.push(Math.min(22, Math.max(4, h)));
    }
    return bars;
  }, []);

  return (
    <div className="timeline">
      {/* Apple Studio Transport Controls Bar */}
      <div className="timeline-transport">
        <div className="timeline-transport-btns">
          <button
            type="button"
            className="timeline-btn"
            title="Rewind 5s"
            onClick={() => skip(-5)}
            disabled={!ready}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M11 5l-7 7 7 7V5zm8 0l-7 7 7 7V5z" />
            </svg>
          </button>

          <button
            type="button"
            className="timeline-btn-play"
            title={activePlaying ? "Pause" : "Play"}
            onClick={togglePlay}
            disabled={!ready}
          >
            {activePlaying ? (
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <rect x="6" y="5" width="4" height="14" rx="1.5" />
                <rect x="14" y="5" width="4" height="14" rx="1.5" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          <button
            type="button"
            className="timeline-btn"
            title="Forward 5s"
            onClick={() => skip(5)}
            disabled={!ready}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M5 5l7 7-7 7V5zm8 0l7 7-7 7V5z" />
            </svg>
          </button>
        </div>

        <div className="timeline-timecode">
          <b>{fmt(currentTime || 0)}</b>
          <span>/</span>
          <span>{ready ? fmt(duration) : "--:--"}</span>
        </div>
      </div>

      {/* Dual Tracks Area (Video + Audio) */}
      <div
        ref={trackRef}
        className={"timeline-tracks-area" + (ready ? "" : " disabled")}
        onMouseDown={ready ? onDown : undefined}
        onTouchStart={ready ? onDown : undefined}
      >
        {/* Track 1: Video */}
        <div className="timeline-track-row timeline-track-video">
          {ready && (clips && clips.length > 0 ? (
            clips.map((c, i) => {
              const left = (c.start / duration) * 100;
              const width = Math.max(0.8, ((c.end - c.start) / duration) * 100);
              const durSec = (c.end - c.start).toFixed(0);
              return (
                <div
                  key={c.index ?? c.url ?? `${c.start}-${c.end}-${i}`}
                  className="timeline-clip-block"
                  style={{ left: `${left}%`, width: `${width}%` }}
                  title={c.title || `Clip ${i + 1}`}
                >
                  <span className="tc-title">{c.title || `Clip ${i + 1}`}</span>
                  <span className="tc-dur">{durSec}s</span>
                </div>
              );
            })
          ) : (
            <div
              className="timeline-clip-block"
              style={{ left: "0%", width: "100%" }}
            >
              <span className="tc-title">Video Stream</span>
              <span className="tc-dur">{ready ? fmt(duration) : "--:--"}</span>
            </div>
          ))}
        </div>

        {/* Track 2: Audio Waveform */}
        <div className="timeline-track-row timeline-track-audio">
          <div className="timeline-audio-content">
            <span style={{ zIndex: 1, textShadow: "0 1px 2px rgba(0,0,0,0.5)" }}>Ambient Audio</span>
            <span className="timeline-audio-badge" style={{ zIndex: 1 }}>{ready ? fmt(duration) : "--:--"}</span>
          </div>
          <div className="timeline-audio-waveform">
            {waveformBars.map((h, i) => (
              <div
                key={i}
                className="timeline-waveform-bar"
                style={{ height: `${h}px` }}
              />
            ))}
          </div>
        </div>

        {/* Playhead with Time Bubble and Diamond Anchor */}
        {ready && (
          <div className="timeline-playhead-line" style={{ left: `${pct}%` }}>
            <div className="timeline-playhead-bubble">{fmtMs(currentTime || 0)}</div>
            <div className="timeline-playhead-anchor" />
          </div>
        )}

        {!ready && (
          <div style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center",
            justifyContent: "center", color: "var(--muted-2)", fontSize: "12px"
          }}>
            Timeline appears once your video loads
          </div>
        )}
      </div>
    </div>
  );
}

