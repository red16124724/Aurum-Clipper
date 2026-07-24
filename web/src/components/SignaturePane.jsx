import { Icons } from "./Icons.jsx";

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

export default function SignaturePane({ sig, setSig }) {
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
