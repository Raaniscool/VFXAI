import { createServer } from "vite";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
let server,
  child,
  stopping = false;
async function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  child?.kill();
  await server?.close();
  process.exitCode = code;
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop());
try {
  // Own this server: automatically selected loopback-only port, no reused or orphaned external server.
  server = await createServer({
    root,
    server: { host: "127.0.0.1", port: 5173, strictPort: false },
  });
  await server.listen();
  const port = server.httpServer.address().port;
  const devURL = `http://127.0.0.1:${port}/`;
  const executable = createRequire(import.meta.url)("electron");
  const env = { ...process.env, VFXAI_DEV_URL: devURL };
  delete env.ELECTRON_RUN_AS_NODE;
  console.log(
    `[VFXAI] Opening desktop window. Closing it also stops ${devURL}`,
  );
  child = spawn(executable, ["."], { cwd: root, env, stdio: "inherit" });
  child.once("error", (error) => {
    console.error(error);
    void stop(1);
  });
  child.once("exit", (code, signal) => void stop(code ?? (signal ? 1 : 0)));
} catch (error) {
  console.error("[VFXAI] Could not start desktop development:", error.message);
  await stop(1);
}
