import fs from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

function parseCsvEnv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

const certFile = String(process.env.VITE_DEV_TLS_CERT_FILE || "").trim();
const keyFile = String(process.env.VITE_DEV_TLS_KEY_FILE || "").trim();
const hasTls = Boolean(certFile && keyFile && fs.existsSync(certFile) && fs.existsSync(keyFile));

const devHost = String(process.env.VITE_DEV_HOST || "0.0.0.0").trim() || "0.0.0.0";
const devHmrHost = String(process.env.VITE_DEV_HMR_HOST || "").trim();
const allowedHosts = parseCsvEnv(process.env.VITE_DEV_ALLOWED_HOSTS);
if (devHmrHost && !allowedHosts.includes(devHmrHost)) {
  allowedHosts.push(devHmrHost);
}

const devPort = hasTls ? 443 : 5173;
const hmrClientPort = hasTls ? 443 : devPort;

export default defineConfig(() => ({
  plugins: [react()],
  server: {
    port: devPort,
    strictPort: true,
    host: devHost,
    ...(hasTls
      ? {
          https: {
            cert: fs.readFileSync(certFile),
            key: fs.readFileSync(keyFile),
          },
        }
      : {}),
    ...(devHmrHost
      ? {
          hmr: {
            protocol: hasTls ? "wss" : "ws",
            host: devHmrHost,
            clientPort: hmrClientPort,
          },
        }
      : {}),
    ...(allowedHosts.length ? { allowedHosts } : {}),
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
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
    // Habilitar sourcemaps opcionalmente para debug de produccion
    sourcemap: process.env.VITE_SOURCEMAP === "1",
  },
}));
