import { defineConfig } from "vite";
import { createRequire } from "node:module";
const policy = createRequire(import.meta.url)("./desktop/policy.cjs");
import { planValidatorPlugin } from "./scripts/plan-validator-plugin.mjs";
export default defineConfig({
  base: "./",
  plugins: [planValidatorPlugin()],
  // The normal local workflow binds Vite to loopback alongside the Python API.
  // Sandbox previews may explicitly override the host; relative /api calls are
  // proxied to Python and remote preview Origin headers are stripped.
  server: {
    host: "127.0.0.1",
    allowedHosts: [".e2b.app"],
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
        configure: (proxy) => proxy.on("proxyReq", (request) => request.removeHeader("origin")),
      },
    },
  },
  preview: {
    headers: { "Content-Security-Policy": policy.contentSecurityPolicy() },
    host: "127.0.0.1",
    allowedHosts: [".e2b.app"],
    port: 4173,
    strictPort: true,
  },
});
