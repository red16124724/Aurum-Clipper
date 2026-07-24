import { Icons } from "../../components/Icons.jsx";
import ClipPhone from "../../components/ClipPhone.jsx";

const STEPS = [["downloading", "Download"], ["transcribing", "Transcribe"], ["selecting", "Analyze"], ["rendering", "Render"]];

// Screen 5 — Clip Rendering & Review. Auto-renders every clip on entry (no
// export yet); each rendered clip shows exactly two actions — Download and
// Reframe — so reviewers can fix a bad crop before moving on to Export.
export default function Screen5Review({ busy, snap, clips, error, onCancel, onOpenReframe, onBack, onNext }) {
  const curStep = STEPS.findIndex(([k]) => k === snap?.stage);
  const done = snap?.status === "done";
  const pct = Math.round((snap?.progress || 0) * 100);

  return (
    <div className="wizard-screen">
      <div className="card">
        <div className="card-h"><h2>Rendering your clips</h2><span className="hint">{clips.length} ready</span></div>

        {busy && (
          <button className="btn btn-cancel" style={{ marginBottom: 14 }} onClick={onCancel}>Cancel</button>
        )}
        {error && <div className="error">{error}</div>}

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
                  <div className="acts">
                    <a href={c.url} download={c.filename || ""}>Download</a>
                    <button onClick={() => onOpenReframe(c)}><Icons.crop /> Reframe</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack} disabled={busy}>← Back to effects</button>
        <button className="btn btn-primary" disabled={!done || !clips.length} onClick={onNext}>Continue to export →</button>
      </div>
    </div>
  );
}
