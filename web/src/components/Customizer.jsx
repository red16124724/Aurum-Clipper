import { useRef, useState } from "react";
import { toggleOn, captionLineStyle } from "../caption.js";
import { Icons } from "./Icons.jsx";

/* ---- small reusable controls (used in the Advanced section) ---- */
function Slider({ label, unit, min, max, step = 1, value, onChange }) {
  const clamp = (v) => Math.max(min, Math.min(max, v));
  return (
    <div className="ctl">
      <label>{label}
        <span className="val">
          <input type="number" className="val-num" min={min} max={max} step={step} value={Math.round(value)}
            onChange={(e) => onChange(e.target.value === "" ? value : clamp(parseFloat(e.target.value) || 0))} />
          {unit}
        </span>
      </label>
      <input type="range" className="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
    </div>
  );
}
function Swatch({ label, value, def, onChange }) {
  return (
    <label className="swatch">{label}
      <input type="color" value={value || def} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
function FxRow({ label, on, onToggle, children }) {
  return (
    <div className="fxrow">
      <button type="button" className={"tg fxtoggle" + (on ? " active" : "")} onClick={onToggle}>{label}</button>
      {on && <div className="fxbody">{children}</div>}
    </div>
  );
}

/* Quick visual themes — each applies a bundle of overrides at once. */
const THEMES = [
  { id: "classic", label: "Classic", color: "#FFFFFF", font: "Roboto",
    ov: { font_family: "Roboto", primary_color: "#FFFFFF", highlight_color: "#FFD400", animation: "none", karaoke: false, bold: true, uppercase: true, glow_enabled: false } },
  { id: "clean", label: "Clean", color: "#D8D8E6", font: "Poppins",
    ov: { font_family: "Poppins", primary_color: "#FFFFFF", highlight_color: "#FFFFFF", animation: "none", karaoke: false, bold: false, uppercase: false, glow_enabled: false } },
  { id: "bold", label: "Bold", color: "#B39DFF", font: "Montserrat",
    ov: { font_family: "Montserrat", primary_color: "#FFFFFF", highlight_color: "#7C4DFF", animation: "highlight", karaoke: false, bold: true, uppercase: true, glow_enabled: false } },
  { id: "neon", label: "Neon", color: "#22D3EE", font: "Poppins",
    ov: { font_family: "Poppins", primary_color: "#FFFFFF", highlight_color: "#22D3EE", animation: "highlight", karaoke: false, bold: true, uppercase: true, glow_enabled: true, glow_color: "#22D3EE", glow_intensity: 12 } },
  { id: "typewriter", label: "Typewriter", color: "#27E36B", font: "JetBrains Mono",
    ov: { font_family: "JetBrains Mono", primary_color: "#27E36B", highlight_color: "#27E36B", animation: "word_reveal", karaoke: false, bold: false, uppercase: false, glow_enabled: false } },
];

// Curated, professional caption-highlight palette (creator/Hormozi-grade).
const HCOLORS = [
  "#FFFFFF", "#FFD400", "#FFB020", "#FF3B30", "#FF2D78",
  "#27E36B", "#22D3EE", "#3B82F6", "#7C4DFF", "#000000",
];

const ANIMS = [
  { v: "none", label: "None" },
  { v: "highlight", label: "Highlight" },
  { v: "word_reveal", label: "Reveal" },
  { v: "one_word", label: "One word" },
  { v: "karaoke", label: "Karaoke" },
];

// 3×3 anchor grid → [x%, y%]
const POS = [[8, 14], [50, 14], [92, 14], [8, 50], [50, 50], [92, 50], [8, 88], [50, 88], [92, 88]];

export default function Customizer({ studio, onFontUpload }) {
  const { cfg, setOverride, resetOverrides, fonts, presets, styleId, selectPreset } = studio;
  const fileRef = useRef(null);
  const [fontNote, setFontNote] = useState("");

  const anim = cfg.karaoke ? "karaoke" : (cfg.animation || "none");
  const setAnim = (v) => {
    if (v === "karaoke") { setOverride("karaoke", true); setOverride("animation", "none"); }
    else { setOverride("karaoke", false); setOverride("animation", v); }
  };
  const applyTheme = (t) => Object.entries(t.ov).forEach(([k, v]) => setOverride(k, v));
  const tg = (key) => {
    const now = !toggleOn(cfg, key);
    setOverride(key, now);
    if (now && key === "background_enabled" && cfg.background_color == null) setOverride("background_color", "#000000");
  };

  const hl = (cfg.highlight_color || "#FFD400").toUpperCase();
  const ow = cfg.outline_width != null ? cfg.outline_width : (cfg.outline || 0);

  // Background mode (None / Semi / Solid) derived from enabled + opacity.
  const bgOn = toggleOn(cfg, "background_enabled");
  const bgOpacity = cfg.background_opacity != null ? cfg.background_opacity : 100;
  const bgMode = !bgOn ? "none" : (bgOpacity <= 60 ? "semi" : "solid");
  const setBg = (m) => {
    if (m === "none") { setOverride("background_enabled", false); return; }
    setOverride("background_enabled", true);
    setOverride("background_color", cfg.background_color || "#000000");
    setOverride("background_opacity", m === "semi" ? 50 : 100);
  };

  // Position anchor (closest of the 9 to current pos).
  const px = cfg.pos_x != null ? cfg.pos_x : 50;
  const py = cfg.pos_y != null ? cfg.pos_y : 88;
  const posActive = POS.reduce((b, p, i) => {
    const d = Math.abs(p[0] - px) + Math.abs(p[1] - py);
    return d < b.d ? { i, d } : b;
  }, { i: 7, d: 1e9 }).i;

  const weight = toggleOn(cfg, "bold") ? "bold" : "regular";
  const sizePct = Math.round((cfg.font_scale || 1) * 100);
  const fontOptions = [...(fonts.user || []), ...(fonts.multilingual || []), ...(fonts.bundled || [])];

  async function pickFont(file) {
    if (!file) return;
    setFontNote(`Uploading ${file.name}…`);
    try { const fam = await onFontUpload(file); setOverride("font_family", fam); setFontNote(""); }
    catch (e) { setFontNote(e.message); }
  }

  return (
    <div className="cz">
      {/* Caption style (base preset) */}
      <div className="cz-field">
        <label className="cz-label">Caption Style</label>
        <div className="cz-select">
          <Icons.create />
          <select value={styleId} onChange={(e) => selectPreset(e.target.value)}>
            {presets.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <span className="cz-chev" />
        </div>
        {/* Live preview of the current caption style */}
        <div className="cz-preview">
          <span className="cz-preview-cap" style={captionLineStyle(cfg, { fontPx: 25, scale: 0.2 })}>
            {["Make", "it", "go", "viral"].map((w, i) => (
              <span key={i} style={{ color: i === 3 && (anim === "highlight" || anim === "karaoke") ? (cfg.highlight_color || "#FFD400") : undefined }}>{w} </span>
            ))}
          </span>
        </div>
      </div>

      {/* Theme cards */}
      <div className="cz-field">
        <label className="cz-label">Theme</label>
        <div className="cz-cards">
          {THEMES.map((t) => {
            const active = (cfg.font_family || "Roboto") === t.font && hl === t.ov.highlight_color.toUpperCase();
            return (
              <button key={t.id} type="button" className={"cz-card" + (active ? " active" : "")} onClick={() => applyTheme(t)}>
                <span className="cz-aa" style={{ color: t.color, fontFamily: `'${t.font}', sans-serif`, fontWeight: t.ov.bold ? 800 : 600 }}>Aa</span>
                <span className="cz-card-l">{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Highlight color */}
      <div className="cz-field">
        <label className="cz-label">Highlight Color</label>
        <div className="cz-colors">
          {HCOLORS.map((c) => (
            <button key={c} type="button" aria-label={c} className={"cz-dot" + (hl === c ? " active" : "")} style={{ background: c }} onClick={() => setOverride("highlight_color", c)} />
          ))}
          <label className={"cz-dot cz-dot-rainbow" + (!HCOLORS.includes(hl) ? " active" : "")} title="Custom colour">
            <input type="color" value={cfg.highlight_color || "#FFD400"} onChange={(e) => setOverride("highlight_color", e.target.value)} />
          </label>
        </div>
      </div>

      {/* Text settings */}
      <div className="cz-field">
        <label className="cz-label">Text Settings</label>
        <div className="cz-row3">
          <div className="cz-select">
            <Icons.create />
            <select value={cfg.font_family || "Roboto"} onChange={(e) => setOverride("font_family", e.target.value)}>
              {fontOptions.map((f) => <option key={f.file} value={f.family}>{f.family}</option>)}
            </select>
            <span className="cz-chev" />
          </div>
          <div className="cz-select">
            <select value={weight} onChange={(e) => setOverride("bold", e.target.value === "bold")}>
              <option value="regular">Regular</option>
              <option value="bold">Extra Bold</option>
            </select>
            <span className="cz-chev" />
          </div>
          <div className="cz-select cz-select-sm">
            <select value={sizePct} onChange={(e) => setOverride("font_scale", +e.target.value / 100)}>
              {[70, 80, 90, 100, 120, 140, 160, 180].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <span className="cz-chev" />
          </div>
        </div>
        <button type="button" className="cz-upload" onClick={() => fileRef.current?.click()}><Icons.upload /> Upload font</button>
        <input ref={fileRef} type="file" accept=".ttf,.otf" hidden onChange={(e) => pickFont(e.target.files[0])} />
        {fontNote && <div className="note">{fontNote}</div>}
      </div>

      {/* Animation cards */}
      <div className="cz-field">
        <label className="cz-label">Animation</label>
        <div className="cz-cards">
          {ANIMS.map((a) => (
            <button key={a.v} type="button" className={"cz-card" + (anim === a.v ? " active" : "")} onClick={() => setAnim(a.v)}>
              <span className="cz-aa">Aa</span>
              <span className="cz-card-l">{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Position + Background */}
      <div className="cz-row2">
        <div className="cz-field">
          <label className="cz-label">Position</label>
          <div className="cz-posgrid">
            {POS.map((p, i) => (
              <button key={i} type="button" aria-label={"position " + (i + 1)} className={"cz-posdot" + (posActive === i ? " active" : "")} onClick={() => { setOverride("pos_x", p[0]); setOverride("pos_y", p[1]); }} />
            ))}
          </div>
        </div>
        <div className="cz-field">
          <label className="cz-label">Background</label>
          <div className="cz-bgcards">
            {[["none", "None"], ["semi", "Semi"], ["solid", "Solid"]].map(([m, l]) => (
              <button key={m} type="button" className={"cz-bgcard" + (bgMode === m ? " active" : "")} onClick={() => setBg(m)}>
                <span className={"cz-bgicon cz-bg-" + m} />
                <span className="cz-card-l">{l}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Advanced controls */}
      <details className="cz-adv">
        <summary>Advanced — outline, shadow, glow &amp; spacing</summary>
        <div className="cz-adv-body">
          <div className="ctl">
            <div className="swatches">
              <Swatch label="Text" value={cfg.primary_color} def="#FFFFFF" onChange={(v) => setOverride("primary_color", v)} />
              <Swatch label="Outline" value={cfg.outline_color} def="#000000" onChange={(v) => setOverride("outline_color", v)} />
            </div>
          </div>
          <Slider label="Letter spacing" unit="px" min={0} max={30} value={cfg.tracking || 0} onChange={(n) => setOverride("tracking", n)} />
          <Slider label="Outline" unit="px" min={0} max={16} value={ow} onChange={(n) => setOverride("outline_width", n)} />
          <Slider label="Rotation" unit="°" min={-180} max={180} value={cfg.rotation || 0} onChange={(n) => setOverride("rotation", n)} />
          <div className="tgs">
            <button type="button" className={"tg" + (toggleOn(cfg, "uppercase") ? " active" : "")} onClick={() => tg("uppercase")}>UPPER</button>
            <button type="button" className={"tg" + (toggleOn(cfg, "underline") ? " active" : "")} onClick={() => tg("underline")}>Underline</button>
          </div>
          <FxRow label="Drop shadow" on={toggleOn(cfg, "shadow_enabled")} onToggle={() => tg("shadow_enabled")}>
            <Swatch label="Colour" value={cfg.shadow_color} def="#000000" onChange={(v) => setOverride("shadow_color", v)} />
            <Slider label="Distance" unit="px" min={0} max={30} value={cfg.shadow_distance != null ? cfg.shadow_distance : 6} onChange={(n) => setOverride("shadow_distance", n)} />
            <Slider label="Opacity" unit="%" min={0} max={100} value={cfg.shadow_opacity != null ? cfg.shadow_opacity : 75} onChange={(n) => setOverride("shadow_opacity", n)} />
          </FxRow>
          <FxRow label="Glow" on={toggleOn(cfg, "glow_enabled")} onToggle={() => tg("glow_enabled")}>
            <Swatch label="Colour" value={cfg.glow_color} def="#7C4DFF" onChange={(v) => setOverride("glow_color", v)} />
            <Slider label="Intensity" unit="px" min={0} max={30} value={cfg.glow_intensity != null ? cfg.glow_intensity : 10} onChange={(n) => setOverride("glow_intensity", n)} />
          </FxRow>
          <FxRow label="Box behind text" on={toggleOn(cfg, "background_enabled")} onToggle={() => tg("background_enabled")}>
            <Swatch label="Colour" value={cfg.background_color} def="#000000" onChange={(v) => setOverride("background_color", v)} />
            <Slider label="Opacity" unit="%" min={0} max={100} value={cfg.background_opacity != null ? cfg.background_opacity : 100} onChange={(n) => setOverride("background_opacity", n)} />
            <Slider label="Corner radius" unit="px" min={0} max={40} value={cfg.background_radius != null ? cfg.background_radius : 10} onChange={(n) => setOverride("background_radius", n)} />
          </FxRow>
        </div>
      </details>

      <div className="cust-foot">
        <button type="button" className="btn btn-ghost" onClick={resetOverrides}><Icons.refresh /> Reset to preset</button>
      </div>
    </div>
  );
}
