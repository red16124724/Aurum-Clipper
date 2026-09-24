import { useState, useEffect } from "react";
import { LANGS } from "../../caption.js";
import { api } from "../../api.js";
import PhonePreview from "../../components/PhonePreview.jsx";

const ASPECTS = [["9:16", "9:16 Vertical"], ["16:9", "16:9 Landscape"], ["1:1", "1:1 Square"]];

// Screen 2 — Download & Basic Settings. Only three real decisions: aspect
// ratio, processing mode, caption language. 1:1 additionally unlocks the
// title-text bar that sits above the square (captions themselves are a
// Screen 3 concern, not duplicated here). The same phone mockup used on
// every later screen previews the download here too, so the look stays
// consistent across the whole wizard.
const WHISPER_MODELS = [
  { id: "large-v3-turbo", label: "Large V3 Turbo (Recommended, >6GB VRAM / 8GB RAM)" },
  { id: "large-v3", label: "Large V3 (>10GB VRAM / 16GB RAM)" },
  { id: "medium", label: "Medium (>5GB VRAM / 8GB RAM)" },
  { id: "savi0ur/whisper-hindi-hinglish-ct2", label: "Hinglish Apex Turbo (~1.6GB, CTranslate2)" },
  { id: "small", label: "Small (>2GB VRAM / 16GB RAM)" },
  { id: "base", label: "Base (>1GB VRAM / 8GB RAM)" },
];

export default function Screen2Settings({
  media, sourceReady, prepView, outputAspect, setOutputAspect,
  fit, setFit, jumpCut, setJumpCut, autoEffects, setAutoEffects, autoTemplate, setAutoTemplate, hevc, setHevc, useIgpu, setUseIgpu,
  squareCorners, setSquareCorners, barText, setBarText, barTextColor, setBarTextColor,
  barTextAnim, setBarTextAnim, language, changeLanguage, strictLanguage, setStrictLanguage, device, setDevice, devices,
  modelSize, setModelSize, faceZone, setFaceZone,
  numClips, setNumClips, clipLen, setClipLen,
  studio, aspect, signature, setSig, videoRef,
  onBack, onNext, nextEnabled,
}) {
  const isSquare = outputAspect === "1:1";
  const [geminiConfig, setGeminiConfig] = useState({ configured: false, masked_key: null });

  useEffect(() => {
    api.getApiKey().then(setGeminiConfig).catch(() => {});
  }, []);

  return (
    <div className="wizard-screen">
      <div className="w3-grid">
        <div className="card w3-left">
          <div className="card-h">
            <div>
              <h2>Layout &amp; Dynamic Split</h2>
              <span className="hint">Framing, AI face tracking, and split-screen</span>
            </div>
            {fit === "dynamic_split" && (
              <span className="badge ok" style={{ fontSize: "11px", padding: "3px 10px" }}>
                <span className="dot" /> Dynamic Split Active
              </span>
            )}
          </div>

          <label className="fieldlabel">Output aspect ratio</label>
          <div className="toggle">
            {ASPECTS.map(([v, l]) => <button key={v} className={outputAspect === v ? "active" : ""} onClick={() => setOutputAspect(v)}>{l}</button>)}
          </div>

          {outputAspect === "9:16" && (
            <>
               <label className="fieldlabel" style={{marginTop: 14}}>Vertical Framing &amp; Layout Mode</label>
               <div className="toggle" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                 {[
                   ["crop", "Full Crop (Center)"],
                   ["auto_reframe", "Auto Reframe (AI Face)"],
                   ["dynamic_split", "Auto Split View (AI Face)"],
                   ["static_split", "Static Split View (50/50)"]
                 ].map(([m, lbl]) => (
                    <button key={m} type="button" className={fit === m ? "active" : ""} onClick={() => setFit(m)} style={{ padding: "8px 8px", fontSize: "0.82rem", textAlign: "center" }}>
                       {lbl}
                    </button>
                 ))}
               </div>
               {fit === "dynamic_split" && (
                 <div style={{ marginTop: 10, padding: "10px 12px", background: "var(--accent-soft)", borderRadius: "var(--radius-sm)", border: "1px solid var(--accent)", fontSize: "0.84rem", color: "var(--text)" }}>
                   <b>✨ Dynamic Split Screen Active:</b> YuNet AI tracks faces on the top half while the main content displays on the bottom half with zero letterboxing.
                 </div>
               )}
               {fit === "static_split" && (
                 <div style={{ marginTop: 14 }}>
                   <label className="fieldlabel">Facecam Zone (Where is the facecam in the source video?)</label>
                   <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, width: 120, marginTop: 8 }}>
                     {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                       <button
                         key={i}
                         type="button"
                         style={{
                           aspectRatio: "1/1",
                           backgroundColor: faceZone === i ? "var(--accent)" : "var(--surface-3)",
                           border: faceZone === i ? "1px solid var(--accent)" : "1px solid var(--line-2)",
                           borderRadius: 4,
                           cursor: "pointer",
                           padding: 0,
                         }}
                         onClick={() => setFaceZone(i)}
                         title={`Zone ${i}`}
                       />
                     ))}
                   </div>
                 </div>
               )}
            </>
          )}

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

          <div className="options-stack" style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 22, marginBottom: 16 }}>
            <label className={"opt-card" + (jumpCut ? " active" : "")} style={{
              display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
              borderRadius: "var(--radius-sm)", border: "1px solid " + (jumpCut ? "var(--accent)" : "var(--line)"),
              background: jumpCut ? "var(--accent-soft)" : "var(--surface-2)", cursor: "pointer", transition: "all 0.15s"
            }}>
              <input type="checkbox" checked={jumpCut} onChange={(e) => setJumpCut(e.target.checked)} style={{ marginTop: 3, width: 16, height: 16, accentColor: "var(--accent)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                <b style={{ fontSize: "0.95rem", color: "var(--text)" }}>Auto Jump-Cuts (Remove Silence)</b>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.35 }}>Removes dead air to make clips snappier</span>
              </div>
            </label>

            <label className={"opt-card" + (autoEffects ? " active" : "")} style={{
              display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
              borderRadius: "var(--radius-sm)", border: "1px solid " + (autoEffects ? "var(--accent)" : "var(--line)"),
              background: autoEffects ? "var(--accent-soft)" : "var(--surface-2)", cursor: "pointer", transition: "all 0.15s"
            }}>
              <input type="checkbox" checked={autoEffects} onChange={(e) => setAutoEffects(e.target.checked)} style={{ marginTop: 3, width: 16, height: 16, accentColor: "var(--accent)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <b style={{ fontSize: "0.95rem", color: "var(--text)" }}>Auto Sound &amp; VFX (Gemini AI)</b>
                  <span style={{
                    fontSize: "0.72rem", fontWeight: 700, padding: "1px 7px", borderRadius: 999,
                    background: geminiConfig.configured ? "rgba(16, 185, 129, 0.18)" : "rgba(245, 158, 11, 0.18)",
                    color: geminiConfig.configured ? "var(--ok, #10b981)" : "#f59e0b",
                    border: `1px solid ${geminiConfig.configured ? "rgba(16, 185, 129, 0.35)" : "rgba(245, 158, 11, 0.35)"}`
                  }}>
                    {geminiConfig.configured ? "✨ Gemini Pro Active" : "Local Heuristic"}
                  </span>
                </div>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.35 }}>
                  {geminiConfig.configured
                    ? "Gemini AI analyzes transcript context to add sound effects & visual flashes"
                    : "Uses local keyword detection (connect Gemini key in topbar for AI virality scoring)"}
                </span>
              </div>
            </label>

            <label className={"opt-card" + (autoTemplate ? " active" : "")} style={{
              display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
              borderRadius: "var(--radius-sm)", border: "1px solid " + (autoTemplate ? "var(--accent)" : "var(--line)"),
              background: autoTemplate ? "var(--accent-soft)" : "var(--surface-2)", cursor: "pointer", transition: "all 0.15s"
            }}>
              <input type="checkbox" checked={autoTemplate} onChange={(e) => setAutoTemplate(e.target.checked)} style={{ marginTop: 3, width: 16, height: 16, accentColor: "var(--accent)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <b style={{ fontSize: "0.95rem", color: "var(--text)" }}>Auto Trending Template (Gemini AI)</b>
                  <span style={{
                    fontSize: "0.72rem", fontWeight: 700, padding: "1px 7px", borderRadius: 999,
                    background: geminiConfig.configured ? "rgba(16, 185, 129, 0.18)" : "rgba(245, 158, 11, 0.18)",
                    color: geminiConfig.configured ? "var(--ok, #10b981)" : "#f59e0b",
                    border: `1px solid ${geminiConfig.configured ? "rgba(16, 185, 129, 0.35)" : "rgba(245, 158, 11, 0.35)"}`
                  }}>
                    {geminiConfig.configured ? "✨ Gemini Pro Active" : "Local Heuristic"}
                  </span>
                </div>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.35 }}>
                  {geminiConfig.configured
                    ? "Gemini-3.8-Flash automatically picks the best cinematic style and editing vibe"
                    : "Uses local rules (connect Gemini key for AI style matching)"}
                </span>
              </div>
            </label>

            <label className={"opt-card" + (hevc ? " active" : "")} style={{
              display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
              borderRadius: "var(--radius-sm)", border: "1px solid " + (hevc ? "var(--accent)" : "var(--line)"),
              background: hevc ? "var(--accent-soft)" : "var(--surface-2)", cursor: "pointer", transition: "all 0.15s"
            }}>
              <input type="checkbox" checked={hevc} onChange={(e) => setHevc(e.target.checked)} style={{ marginTop: 3, width: 16, height: 16, accentColor: "var(--accent)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                <b style={{ fontSize: "0.95rem", color: "var(--text)" }}>Use H.265 (HEVC) Encoding</b>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.35 }}>Smaller file sizes, high quality (GPU accelerated)</span>
              </div>
            </label>

            <label className={"opt-card" + (useIgpu ? " active" : "")} style={{
              display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px",
              borderRadius: "var(--radius-sm)", border: "1px solid " + (useIgpu ? "var(--accent)" : "var(--line)"),
              background: useIgpu ? "var(--accent-soft)" : "var(--surface-2)", cursor: "pointer", transition: "all 0.15s"
            }}>
              <input type="checkbox" checked={useIgpu} onChange={(e) => setUseIgpu(e.target.checked)} style={{ marginTop: 3, width: 16, height: 16, accentColor: "var(--accent)" }} />
              <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                <b style={{ fontSize: "0.95rem", color: "var(--text)" }}>Force Integrated GPU (iGPU)</b>
                <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.35 }}>Prioritizes Intel QSV over dGPU (NVENC/AMF)</span>
              </div>
            </label>
          </div>

          <div className="row" style={{ gap: 16, marginTop: 14, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label className="fieldlabel">Processing mode</label>
              <select value={device} onChange={(e) => setDevice(e.target.value)}>
                {["auto", ...devices.filter((d) => d !== "auto")].filter((v, i, a) => a.indexOf(v) === i).map((d) => <option key={d} value={d}>{d === "cuda" ? "GPU (CUDA)" : d.toUpperCase()}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label className="fieldlabel">Whisper AI Model</label>
              <select value={modelSize} onChange={(e) => setModelSize(e.target.value)}>
                {WHISPER_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label className="fieldlabel">Caption language</label>
              <select value={language} onChange={(e) => changeLanguage(e.target.value)}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              {language !== "auto" && (
                <label style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 10, cursor: "pointer" }}>
                  <input type="checkbox" checked={strictLanguage} onChange={(e) => setStrictLanguage(e.target.checked)} style={{ marginTop: 2, accentColor: "var(--accent)" }} />
                  <span style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.3 }}>Only show {LANGS.find(l => l[0] === language)?.[1] || "this language"} (Drops other languages)</span>
                </label>
              )}
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
