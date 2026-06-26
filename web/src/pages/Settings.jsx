import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Settings() {
  const [d, setD] = useState(null);
  useEffect(() => { api.devices().then(setD).catch(() => setD({ devices: [], cuda_available: false })); }, []);

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <div className="card-h"><h2>Compute</h2></div>
      {!d ? <div className="note">Checking…</div> : (
        <>
          <div className="row" style={{ justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
            <span className="note" style={{ margin: 0 }}>GPU (CUDA)</span>
            <b>{d.cuda_available ? (d.gpu_name || "Available") : "Not available"}</b>
          </div>
          <div className="row" style={{ justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid var(--line)" }}>
            <span className="note" style={{ margin: 0 }}>Active device</span>
            <b>{(d.default || "—").toUpperCase()}</b>
          </div>
          <div className="row" style={{ justifyContent: "space-between", padding: "10px 0" }}>
            <span className="note" style={{ margin: 0 }}>Available</span>
            <b>{(d.devices || []).map((x) => x.toUpperCase()).join(" · ") || "—"}</b>
          </div>
          <div className="note" style={{ marginTop: 16 }}>
            Everything runs locally — yt-dlp downloads, faster-whisper transcribes, and ffmpeg renders.
            No video or audio leaves this machine.
          </div>
        </>
      )}
    </div>
  );
}
