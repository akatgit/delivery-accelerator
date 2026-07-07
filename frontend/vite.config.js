import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// ASDA frontend (ARCHITECTURE_v2.0.md section 11): talks to the FastAPI
// backend at VITE_API_BASE_URL (default http://localhost:8000), proxied here
// during development so the browser can call relative "/api/..." paths
// without a CORS round trip.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
