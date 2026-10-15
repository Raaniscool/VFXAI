import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";
import plan from "../examples/lightning-burst.vfx.json" with { type: "json" };

// Run a dev/preview server separately. Install Chromium with `npx playwright install chromium`.
// Arena used an npm-distributed Chromium because its network disallows the browser CDN.
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
  args: [
    "--no-sandbox",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
  ],
});
const failures = [];
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
page.on("pageerror", (error) => failures.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") failures.push(message.text());
});
const upload = async (value) =>
  page
    .locator("#file")
    .setInputFiles({
      name: "test.vfx.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        typeof value === "string" ? value : JSON.stringify(value),
      ),
    });
try {
  await page.goto(process.env.VFX_TEST_URL || "http://127.0.0.1:5173");
  await page.locator("#viewport canvas").waitFor();
  await page.waitForFunction(
    () => parseFloat(document.querySelector("#time").textContent) > 0.1,
  );
  assert.equal(await page.locator("#message").isVisible(), false);
  assert.equal(await page.locator(".component").count(), 5);
  assert.equal(await page.locator("#objects").textContent(), "13 / 64");
  assert.equal(await page.locator("#particles").textContent(), "96 / 128");
  await page.getByRole("button", { name: "Pause animation" }).click();
  await page.locator("#scrub").evaluate((input) => {
    input.value = "0.38";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  const paused = await page.locator("#time").textContent();
  await page.waitForTimeout(180);
  assert.equal(await page.locator("#time").textContent(), paused);
  assert.equal(
    await page
      .getByRole("button", { name: "Play animation", exact: true })
      .count(),
    1,
  );
  await page.waitForFunction(
    () => parseInt(document.querySelector("#draw-calls").textContent) === 14,
  );
  // Active effect draws all 13 objects plus the ground grid. Test canvas pixels,
  // not merely the presence of a canvas node or textual metadata.
  const pixels = await page.locator("#viewport canvas").evaluate(
    (canvas) =>
      new Promise((resolve) =>
        requestAnimationFrame(() => {
          const gl = canvas.getContext("webgl2");
          const width = gl.drawingBufferWidth,
            height = gl.drawingBufferHeight;
          const data = new Uint8Array(width * height * 4);
          gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);
          let bright = 0;
          for (let i = 0; i < data.length; i += 4)
            if (data[i + 2] > 100 && data[i + 3] > 20) bright++;
          resolve({ bright, width, height });
        }),
      ),
  );
  assert.ok(
    pixels.bright > 100,
    `Expected visible blue effect pixels: ${JSON.stringify(pixels)}`,
  );
  await mkdir(".artifacts", { recursive: true });
  await page.screenshot({ path: ".artifacts/preview-desktop.png" });
  await page.getByRole("button", { name: "Toggle ground grid" }).click();
  assert.equal(
    await page.locator("#grid").getAttribute("aria-pressed"),
    "false",
  );
  await page.waitForFunction(
    () => parseInt(document.querySelector("#draw-calls").textContent) === 13,
  );
  await page.getByRole("button", { name: "Reset camera" }).click();
  await page.locator("#plan-tab").click();
  assert.deepEqual(JSON.parse(await page.locator("#json").textContent()), plan);
  await page.locator("#preview-tab").click();
  const changed = structuredClone(plan);
  changed.name = "Loaded manual test";
  changed.seed = 7;
  await upload(changed);
  await page.waitForFunction(
    () =>
      document.querySelector("#effect-name").textContent ===
      "Loaded manual test",
  );
  assert.equal(await page.locator("#seed").textContent(), "7");
  const bad = structuredClone(changed);
  bad.components[4].properties.count = 999999;
  await upload(bad);
  await page.locator("#message").waitFor({ state: "visible" });
  assert.match(await page.locator("#message").textContent(), /Plan rejected/);
  assert.equal(await page.locator("#effect-name").textContent(), changed.name);
  await upload("{");
  await page.waitForFunction(
    () =>
      !document
        .querySelector("#message")
        .textContent.startsWith("Plan rejected"),
  );
  assert.equal(await page.locator("#message").isVisible(), true);
  await page
    .locator("#file")
    .setInputFiles({
      name: "large.json",
      mimeType: "application/json",
      buffer: Buffer.alloc(65537, 32),
    });
  await page.waitForFunction(() =>
    document.querySelector("#message").textContent.includes("64 KiB"),
  );
  await page.locator("#sample").click();
  assert.equal(await page.locator("#message").isVisible(), false);
  assert.equal(await page.locator("#effect-name").textContent(), plan.name);
  const downloaded = page.waitForEvent("download");
  await page.locator("#download").click();
  const download = await downloaded;
  assert.equal(download.suggestedFilename(), "effect.vfx.json");
  let text = "";
  for await (const chunk of await download.createReadStream()) text += chunk;
  assert.deepEqual(JSON.parse(text), plan);
  await page.locator("#loop").uncheck();
  await page.locator("#scrub").evaluate((input) => {
    input.value = "1.499";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page
    .getByRole("button", { name: "Play animation", exact: true })
    .click();
  await page.waitForFunction(() =>
    document.querySelector("#time").textContent.startsWith("1.50"),
  );
  await page
    .getByRole("button", { name: "Play animation", exact: true })
    .waitFor();
  await page.getByRole("button", { name: "Replay", exact: true }).click();
  await page.waitForFunction(
    () => parseFloat(document.querySelector("#time").textContent) < 1,
  );
  await page.getByRole("button", { name: "Pause animation" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.screenshot({
    path: ".artifacts/preview-mobile.png",
    fullPage: true,
  });
  assert.deepEqual(failures, []);
  // Reduced-motion preference produces a real, paused scene (not automatic motion).
  const reduced = await browser.newPage({ reducedMotion: "reduce" });
  await reduced.goto(process.env.VFX_TEST_URL || "http://127.0.0.1:5173");
  await reduced
    .getByRole("button", { name: "Play animation", exact: true })
    .waitFor();
  await reduced.close();
  // A browser without WebGL gets an explicit blocker, not a fabricated preview.
  const blockedContext = await browser.newContext();
  await blockedContext.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      if (type === "webgl2" || type === "webgl") return null;
      return original.call(this, type, ...args);
    };
  });
  const blocked = await blockedContext.newPage();
  await blocked.goto(process.env.VFX_TEST_URL || "http://127.0.0.1:5173");
  await blocked.locator(".webgl-error").waitFor();
  assert.equal(await blocked.locator("#viewport canvas").count(), 0);
  assert.equal(await blocked.locator("#play").isDisabled(), true);
  await blocked.locator("#plan-tab").click();
  assert.deepEqual(
    JSON.parse(await blocked.locator("#json").textContent()),
    plan,
  );
  await blockedContext.close();
  console.log(
    "PASS: real WebGL pixels, exact draw counts, playback, seek, grid, camera, JSON view, valid/invalid/oversized input, download, restore, responsive layout, reduced motion, explicit no-WebGL fallback; no unexpected browser errors.",
  );
} finally {
  await browser.close();
}
