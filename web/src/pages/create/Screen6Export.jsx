import { Icons } from "../../components/Icons.jsx";
import ClipPhone from "../../components/ClipPhone.jsx";
import { api, downloadClipBlob } from "../../api.js";

export default function Screen6Export({ clips, onBack, onRestart }) {
  async function downloadAll() {
    for (let i = 0; i < clips.length; i++) {
      const c = clips[i];
      await downloadClipBlob(c.url, c.filename || `clip-${i + 1}.mp4`);
      if (i < clips.length - 1) {
        await new Promise((r) => setTimeout(r, 600));
      }
    }
  }

  function handleReveal(c) {
    const ref = (c.url || "").match(/\/clips\/([0-9a-f]{32})\/(\d+)\.mp4/);
    if (ref) {
      api.reveal(ref[1], +ref[2]).catch(() => {});
    }
  }

  function handleOpenFolder() {
    if (clips.length > 0) {
      handleReveal(clips[0]);
    }
  }

  return (
    <div className="wizard-screen" style={{ maxWidth: 1000, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Apple Studio Export Sheet */}
      <div className="export-card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>Export Video</h2>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              {clips.length} clip{clips.length === 1 ? "" : "s"} rendered at master quality
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleOpenFolder}
              title="Open clips directory on your computer"
              style={{ borderRadius: 10 }}
            >
              <Icons.film /> Open Folder
            </button>
          </div>
        </div>

        {/* Export Spec Metadata Sheet */}
        <div className="export-meta-table">
          <div className="export-meta-row">
            <span className="export-meta-label">Output Target</span>
            <span className="export-meta-val">Short-form Video (9:16 Vertical)</span>
          </div>
          <div className="export-meta-row">
            <span className="export-meta-label">Constant Video Bitrate</span>
            <span className="export-meta-val" style={{ color: "var(--accent)" }}>10,000 kbps CBR</span>
          </div>
          <div className="export-meta-row">
            <span className="export-meta-label">Audio Quality</span>
            <span className="export-meta-val">320 kbps Stereo AAC</span>
          </div>
          <div className="export-meta-row">
            <span className="export-meta-label">Container & Codec</span>
            <span className="export-meta-val">MP4 (H.264 / HEVC Master)</span>
          </div>
          <div className="export-meta-row">
            <span className="export-meta-label">Total Ready Clips</span>
            <span className="export-meta-val">{clips.length}</span>
          </div>
        </div>

        {/* Primary Export Action */}
        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={downloadAll}
          style={{ height: 48, fontSize: 15, borderRadius: 12 }}
        >
          <Icons.download /> Download All Clips ({clips.length})
        </button>
      </div>

      {/* Rendered Clips Grid */}
      <div className="card">
        <div className="card-h">
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Generated Clips Review</h2>
          <span className="hint">{clips.length} clip{clips.length === 1 ? "" : "s"}</span>
        </div>

        <div className="clips">
          {clips.map((c) => (
            <div className="clip" key={c.index} style={{ borderRadius: 18 }}>
              <ClipPhone src={c.url} filename={c.filename} />
              <div className="meta">
                <h3>{c.title}</h3>
                <div className="sub">{(c.end - c.start).toFixed(1)}s · {c.start.toFixed(1)}–{c.end.toFixed(1)}s</div>
                <div className="acts" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ padding: "7px 10px", fontSize: "0.82rem", borderRadius: 8 }}
                    onClick={() => downloadClipBlob(c.url, c.filename)}
                  >
                    <Icons.download /> Download
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "7px 10px", fontSize: "0.82rem", borderRadius: 8 }}
                    onClick={() => handleReveal(c)}
                  >
                    <Icons.film /> Folder
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ gridColumn: "1 / -1", padding: "6px 10px", fontSize: "0.78rem" }}
                    onClick={() => navigator.clipboard.writeText(location.origin + c.url)}
                  >
                    <Icons.link /> Copy link
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="wizard-nav">
        <button className="btn btn-ghost" onClick={onBack}>← Back to review</button>
        <button className="btn btn-primary" onClick={onRestart}><Icons.bolt /> Create another video</button>
      </div>
    </div>
  );
}

