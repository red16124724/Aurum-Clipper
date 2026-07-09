import { useEffect, useRef, useState } from "react";
import { Icons } from "./Icons.jsx";
import Waveform from "./Waveform.jsx";

export default function Music({ tracks, track, volume, duck, musicStart, suggest, onTrack, onVolume, onDuck, onStart, onUpload, onRefresh }) {
  const ref = useRef(null);
  const audioRef = useRef(null);
  const [note, setNote] = useState("");
  const [playing, setPlaying] = useState(false);

  const current = tracks.find((t) => t.file === track);

  // Reset the play state whenever the selected track changes.
  useEffect(() => { setPlaying(false); if (audioRef.current) audioRef.current.pause(); }, [track]);

  async function pick(file) {
    if (!file) return;
    const isVideo = /\.(mp4|mov|mkv|webm|m4v|avi|flv|wmv|mpe?g|ts|m2ts)$/i.test(file.name) || file.type.startsWith("video/");
    setNote(isVideo ? `Pulling audio from ${file.name}…` : `Uploading ${file.name}…`);
    try { const t = await onUpload(file); setNote(`Added “${t.name}”.`); onTrack(t.file); }
    catch (e) { setNote(e.message); }
  }

  function togglePlay() {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play(); setPlaying(true); } else { a.pause(); setPlaying(false); }
  }

  return (
    <details className="card sect music-card" open>
      <summary className="card-h sect-h">
        <h2><span className="music-ico"><Icons.film /></span>Background music{track ? <span className="sect-badge">On</span> : null}</h2>
        <span className="sect-h-r">
          <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: 12 }}
            onClick={(e) => { e.stopPropagation(); e.preventDefault(); onRefresh(); }}><Icons.refresh /> Refresh</button>
          <span className="sect-x" />
        </span>
      </summary>

      <div className="music-grid">
        {/* Track picker + now-playing */}
        <div className="music-pick">
          {suggest && (
            <div className="music-suggest">
              <span className="ms-emoji">{suggest.emoji}</span>
              <span className="ms-text">Suggested: <b>{suggest.label}</b> — {suggest.hint}</span>
            </div>
          )}
          <label className="fieldlabel">Track</label>
          <div className="cz-select">
            <Icons.film />
            <select value={track || ""} onChange={(e) => onTrack(e.target.value)}>
              <option value="">No music</option>
              {tracks.map((t) => <option key={t.file} value={t.file}>{t.name}</option>)}
            </select>
            <span className="cz-chev" />
          </div>

          <button type="button" className="cz-upload" onClick={() => ref.current?.click()}><Icons.upload /> Upload audio or video</button>
          <input ref={ref} type="file"
            accept="audio/*,video/*,.mp3,.m4a,.wav,.aac,.ogg,.flac,.mp4,.mov,.mkv,.webm,.m4v"
            hidden onChange={(e) => pick(e.target.files[0])} />

          {track && (
            <div className={"now-playing" + (playing ? " on" : "")}>
              <button type="button" className="np-play" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                {playing
                  ? <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
                  : <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>}
              </button>
              <div className="np-info">
                <span className="np-name">{current?.name || track}</span>
                <div className="np-bars" aria-hidden="true">{Array.from({ length: 9 }).map((_, i) => <span key={i} style={{ animationDelay: `${i * 0.09}s` }} />)}</div>
              </div>
              <audio ref={audioRef} src={`/music/${encodeURIComponent(track)}`} preload="none"
                onEnded={() => setPlaying(false)} onPause={() => setPlaying(false)} onPlay={() => setPlaying(true)} />
            </div>
          )}

          {track && (
            <Waveform src={`/music/${encodeURIComponent(track)}`} start={musicStart || 0} onStart={onStart} />
          )}
        </div>

        {/* Mix controls */}
        <div className="music-mix">
          <div className="ctl">
            <label>Music volume <span className="val">{Math.round(volume)}%</span></label>
            <input type="range" className="range" min="0" max="100" value={volume} onChange={(e) => onVolume(parseFloat(e.target.value))} />
          </div>
          <div className="ctl">
            <label>Duck under voice <span className="val">{Math.round(duck)}%</span></label>
            <input type="range" className="range" min="0" max="100" value={duck} onChange={(e) => onDuck(parseFloat(e.target.value))} />
            <div className="ctl-hint">
              {duck <= 5 ? "Off — music stays at one level the whole time."
                : duck < 40 ? "Gentle — music dips a little when someone talks."
                : duck < 75 ? "Balanced — music steps back so the voice leads."
                : "Strong — music drops right down whenever there's a voice."}
            </div>
          </div>
        </div>
      </div>

      <div className="note">
        Mixed under the original voice and auto-ducked while someone's talking — subtle, reels-style.
        Upload an audio file <b>or an MP4/video</b> (we'll pull just its sound), or drop files into <b>assets/music/</b>.
      </div>
      {note && <div className="note">{note}</div>}
    </details>
  );
}
