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

      // Vite HMR
      hmr: true,

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