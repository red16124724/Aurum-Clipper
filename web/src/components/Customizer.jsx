import { useRef, useState } from "react";
import { toggleOn } from "../caption.js";
import { Icons } from "./Icons.jsx";

function Slider({ label, unit, min, max, step = 1, value, onChange }) {
  return (
    <div className="ctl">
      <label>{label}<span className="val">{Math.round(value)}{unit}</span></label>
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

function FontSelect({ fonts, value, onChange, onUpload }) {
  const ref = useRef(null);
  const [note, setNote] = useState("");
  const group = (label, list) => list?.length ? (
    <optgroup label={label}>{list.map((f) => <option key={f.file} value={f.family}>{f.family}</option>)}</optgroup>
  ) : null;
  async function pick(file) {
    if (!file) return;
    setNote(`Uploading ${file.name}…`);
    try { const fam = await onUpload(file); onChange(fam); setNote(`Added “${fam}”.`); }
    catch (e) { setNote(e.message); }
  }
  return (
    <div className="ctl">
      <label>Font <span className="val">{value || "Roboto"}</span></label>
      <div className="font-row">
        <select value={value || "Roboto"} onChange={(e) => onChange(e.target.value)}>
          {group("Your fonts", fonts.user)}
          {group("Urdu / Hindi", fonts.multilingual)}
          {group("Trending", fonts.bundled)}
        </select>
        <button type="button" className="btn" onClick={() => ref.current?.click()}><Icons.upload /> Upload</button>
        <input ref={ref} type="file" accept=".ttf,.otf" hidden onChange={(e) => pick(e.target.files[0])} />
      </div>
      {note && <div className="note">{note}</div>}
    </div>
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

export default function Customizer({ studio, onFontUpload }) {
  const { cfg, overrides, setOverride, resetOverrides, fonts } = studio;
  const anim = cfg.karaoke ? "karaoke" : (cfg.animation || "none");
  const setAnim = (v) => {
    if (v === "karaoke") { setOverride("karaoke", true); setOverride("animation", "none"); }
    else { setOverride("karaoke", false); setOverride("animation", v); }
  };
  const tg = (key) => {
    const now = !toggleOn(cfg, key);
    setOverride(key, now);
    if (now && key === "background_enabled" && overrides.background_color == null) setOverride("background_color", "#000000");
  };
  const ow = cfg.outline_width != null ? cfg.outline_width : (cfg.outline || 0);

  return (
    <div className="cust-grid">
      <div className="grouphd"><span>Typography</span></div>
      <FontSelect fonts={fonts} value={cfg.font_family} onChange={(v) => setOverride("font_family", v)} onUpload={onFontUpload} />
      <div className="ctl">
        <label>Animation</label>
        <select value={anim} onChange={(e) => setAnim(e.target.value)}>
          <option value="none">None — static</option>
          <option value="highlight">Highlight active word</option>
          <option value="word_reveal">Word reveal</option>
          <option value="one_word">One word at a time</option>
          <option value="karaoke">Karaoke fill</option>
        </select>
      </div>

      <div className="grouphd"><span>Colours</span></div>
      <div className="ctl">
        <div className="swatches">
          <Swatch label="Text" value={cfg.primary_color} def="#FFFFFF" onChange={(v) => setOverride("primary_color", v)} />
          <Swatch label="Highlight" value={cfg.highlight_color} def="#FFD400" onChange={(v) => setOverride("highlight_color", v)} />
          <Swatch label="Outline" value={cfg.outline_color} def="#000000" onChange={(v) => setOverride("outline_color", v)} />
        </div>
      </div>

      <div className="grouphd"><span>Size &amp; spacing</span></div>
      <Slider label="Size" unit="%" min={60} max={180} step={5} value={(cfg.font_scale || 1) * 100} onChange={(n) => setOverride("font_scale", n / 100)} />
      <Slider label="Letter spacing" unit="px" min={0} max={30} value={cfg.tracking || 0} onChange={(n) => setOverride("tracking", n)} />
      <Slider label="Outline" unit="px" min={0} max={16} value={ow} onChange={(n) => setOverride("outline_width", n)} />

      <div className="grouphd"><span>Position</span></div>
      <div className="note">Drag the caption in the preview, or fine-tune below.</div>
      <Slider label="X position" unit="%" min={0} max={100} value={cfg.pos_x != null ? cfg.pos_x : 50}
        onChange={(n) => { if (cfg.pos_y == null) setOverride("pos_y", 88); setOverride("pos_x", n); }} />
      <Slider label="Y position" unit="%" min={0} max={100} value={cfg.pos_y != null ? cfg.pos_y : 88}
        onChange={(n) => { if (cfg.pos_x == null) setOverride("pos_x", 50); setOverride("pos_y", n); }} />
      <Slider label="Rotation" unit="°" min={-180} max={180} value={cfg.rotation || 0} onChange={(n) => setOverride("rotation", n)} />

      <div className="grouphd"><span>Emphasis &amp; effects</span></div>
      <div className="ctl">
        <div className="tgs">
          <button type="button" className={"tg" + (toggleOn(cfg, "bold") ? " active" : "")} onClick={() => tg("bold")}>Bold</button>
          <button type="button" className={"tg" + (toggleOn(cfg, "uppercase") ? " active" : "")} onClick={() => tg("uppercase")}>UPPER</button>
          <button type="button" className={"tg" + (toggleOn(cfg, "underline") ? " active" : "")} onClick={() => tg("underline")}>Underline</button>
        </div>

        <FxRow label="Box" on={toggleOn(cfg, "background_enabled")} onToggle={() => tg("background_enabled")}>
          <Swatch label="Colour" value={cfg.background_color} def="#000000" onChange={(v) => setOverride("background_color", v)} />
          <Slider label="Opacity" unit="%" min={0} max={100} value={cfg.background_opacity != null ? cfg.background_opacity : 100} onChange={(n) => setOverride("background_opacity", n)} />
          <Slider label="Corner radius" unit="px" min={0} max={40} value={cfg.background_radius != null ? cfg.background_radius : 10} onChange={(n) => setOverride("background_radius", n)} />
        </FxRow>
        <FxRow label="Drop shadow" on={toggleOn(cfg, "shadow_enabled")} onToggle={() => tg("shadow_enabled")}>
          <Swatch label="Colour" value={cfg.shadow_color} def="#000000" onChange={(v) => setOverride("shadow_color", v)} />
          <Slider label="Distance" unit="px" min={0} max={30} value={cfg.shadow_distance != null ? cfg.shadow_distance : 6} onChange={(n) => setOverride("shadow_distance", n)} />
          <Slider label="Opacity" unit="%" min={0} max={100} value={cfg.shadow_opacity != null ? cfg.shadow_opacity : 75} onChange={(n) => setOverride("shadow_opacity", n)} />
        </FxRow>
        <FxRow label="Glow" on={toggleOn(cfg, "glow_enabled")} onToggle={() => tg("glow_enabled")}>
          <Swatch label="Colour" value={cfg.glow_color} def="#7C4DFF" onChange={(v) => setOverride("glow_color", v)} />
          <Slider label="Intensity" unit="px" min={0} max={30} value={cfg.glow_intensity != null ? cfg.glow_intensity : 10} onChange={(n) => setOverride("glow_intensity", n)} />
        </FxRow>
      </div>

      <div className="cust-foot">
        <button type="button" className="btn btn-ghost" onClick={resetOverrides}><Icons.refresh /> Reset to preset</button>
      </div>
    </div>
  );
}
