import { useEffect, useRef, useState } from "react";

// Decode an audio URL in the browser, draw its waveform + auto-detected beats, and
// let the user choose where the music starts: clicking snaps to the nearest beat,
// and the chosen start (seconds) is reported via onStart for the render to use.
export default function Waveform({ src, start, onStart }) {
  const canvasRef = useRef(null);
  const [peaks, setPeaks] = useState(null);
  const [beats, setBeats] = useState([]);
  const [dur, setDur] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // Decode + analyze whenever the track changes.
  useEffect(() => {
    if (!src) { setPeaks(null); setBeats([]); setDur(0); return; }
    let cancelled = false;
    setLoading(true); setErr("");
    (async () => {
      try {
        const res = await fetch(src);
        const arr = await res.arrayBuffer();
        const Ctx = window.AudioContext || window.webkitAudioContext;
        const ac = new Ctx();
        const audio = await ac.decodeAudioData(arr);
        try { ac.close(); } catch { /* ignore */ }
        if (cancelled) return;

        const ch = audio.getChannelData(0);
        const sr = audio.sampleRate;

        // Waveform peaks (downsampled).
        const N = 640;
        const block = Math.max(1, Math.floor(ch.length / N));
        const pk = new Float32Array(N);
        for (let i = 0; i < N; i++) {
          let m = 0;
          for (let j = 0; j < block; j++) { const v = Math.abs(ch[i * block + j] || 0); if (v > m) m = v; }
          pk[i] = m;
        }

        // Beat/onset detection: short-window energy, peaks above a local average.
        const hop = 1024;
        const frames = Math.floor(ch.length / hop);
        const energy = new Float32Array(frames);
        for (let i = 0; i < frames; i++) {
          let s = 0;
          for (let j = 0; j < hop; j++) { const v = ch[i * hop + j] || 0; s += v * v; }
          energy[i] = s / hop;
        }
        const win = Math.max(4, Math.floor((0.4 * sr) / hop));
        const det = [];
        let last = -1e9;
        for (let i = 1; i < frames - 1; i++) {
          let avg = 0, cnt = 0;
          for (let k = Math.max(0, i - win); k < Math.min(frames, i + win); k++) { avg += energy[k]; cnt++; }
          avg /= cnt || 1;
          const t = (i * hop) / sr;
          if (energy[i] > avg * 1.5 && energy[i] >= energy[i - 1] && energy[i] > energy[i + 1] && t - last > 0.27) {
            det.push(+t.toFixed(3)); last = t;
          }
        }
        setPeaks(pk); setBeats(det); setDur(audio.duration); setLoading(false);
      } catch {
        if (!cancelled) { setErr("Couldn't analyze this track."); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [src]);

  // Draw the waveform + beats + start handle.
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || !peaks) return;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr;
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const n = peaks.length, bw = w / n;
    for (let i = 0; i < n; i++) {
      const ph = Math.max(1, peaks[i] * h * 0.92);
      const t = dur ? (i / n) * dur : 0;
      g.fillStyle = t < start ? "rgba(124,77,255,0.22)" : "rgba(179,157,255,0.9)";
      g.fillRect(i * bw, (h - ph) / 2, Math.max(1, bw - 0.6), ph);
    }
    g.fillStyle = "rgba(255,255,255,0.16)";
    beats.forEach((t) => g.fillRect((t / (dur || 1)) * w, 0, 1, h));
    const sx = (start / (dur || 1)) * w;
    g.fillStyle = "#7c4dff"; g.fillRect(sx - 1.5, 0, 3, h);
    g.fillStyle = "#fff"; g.beginPath(); g.arc(sx, 7, 5, 0, Math.PI * 2); g.fill();
  }, [peaks, beats, dur, start]);

  const pick = (e) => {
    const cv = canvasRef.current;
    if (!cv || !dur) return;
    const r = cv.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    let t = frac * dur, best = t, bd = 0.45;
    beats.forEach((b) => { const d = Math.abs(b - t); if (d < bd) { bd = d; best = b; } });
    onStart(+best.toFixed(2));
  };

  if (!src) return null;
  return (
    <div className="wave">
      <div className="wave-head">
        <span>Beat analysis</span>
        <span className="wave-start">
          {loading ? "Analyzing…" : err ? err : `Start ${start.toFixed(1)}s · ${beats.length} beats`}
        </span>
      </div>
      <canvas ref={canvasRef} className="wave-canvas" onClick={pick} />
      <div className="wave-row">
        <span className="wave-hint">Click to set the music start — snaps to the nearest beat.</span>
        {start > 0 && <button type="button" className="wave-reset" onClick={() => onStart(0)}>Reset</button>}
      </div>
    </div>
  );
}
