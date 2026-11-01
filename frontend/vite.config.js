import { defineConfig } from "vite";
const target = process.env.TRIPSYNC_API_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  server: { proxy: { "/api": target, "/ws": { target, ws: true } } },
});
