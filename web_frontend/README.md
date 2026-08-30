# JARVIS Organism -- Web Frontend (V6)

React + TypeScript + Vite UI for the JARVIS Organism backend
(`backend/server.py`, FastAPI). This replaces the old Node/Express
mock server entirely -- every endpoint it calls now hits the real
organism (see `backend/routes_frontend_v6.py`).

## Dev (hot reload)

```bash
cd web_frontend
npm install
npm run dev
```

Vite's dev server proxies `/api` and `/ws` to `http://127.0.0.1:8000`
by default -- start the Python backend first (`python3 cli.py` or
however you normally run it), then `npm run dev` here and edit
components; changes appear instantly, no rebuild.

If the backend is running somewhere else (e.g. on your Android device
while you develop from a laptop on the same network), copy
`.env.example` to `.env` and set `VITE_BACKEND_URL` to that machine's
address.

## Production build

```bash
cd web_frontend
npm install
npm run build
```

This outputs straight into `../frontend/dist_v6`. The backend
(`backend/routes_http.py`) automatically serves that build at `/`
once it exists -- no copy step, no separate server process. If the
build doesn't exist yet, the backend falls back to the legacy static
dashboard in `frontend/`.

## What talks to what

Every network call this app makes lives in `src/App.tsx`. No other
component touches the network. Endpoints:

| Endpoint | Real data source |
|---|---|
| `GET /api/organism/state` | heartbeat, Brain.status(), all attached organs |
| `GET/POST/DELETE /api/memory/engrams` | `SemanticMemory` (FAISS + SQLite) |
| `GET/POST /api/autonomy/state`, `/trigger-idle` | `GoalManager`, `Curiosity`, `IdleLoop`, `EvolutionEngine` |
| `POST /api/chat` | `Brain.think_and_respond()` -- same pipeline as the CLI and `/ws` |
| `GET/POST /api/sessions`, `GET /api/history` | `backend/database.py` (SQLite chat history) |
