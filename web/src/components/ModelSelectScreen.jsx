import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icons } from "./Icons.jsx";
import GeminiKeyModal from "./GeminiKeyModal.jsx";

export default function ModelSelectScreen({ onSelect, currentModel = "large-v3-turbo" }) {
  const [info, setInfo] = useState(null);
  const [selected, setSelected] = useState(currentModel);
  const [device, setDevice] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [geminiModalOpen, setGeminiModalOpen] = useState(false);
  const [geminiConfig, setGeminiConfig] = useState({ configured: false, masked_key: null });

  const loadGemini = () => {
    api.getApiKey().then((cfg) => {
      setGeminiConfig(cfg);
      const onboarded = localStorage.getItem("cf-gemini-onboarded");
      if (!cfg.configured && !onboarded) {
        setGeminiModalOpen(true);
      }
    }).catch(() => {});
  };

  useEffect(() => {
    loadGemini();
    api.modelsInfo()
      .then((d) => {
        setInfo(d);
        if (d.active_model) {
          setSelected(d.active_model);
        } else if (d.recommended_installed_model) {
          setSelected(d.recommended_installed_model);
        }
      })
      .catch(() => {});
  }, []);

  const handleConfirm = () => {
    setLoading(true);
    onSelect(selected, device);
  };

  const models = info?.models || [
    {
      id: "large-v3-turbo",
      name: "Large V3 Turbo",
      tag: "Recommended",
      size_label: "~1.6 GB",
      min_ram: "8 GB RAM",
      min_vram: "6 GB VRAM",
      device_rec: "NVIDIA GPU (CUDA) or 6+ Core CPU",
      description: "Optimized version of Large-V3. Up to 8x faster while maintaining top-tier multi-lingual transcription quality.",
      accuracy: 5,
      speed: 4.5,
    },
    {
      id: "large-v3",
      name: "Large V3",
      tag: "Max Accuracy",
      size_label: "~3.1 GB",
      min_ram: "16 GB RAM",
      min_vram: "10 GB VRAM",
      device_rec: "Dedicated NVIDIA GPU (10GB+ VRAM)",
      description: "The most powerful OpenAI Whisper model. Flawless punctuation and handling of complex accents and languages.",
      accuracy: 5,
      speed: 2.5,
    },
    {
      id: "medium",
      name: "Medium",
      tag: "Balanced",
      size_label: "~1.5 GB",
      min_ram: "8 GB RAM",
      min_vram: "5 GB VRAM",
      device_rec: "Mid-tier GPU or Modern Multi-Core CPU",
      description: "Excellent balance of accuracy and resource usage. Great for gaming rigs and standard workstations.",
      accuracy: 4,
      speed: 3.5,
    },
    {
      id: "small",
      name: "Small",
      tag: "Lightweight",
      size_label: "~480 MB",
      min_ram: "4 GB RAM",
      min_vram: "2 GB VRAM",
      device_rec: "Laptops, Integrated Graphics & Standard CPUs",
      description: "Compact footprint with very fast transcription. Ideal for quick clipping on low-spec devices.",
      accuracy: 3.5,
      speed: 4.5,
    },
    {
      id: "base",
      name: "Base",
      tag: "Ultra Fast",
      size_label: "~145 MB",
      min_ram: "4 GB RAM",
      min_vram: "1 GB VRAM",
      device_rec: "Budget PCs & Legacy Hardware",
      description: "Instant download with minimal memory impact. Great for testing or rapid drafting on any hardware.",
      accuracy: 2.5,
      speed: 5,
    },
    {
      id: "savi0ur/whisper-hindi-hinglish-ct2",
      name: "Hinglish Apex Turbo",
      tag: "Hinglish",
      size_label: "~1.6 GB",
      min_ram: "8 GB RAM",
      min_vram: "5 GB VRAM",
      device_rec: "Dedicated NVIDIA GPU or Fast CPU",
      description: "Specialized CTranslate2 model for transcribing Hindi and Hinglish directly into Romanized English script.",
      accuracy: 4.5,
      speed: 4.0,
    },
  ];

  const selectedModelObj = models.find((m) => m.id === selected) || models[0];
  const installedCount = info?.installed_models?.length || 0;

  return (
    <div className="model-select-wrapper" style={{
      maxWidth: 960,
      margin: "0 auto",
      padding: "32px 20px",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
    }}>
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 52,
          height: 52,
          borderRadius: 16,
          background: "linear-gradient(135deg, var(--accent), #ff8a00)",
          color: "#fff",
          fontSize: 26,
          marginBottom: 12,
          boxShadow: "0 8px 24px rgba(255, 107, 0, 0.3)",
        }}>
          <Icons.bolt />
        </div>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: "0 0 8px" }}>
          Welcome to Aurum Clipper
        </h1>
        <p style={{ color: "var(--muted)", fontSize: "1.05rem", maxWidth: 640, margin: "0 auto" }}>
          Choose your local Whisper AI transcription model. Everything runs 100% offline on your device with no external API fees or data leaks.
        </p>
      </div>

      {/* Google Gemini Cloud AI Integration Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, rgba(147, 51, 234, 0.12) 0%, rgba(59, 130, 246, 0.1) 100%)",
          border: "1px solid rgba(147, 51, 234, 0.35)",
          borderRadius: 16,
          padding: "16px 20px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          marginBottom: 20,
          boxShadow: "0 8px 24px -6px rgba(147, 51, 234, 0.2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 260, flex: 1 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: "linear-gradient(135deg, #9333ea 0%, #3b82f6 100%)",
              display: "grid",
              placeItems: "center",
              fontSize: 20,
              flexShrink: 0,
              boxShadow: "0 4px 14px rgba(147, 51, 234, 0.4)",
            }}
          >
            ✨
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text)" }}>
                Google Gemini Pro AI Connection
              </span>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  padding: "2px 7px",
                  borderRadius: 999,
                  background: geminiConfig.configured ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
                  color: geminiConfig.configured ? "var(--ok, #10b981)" : "#f59e0b",
                  border: `1px solid ${geminiConfig.configured ? "rgba(16, 185, 129, 0.4)" : "rgba(245, 158, 11, 0.4)"}`,
                }}
              >
                {geminiConfig.configured ? `✓ Active (${geminiConfig.masked_key})` : "Optional"}
              </span>
            </div>
            <div style={{ fontSize: "0.82rem", color: "var(--muted)", marginTop: 2 }}>
              {geminiConfig.configured
                ? "Gemini-3.8-Flash virality scoring and smart SFX/VFX automation enabled."
                : "Connect your free Gemini API key for smart viral hook curation and auto-editing."}
            </div>
          </div>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setGeminiModalOpen(true)}
          style={{
            fontSize: "0.84rem",
            padding: "8px 16px",
            borderRadius: 10,
            border: "1px solid rgba(147, 51, 234, 0.4)",
            background: "rgba(147, 51, 234, 0.15)",
            color: "#e9d5ff",
            fontWeight: 600,
          }}
        >
          {geminiConfig.configured ? "Manage Key" : "✨ Connect Key"}
        </button>
      </div>

      {/* Installed Models Discovery Banner */}
      {installedCount > 0 && (
        <div style={{
          background: "rgba(16, 185, 129, 0.08)",
          border: "1px solid rgba(16, 185, 129, 0.3)",
          borderRadius: 14,
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 20,
        }}>
          <span style={{ fontSize: "1.4rem" }}>🔍</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, color: "var(--ok, #10b981)", fontSize: "0.95rem", marginBottom: 2 }}>
              Device Scan: {installedCount} Installed Model{installedCount > 1 ? "s" : ""} Found on this PC
            </div>
            <div style={{ fontSize: "0.83rem", color: "var(--muted)" }}>
              Detected on disk: <b>{info.installed_models.map((m) => m.name).join(", ")}</b>. You can launch immediately with zero download required.
            </div>
          </div>
        </div>
      )}

      {/* System Specs Banner */}
      {info && (
        <div style={{
          background: "var(--card-bg, rgba(255,255,255,0.03))",
          border: "1px solid var(--line)",
          borderRadius: 14,
          padding: "14px 20px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 24,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>System RAM</span>
              <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                {info.system_ram_gb ? `${info.system_ram_gb.toFixed(1)} GB` : "Detected"}
              </span>
            </div>
            <div style={{ width: 1, height: 16, background: "var(--line)" }} />
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: "0.85rem", color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>GPU</span>
              <span style={{ fontWeight: 600, fontSize: "0.95rem", color: info.cuda_available ? "var(--ok, #10b981)" : "inherit" }}>
                {info.cuda_available ? (info.gpu_name || "NVIDIA CUDA GPU") : "CPU Mode (No CUDA GPU)"}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Compute Target:</span>
            <select
              value={device}
              onChange={(e) => setDevice(e.target.value)}
              style={{
                background: "var(--bg)",
                color: "var(--fg)",
                border: "1px solid var(--line)",
                borderRadius: 8,
                padding: "4px 10px",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              <option value="auto">Auto (GPU priority)</option>
              {info.cuda_available && <option value="cuda">GPU (CUDA)</option>}
              <option value="cpu">CPU (Standard)</option>
            </select>
          </div>
        </div>
      )}

      {/* Model Cards Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
        gap: 16,
        marginBottom: 28,
      }}>
        {models.map((m) => {
          const isSel = selected === m.id;
          const isRec = m.tag === "Recommended";
          return (
            <div
              key={m.id}
              onClick={() => setSelected(m.id)}
              style={{
                background: isSel ? "var(--card-hover, rgba(255, 107, 0, 0.06))" : "var(--card-bg, rgba(255,255,255,0.02))",
                border: `2px solid ${isSel ? "var(--accent, #ff6b00)" : isRec ? "rgba(255, 107, 0, 0.3)" : "var(--line)"}`,
                borderRadius: 16,
                padding: "20px 18px",
                cursor: "pointer",
                position: "relative",
                transition: "all 0.2s ease",
                display: "flex",
                flexDirection: "column",
                boxShadow: isSel ? "0 8px 24px rgba(255, 107, 0, 0.15)" : "none",
              }}
            >
              {/* Top Tag Badges */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  padding: "3px 8px",
                  borderRadius: 6,
                  background: isRec ? "rgba(255, 107, 0, 0.2)" : "rgba(255, 255, 255, 0.08)",
                  color: isRec ? "var(--accent, #ff6b00)" : "inherit",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                }}>
                  {m.tag}
                </span>

                <span style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--muted)",
                }}>
                  {m.size_label}
                </span>
              </div>

              {/* Title & Radio */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 700 }}>{m.name}</h3>
                <div style={{
                  width: 20,
                  height: 20,
                  borderRadius: "50%",
                  border: `2px solid ${isSel ? "var(--accent, #ff6b00)" : "var(--line)"}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: isSel ? "var(--accent, #ff6b00)" : "transparent",
                }}>
                  {isSel && <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#fff" }} />}
                </div>
              </div>

              {/* Description */}
              <p style={{
                fontSize: "0.86rem",
                color: "var(--muted)",
                margin: "0 0 14px",
                lineHeight: 1.45,
                flex: 1,
              }}>
                {m.description}
              </p>

              {/* Requirements & Specs Box */}
              <div style={{
                background: "rgba(0,0,0,0.15)",
                border: "1px solid var(--line)",
                borderRadius: 10,
                padding: "10px 12px",
                fontSize: "0.8rem",
                display: "flex",
                flexDirection: "column",
                gap: 6,
                marginBottom: 12,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                  <span style={{ color: "var(--muted)", flexShrink: 0 }}>Min RAM:</span>
                  <span style={{ fontWeight: 600, textAlign: "right" }}>{m.min_ram}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                  <span style={{ color: "var(--muted)", flexShrink: 0 }}>Min VRAM:</span>
                  <span style={{ fontWeight: 600, textAlign: "right" }}>{m.min_vram}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                  <span style={{ color: "var(--muted)", flexShrink: 0 }}>Target:</span>
                  <span style={{ fontWeight: 500, textAlign: "right", wordBreak: "break-word" }}>{m.device_rec}</span>
                </div>
              </div>

              {/* Speed & Accuracy Meters */}
              <div style={{ display: "flex", gap: 12, alignItems: "center", fontSize: "0.78rem" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, color: "var(--muted)" }}>
                    <span>Accuracy</span>
                    <span>{m.accuracy}/5</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.1)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${(m.accuracy / 5) * 100}%`, background: "var(--accent, #ff6b00)" }} />
                  </div>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, color: "var(--muted)" }}>
                    <span>Speed</span>
                    <span>{m.speed}/5</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 2, background: "rgba(255,255,255,0.1)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${(m.speed / 5) * 100}%`, background: "var(--ok, #10b981)" }} />
                  </div>
                </div>
              </div>

              {/* Cache status pill */}
              {m.is_cached && (
                <div style={{
                  marginTop: 10,
                  fontSize: "0.75rem",
                  color: "var(--ok, #10b981)",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontWeight: 600,
                }}>
                  <span>✓ Downloaded on disk (Instant Launch)</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom Action Footer */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 12,
        width: "100%",
      }}>
        <button
          className="btn btn-primary"
          onClick={handleConfirm}
          disabled={loading}
          style={{
            minWidth: 280,
            maxWidth: "100%",
            padding: "14px 28px",
            fontSize: "1.05rem",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            borderRadius: 12,
            boxShadow: "0 6px 20px rgba(255, 107, 0, 0.3)",
          }}
        >
          {loading ? (
            <>Starting Engine…</>
          ) : selectedModelObj.is_cached ? (
            <>Launch Engine with {selectedModelObj.name} →</>
          ) : (
            <>Download &amp; Initialize {selectedModelObj.name} ({selectedModelObj.size_label}) →</>
          )}
        </button>
        <span style={{ fontSize: "0.82rem", color: "var(--muted)", textAlign: "center" }}>
          You can change or download other models anytime from Settings.
        </span>
      </div>

      <GeminiKeyModal
        isOpen={geminiModalOpen}
        onClose={() => setGeminiModalOpen(false)}
        onKeySaved={() => {
          loadGemini();
        }}
        isFirstRun={!geminiConfig.configured}
      />
    </div>
  );
}
