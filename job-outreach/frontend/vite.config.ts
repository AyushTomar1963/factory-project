import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In dev, /api is proxied to the backend so the browser stays same-origin (no CORS),
// exactly like the Vercel rewrite does in production.
export default defineConfig({
  // GitHub Pages serves the app from /<repo>/; Vercel serves it from /.
  base: process.env.VITE_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": process.env.BACKEND_URL ?? "http://localhost:8000",
    },
  },
});
