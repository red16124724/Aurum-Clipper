import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Icons } from "../components/Icons.jsx";

function deriveName(entry) {
  if (entry.source_type === "upload") return entry.source || "Uploaded video";
  const url = entry.source || "";
  let m = url.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([\w-]{11})/);
  if (m) return "YouTube · " + m[1];
  try { const u = new URL(url); return u.hostname.replace(/^www\./, ""); } catch { return url || "Video"; }
}

export default function Library() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => api.history().then((h) => setHistory(Array.isArray(h) ? h : [])).catch(() => setHistory([])).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const allClips = history.flatMap((e) => (e.clips || []).map((c) => ({ ...c, entry: e })));
  const totalClips = allClips.length;

  async function del(entry, c) {
    const ref = (c.url || "").match(/\/clips\/([0-9a-f]{32})\/(\d+)\.mp4/);
    if (!ref) return;
    if (!confirm("Delete this clip from disk?")) return;
    if (await api.deleteClip(ref[1], +ref[2])) load();
  }

  if (loading) return <div className="empty">Loading…</div>;

  return (
    <>
      <div className="kpis">
        <div className="kpi"><div className="v">{history.length}</div><div className="k">Videos processed</div></div>
        <div className="kpi"><div className="v">{totalClips}</div><div className="k">Clips generated</div></div>
        <div className="kpi"><div className="v">{history.filter((e) => e.source_type === "upload").length}</div><div className="k">Uploads</div></div>
      </div>

      <div className="card-h" style={{ marginBottom: 6 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>All clips</h2>
        <button className="btn btn-ghost" onClick={load}><Icons.refresh /> Refresh</button>
      </div>

      {totalClips === 0 ? (
        <div className="empty">No clips yet — head to <b>Create</b> and generate your first short.</div>
      ) : (
        <div className="clips">
          {allClips.map((c) => (
            <div className="clip" key={c.url}>
              <video src={c.url} controls preload="metadata" />
              <div className="meta">
                <h3>{c.title || `Clip ${c.index + 1}`}</h3>
                <div className="sub">{deriveName(c.entry)}</div>
                <div className="acts">
                  <a href={c.url} download={c.filename || ""}>Download</a>
                  <button onClick={() => del(c.entry, c)}>Delete</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
