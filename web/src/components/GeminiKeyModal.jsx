import { useState, useEffect } from "react";
import { api } from "../api.js";
import { Icons } from "./Icons.jsx";

export default function GeminiKeyModal({ isOpen, onClose, onKeySaved, isFirstRun = false }) {
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [validating, setValidating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success' | 'error' | 'info', message: '', models: [] }
  const [currentConfig, setCurrentConfig] = useState({ configured: false, masked_key: null });

  useEffect(() => {
    if (isOpen) {
      api.getApiKey()
        .then((res) => {
          setCurrentConfig(res);
          if (res.configured && res.masked_key) {
            setStatus({
              type: "info",
              message: `Active key configured (${res.masked_key}). You can test or replace it below.`,
            });
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleValidate = async () => {
    const keyToTest = apiKey.trim();
    if (!keyToTest && !currentConfig.configured) {
      setStatus({ type: "error", message: "Please enter a Google Gemini API key to validate." });
      return;
    }

    setValidating(true);
    setStatus(null);
    try {
      const res = await api.validateApiKey(keyToTest || undefined);
      if (res.valid) {
        setStatus({
          type: "success",
          message: res.message || "Connected successfully to Google Gemini!",
          models: res.models || [],
        });
      } else {
        setStatus({
          type: "error",
          message: res.message || "Failed to validate API key. Please verify on Google AI Studio.",
        });
      }
    } catch (err) {
      setStatus({
        type: "error",
        message: err.message || "Network error while connecting to Gemini API.",
      });
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    const keyToSave = apiKey.trim();
    if (!keyToSave) {
      setStatus({ type: "error", message: "Please paste your API key before saving." });
      return;
    }

    setSaving(true);
    try {
      // First quick validate to ensure user didn't paste invalid text
      const valRes = await api.validateApiKey(keyToSave);
      if (!valRes.valid) {
        setStatus({
          type: "error",
          message: valRes.message || "Invalid API key. Please check and try again.",
        });
        setSaving(false);
        return;
      }

      await api.setApiKey(keyToSave);
      try { localStorage.setItem("cf-gemini-onboarded", "true"); } catch {}
      setStatus({
        type: "success",
        message: "Gemini API key saved & activated successfully!",
      });
      if (onKeySaved) onKeySaved(keyToSave);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      setStatus({
        type: "error",
        message: err.message || "Failed to save API key.",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    if (!confirm("Remove the configured Google Gemini API key? The app will revert to heuristic selection.")) return;
    try {
      await api.setApiKey("");
      setApiKey("");
      setCurrentConfig({ configured: false, masked_key: null });
      setStatus({ type: "info", message: "API key removed. Running in 100% offline local mode." });
      if (onKeySaved) onKeySaved("");
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Failed to remove key." });
    }
  };

  return (
    <div
      className="gemini-modal-scrim"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(5, 7, 12, 0.82)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "cfFadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isFirstRun) onClose();
      }}
    >
      <div
        className="gemini-modal-card"
        style={{
          width: "100%",
          maxWidth: 620,
          background: "linear-gradient(175deg, rgba(26, 29, 43, 0.95) 0%, rgba(15, 17, 26, 0.98) 100%)",
          border: "1px solid rgba(139, 92, 246, 0.35)",
          borderRadius: 24,
          padding: "32px 30px",
          boxShadow: "0 20px 60px -10px rgba(0, 0, 0, 0.8), 0 0 40px -10px rgba(139, 92, 246, 0.25), inset 0 1px 1px rgba(255, 255, 255, 0.15)",
          position: "relative",
          overflow: "hidden",
          color: "var(--text)",
        }}
      >
        {/* Ambient Top Glow */}
        <div
          style={{
            position: "absolute",
            top: -80,
            left: "50%",
            transform: "translateX(-50%)",
            width: 320,
            height: 160,
            background: "radial-gradient(ellipse at center, rgba(168, 85, 247, 0.35) 0%, rgba(59, 130, 246, 0.15) 50%, transparent 80%)",
            filter: "blur(30px)",
            pointerEvents: "none",
          }}
        />

        {/* Close button (if not mandatory first run) */}
        {!isFirstRun && (
          <button
            type="button"
            onClick={onClose}
            style={{
              position: "absolute",
              top: 20,
              right: 20,
              background: "rgba(255, 255, 255, 0.06)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "50%",
              width: 34,
              height: 34,
              display: "grid",
              placeItems: "center",
              color: "var(--muted)",
              cursor: "pointer",
              fontSize: 16,
              transition: "all 0.15s ease",
            }}
            title="Close"
          >
            ✕
          </button>
        )}

        {/* Header with Glowing AI Sparkle */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 16,
              background: "linear-gradient(135deg, #9333ea 0%, #3b82f6 50%, #06b6d4 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 26,
              boxShadow: "0 8px 24px -4px rgba(147, 51, 234, 0.5)",
              flexShrink: 0,
            }}
          >
            ✨
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h2 style={{ fontSize: "1.45rem", fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>
                Connect Google Gemini AI
              </h2>
              <span
                style={{
                  fontSize: "0.7rem",
                  fontWeight: 800,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "linear-gradient(90deg, rgba(168, 85, 247, 0.25), rgba(59, 130, 246, 0.25))",
                  border: "1px solid rgba(168, 85, 247, 0.5)",
                  color: "#c084fc",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                PRO AI ENGINE
              </span>
            </div>
            <p style={{ margin: "4px 0 0", fontSize: "0.88rem", color: "var(--muted)", lineHeight: 1.4 }}>
              Unlock next-generation AI clip curation, automated SFX/VFX triggers, and trending cinematic templates.
            </p>
          </div>
        </div>

        {/* Value Prop Feature Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            marginBottom: 22,
          }}
        >
          {[
            { icon: "🎯", title: "Viral Hook Scoring", desc: "Gemini-3.8-Flash finds the most gripping moments" },
            { icon: "💥", title: "Smart VFX & SFX", desc: "Auto-adds sound effects, zoom punches & flashes" },
            { icon: "🎬", title: "Trending Templates", desc: "Auto-selects Sigma, Chill, Podcast, or Hype vibe" },
            { icon: "⚡", title: "100% Free Tier", desc: "Free tier on Google AI Studio with high rate limits" },
          ].map((f, i) => (
            <div
              key={i}
              style={{
                background: "rgba(255, 255, 255, 0.03)",
                border: "1px solid rgba(255, 255, 255, 0.06)",
                borderRadius: 12,
                padding: "10px 12px",
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <span style={{ fontSize: "1.15rem", lineHeight: 1 }}>{f.icon}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "var(--text)" }}>{f.title}</div>
                <div style={{ fontSize: "0.74rem", color: "var(--muted)", marginTop: 2, lineHeight: 1.3 }}>{f.desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Input Area */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <label style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text)" }}>
              Google Gemini API Key
            </label>
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: "0.8rem",
                color: "#60a5fa",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontWeight: 600,
              }}
            >
              Get free key on Google AI Studio ↗
            </a>
          </div>

          <div style={{ position: "relative" }}>
            <input
              type={showKey ? "text" : "password"}
              placeholder={currentConfig.configured ? `Current: ${currentConfig.masked_key} (Paste new to replace)` : "Paste AIzaSy... API key here"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={{
                width: "100%",
                padding: "13px 44px 13px 14px",
                background: "rgba(10, 12, 18, 0.8)",
                border: "1px solid rgba(139, 92, 246, 0.4)",
                borderRadius: 12,
                color: "#ffffff",
                fontFamily: apiKey ? "var(--mono)" : "inherit",
                fontSize: "0.9rem",
                outline: "none",
                boxShadow: "inset 0 2px 4px rgba(0,0,0,0.4)",
                transition: "border-color 0.2s ease, box-shadow 0.2s ease",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "#a855f7";
                e.target.style.boxShadow = "0 0 0 3px rgba(168, 85, 247, 0.25)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "rgba(139, 92, 246, 0.4)";
                e.target.style.boxShadow = "inset 0 2px 4px rgba(0,0,0,0.4)";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (apiKey.trim() || currentConfig.configured)) {
                  handleSave();
                }
              }}
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              style={{
                position: "absolute",
                right: 12,
                top: "50%",
                transform: "translateY(-50%)",
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                padding: 4,
                display: "grid",
                placeItems: "center",
                fontSize: "0.95rem",
              }}
              title={showKey ? "Hide key" : "Show key"}
            >
              {showKey ? "👁️‍🗨️" : "👁️"}
            </button>
          </div>
        </div>

        {/* Feedback / Status Alert */}
        {status && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              fontSize: "0.84rem",
              marginBottom: 18,
              display: "flex",
              alignItems: "center",
              gap: 10,
              background:
                status.type === "success"
                  ? "rgba(16, 185, 129, 0.12)"
                  : status.type === "error"
                  ? "rgba(239, 68, 68, 0.12)"
                  : "rgba(59, 130, 246, 0.12)",
              border: `1px solid ${
                status.type === "success"
                  ? "rgba(16, 185, 129, 0.35)"
                  : status.type === "error"
                  ? "rgba(239, 68, 68, 0.35)"
                  : "rgba(59, 130, 246, 0.35)"
              }`,
              color:
                status.type === "success"
                  ? "var(--ok, #10b981)"
                  : status.type === "error"
                  ? "var(--danger, #ef4444)"
                  : "#93c5fd",
            }}
          >
            <span>{status.type === "success" ? "✓" : status.type === "error" ? "⚠️" : "ℹ️"}</span>
            <span style={{ flex: 1, wordBreak: "break-word" }}>{status.message}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleValidate}
              disabled={validating || (!apiKey.trim() && !currentConfig.configured)}
              style={{
                fontSize: "0.85rem",
                padding: "9px 16px",
                borderRadius: 10,
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              {validating ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  Testing…
                </>
              ) : (
                <>🧪 Test Connection</>
              )}
            </button>

            {currentConfig.configured && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleRemove}
                style={{
                  fontSize: "0.82rem",
                  padding: "9px 12px",
                  color: "var(--danger)",
                }}
              >
                Remove Key
              </button>
            )}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {!isFirstRun && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={onClose}
                style={{ fontSize: "0.85rem", padding: "9px 16px" }}
              >
                Cancel
              </button>
            )}

            {isFirstRun && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  try { localStorage.setItem("cf-gemini-onboarded", "true"); } catch {}
                  onClose();
                }}
                style={{ fontSize: "0.82rem", padding: "9px 14px", color: "var(--muted)" }}
                title="Use Aurum Clipper with offline heuristic scoring"
              >
                Skip (Local Offline Mode)
              </button>
            )}

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSave}
              disabled={saving || !apiKey.trim()}
              style={{
                fontSize: "0.88rem",
                fontWeight: 700,
                padding: "10px 22px",
                borderRadius: 10,
                background: "linear-gradient(135deg, #9333ea 0%, #3b82f6 100%)",
                boxShadow: "0 6px 20px rgba(147, 51, 234, 0.4)",
                border: "none",
                color: "#ffffff",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {saving ? (
                <>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
                  Saving…
                </>
              ) : (
                <>✨ Save &amp; Activate</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
