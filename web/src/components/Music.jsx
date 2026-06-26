import { useRef, useState } from "react";
import { Icons } from "./Icons.jsx";

export default function Music({ tracks, track, volume, onTrack, onVolume, onUpload, onRefresh }) {
  const ref = useRef(null);
  const [note, setNote] = useState("");
  const audioRef = useRef(null);

  async function pick(file) {
    if (!file) return;
    setNote(`Uploading ${file.name}…`);
    try { const t = await onUpload(file); setNote(`Added “${t.name}”.`); onTrack(t.file); }
    catch (e) { setNote(e.message); }
  }

  return (
    <div className="card">
      <div className="card-h">
        <h2>Background music</h2>
        <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: 12 }} onClick={onRefresh}><Icons.refresh /> Refresh</button>
      </div>

      <div className="music-row">
        <select value={track || ""} onChange={(e) => onTrack(e.target.value)}>
          <option value="">No music</option>
          {tracks.map((t) => <option key={t.file} value={t.file}>{t.name}</option>)}
        </select>
        <button type="button" className="btn" onClick={() => ref.current?.click()}><Icons.upload /> Upload</button>
        <input ref={ref} type="file" accept="audio/*,.mp3,.m4a,.wav,.aac,.ogg,.flac" hidden onChange={(e) => pick(e.target.files[0])} />
      </div>

      {track && (
        <audio ref={audioRef} className="music-prev" controls src={`/music/${encodeURIComponent(track)}`} preload="none" />
      )}

      <div className="ctl" style={{ marginTop: 14 }}>
        <label>Music volume <span className="val">{Math.round(volume)}%</span></label>
        <input type="range" className="range" min="0" max="100" value={volume} onChange={(e) => onVolume(parseFloat(e.target.value))} />
      </div>
      <div className="note">
        Mixed under the original voice and auto-ducked while someone's talking — subtle, reels-style.
        Drop files into <b>assets/music/</b> to add your own, or upload above.
      </div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}
