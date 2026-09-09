import path from 'path';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

// JARVIS Organism -- V6 web frontend build/dev config.
//
// No backend proxy here anymore (there used to be a /api and /ws
// rewrite rule pointing at the FastAPI backend) -- the frontend now
// connects to the backend DIRECTLY by hostname:8000 instead (see
// src/api/client.ts's computeDefaultBackendUrl()), since the backend's
// CORS is already open to any origin. That means this file no longer
// needs any project-specific customization to work correctly, and a
// fresh AI Studio export's own vite.config.ts can safely replace this
// one without breaking the connection to the real backend.
export default defineConfig({
  plugins: [
    tailwindcss(),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },

  server: {
    host: true,
    hmr: true,

    // Prevents a stale Vite process (e.g. from a CLI session that
    // didn't exit cleanly) silently pushing a NEW dev server onto
    // :5174/:5175 instead of :5173, which looks like "the server
    // isn't responding" when it's genuinely just on another port.
    strictPort: true,
  },

  build: {
    // Where cli.py's backend looks for the production build (see
    // backend/config.py's FRONTEND_V6_DIST_DIR). Only matters for the
    // build+serve-from-backend workflow (CLI option 2) -- the normal
    // `npm run dev` workflow doesn't read this at all, so even if a
    // future AI Studio export's vite.config.ts overwrites this with
    // its own default `dist/` output path, daily development still
    // works; only that one specific production-build workflow would
    // need this path restored.
    outDir: path.resolve(__dirname, '../frontend/dist_v6'),
    emptyOutDir: true,
  },
});
