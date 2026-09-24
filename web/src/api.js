// Thin API client for the FastAPI backend. All paths are proxied by Vite in dev
// (see vite.config.js) so these are plain same-origin fetches.

async function jget(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function jpost(path, body, signal) {
  const req = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  if (signal) req.signal = signal;
  const r = await fetch(path, req);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${path} → ${r.status}`);
  return data;
}

export const api = {
  health: () => jget("/health"),
  cleanup: () => jpost("/api/cleanup", {}),
  modelStatus: () => jget("/api/model-status"),
  modelsInfo: () => jget("/api/models-info"),
  warmup: (device = "auto", modelSize = "large-v3-turbo") =>
    jpost(`/api/warmup?device=${encodeURIComponent(device)}&model_size=${encodeURIComponent(modelSize)}`, {}),
  getApiKey: () => jget("/api/settings/api-key"),
  setApiKey: (apiKey) => jpost("/api/settings/api-key", { api_key: apiKey }),
  validateApiKey: (apiKey) => jpost("/api/gemini/validate", { api_key: apiKey }),
  geminiStatus: () => jget("/api/gemini/status"),
  devices: () => jget("/api/devices"),
  captionStyles: () => jget("/api/caption-styles"),
  fonts: () => jget("/api/fonts"),
  history: () => jget("/api/history"),
  generate: (payload) => jpost("/api/generate", payload),
  pretranscribe: (sourceId, device, language, modelSize, signal) => jpost("/api/pretranscribe", { source_id: sourceId, device, language, model_size: modelSize }, signal),
  musicSuggest: (sourceId, language, modelSize) => {
    let url = `/api/music-suggest/${sourceId}?model_size=${encodeURIComponent(modelSize)}`;
    if (language) url += `&language=${encodeURIComponent(language)}`;
    return jget(url);
  },
  transcript: (sourceId, language, modelSize) => {
    let url = `/api/transcript/${sourceId}?model_size=${encodeURIComponent(modelSize)}`;
    if (language) url += `&language=${encodeURIComponent(language)}`;
    return jget(url);
  },
  cancel: (jobId) => jpost(`/api/cancel/${jobId}`, {}),
  result: (jobId) => jget(`/api/result/${jobId}`),
  prefetch: (video_url) => jpost("/api/prefetch", { video_url }),
  prefetchStatus: (id) => jget(`/api/prefetch/${id}`),
  pretranscribeStatus: (id) => jget(`/api/pretranscribe/${id}`),
  deleteClip: async (clipId, index) => {
    const r = await fetch(`/api/clip/${clipId}/${index}`, { method: "DELETE" });
    return r.ok;
  },
  reveal: (clipId, index) => jpost("/api/reveal", { clip_id: clipId, index: Number(index) }),
  clipSourceUrl: (clipId, index) => `/api/clip/${clipId}/${index}/source`,
  reframeInfo: (clipId, index) => jget(`/api/clip/${clipId}/${index}/reframe`),
  reframeClip: (clipId, index, keyframes) => jpost(`/api/clip/${clipId}/${index}/reframe`, { keyframes }),
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

/**
 * Downloads a video via Blob to reliably trigger file saving across all webviews and browsers.
 */
export async function downloadClipBlob(url, filename) {
  const cleanFilename = filename || url.split("/").pop()?.split("?")[0] || "clip.mp4";
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("Fetch failed");
    const blob = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = cleanFilename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    }, 2000);
  } catch (e) {
    // Fallback direct click
    const a = document.createElement("a");
    a.href = url;
    a.download = cleanFilename;
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => document.body.removeChild(a), 500);
  }
}

