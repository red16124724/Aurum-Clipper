function fmt(t) {
  if (t == null || !isFinite(t)) return "0:00";
  t = Math.max(0, t);
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Left-rail "Transcript" tab — read-only reference list of what Whisper heard,
// shown once pre-transcription finishes. Clicking a row seeks the canvas preview.
export default function Transcript({ state, onSeek, currentTime }) {
  if (state.loading && !state.ready) {
    return <div className="transcript-empty"><span className="spinner" /> Transcribing…</div>;
  }
  if (!state.ready) {
    return <div className="transcript-empty">Transcript will appear here once your video is processed.</div>;
  }
  if (!state.segments.length) {
    return <div className="transcript-empty">No speech detected.</div>;
  }
  return (
    <div className="transcript-list">
      {state.segments.map((seg) => {
        const active = currentTime != null && currentTime >= seg.start && currentTime < seg.end;
        return (
          <button
            key={seg.id}
            className={"transcript-row" + (active ? " active" : "")}
            onClick={() => onSeek(seg.start)}
            title={`${fmt(seg.start)} – ${fmt(seg.end)}`}
          >
            <span className="transcript-ts">{fmt(seg.start)}</span>
            <span className="transcript-text">{(seg.text || "").trim()}</span>
          </button>
        );
      })}
    </div>
  );
}
