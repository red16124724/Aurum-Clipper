import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icons } from "../components/Icons.jsx";
import GeminiKeyModal from "../components/GeminiKeyModal.jsx";

export default function Settings() {
  const [d, setD] = useState(null);
  const [modelsInfo, setModelsInfo] = useState(null);
  const [switching, setSwitching] = useState(null);
  const [msg, setMsg] = useState("");
  const [geminiStatus, setGeminiStatus] = useState({ configured: false, masked_key: null });
  const [modalOpen, setModalOpen] = useState(false);
  const [testingGemini, setTestingGemini] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const refresh = () => {
    api.devices().then(setD).catch(() => setD({ devices: [], cuda_available: false }));
    api.modelsInfo().then(setModelsInfo).catch(() => {});
    api.getApiKey().then(setGeminiStatus).catch(() => {});
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleSwitchModel = async (modelId) => {
    setSwitching(modelId);
    setMsg(`Initializing ${modelId}...`);
    try {
      localStorage.setItem("cf-model-size", modelId);
      localStorage.setItem("whisperModel", modelId);
      await api.warmup(d?.default || "auto", modelId);
      setMsg(`Switched active model to ${modelId}.`);
      refresh();
    } catch (err) {
      setMsg(`Error switching model: ${err.message || err}`);
    } finally {
      setSwitching(null);
    }
  };

  const handleTestGemini = async () => {
    setTestingGemini(true);
    setTestResult(null);
    try {
      const res = await api.validateApiKey();
      setTestResult(res);
      refresh();
    } catch (err) {
      setTestResult({ valid: false, message: err.message || "Failed to connect." });
    } finally {
      setTestingGemini(false);
    }
  };

  const handleRemoveGemini = async () => {
    if (!confirm("Remove the Google Gemini API key? App will fall back to local heuristic mode.")) return;
    try {
      await api.setApiKey("");
      setTestResult(null);
      refresh();
    } catch (err) {
      setMsg(`Error: ${err.message}`);
    }
  };

  return (
    <div style={{ maxWidth: 880, margin: "0 auto", display: "flex", flexDirection: "column", gap: 28 }}>
      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 26, fontWeight: 800, margin: 0, letterSpacing: "-0.025em" }}>Settings &amp; Engine</h2>
          <span style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4, display: "block" }}>
            Manage Google Gemini AI, local compute hardware, Whisper transcription models, and cache storage
          </span>
        </div>
      </div>

      {/* Google Gemini AI Cloud Engine Card */}
      <div>
        <div className="ios-group-title" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span>✨ Google Gemini AI Cloud Engine</span>
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: "2px 7px",
              borderRadius: 6,
              background: "linear-gradient(135deg, rgba(147, 51, 234, 0.2), rgba(59, 130, 246, 0.2))",
              color: "#a855f7",
              border: "1px solid rgba(147, 51, 234, 0.4)",
              letterSpacing: "0.05em",
            }}
          >
            PRO CAPABILITIES
          </span>
        </div>

        <div
          className="ios-group"
          style={{
            background: "linear-gradient(175deg, rgba(30, 27, 46, 0.75) 0%, var(--surface) 100%)",
            border: "1px solid rgba(147, 51, 234, 0.3)",
            boxShadow: "0 10px 30px -10px rgba(147, 51, 234, 0.15)",
          }}
        >
          {/* Row 1: Status & Actions */}
          <div className="ios-row" style={{ padding: "18px 20px" }}>
            <div className="ios-row-left">
              <div
                className="ios-icon-box"
                style={{
                  background: geminiStatus.configured
                    ? "linear-gradient(135deg, #9333ea, #3b82f6)"
                    : "rgba(255,255,255,0.06)",
                  color: "#ffffff",
                  fontSize: 18,
                }}
              >
                ✨
              </div>
              <div className="ios-row-labels">
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span className="ios-row-title" style={{ fontSize: 15, fontWeight: 700 }}>
                    Google Gemini Model Connectivity
                  </span>
                  <span
                    className="badge"
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 999,
                      background: geminiStatus.configured ? "rgba(16, 185, 129, 0.18)" : "rgba(245, 158, 11, 0.18)",
                      color: geminiStatus.configured ? "var(--ok, #10b981)" : "#f59e0b",
                      border: `1px solid ${geminiStatus.configured ? "rgba(16, 185, 129, 0.4)" : "rgba(245, 158, 11, 0.4)"}`,
                    }}
                  >
                    <span className="dot" style={{ background: geminiStatus.configured ? "var(--ok, #10b981)" : "#f59e0b" }} />
                    {geminiStatus.configured ? "Connected & Active" : "Not Configured (Offline Fallback)"}
                  </span>
                </div>
                <span className="ios-row-desc" style={{ marginTop: 3 }}>
                  {geminiStatus.configured
                    ? `Key: ${geminiStatus.masked_key} · Powers Gemini-3.8-Flash virality curation, smart SFX/VFX & trending templates.`
                    : "Connect your free Google Gemini API key to enable AI viral hook selection, auto SFX/VFX, and template auto-styling."}
                </span>
              </div>
            </div>

            <div className="ios-row-right" style={{ gap: 8 }}>
              {geminiStatus.configured && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleTestGemini}
                  disabled={testingGemini}
                  style={{ fontSize: 12.5, padding: "7px 14px", borderRadius: 8 }}
                >
                  {testingGemini ? "Testing…" : "🧪 Test"}
                </button>
              )}

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setModalOpen(true)}
                style={{
                  fontSize: 12.5,
                  padding: "7px 16px",
                  borderRadius: 8,
                  background: "linear-gradient(135deg, #9333ea 0%, #3b82f6 100%)",
                  boxShadow: "0 4px 14px rgba(147, 51, 234, 0.35)",
                  border: "none",
                }}
              >
                {geminiStatus.configured ? "Edit Key" : "Connect Google Key"}
              </button>

              {geminiStatus.configured && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={handleRemoveGemini}
                  style={{ fontSize: 12, padding: "7px 10px", color: "var(--danger)" }}
                  title="Remove Key"
                >
                  Remove
                </button>
              )}
            </div>
          </div>

          {/* Inline Test Result Banner */}
          {testResult && (
            <div
              style={{
                margin: "0 20px 16px",
                padding: "10px 14px",
                borderRadius: 10,
                fontSize: "0.84rem",
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: testResult.valid ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                border: `1px solid ${testResult.valid ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                color: testResult.valid ? "var(--ok, #10b981)" : "var(--danger, #ef4444)",
              }}
            >
              <span>{testResult.valid ? "✓" : "⚠️"}</span>
              <span style={{ flex: 1 }}>{testResult.message}</span>
              {testResult.models?.length > 0 && (
                <span style={{ fontSize: "0.75rem", opacity: 0.85 }}>
                  Models verified: {testResult.models.slice(0, 3).join(", ")}
                </span>
              )}
            </div>
          )}

          {/* Quick Info Footer */}
          <div
            style={{
              padding: "12px 20px",
              background: "rgba(0, 0, 0, 0.2)",
              borderTop: "1px solid rgba(255, 255, 255, 0.05)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "0.82rem",
              color: "var(--muted)",
            }}
          >
            <span>
              Need a key? Get one in seconds for free with generous daily rate limits.
            </span>
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noreferrer"
              style={{ color: "#60a5fa", fontWeight: 600, textDecoration: "none" }}
            >
              Google AI Studio ↗
            </a>
          </div>
        </div>
      </div>

      {/* Compute & Hardware Group */}
      <div>
        <div className="ios-group-title">Hardware &amp; Compute</div>
        <div className="ios-group">
          {!d ? (
            <div style={{ padding: 20, color: "var(--muted)", fontSize: 13 }}>Detecting system hardware…</div>
          ) : (
            <>
              <div className="ios-row">
                <div className="ios-row-left">
                  <div className="ios-icon-box">💾</div>
                  <div className="ios-row-labels">
                    <span className="ios-row-title">System RAM</span>
                    <span className="ios-row-desc">Total host memory available for speech pipelines</span>
                  </div>
                </div>
                <div className="ios-row-right">
                  <span className="ios-badge">
                    {modelsInfo?.system_ram_gb ? `${modelsInfo.system_ram_gb.toFixed(1)} GB` : "Available"}
                  </span>
                </div>
              </div>

              <div className="ios-row">
                <div className="ios-row-left">
                  <div className="ios-icon-box">⚡</div>
                  <div className="ios-row-labels">
                    <span className="ios-row-title">GPU Acceleration (CUDA)</span>
                    <span className="ios-row-desc">{d.cuda_available ? (d.gpu_name || "NVIDIA CUDA GPU") : "CUDA not detected"}</span>
                  </div>
                </div>
                <div className="ios-row-right">
                  <span
                    className="ios-badge"
                    style={{
                      color: d.cuda_available ? "var(--ok)" : "var(--muted)",
                      borderColor: d.cuda_available ? "rgba(52, 199, 89, 0.3)" : "var(--line)",
                    }}
                  >
                    {d.cuda_available ? "CUDA Enabled" : "CPU Fallback"}
                  </span>
                </div>
              </div>

              <div className="ios-row">
                <div className="ios-row-left">
                  <div className="ios-icon-box">⚙️</div>
                  <div className="ios-row-labels">
                    <span className="ios-row-title">Default Compute Target</span>
                    <span className="ios-row-desc">Engine device selected for Whisper tensor operations</span>
                  </div>
                </div>
                <div className="ios-row-right">
                  <span className="ios-badge">{(d.default || "AUTO").toUpperCase()}</span>
                </div>
              </div>

              <div className="ios-row">
                <div className="ios-row-left">
                  <div className="ios-icon-box">🎙️</div>
                  <div className="ios-row-labels">
                    <span className="ios-row-title">Active Whisper Model</span>
                    <span className="ios-row-desc">Current speech transcription engine loaded in memory</span>
                  </div>
                </div>
                <div className="ios-row-right">
                  <span
                    className="ios-badge"
                    style={{
                      color: "var(--accent)",
                      background: "var(--accent-soft)",
                      borderColor: "transparent",
                      fontWeight: 700,
                    }}
                  >
                    {modelsInfo?.active_model || d.model_size || "large-v3-turbo"}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Models Catalog Group */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div className="ios-group-title" style={{ margin: 0 }}>Whisper AI Models &amp; System Requirements</div>
          {msg && <span style={{ fontSize: "0.82rem", color: "var(--accent)", fontWeight: 600 }}>{msg}</span>}
        </div>

        <div className="ios-group">
          {(modelsInfo?.models || []).map((m) => {
            const isActive = m.is_active || modelsInfo?.active_model === m.id;
            const isRec = m.tag === "Recommended";

            return (
              <div
                key={m.id}
                className="ios-row"
                style={{
                  background: isActive ? "var(--accent-soft)" : undefined,
                  alignItems: "flex-start",
                  paddingTop: 16,
                  paddingBottom: 16,
                }}
              >
                <div className="ios-row-left" style={{ alignItems: "flex-start" }}>
                  <div className="ios-icon-box" style={{ marginTop: 2 }}>
                    {isActive ? "✓" : "🤖"}
                  </div>
                  <div className="ios-row-labels">
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="ios-row-title" style={{ fontWeight: 700 }}>{m.name}</span>
                      {isRec && (
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            padding: "2px 6px",
                            borderRadius: 6,
                            background: "var(--accent)",
                            color: "#ffffff",
                          }}
                        >
                          RECOMMENDED
                        </span>
                      )}
                      <span style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--mono)" }}>
                        {m.size_label}
                      </span>
                    </div>

                    <span className="ios-row-desc" style={{ marginTop: 4 }}>{m.description}</span>

                    <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--muted-2)", marginTop: 6, flexWrap: "wrap" }}>
                      <span><b>Min RAM:</b> {m.min_ram}</span>
                      <span><b>Min VRAM:</b> {m.min_vram}</span>
                      <span><b>Recommended:</b> {m.device_rec}</span>
                    </div>
                  </div>
                </div>

                <div className="ios-row-right" style={{ alignSelf: "center", gap: 8 }}>
                  {m.is_cached && (
                    <span style={{ fontSize: 11.5, color: "var(--ok)", fontWeight: 700 }}>
                      ✓ On Disk
                    </span>
                  )}
                  <button
                    type="button"
                    className={isActive ? "btn btn-secondary" : "btn btn-primary"}
                    disabled={isActive || switching === m.id}
                    onClick={() => handleSwitchModel(m.id)}
                    style={{ fontSize: 12.5, padding: "6px 14px", borderRadius: 8 }}
                  >
                    {isActive ? "Active" : switching === m.id ? "Loading…" : m.is_cached ? "Select" : "Download & Select"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Storage & Disk Management Group */}
      <div>
        <div className="ios-group-title">Storage &amp; Cache Management</div>
        <div className="ios-group">
          <div className="ios-row">
            <div className="ios-row-left">
              <div className="ios-icon-box">🗑️</div>
              <div className="ios-row-labels">
                <span className="ios-row-title">Temporary Media Cache</span>
                <span className="ios-row-desc">
                  Safely clears temporary source videos from downloads and uploads to free disk space.
                </span>
              </div>
            </div>
            <div className="ios-row-right">
              <button
                className="btn btn-secondary"
                style={{ fontSize: 12.5, padding: "7px 14px", borderRadius: 8 }}
                onClick={async (e) => {
                  const btn = e.currentTarget;
                  btn.textContent = "Clearing…";
                  btn.disabled = true;
                  try {
                    const res = await api.cleanup();
                    const mb = (res.freed_bytes / 1024 / 1024).toFixed(1);
                    btn.textContent = `Freed ${mb} MB`;
                  } catch (err) {
                    btn.textContent = "Error";
                  }
                  setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = "Clear Cache";
                  }, 3000);
                }}
              >
                Clear Cache
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Modal Integration */}
      <GeminiKeyModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onKeySaved={() => {
          refresh();
        }}
      />
    </div>
  );
}
