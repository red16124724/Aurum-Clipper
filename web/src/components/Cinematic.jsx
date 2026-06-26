import { COLOR_GRADES } from "../caption.js";
import { Icons } from "./Icons.jsx";

function Slider({ label, unit, min, max, value, onChange }) {
  return (
    <div className="ctl">
      <label>{label}<span className="val">{Math.round(value)}{unit}</span></label>
      <input type="range" className="range" min={min} max={max} value={value} onChange={(e) => onChange(parseFloat(e.target.value))} />
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

export default function Cinematic({ cinematic: c, setCine, resetCine }) {
  return (
    <div className="cust-grid">
      <div className="grouphd"><span>Colour grade</span></div>
      <div className="ctl">
        <label>Look</label>
        <select value={c.color_grade} onChange={(e) => setCine("color_grade", e.target.value)}>
          {COLOR_GRADES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <div className="grouphd"><span>Gradients</span></div>
      <div className="ctl">
        <FxRow label="Bottom fade" on={c.bottom_gradient} onToggle={() => setCine("bottom_gradient", !c.bottom_gradient)}>
          <Slider label="Height" unit="%" min={0} max={80} value={c.bottom_gradient_height} onChange={(n) => setCine("bottom_gradient_height", n)} />
          <Slider label="Strength" unit="%" min={0} max={100} value={c.bottom_gradient_strength} onChange={(n) => setCine("bottom_gradient_strength", n)} />
        </FxRow>
        <FxRow label="Top fade" on={c.top_gradient} onToggle={() => setCine("top_gradient", !c.top_gradient)}>
          <Slider label="Height" unit="%" min={0} max={80} value={c.top_gradient_height} onChange={(n) => setCine("top_gradient_height", n)} />
          <Slider label="Strength" unit="%" min={0} max={100} value={c.top_gradient_strength} onChange={(n) => setCine("top_gradient_strength", n)} />
        </FxRow>
      </div>

      <div className="grouphd"><span>Atmosphere</span></div>
      <div className="ctl">
        <FxRow label="Vignette" on={c.vignette} onToggle={() => setCine("vignette", !c.vignette)}>
          <Slider label="Strength" unit="%" min={0} max={100} value={c.vignette_strength} onChange={(n) => setCine("vignette_strength", n)} />
        </FxRow>
        <FxRow label="Glow" on={c.glow} onToggle={() => setCine("glow", !c.glow)}>
          <Slider label="Strength" unit="%" min={0} max={100} value={c.glow_strength} onChange={(n) => setCine("glow_strength", n)} />
        </FxRow>
        <FxRow label="Film grain" on={c.grain} onToggle={() => setCine("grain", !c.grain)}>
          <Slider label="Strength" unit="%" min={0} max={100} value={c.grain_strength} onChange={(n) => setCine("grain_strength", n)} />
          <div className="note">Grain appears in the exported clip.</div>
        </FxRow>
        <FxRow label="Cinematic bars" on={c.letterbox} onToggle={() => setCine("letterbox", !c.letterbox)}>
          <Slider label="Size" unit="%" min={0} max={100} value={c.letterbox_size} onChange={(n) => setCine("letterbox_size", n)} />
        </FxRow>
      </div>

      <div className="cust-foot">
        <button type="button" className="btn btn-ghost" onClick={resetCine}><Icons.refresh /> Reset effects</button>
      </div>
    </div>
  );
}
