// Caption + cinematic helpers shared across the studio and preview — a faithful
// port of the vanilla app's styling logic so the React preview matches the burn.

export const LANGS = [
  ["auto", "Auto-detect"], ["en", "English"], ["hinglish", "Hinglish — Roman Urdu / Hindi"],
  ["ur", "Urdu — اردو"], ["hi", "Hindi — हिन्दी"], ["ar", "Arabic — العربية"], ["fa", "Persian — فارسی"],
  ["pa", "Punjabi — ਪੰਜਾਬੀ"], ["bn", "Bengali — বাংলা"], ["es", "Spanish — Español"], ["fr", "French — Français"],
  ["de", "German — Deutsch"], ["pt", "Portuguese — Português"], ["ru", "Russian — Русский"], ["tr", "Turkish — Türkçe"],
  ["id", "Indonesian — Bahasa"], ["ja", "Japanese — 日本語"], ["ko", "Korean — 한국어"], ["zh", "Chinese — 中文"],
];

// Preview phrase per caption language (so the preview reads in the target language).
export const CAP_SAMPLES = {
  en: { words: ["Make", "it", "go", "viral"], hl: 3 },
  hinglish: { words: ["Caption", "ab", "Hinglish", "mein"], hl: 2 },
  hi: { words: ["कैप्शन", "अब", "हिंदी", "में"], hl: 2 },
  ur: { words: ["کیپشن", "اب", "اردو", "میں"], hl: 2 },
  ar: { words: ["التعليقات", "الآن", "بالعربية"], hl: 2 },
  fa: { words: ["زیرنویس", "به", "فارسی"], hl: 2 },
  pa: { words: ["ਕੈਪਸ਼ਨ", "ਹੁਣ", "ਪੰਜਾਬੀ"], hl: 2 },
  bn: { words: ["ক্যাপশন", "এখন", "বাংলা"], hl: 2 },
  es: { words: ["Hazlo", "volverse", "viral"], hl: 2 },
  fr: { words: ["Rends-le", "viral"], hl: 1 },
  de: { words: ["Mach", "es", "viral"], hl: 2 },
  pt: { words: ["Torne-o", "viral"], hl: 1 },
  ru: { words: ["Сделай", "это", "вирусным"], hl: 2 },
  tr: { words: ["Onu", "viral", "yap"], hl: 1 },
  id: { words: ["Buat", "jadi", "viral"], hl: 2 },
  ja: { words: ["バズら", "せよう"], hl: 1 },
  ko: { words: ["떡상", "가자"], hl: 0 },
  zh: { words: ["让它", "爆红"], hl: 1 },
};

export const LANG_DEFAULT_FONT = {
  ur: "Noto Nastaliq Urdu", fa: "Noto Naskh Arabic", ar: "Noto Sans Arabic",
  hi: "Noto Sans Devanagari", mr: "Noto Sans Devanagari", ne: "Noto Sans Devanagari",
  bn: "Noto Sans Devanagari", pa: "Noto Sans Devanagari",
};

export function captionSample(language) {
  return CAP_SAMPLES[language] || CAP_SAMPLES.en;
}

export function presetById(presets, id) {
  return presets.find((p) => p.id === id) || presets[0] || {};
}

// preset + overrides → effective config
export function effectiveCfg(presets, styleId, overrides) {
  return Object.assign({}, presetById(presets, styleId), overrides || {});
}

export function hexToRgba(hex, a) {
  hex = (hex || "#000000").replace("#", "");
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const r = parseInt(hex.slice(0, 2), 16) || 0, g = parseInt(hex.slice(2, 4), 16) || 0, b = parseInt(hex.slice(4, 6), 16) || 0;
  return `rgba(${r},${g},${b},${a})`;
}

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

// Whether an emphasis/effect toggle is on, honouring override → preset fallback.
export function toggleOn(cfg, key) {
  if (key === "shadow_enabled") {
    return cfg.shadow_enabled !== undefined ? !!cfg.shadow_enabled : (cfg.shadow || 0) > 0;
  }
  return !!cfg[key];
}

// Full inline style for a caption line (preview). Mirrors styleCaptionEl().
export function captionLineStyle(cfg, { fontPx = 40, scale = 0.2 } = {}) {
  const outlinePx = ((cfg.outline_width != null ? cfg.outline_width : cfg.outline) || 0) * scale;
  const box = !!cfg.background_enabled;
  const shadows = [];
  if (!box) { const o = outlineShadow(outlinePx, cfg.outline_color || "#000"); if (o) shadows.push(o); }
  if (toggleOn(cfg, "glow_enabled")) {
    const g = (cfg.glow_intensity != null ? cfg.glow_intensity : 10) * scale;
    const gc = cfg.glow_color || "#7C4DFF";
    shadows.push(`0 0 ${g.toFixed(1)}px ${gc}`, `0 0 ${(g * 2).toFixed(1)}px ${gc}`);
  }
  if (toggleOn(cfg, "shadow_enabled")) {
    const d = (cfg.shadow_distance != null ? cfg.shadow_distance : (cfg.shadow || 6)) * scale;
    const op = (cfg.shadow_opacity != null ? cfg.shadow_opacity : 75) / 100;
    shadows.push(`${d.toFixed(1)}px ${d.toFixed(1)}px ${(d * 0.6).toFixed(1)}px ${hexToRgba(cfg.shadow_color || "#000", op)}`);
  }
  const style = {
    fontFamily: `'${(cfg.font_family || "Roboto").replace(/'/g, "")}', sans-serif`,
    fontWeight: cfg.bold ? 800 : 600,
    color: cfg.primary_color || "#fff",
    fontSize: `${fontPx}px`,
    letterSpacing: `${((cfg.tracking || 0) * scale).toFixed(1)}px`,
    textTransform: cfg.uppercase ? "uppercase" : "none",
    textDecoration: ((cfg.underline ? "underline " : "") + (cfg.strikethrough ? "line-through" : "")).trim() || "none",
    transform: cfg.rotation ? `rotate(${-cfg.rotation}deg)` : "none",
    textShadow: shadows.join(",") || "none",
    lineHeight: 1.12,
  };
  if (box) {
    const bop = (cfg.background_opacity != null ? cfg.background_opacity : 100) / 100;
    style.background = hexToRgba(cfg.background_color || "#000", bop);
    style.padding = ".12em .34em";
    style.borderRadius = `${((cfg.background_radius != null ? cfg.background_radius : 10) * scale).toFixed(1)}px`;
  }
  return style;
}

// CSS filter approximating each cinematic colour grade for the live preview.
export const CINE_GRADE_CSS = {
  none: "",
  warm: "saturate(1.1) sepia(.18) hue-rotate(-8deg) brightness(1.02)",
  cool: "saturate(1.05) hue-rotate(12deg) contrast(1.03)",
  teal_orange: "saturate(1.18) contrast(1.06) sepia(.12) hue-rotate(-6deg)",
  vintage: "sepia(.35) saturate(.85) contrast(.95) brightness(1.03)",
  vibrant: "saturate(1.4) contrast(1.08) brightness(1.01)",
  bw: "grayscale(1) contrast(1.1)",
};

export const COLOR_GRADES = [
  ["none", "None"], ["warm", "Warm"], ["cool", "Cool"], ["teal_orange", "Teal & Orange"],
  ["vintage", "Vintage"], ["vibrant", "Vibrant"], ["bw", "Black & White"],
];

export const DEFAULT_CINEMATIC = {
  color_grade: "none",
  bottom_gradient: false, bottom_gradient_height: 25, bottom_gradient_strength: 70,
  top_gradient: false, top_gradient_height: 20, top_gradient_strength: 60,
  vignette: false, vignette_strength: 50,
  glow: false, glow_strength: 50,
  grain: false, grain_strength: 40,
  letterbox: false, letterbox_size: 50,
  sharpen: false, sharpen_strength: 40,
  chroma_shift: false, chroma_shift_strength: 40,
};

export function cineActive(c) {
  return (c.color_grade && c.color_grade !== "none") || c.bottom_gradient || c.top_gradient
    || c.vignette || c.glow || c.grain || c.letterbox || c.sharpen || c.chroma_shift;
}

// Embed parser for the URL source preview (YouTube / Vimeo → iframe; else <video>).
export function parseEmbed(url) {
  if (!url) return null;
  let m = url.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([\w-]{11})/);
  if (m) return { kind: "embed", src: `https://www.youtube.com/embed/${m[1]}` };
  m = url.match(/vimeo\.com\/(\d+)/);
  if (m) return { kind: "embed", src: `https://player.vimeo.com/video/${m[1]}` };
  if (/\.(mp4|webm|mov|m4v)(\?|$)/i.test(url)) return { kind: "video", src: url };
  return { kind: "unknown", src: url };
}
