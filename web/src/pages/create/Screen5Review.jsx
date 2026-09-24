import { Icons } from "../../components/Icons.jsx";
import ClipPhone from "../../components/ClipPhone.jsx";
import { api, downloadClipBlob } from "../../api.js";

const STEPS = [["downloading", "Download"], ["transcribing", "Transcribe"], ["selecting", "Analyze"], ["rendering", "Render"]];

// Screen 5 — Clip Rendering & Review. Auto-renders every clip on entry (no
// export yet); each rendered clip shows exactly two actions — Download and
// Reframe — so reviewers can fix a bad crop before moving on to Export.
export default function Screen5Review({ busy, snap, clips, error, onCancel, onOpenReframe, onRetry, onBack, onNext }) {
  const curStep = STEPS.findIndex(([k]) => k === snap?.stage);
  const done = snap?.status === "done";
  const pct = Math.round((snap?.progress || 0) * 100);

  function handleReveal(c) {
    const ref = (c.url || "").match(/\/clips\/([0-9a-f]{32})\/(\d+)\.mp4/);
    if (ref) {
      api.reveal(ref[1], +ref[2]).catch(() => {});
    }
  }

  return (
    <div className="wizard-screen">
      <div className="card">
        <div className="card-h"><h2>Rendering your clips</h2><span className="hint">{clips.length} ready</span></div>

        {busy && (
          <button className="btn btn-cancel" style={{ marginBottom: 14 }} onClick={onCancel}>Cancel</button>
        )}
        {error && (
          <div className="error" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
            <span>{error}</span>
            {onRetry && !busy && (
              <button type="button" className="btn btn-primary" style={{ padding: "6px 14px", fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 }} onClick={onRetry}>
                <Icons.refresh /> Retry Generation
              </button>
            )}
          </div>
        )}

        {snap && (
          <div className="cc-progress" style={{ padding: 0 }}>
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

      {clips.length > 0 && (
        <div className="card">
          <div className="clips">
            {clips.map((c) => (
              <div className="clip" key={c.index}>
                <ClipPhone src={c.url} filename={c.filename} />
                <div className="meta">
                  <h3>{c.title}</h3>
                  <div className="sub">{(c.end - c.start).toFixed(1)}s · {c.start.toFixed(1)}–{c.end.toFixed(1)}s</div>
                  <div className="acts" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  <button type="button" className="btn btn-primary" style={{ padding: "7px 10px", fontSize: "0.82rem" }} onClick={() => downloadClipBlob(c.url, c.filename)}>
                    <Icons.download /> Download
                  </button>
                  <button type="button" className="btn" style={{ padding: "7px 10px", fontSize: "0.82rem" }} onClick={() => onOpenReframe(c)}>
                    <Icons.crop /> Reframe
                  </button>
                  <button type="button" className="btn btn-ghost" style={{ gridColumn: "1 / -1", padding: "6px 10px", fontSize: "0.78rem" }} onClick={() => handleReveal(c)}>
                    <Icons.film /> Show in Folder
                  </button>
                </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack} disabled={busy}>← Back to music</button>
        <button className="btn btn-primary" disabled={busy || !clips.length} onClick={onNext}>Continue to export →</button>
      </div>
    </div>
  );
}
