import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      // Avoid stale ESM chunks after git pull / branch switches (browser disk cache).
      headers: { "Cache-Control": "no-store" },
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
