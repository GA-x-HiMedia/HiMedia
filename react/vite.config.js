import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The agent API runs as a separate Python process. Proxying /api through the
// dev server keeps the browser on one origin, so there is no CORS to think
// about and the fetch calls in src/api.js can stay relative.
//
// Point it somewhere else with:  VITE_API_TARGET=http://127.0.0.1:8010 npm run dev
const target = process.env.VITE_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
        // The chat endpoint is server-sent events. Without this the proxy
        // buffers the whole response and every status update arrives at
        // once, after the reply — which defeats the point of streaming.
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            proxyRes.headers["cache-control"] = "no-cache, no-transform";
          });
        },
      },
    },
  },
});
