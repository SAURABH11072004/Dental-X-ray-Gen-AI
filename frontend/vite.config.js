import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// The dev server proxies /api to the FastAPI backend and adds the API token on the SERVER side (token: DENTAMIND_API_TOKEN, or runtime/api_token.txt
// created by the backend). The token is never bundled into browser code. Override the target with VITE_API_TARGET in frontend/.env.
function apiToken() {
  if (process.env.DENTAMIND_API_TOKEN) return process.env.DENTAMIND_API_TOKEN.trim();
  try { return fs.readFileSync(path.resolve(__dirname, "..", "runtime", "api_token.txt"), "utf8").trim(); } catch { return ""; }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_TARGET || "http://127.0.0.1:8000",
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on("proxyReq", (proxyReq) => {
              const t = apiToken();                       // read per request: works whichever of backend/frontend started first
              if (t) proxyReq.setHeader("Authorization", `Bearer ${t}`);
            });
          },
        },
      },
    },
  };
});
