import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During `npm run dev`, the React app runs on its own port (5173 by default) and
// proxies API calls to the FastAPI server on :3000. In production, FastAPI serves
// the built static files directly.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/gtm_os/server/frontend_dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:3000",
    },
  },
});
