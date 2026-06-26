import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The FastAPI backend runs on 127.0.0.1:8000. Proxy the API + asset routes so the
// React dev server (5173) can call them same-origin (no CORS, real SSE streaming).
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/clips": { target: backend, changeOrigin: true },
      "/fonts": { target: backend, changeOrigin: true },
      "/music": { target: backend, changeOrigin: true },
      "/health": { target: backend, changeOrigin: true },
    },
  },
  // Build into ../static-react so FastAPI could serve it in production if wanted.
  build: { outDir: "dist", emptyOutDir: true },
});
