import { useEffect, useState, useMemo } from "react";
import { api, downloadClipBlob } from "../api.js";
import { Icons } from "../components/Icons.jsx";

function deriveName(entry) {
  if (entry.source_type === "upload") return entry.source || "Uploaded video";
  const url = entry.source || "";
  let m = url.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)([\w-]{11})/);
  if (m) return "YouTube · " + m[1];
  try { const u = new URL(url); return u.hostname.replace(/^www\./, ""); } catch { return url || "Video"; }
}

function fmtSecs(s) {
  if (s == null || !isFinite(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function Library() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const load = () =>
    api
      .history()
      .then((h) => setHistory(Array.isArray(h) ? h : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const allClips = useMemo(
    () => history.flatMap((e) => (e.clips || []).map((c) => ({ ...c, entry: e }))),
    [history]
  );
  const totalClips = allClips.length;

  const filteredClips = useMemo(() => {
    if (!query.trim()) return allClips;
    const q = query.toLowerCase();
    return allClips.filter(
      (c) =>
        (c.title || "").toLowerCase().includes(q) ||
        deriveName(c.entry).toLowerCase().includes(q)
    );
  }, [allClips, query]);

  async function del(entry, c) {
    const ref = (c.url || "").match(/\/clips\/([0-9a-f]{32})\/(\d+)\.mp4/);
    if (!ref) return;
    if (!confirm("Delete this clip from disk?")) return;
    if (await api.deleteClip(ref[1], +ref[2])) load();
  }

  function handleReveal(c) {
    const ref = (c.url || "").match(/\/clips\/([0-9a-f]{32})\/(\d+)\.mp4/);
    if (ref) {
      api.reveal(ref[1], +ref[2]).catch(() => {});
    }
  }

  if (loading) return <div className="empty">Loading your projects…</div>;

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto", display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Apple Studio Header Bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
        <div>
          <h2 style={{ fontSize: 24, fontWeight: 800, margin: 0, letterSpacing: "-0.02em" }}>Your Projects</h2>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>
            {totalClips} clip{totalClips === 1 ? "" : "s"} across {history.length} video project{history.length === 1 ? "" : "s"}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ position: "relative", minWidth: 220 }}>
            <input
              type="text"
              placeholder="Search projects…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{
                paddingLeft: 34,
                paddingTop: 8,
                paddingBottom: 8,
                fontSize: 13,
                borderRadius: 999,
                background: "var(--surface-2)",
              }}
            />
            <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--muted)", pointerEvents: "none" }}>
              🔍
            </span>
          </div>
          <button className="btn btn-secondary" onClick={load} style={{ borderRadius: 999, padding: "8px 14px", fontSize: 13 }}>
            <Icons.refresh /> Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="kpis">
        <div className="kpi">
          <div className="v">{history.length}</div>
          <div className="k">Videos processed</div>
        </div>
        <div className="kpi">
          <div className="v">{totalClips}</div>
          <div className="k">Clips generated</div>
        </div>
        <div className="kpi">
          <div className="v">{history.filter((e) => e.source_type === "upload").length}</div>
          <div className="k">Uploads</div>
        </div>
      </div>

      {totalClips === 0 ? (
        <div className="empty">No clips yet — head to <b>Create</b> and generate your first short.</div>
      ) : (
        <div className="clips" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 20 }}>
          {filteredClips.map((c) => {
            const durationSec = c.end && c.start ? c.end - c.start : 0;
            const rawDate = c.entry.created || c.entry.created_at;
            const dateStr = rawDate
              ? new Date(rawDate).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
              : "Recent";

            return (
              <div
                className="clip"
                key={c.url}
                style={{
                  borderRadius: 20,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  boxShadow: "var(--shadow-sm)",
                  transition: "transform .15s ease, box-shadow .15s ease",
                }}
              >
                {/* 16:9 Thumbnail / Video Player */}
                <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 9", background: "#000", overflow: "hidden" }}>
                  <video
                    src={c.url}
                    controls
                    preload="metadata"
                    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  />
                  {durationSec > 0 && (
                    <div
                      style={{
                        position: "absolute",
                        bottom: 8,
                        right: 8,
                        background: "rgba(0, 0, 0, 0.75)",
                        color: "#ffffff",
                        backdropFilter: "blur(4px)",
                        padding: "2px 7px",
                        borderRadius: 6,
                        fontFamily: "var(--mono)",
                        fontSize: 11,
                        fontWeight: 700,
                        pointerEvents: "none",
                      }}
                    >
                      {fmtSecs(durationSec)}
                    </div>
                  )}
                </div>

                {/* Metadata & Actions */}
                <div className="meta" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em" }}>
                      {c.title || `Clip ${c.index + 1}`}
                    </h3>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4, display: "flex", alignItems: "center", gap: 6 }}>
                      <span>{fmtSecs(durationSec)}</span>
                      <span>•</span>
                      <span>{dateStr}</span>
                      <span>•</span>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {deriveName(c.entry)}
                      </span>
                    </div>
                  </div>

                  <div className="acts" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: "auto" }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      style={{ padding: "8px 12px", fontSize: "0.85rem", borderRadius: 10 }}
                      onClick={() => downloadClipBlob(c.url, c.filename || `clip-${c.index + 1}.mp4`)}
                    >
                      <Icons.download /> Download
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: "8px 12px", fontSize: "0.85rem", borderRadius: 10 }}
                      onClick={() => handleReveal(c)}
                    >
                      <Icons.film /> Folder
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ gridColumn: "1 / -1", padding: "6px 10px", fontSize: "0.8rem", color: "var(--danger)" }}
                      onClick={() => del(c.entry, c)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

