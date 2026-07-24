import { LANGS } from "../../caption.js";
import PhonePreview from "../../components/PhonePreview.jsx";

const ASPECTS = [["9:16", "9:16 Vertical"], ["16:9", "16:9 Landscape"], ["1:1", "1:1 Square"]];

// Screen 2 — Download & Basic Settings. Only three real decisions: aspect
// ratio, processing mode, caption language. 1:1 additionally unlocks the
// title-text bar that sits above the square (captions themselves are a
// Screen 3 concern, not duplicated here). The same phone mockup used on
// every later screen previews the download here too, so the look stays
// consistent across the whole wizard.
export default function Screen2Settings({
  media, sourceReady, prepView, outputAspect, setOutputAspect,
  squareCorners, setSquareCorners, barText, setBarText, barTextColor, setBarTextColor,
  barTextAnim, setBarTextAnim, language, changeLanguage, device, setDevice, devices,
  numClips, setNumClips, clipLen, setClipLen,
  studio, aspect, fit, signature, setSig, videoRef,
  onBack, onNext, nextEnabled,
}) {
  const isSquare = outputAspect === "1:1";

  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="card w3-left">
          <div className="card-h"><h2>Basic settings</h2></div>

          <label className="fieldlabel">Output aspect ratio</label>
          <div className="toggle">
            {ASPECTS.map(([v, l]) => <button key={v} className={outputAspect === v ? "active" : ""} onClick={() => setOutputAspect(v)}>{l}</button>)}
          </div>

          {isSquare && (
            <>
              <label className="fieldlabel">Corners</label>
              <div className="toggle">
                {["round", "square"].map((c) => <button key={c} className={squareCorners === c ? "active" : ""} onClick={() => setSquareCorners(c)}>{c[0].toUpperCase() + c.slice(1)}</button>)}
              </div>

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
            </>
          )}

          <div className="row" style={{ gap: 16, marginTop: 14, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label className="fieldlabel">Processing mode</label>
              <select value={device} onChange={(e) => setDevice(e.target.value)}>
                {["auto", ...devices.filter((d) => d !== "auto")].filter((v, i, a) => a.indexOf(v) === i).map((d) => <option key={d} value={d}>{d === "cuda" ? "GPU (CUDA)" : d.toUpperCase()}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label className="fieldlabel">Caption language</label>
              <select value={language} onChange={(e) => changeLanguage(e.target.value)}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            </div>
          </div>

          <details className="w2-advanced">
            <summary>Advanced — number &amp; length of clips (optional, auto by default)</summary>
            <div className="row" style={{ gap: 16, marginTop: 14, flexWrap: "wrap" }}>
              <div><label className="fieldlabel">Clips</label>
                <div className="counter">
                  <button onClick={() => setNumClips((n) => Math.max(1, n - 1))}>−</button>
                  <input type="number" min="1" max="100" value={numClips} onChange={(e) => setNumClips(Math.max(1, Math.min(100, +e.target.value || 1)))} />
                  <button onClick={() => setNumClips((n) => Math.min(100, n + 1))}>+</button>
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 220 }}>
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
          </details>
        </div>

        <div className="w3-right">
          <PhonePreview cfg={studio.cfg} cinematic={studio.cinematic} language={language} media={media}
            preparing={!media && sourceReady} aspect={aspect} fit={fit} barText={barText}
            barTextColor={barTextColor} barTextAnim={barTextAnim}
            signature={signature} setSig={setSig} videoRef={videoRef}
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
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back</button>
        <button className="btn btn-primary" disabled={!nextEnabled} onClick={onNext}>Next →</button>
      </div>
    </div>
  );
}
