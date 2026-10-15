import { defineConfig } from "vite";
import { createRequire } from "node:module";
const policy = createRequire(import.meta.url)("./desktop/policy.cjs");
import { planValidatorPlugin } from "./scripts/plan-validator-plugin.mjs";
export default defineConfig({
  base: "./",
  plugins: [planValidatorPlugin()],
  // Arena forwards an ephemeral hostname; this local, static-only dev server
  // contains no credentials or API. Do not expose it to an untrusted network.
  server: {
    host: "0.0.0.0",
    allowedHosts: [".e2b.app"],
    port: 5173,
    strictPort: true,
  },
  preview: {
    headers: { "Content-Security-Policy": policy.contentSecurityPolicy() },
    host: "0.0.0.0",
    allowedHosts: [".e2b.app"],
    port: 4173,
    strictPort: true,
  },
});
