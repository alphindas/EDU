import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev proxy: browser talks only to :5173; /api -> FastAPI (8000), /vision -> Flask vision service (5000).
const api = process.env.VITE_API_TARGET ?? "http://localhost:8000";
const vision = process.env.VITE_VISION_TARGET ?? "http://localhost:5000";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: { manualChunks: { react: ["react", "react-dom", "react-router-dom"], charts: ["recharts"], i18n: ["i18next", "react-i18next"] } },
    },
  },
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: api, changeOrigin: true, ws: true }, // ws: CHITTI live messages + bus tracking
      "/vision": { target: vision, changeOrigin: true, rewrite: (p) => p.replace(/^\/vision/, "") },
    },
  },
});
