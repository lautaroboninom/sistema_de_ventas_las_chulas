import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(() => ({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: process.env.VITE_DEV_PROXY_TARGET || "http://api:8000",
        changeOrigin: false,
        secure: false,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    // Habilitar sourcemaps opcionalmente para debug de producción
    sourcemap: process.env.VITE_SOURCEMAP === '1',
  },
}));
