import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { readFile } from "node:fs/promises";
import policy from "../desktop/policy.cjs";
import { planValidatorPlugin } from "../scripts/plan-validator-plugin.mjs";
import validate from "../src/plan-validator.js";
import plan from "../examples/lightning-burst.vfx.json" with { type: "json" };
const root = path.resolve("dist");

test("desktop renderer is sandboxed and has no Node or webview bridge", () => {
  assert.equal(policy.WINDOW_SECURITY.sandbox, true);
  assert.equal(policy.WINDOW_SECURITY.contextIsolation, true);
  assert.equal(policy.WINDOW_SECURITY.webSecurity, true);
  assert.equal(policy.WINDOW_SECURITY.nodeIntegration, false);
  assert.equal(policy.WINDOW_SECURITY.nodeIntegrationInWorker, false);
  assert.equal(policy.WINDOW_SECURITY.webviewTag, false);
  assert.equal(policy.WINDOW_SECURITY.allowRunningInsecureContent, false);
});
test("desktop asset protocol cannot escape the bundled renderer directory", () => {
  assert.equal(
    policy.assetPath(root, policy.APP_URL),
    path.join(root, "index.html"),
  );
  assert.equal(
    policy.assetPath(root, "vfxai://app/"),
    path.join(root, "index.html"),
  );
  assert.equal(
    policy.assetPath(root, "vfxai://app/assets/main.js"),
    path.join(root, "assets/main.js"),
  );
  for (const url of [
    "https://example.com/",
    "file:///etc/passwd",
    "vfxai://other/index.html",
    "vfxai://app/%2e%2e%2fpackage.json",
    "vfxai://app/assets/..%5c..%5csecret.json",
    "vfxai://app/%00.json",
    "vfxai://app/%zz.js",
    "vfxai://user:pass@app/index.html",
    "vfxai://app:4000/index.html",
    "vfxai://app/desktop/main.cjs",
  ]) {
    assert.equal(policy.assetPath(root, url), null, url);
  }
});
test("development accepts only an explicit loopback HTTP URL", () => {
  assert.equal(policy.parseDevURL(undefined), null);
  assert.equal(
    policy.parseDevURL("http://127.0.0.1:5173"),
    "http://127.0.0.1:5173/",
  );
  for (const url of [
    "https://example.com/",
    "file:///index.html",
    "http://localhost:5173/",
    "http://0.0.0.0:5173/",
    "http://127.0.0.1/",
    "http://127.0.0.1:5173/path",
    "http://user@127.0.0.1:5173/",
    "http://127.0.0.1:5173/?evil=1",
  ]) {
    assert.throws(() => policy.parseDevURL(url));
  }
});
test("packaged desktop blocks remote/file requests and foreign navigation", () => {
  for (const url of [
    "https://example.com/a.js",
    "http://127.0.0.1:5173/",
    "file:///etc/passwd",
    "ws://127.0.0.1:5173/",
  ]) {
    assert.equal(policy.isAllowedRequest(url), false, url);
    assert.equal(policy.isAllowedNavigation(url), false, url);
  }
  assert.equal(policy.isAllowedRequest("vfxai://app/assets/main.js"), true);
  assert.equal(policy.isAllowedNavigation(policy.APP_URL), true);
  assert.equal(policy.isAllowedNavigation("vfxai://app/"), true);
  assert.equal(policy.isAllowedNavigation("vfxai://app/assets/main.js"), false);
  assert.equal(
    policy.isAllowedNavigation("vfxai://app/index.html?bad=1"),
    false,
  );
  const dev = "http://127.0.0.1:51234/";
  assert.equal(policy.isAllowedRequest(`${dev}@vite/client`, dev), true);
  assert.equal(policy.isAllowedRequest("ws://127.0.0.1:51234/", dev), true);
  assert.equal(policy.isAllowedRequest("http://127.0.0.1:51235/", dev), false);
  assert.equal(policy.isAllowedNavigation(dev, dev), true);
});
test("only JSON Blob downloads from the current app origin can open a save dialog", () => {
  assert.equal(policy.isPlanDownload("blob:vfxai://app/id"), true);
  assert.equal(policy.isAllowedRequest("blob:vfxai://app/id"), true);
  assert.equal(policy.isPlanDownload("https://example.com/file.exe"), false);
  assert.equal(policy.isPlanDownload("file:///etc/passwd"), false);
  assert.equal(policy.isPlanDownload("blob:https://example.com/id"), false);
  assert.equal(
    policy.isPlanDownload(
      "blob:http://127.0.0.1:1234/id",
      "http://127.0.0.1:1234/",
    ),
    true,
  );
  assert.equal(policy.isPlanDownload("blob:http://127.0.0.1:1234/id"), false);
});
test("production CSP forbids eval, remote scripts, frames and network APIs", () => {
  const csp = policy.contentSecurityPolicy();
  assert.ok(csp.includes("script-src 'self';"));
  assert.ok(csp.includes("connect-src 'none'"));
  assert.ok(csp.includes("frame-src 'none'"));
  assert.ok(!csp.includes("unsafe-eval"));
  assert.ok(
    policy
      .contentSecurityPolicy("http://127.0.0.1:1234/")
      .includes("ws://127.0.0.1:1234"),
  );
});
test("standalone renderer validator matches the Node validator without runtime eval", async () => {
  const source = planValidatorPlugin().transform(
    "",
    path.resolve("src/plan-validator.js"),
  ).code;
  assert.ok(!source.includes("require("));
  assert.ok(!source.includes("new Function"));
  const { default: rendererValidate } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const missingSeed = structuredClone(plan);
  delete missingSeed.seed;
  const unicodeName = { ...plan, name: "⚡".repeat(80) };
  const cases = [
    plan,
    null,
    {},
    missingSeed,
    unicodeName,
    { ...plan, name: "⚡".repeat(81) },
    { ...plan, duration: NaN },
    { ...plan, schemaVersion: "2.0" },
  ];
  for (const value of cases) {
    assert.equal(rendererValidate(value), validate(value));
    assert.deepEqual(rendererValidate.errors, validate.errors);
  }
});
test("active source workflow is Python-first and does not install or package Electron", async () => {
  const pkg = JSON.parse(await readFile("package.json", "utf8"));
  const requirements = await readFile("requirements.txt", "utf8");
  const launcher = await readFile("START_VFXAI.bat", "utf8");
  const scripts = Object.keys(pkg.scripts).join(" ");
  const dependencies = Object.keys(pkg.devDependencies || {}).join(" ");
  assert.ok(!/electron|electron-builder|dist:win|desktop:start/.test(scripts));
  assert.ok(!/electron|electron-builder/.test(dependencies));
  const dependencyLines = requirements.split(/\r?\n/).filter((line) => line && !line.trim().startsWith("#"));
  assert.match(dependencyLines.join("\n"), /numpy==/);
  assert.match(dependencyLines.join("\n"), /jsonschema==/);
  assert.doesNotMatch(dependencyLines.join("\n"), /torch|cuda|transformers/i);
  assert.match(launcher, /vfxai\.cli serve/);
  assert.doesNotMatch(launcher, /electron|dist:win/i);
});
