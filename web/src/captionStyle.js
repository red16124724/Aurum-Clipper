// Turn a caption preset (from /api/caption-styles) into an inline style + content
// for a small preview sample — a lightweight port of the vanilla app's styler.

function outlineShadow(px, color) {
  if (!px || px < 0.4) return "";
  const o = [];
  for (let a = 0; a < 360; a += 45) {
    const x = (Math.cos((a * Math.PI) / 180) * px).toFixed(1);
    const y = (Math.sin((a * Math.PI) / 180) * px).toFixed(1);
    o.push(`${x}px ${y}px 0 ${color}`);
  }
  return o.join(",");
}

// Returns { style, words, hlIndex } for rendering a styled sample.
export function captionSampleStyle(preset, { fontPx = 20, scale = 0.2, words } = {}) {
  const p = preset || {};
  const w = words || (p.label || "Aa").split(/\s+/).slice(0, 3);
  const outline = (p.outline_width != null ? p.outline_width : p.outline) || 0;
  const style = {
    fontFamily: `'${(p.font_family || "Roboto").replace(/'/g, "")}', sans-serif`,
    fontWeight: p.bold ? 800 : 600,
    color: p.primary_color || "#fff",
    fontSize: `${fontPx}px`,
    letterSpacing: `${((p.tracking || 0) * scale).toFixed(1)}px`,
    textTransform: p.uppercase ? "uppercase" : "none",
    textShadow: outlineShadow(outline * scale, p.outline_color || "#000") || "none",
  };
  const hlIndex = (p.animation === "highlight" || p.karaoke) ? w.length - 1 : -1;
  return { style, words: w, hlIndex, highlight: p.highlight_color || "#FFD400" };
}
