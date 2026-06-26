import { useMemo, useState } from "react";
import { effectiveCfg, DEFAULT_CINEMATIC, LANG_DEFAULT_FONT } from "./caption.js";

const LS_KEY = "clipforge_caption_presets_v1";
function loadUserPresets() {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; }
}
function saveLS(list) { try { localStorage.setItem(LS_KEY, JSON.stringify(list)); } catch {} }

// Central caption/cinematic studio state + actions, shared by the studio UI and
// the live preview. Mirrors the vanilla app's state model 1:1.
export function useStudio(presets, fonts, language) {
  const [styleId, setStyleId] = useState("bold_white");
  const [activeKey, setActiveKey] = useState("bold_white");
  const [overrides, setOverrides] = useState({});
  const [userPresets, setUserPresets] = useState(loadUserPresets);
  const [galleryFilter, setGalleryFilter] = useState("all");
  const [cinematic, setCinematic] = useState({ ...DEFAULT_CINEMATIC });

  const cfg = useMemo(() => effectiveCfg(presets, styleId, overrides), [presets, styleId, overrides]);
  const fontFiles = useMemo(() => {
    const m = {};
    [...(fonts.user || []), ...(fonts.multilingual || []), ...(fonts.bundled || [])].forEach((f) => (m[f.family] = f.file));
    return m;
  }, [fonts]);

  const setOverride = (k, v) => setOverrides((o) => ({ ...o, [k]: v }));
  const applyLangFont = (lang, base) => {
    const def = LANG_DEFAULT_FONT[lang];
    return def && fontFiles[def] ? { ...base, font_family: def } : base;
  };

  function selectPreset(id) {
    setStyleId(id); setActiveKey(id);
    setOverrides(applyLangFont(language, {}));
  }
  function selectUserPreset(up) {
    setStyleId(up.base); setActiveKey(up.id);
    setOverrides(JSON.parse(JSON.stringify(up.overrides || {})));
  }
  function resetOverrides() {
    setOverrides(applyLangFont(language, {}));
    setActiveKey(styleId);
  }
  function saveCurrentPreset(name) {
    const label = (name || "").trim();
    if (!label) return false;
    const up = { id: "user_" + Date.now().toString(36), label, base: styleId, overrides: JSON.parse(JSON.stringify(overrides)) };
    const next = [up, ...userPresets];
    setUserPresets(next); saveLS(next); setActiveKey(up.id);
    return true;
  }
  function removeUserPreset(id) {
    const next = userPresets.filter((p) => p.id !== id);
    setUserPresets(next); saveLS(next);
    if (activeKey === id) setActiveKey(styleId);
  }
  // When language changes, swap to a script-capable font if needed.
  function onLanguageChange(lang) {
    const def = LANG_DEFAULT_FONT[lang];
    if (def && fontFiles[def]) setOverride("font_family", def);
  }

  const setCine = (k, v) => setCinematic((c) => ({ ...c, [k]: v }));
  const resetCine = () => setCinematic({ ...DEFAULT_CINEMATIC });

  return {
    presets, fonts, fontFiles, cfg,
    styleId, activeKey, overrides, userPresets, galleryFilter, cinematic,
    setGalleryFilter, setOverride, resetOverrides,
    selectPreset, selectUserPreset, saveCurrentPreset, removeUserPreset, onLanguageChange,
    setCine, resetCine,
  };
}
