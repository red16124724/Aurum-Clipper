# ClipForge — React Dashboard

A modern React (Vite) frontend for the local AI Video Clipper. It talks to the
existing FastAPI backend over the same API the vanilla UI uses, so nothing on the
Python side changes.

## Run (development)

1. Start the backend (from the project root):

   ```
   uvicorn app.main:app --reload      # serves on http://127.0.0.1:8000
   ```

2. Start the dashboard:

   ```
   cd web
   npm install        # first time only
   npm run dev        # http://localhost:5173 (or next free port)
   ```

Vite proxies `/api`, `/clips`, `/fonts`, and `/health` to the backend on
`:8000` (see `vite.config.js`), so the React app runs same-origin — real SSE
progress streaming works out of the box.

## Build (production)

```
npm run build        # outputs to web/dist
```

You can serve `web/dist` from any static host, or wire FastAPI to serve it.

## Structure

- `src/api.js` — API client + SSE helper
- `src/App.jsx` — shell (sidebar + topbar + routing)
- `src/pages/Create.jsx` — source → output settings → caption style → generate (live progress) → results
- `src/pages/Library.jsx` — history of every generated clip
- `src/pages/Settings.jsx` — compute device info
- `src/captionStyle.js` — caption-preset → preview style
- `src/styles.css` — premium dark theme
