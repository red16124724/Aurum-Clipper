// Thin API client for the FastAPI backend. All paths are proxied by Vite in dev
// (see vite.config.js) so these are plain same-origin fetches.

async function jget(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function jpost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${path} → ${r.status}`);
  return data;
}

export const api = {
  health: () => jget("/health"),
  devices: () => jget("/api/devices"),
  captionStyles: () => jget("/api/caption-styles"),
  fonts: () => jget("/api/fonts"),
  history: () => jget("/api/history"),
  generate: (payload) => jpost("/api/generate", payload),
  cancel: (jobId) => jpost(`/api/cancel/${jobId}`, {}),
  musicSuggest: (sourceId, language) => jget(`/api/music-suggest/${sourceId}` + (language ? `?language=${encodeURIComponent(language)}` : "")),
  transcript: (sourceId, language) => jget(`/api/transcript/${sourceId}` + (language ? `?language=${encodeURIComponent(language)}` : "")),
  result: (jobId) => jget(`/api/result/${jobId}`),
  prefetch: (video_url) => jpost("/api/prefetch", { video_url }),
  prefetchStatus: (id) => jget(`/api/prefetch/${id}`),
  pretranscribe: (source_id, device, language) => jpost("/api/pretranscribe", { source_id, device, language }),
  pretranscribeStatus: (id) => jget(`/api/pretranscribe/${id}`),
  deleteClip: async (clipId, index) => {
    const r = await fetch(`/api/clip/${clipId}/${index}`, { method: "DELETE" });
    return r.ok;
  },
  music: () => jget("/api/music"),
  uploadMusic: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/music/upload", { method: "POST", body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Music upload failed.");
    return d; // { name, file }
  },
  uploadFont: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/fonts/upload", { method: "POST", body: fd });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Font upload failed.");
    return d; // { family, file }
  },
  upload: async (file, onProgress) =>
    new Promise((resolve, reject) => {
      const fd = new FormData();
      fd.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/upload");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        let d = {};
        try { d = JSON.parse(xhr.responseText); } catch {}
        if (xhr.status === 200 && d.upload_id) resolve(d);
        else reject(new Error(d.detail || "Upload failed."));
      };
      xhr.onerror = () => reject(new Error("Upload failed — network error."));
      xhr.send(fd);
    }),
};

// Subscribe to a job's Server-Sent Events. Returns a close() fn.
export function streamProgress(jobId, onSnap, onError) {
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = (ev) => {
    try { onSnap(JSON.parse(ev.data)); } catch {}
  };
  es.onerror = async () => {
    es.close();
    // Fall back to a one-shot result fetch so we don't lose the final state.
    try {
      const r = await fetch(`/api/result/${jobId}`);
      if (r.ok) { onSnap(await r.json()); return; }
    } catch {}
    if (onError) onError();
  };
  return () => es.close();
}
