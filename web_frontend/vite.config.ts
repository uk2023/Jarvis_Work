import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import tailwindcss from '@tailwindcss/vite';

// JARVIS Organism -- V6 web frontend build/dev config.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const backendUrl =
    env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

  return {
    // ============================================================
    // PLUGINS
    // ============================================================
    plugins: [
      tailwindcss(),
    ],

    // ============================================================
    // RESOLVE
    // ============================================================
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },

    // ============================================================
    // DEV SERVER + HOT RELOAD
    // ============================================================
    server: {
      host: true,

<<<<<<< HEAD
      // Vite HMR
      hmr: true,
=======
    // Prevents a stale Vite process (e.g. from a CLI session that
    // didn't exit cleanly) silently pushing a NEW dev server onto
    // :5174/:5175 instead of :5173, which looks like "the server
    // isn't responding" when it's genuinely just on another port.
    strictPort: true,

    // NGROK / TUNNEL ACCESS (2026-09-12, from UK's live error:
    // "Blocked request. This host (...ngrok-free.dev) is not
    // allowed."). Vite 5+ rejects any Host header it doesn't
    // recognize as a defence against DNS-rebinding attacks. A tunnel
    // hostname is random per session (freeware-deflation-upcountry...
    // changes every restart), so it can never be listed literally --
    // the wildcard forms below cover ngrok's domains permanently.
    // Deliberately NOT `allowedHosts: true` (which disables the check
    // for ALL hosts): this keeps the DNS-rebinding protection intact
    // for every origin except the tunnel provider actually in use.
    allowedHosts: ['.ngrok-free.dev', '.ngrok-free.app', '.ngrok.io', '.ngrok.app', 'localhost', '127.0.0.1'],

    // REMOTE ACCESS (2026-09-12, jarvis_remote.py): when JARVIS is
    // tunneled through ngrok, only ONE port (5173, this Vite server)
    // is reachable from outside -- a tunnel maps one hostname to one
    // port, it can't also reach :8000 directly the way client.ts's
    // computeDefaultBackendUrl() does for plain localhost access. This
    // proxy lets the SAME frontend build work both ways: on localhost
    // it still connects to :8000 directly (unchanged, see client.ts),
    // and on a tunnel it falls back to these relative /api and /ws
    // paths, which Vite forwards to the real backend on 127.0.0.1:8000
    // for us. Purely additive -- does not change plain localhost
    // behavior at all.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true, changeOrigin: true },
    },
  },
>>>>>>> 90fbd2a (Save local project changes before branch checkout)

      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },

        '/ws': {
          target: backendUrl,
          ws: true,
          changeOrigin: true,
        },
      },
    },

    // ============================================================
    // BUILD
    // ============================================================
    build: {
      outDir: path.resolve(
        __dirname,
        '../frontend/dist_v6'
      ),

      emptyOutDir: true,
    },
  };
});