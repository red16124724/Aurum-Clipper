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

export default function CaptionStudio({ studio, language, onLanguageFontHint, onFontUpload }) {
  const [tab, setTab] = useState("templates");
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const s = studio;

  const f = s.galleryFilter;
  const showMine = f === "all" || f === "mine";
  const showTrend = f === "all" || f === "trending";
  const showStd = f === "all";
  const trending = s.presets.filter((p) => p.trending);
  const standard = s.presets.filter((p) => !p.trending);

  const commitSave = () => { if (s.saveCurrentPreset(saveName)) { setSaveOpen(false); setSaveName(""); } };

  return (
    <details className="studio sect" open>
      <summary className="studio-head sect-h"><span className="studio-title"><span className="dot" />Captions</span><span className="sect-x" /></summary>
      <div className="studio-tabs">
        <button className={"studio-tab" + (tab === "templates" ? " active" : "")} onClick={() => setTab("templates")}><Icons.library /> Templates</button>
        <button className={"studio-tab" + (tab === "customize" ? " active" : "")} onClick={() => setTab("customize")}><Icons.create /> Customize styles</button>
      </div>

      {tab === "templates" && (
        <div className="studio-pane">
          <div className="style-head">
            <span className="eyebrow">Caption style</span>
            <button className="save-btn" onClick={() => setSaveOpen((v) => !v)}><Icons.download /> Save current</button>
          </div>
          {saveOpen && (
            <div className="save-form">
              <input type="text" placeholder="Name your style…" value={saveName} maxLength={40} autoFocus
                onChange={(e) => setSaveName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") commitSave(); if (e.key === "Escape") setSaveOpen(false); }} />
              <button className="btn btn-primary" onClick={commitSave}>Save</button>
              <button className="btn" onClick={() => setSaveOpen(false)}>✕</button>
            </div>
          )}
          <div className="gfilters">
            {[["all", "All"], ["trending", "Trending"], ["mine", "My Styles"]].map(([v, l]) => (
              <button key={v} className={"gfilter" + (f === v ? " active" : "")} onClick={() => s.setGalleryFilter(v)}>{l}</button>
            ))}
          </div>
          <div className="chips">
            {showMine && s.userPresets.map((up) => (
              <Chip key={up.id} label={up.label} custom active={s.activeKey === up.id}
                cfg={effectiveCfg(s.presets, up.base, up.overrides)}
                onClick={() => s.selectUserPreset(up)} onDelete={() => s.removeUserPreset(up.id)} />
            ))}
            {showMine && f === "mine" && !s.userPresets.length && (
              <div className="empty" style={{ gridColumn: "1/-1", padding: 24 }}>No saved styles yet — tune a look and hit “Save current”.</div>
            )}
            {showTrend && trending.map((p) => (
              <Chip key={p.id} label={p.label} trending cfg={p} active={s.activeKey === p.id} onClick={() => s.selectPreset(p.id)} />
            ))}
            {showStd && standard.map((p) => (
              <Chip key={p.id} label={p.label} cfg={p} active={s.activeKey === p.id} onClick={() => s.selectPreset(p.id)} />
            ))}
          </div>
        </div>
      )}

      {tab === "customize" && (
        <div className="studio-pane">
          <Customizer studio={s} onFontUpload={onFontUpload} />
          <div className="cine-sep"><span>Cinematic effects</span></div>
          <Cinematic cinematic={s.cinematic} setCine={s.setCine} resetCine={s.resetCine} />
        </div>
      )}
    </details>
  );
}
