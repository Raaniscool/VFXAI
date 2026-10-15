import { _electron as electron } from "@playwright/test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { mkdir, readFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import plan from "../examples/lightning-burst.vfx.json" with { type: "json" };

// Real Electron, bundled UI, no Vite server. On Linux use xvfb-run.
// This test must fail (not silently skip) if Electron/download/display is unavailable.
const root = fileURLToPath(new URL("../", import.meta.url));
const executable = process.env.VFXAI_DESKTOP_EXECUTABLE;
const profile = await mkdtemp(path.join(tmpdir(), "vfxai-desktop-test-"));
let desktop;
const errors = [];
try {
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.VFXAI_DEV_URL;
  desktop = await electron.launch({
    executablePath: executable || undefined,
    args: [
      ...(executable ? [] : [root]),
      `--user-data-dir=${profile}`,
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ],
    cwd: root,
    env,
    timeout: 60000,
  });
  const page = await desktop.firstWindow();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.locator("#viewport canvas").waitFor();
  assert.equal(page.url(), "vfxai://app/index.html");
  await page.waitForFunction(
    () => document.querySelector("#time").textContent !== "0.00 / 1.50 s",
  );
  assert.equal(await page.locator("#message").isVisible(), false);
  assert.equal(await page.locator(".component").count(), 5);
  assert.equal(await page.locator("#objects").textContent(), "13 / 64");
  const security = await desktop.evaluate(({ BrowserWindow, app }) => ({
    preferences:
      BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences(),
    packaged: app.isPackaged,
  }));
  assert.equal(security.preferences.sandbox, true);
  assert.equal(security.preferences.nodeIntegration, false);
  assert.equal(security.preferences.contextIsolation, true);
  if (executable) assert.equal(security.packaged, true);
  assert.deepEqual(
    await page.evaluate(() => [typeof window.require, typeof window.process]),
    ["undefined", "undefined"],
  );
  await page.getByRole("button", { name: "Pause animation" }).click();
  await page.locator("#scrub").evaluate((input) => {
    input.value = "0.38";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.waitForFunction(
    () => parseInt(document.querySelector("#draw-calls").textContent) === 14,
  );
  const brightPixels = await page.locator("canvas").evaluate(
    (canvas) =>
      new Promise((resolve) =>
        requestAnimationFrame(() => {
          const gl = canvas.getContext("webgl2");
          const data = new Uint8Array(
            gl.drawingBufferWidth * gl.drawingBufferHeight * 4,
          );
          gl.readPixels(
            0,
            0,
            gl.drawingBufferWidth,
            gl.drawingBufferHeight,
            gl.RGBA,
            gl.UNSIGNED_BYTE,
            data,
          );
          let bright = 0;
          for (let i = 0; i < data.length; i += 4)
            if (data[i + 2] > 100 && data[i + 3] > 20) bright++;
          resolve(bright);
        }),
      ),
  );
  assert.ok(brightPixels > 100, `No visible effect pixels: ${brightPixels}`);
  // native chooser UI is left to a human; supply files to the same input for automation.
  const modified = structuredClone(plan);
  modified.name = "Desktop smoke";
  modified.seed = 99;
  const upload = (value) =>
    page
      .locator("#file")
      .setInputFiles({
        name: "test.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(value)),
      });
  await upload(modified);
  await page.waitForFunction(
    () =>
      document.querySelector("#effect-name").textContent === "Desktop smoke",
  );
  const bad = structuredClone(modified);
  bad.duration = -1;
  await upload(bad);
  await page.locator("#message").waitFor({ state: "visible" });
  assert.equal(await page.locator("#effect-name").textContent(), modified.name);
  await page.locator("#sample").click();
  // Set the download destination in the test only, to avoid blocking on Save As.
  const savePath = path.join(profile, "saved-plan.json");
  await desktop.evaluate(({ session }, file) => {
    globalThis.vfxaiSaved = null;
    session.defaultSession.once("will-download", (_event, item) => {
      item.setSavePath(file);
      item.once("done", (_e, state) => {
        globalThis.vfxaiSaved = state;
      });
    });
  }, savePath);
  await page.locator("#download").click();
  await page.waitForTimeout(200);
  for (let attempt = 0; attempt < 100; attempt++) {
    if ((await desktop.evaluate(() => globalThis.vfxaiSaved)) === "completed")
      break;
    if (attempt === 99)
      throw new Error("Desktop JSON download did not complete");
    await page.waitForTimeout(100);
  }
  assert.deepEqual(JSON.parse(await readFile(savePath, "utf8")), plan);
  await page.locator("#plan-tab").click();
  assert.deepEqual(JSON.parse(await page.locator("#json").textContent()), plan);
  await page.locator("#preview-tab").click();
  const csp = await desktop.evaluate(async ({ session }) =>
    (await session.defaultSession.fetch("vfxai://app/index.html")).headers.get(
      "Content-Security-Policy",
    ),
  );
  assert.ok(csp.includes("script-src 'self'"));
  assert.ok(!csp.includes("unsafe-eval"));
  await mkdir(".artifacts", { recursive: true });
  await page.screenshot({ path: ".artifacts/desktop-electron.png" });
  assert.deepEqual(errors, []);
  console.log(
    `PASS: real Electron ${executable ? "packaged executable" : "source entry"}, bundled protocol without server, WebGL pixels, sandbox, playback/seek, plan validation, save/download, strict CSP.`,
  );
} finally {
  await desktop?.close();
  await rm(profile, { recursive: true, force: true });
}
