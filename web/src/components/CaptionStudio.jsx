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

export default function CaptionStudio({ studio, onFontUpload }) {
  const [tab, setTab] = useState("style");
  const [saveOpen, setSaveOpen] = useState(false);
  const s = studio;

  const trending = s.presets.filter((p) => p.trending);
  const standard = s.presets.filter((p) => !p.trending);

  return (
    <details className="studio sect" open>
      <summary className="studio-head sect-h"><span className="studio-title"><span className="dot" />Captions</span><span className="sect-x" /></summary>

      <div className="studio-tabs">
        <button className={"studio-tab" + (tab === "style" ? " active" : "")} onClick={() => setTab("style")}><Icons.create /> Style</button>
        <button className={"studio-tab" + (tab === "effects" ? " active" : "")} onClick={() => setTab("effects")}><Icons.film /> Effects</button>
        <button className={"studio-tab" + (tab === "themes" ? " active" : "")} onClick={() => setTab("themes")}><Icons.library /> Themes</button>
        <button className={"studio-tab" + (tab === "presets" ? " active" : "")} onClick={() => setTab("presets")}><Icons.download /> Presets</button>
      </div>

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
