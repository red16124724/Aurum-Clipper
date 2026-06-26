import { useRef, useState } from "react";
import { Icons } from "./Icons.jsx";

export default function Music({ tracks, track, volume, duck, onTrack, onVolume, onDuck, onUpload, onRefresh }) {
  const ref = useRef(null);
  const [note, setNote] = useState("");
  const audioRef = useRef(null);

  async function pick(file) {
    if (!file) return;
    const isVideo = /\.(mp4|mov|mkv|webm|m4v|avi|flv|wmv|mpe?g|ts|m2ts)$/i.test(file.name) || file.type.startsWith("video/");
    setNote(isVideo ? `Pulling audio from ${file.name}…` : `Uploading ${file.name}…`);
    try { const t = await onUpload(file); setNote(`Added “${t.name}”.`); onTrack(t.file); }
    catch (e) { setNote(e.message); }
  }

  return (
    <details className="card sect">
      <summary className="card-h sect-h">
        <h2>Background music{track ? <span className="sect-badge">On</span> : null}</h2>
        <span className="sect-h-r">
          <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: 12 }}
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); onRefresh(); }}><Icons.refresh /> Refresh</button>
          <span className="sect-x" />
        </span>
      </summary>

      <div className="music-row">
        <select value={track || ""} onChange={(e) => onTrack(e.target.value)}>
          <option value="">No music</option>
          {tracks.map((t) => <option key={t.file} value={t.file}>{t.name}</option>)}
        </select>
        <button type="button" className="btn" onClick={() => ref.current?.click()}><Icons.upload /> Upload</button>
        <input ref={ref} type="file"
          accept="audio/*,video/*,.mp3,.m4a,.wav,.aac,.ogg,.flac,.mp4,.mov,.mkv,.webm,.m4v"
          hidden onChange={(e) => pick(e.target.files[0])} />
      </div>

      {track && (
        <audio ref={audioRef} className="music-prev" controls src={`/music/${encodeURIComponent(track)}`} preload="none" />
      )}

      <div className="ctl" style={{ marginTop: 14 }}>
        <label>Music volume <span className="val">{Math.round(volume)}%</span></label>
        <input type="range" className="range" min="0" max="100" value={volume} onChange={(e) => onVolume(parseFloat(e.target.value))} />
      </div>

      <div className="ctl" style={{ marginTop: 14 }}>
        <label>Duck under voice <span className="val">{Math.round(duck)}%</span></label>
        <input type="range" className="range" min="0" max="100" value={duck} onChange={(e) => onDuck(parseFloat(e.target.value))} />
        <div className="ctl-hint">
          {duck <= 5 ? "Off — music stays at one level the whole time."
            : duck < 40 ? "Gentle — music dips a little when someone talks."
            : duck < 75 ? "Balanced — music steps back so the voice leads."
            : "Strong — music drops right down whenever there's a voice."}
        </div>
      </div>

      <div className="note">
        Mixed under the original voice and auto-ducked while someone's talking — subtle, reels-style.
        Raise <b>Duck under voice</b> if the music is fighting the speaker, lower it if you want the music
        more present in the quiet bits. Upload an audio file <b>or an MP4/video</b> — we'll pull just its
        sound out to use as music. Or drop files into <b>assets/music/</b> to add your own.
      </div>
      {note && <div className="note">{note}</div>}
    </details>
  );
}
