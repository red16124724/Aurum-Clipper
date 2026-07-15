import { useState } from "react";
import { captionLineStyle, effectiveCfg } from "../caption.js";
import Customizer from "./Customizer.jsx";
import Cinematic from "./Cinematic.jsx";
import { Icons } from "./Icons.jsx";

function Chip({ label, cfg, active, trending, custom, onClick, onDelete }) {
  const words = (label || "Aa").split(/\s+/).slice(0, 3);
  const style = captionLineStyle(cfg, { fontPx: 19, scale: 0.18 });
  const hl = (cfg.animation === "highlight" || cfg.karaoke) ? words.length - 1 : -1;
  return (
    <button type="button" className={"chip" + (active ? " active" : "")} onClick={onClick}>
      {custom ? <span className="tag custom">Custom</span> : trending ? <span className="tag">Trending</span> : null}
      {custom && <span className="chip-del" onClick={(e) => { e.stopPropagation(); onDelete(); }}>✕</span>}
      <span className="stage"><span className="sample" style={style}>
        {words.map((w, i) => <span key={i} style={{ color: i === hl ? (cfg.highlight_color || "#FFD400") : undefined }}>{w} </span>)}
      </span></span>
      <span className="name">{label}</span>
    </button>
  );
}

function SaveBlock({ s, open, setOpen }) {
  const [name, setName] = useState("");
  const commit = () => { if (s.saveCurrentPreset(name)) { setOpen(false); setName(""); } };
  if (!open) return null;
  return (
    <div className="save-form">
      <input type="text" placeholder="Name your style…" value={name} maxLength={40} autoFocus
        onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") setOpen(false); }} />
      <button className="btn btn-primary" onClick={commit}>Save</button>
      <button className="btn" onClick={() => setOpen(false)}>✕</button>
    </div>
  );
}

const SIG_POS = [[8, 8], [50, 8], [92, 8], [8, 50], [50, 50], [92, 50], [8, 92], [50, 92], [92, 92]];

function SigSlider({ label, unit, min, max, value, onChange }) {
  const clamp = (v) => Math.max(min, Math.min(max, v));
  return (
    <div className="ctl">
      <label>{label}
        <span className="val">
          <input type="number" className="val-num" min={min} max={max} value={Math.round(value)}
            onChange={(e) => onChange(e.target.value === "" ? value : clamp(parseFloat(e.target.value) || 0))} />
          {unit}
        </span>
      </label>
      <input type="range" className="range" min={min} max={max} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} />
    </div>
  );
}

function SignaturePane({ sig, setSig }) {
  if (!sig) return null;
  const on = !!sig.enabled;
  const px = sig.pos_x != null ? sig.pos_x : 50;
  const py = sig.pos_y != null ? sig.pos_y : 92;
  const posActive = SIG_POS.reduce((b, p, i) => {
    const d = Math.abs(p[0] - px) + Math.abs(p[1] - py);
    return d < b.d ? { i, d } : b;
  }, { i: 7, d: 1e9 }).i;
  return (
    <div className="cz">
      <div className="style-head"><span className="eyebrow">Signature / watermark</span></div>
      <div className="fxrow">
        <button type="button" className={"tg fxtoggle" + (on ? " active" : "")} onClick={() => setSig("enabled", !on)}>
          {on ? "Signature ON" : "Signature OFF"}
        </button>
      </div>
      {on && (
        <>
          <div className="cz-field">
            <label className="cz-label">Text</label>
            <div className="cz-select">
              <Icons.bolt />
              <input type="text" value={sig.text || ""} placeholder="@yourhandle" onChange={(e) => setSig("text", e.target.value)} />
            </div>
          </div>
          <div className="cz-row2">
            <div className="cz-field">
              <label className="cz-label">Position</label>
              <div className="cz-posgrid">
                {SIG_POS.map((p, i) => (
                  <button key={i} type="button" className={"cz-posdot" + (posActive === i ? " active" : "")}
                    onClick={() => { setSig("pos_x", p[0]); setSig("pos_y", p[1]); }} />
                ))}
              </div>
            </div>
            <div className="cz-field">
              <label className="cz-label">Colour</label>
              <label className="swatch">Pick<input type="color" value={sig.color || "#FFFFFF"} onChange={(e) => setSig("color", e.target.value)} /></label>
            </div>
          </div>
          <SigSlider label="Size" unit="px" min={14} max={90} value={sig.size != null ? sig.size : 34} onChange={(n) => setSig("size", n)} />
          <SigSlider label="Opacity" unit="%" min={10} max={100} value={sig.opacity != null ? sig.opacity : 75} onChange={(n) => setSig("opacity", n)} />
          <div className="note">Tip: you can also <b>drag the signature</b> right on the preview. Use the grid for static corners, or drag to place it freely (movable).</div>
        </>
      )}
    </div>
  );
}

export default function CaptionStudio({ studio, onFontUpload, signature, setSig }) {
  const [tab, setTab] = useState("style");
  const [saveOpen, setSaveOpen] = useState(false);
  const s = studio;

  const trending = s.presets.filter((p) => p.trending);
  const standard = s.presets.filter((p) => !p.trending);

  return (
    <details className="studio sect" open>
      <summary className="studio-head sect-h"><span className="studio-title"><span className="dot" />Captions</span><span className="sect-x" /></summary>

      <div className="studio-tabs">
        <button className={"studio-tab" + (tab === "style" ? " active" : "")} onClick={() => setTab("style")} title="Style"><Icons.create /><span className="studio-tab-lbl">Style</span></button>
        <button className={"studio-tab" + (tab === "effects" ? " active" : "")} onClick={() => setTab("effects")} title="Effects"><Icons.film /><span className="studio-tab-lbl">Effects</span></button>
        <button className={"studio-tab" + (tab === "themes" ? " active" : "")} onClick={() => setTab("themes")} title="Themes"><Icons.library /><span className="studio-tab-lbl">Themes</span></button>
        <button className={"studio-tab" + (tab === "sign" ? " active" : "")} onClick={() => setTab("sign")} title="Sign"><Icons.bolt /><span className="studio-tab-lbl">Sign</span></button>
        <button className={"studio-tab" + (tab === "presets" ? " active" : "")} onClick={() => setTab("presets")} title="Presets"><Icons.download /><span className="studio-tab-lbl">Presets</span></button>
      </div>

      {tab === "sign" && (
        <div className="studio-pane">
          <SignaturePane sig={signature} setSig={setSig} />
        </div>
      )}

      {tab === "style" && (
        <div className="studio-pane">
          <div className="style-head">
            <span className="eyebrow">Customize</span>
            <button className="save-btn" onClick={() => setSaveOpen((v) => !v)}><Icons.download /> Save current</button>
          </div>
          <SaveBlock s={s} open={saveOpen} setOpen={setSaveOpen} />
          <Customizer studio={s} onFontUpload={onFontUpload} />
        </div>
      )}

      {tab === "effects" && (
        <div className="studio-pane">
          <div className="style-head"><span className="eyebrow">Cinematic effects</span></div>
          <Cinematic cinematic={s.cinematic} setCine={s.setCine} resetCine={s.resetCine} />
        </div>
      )}

      {tab === "themes" && (
        <div className="studio-pane">
          <div className="style-head"><span className="eyebrow">Built-in themes</span></div>
          <div className="chips">
            {trending.map((p) => (
              <Chip key={p.id} label={p.label} trending cfg={p} active={s.activeKey === p.id} onClick={() => s.selectPreset(p.id)} />
            ))}
            {standard.map((p) => (
              <Chip key={p.id} label={p.label} cfg={p} active={s.activeKey === p.id} onClick={() => s.selectPreset(p.id)} />
            ))}
          </div>
        </div>
      )}

      {tab === "presets" && (
        <div className="studio-pane">
          <div className="style-head">
            <span className="eyebrow">My styles</span>
            <button className="save-btn" onClick={() => setSaveOpen((v) => !v)}><Icons.download /> Save current</button>
          </div>
          <SaveBlock s={s} open={saveOpen} setOpen={setSaveOpen} />
          <div className="chips">
            {s.userPresets.map((up) => (
              <Chip key={up.id} label={up.label} custom active={s.activeKey === up.id}
                cfg={effectiveCfg(s.presets, up.base, up.overrides)}
                onClick={() => s.selectUserPreset(up)} onDelete={() => s.removeUserPreset(up.id)} />
            ))}
            {!s.userPresets.length && (
              <div className="empty" style={{ gridColumn: "1/-1", padding: 24 }}>No saved styles yet — tune a look in <b>Style</b> and hit “Save current”.</div>
            )}
          </div>
        </div>
      )}
    </details>
  );
}
