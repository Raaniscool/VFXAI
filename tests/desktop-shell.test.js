import test from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import vm from "node:vm";
import path from "node:path";
const require = createRequire(import.meta.url);

// Wiring tests with explicit Electron doubles. These are NOT native startup tests;
// tests/desktop-smoke.mjs is the separate real-Electron test.
async function shellFixture() {
  const bundle = path.resolve("virtual-bundle");
  const calls = {};
  const app = Object.assign(new EventEmitter(), {
    isPackaged: true,
    setName() {},
    setAppUserModelId() {},
    requestSingleInstanceLock: () => true,
    getAppPath: () => bundle,
    getPath: () => path.join(bundle, "documents"),
    getVersion: () => "0.2.0",
    quit: () => {
      calls.quit = true;
    },
    exit: (code) => {
      calls.exit = code;
    },
    whenReady: () => ({
      then: (fn) => (calls.started = Promise.resolve().then(fn)),
    }),
  });
  const session = Object.assign(new EventEmitter(), {
    setPermissionRequestHandler: (fn) => {
      calls.permission = fn;
    },
    setPermissionCheckHandler: (fn) => {
      calls.permissionCheck = fn;
    },
    webRequest: {
      onBeforeRequest: (fn) => {
        calls.request = fn;
      },
      onHeadersReceived: (fn) => {
        calls.headers = fn;
      },
    },
  });
  class BrowserWindow extends EventEmitter {
    constructor(options) {
      super();
      calls.options = options;
      calls.window = this;
      this.webContents = Object.assign(new EventEmitter(), {
        setWindowOpenHandler: (fn) => {
          calls.open = fn;
        },
      });
    }
    async loadURL(url) {
      calls.url = url;
      this.emit("ready-to-show");
    }
    show() {
      calls.shown = true;
    }
    static getAllWindows() {
      return [calls.window];
    }
  }
  const electron = {
    app,
    screen: {
      getPrimaryDisplay: () => ({ workAreaSize: { width: 1366, height: 728 } }),
    },
    BrowserWindow,
    session: { defaultSession: session },
    protocol: {
      registerSchemesAsPrivileged: (schemes) => {
        calls.schemes = schemes;
      },
      handle: (scheme, handler) => {
        assert.equal(scheme, "vfxai");
        calls.protocol = handler;
      },
    },
    Menu: { buildFromTemplate: (menu) => menu, setApplicationMenu: () => {} },
    dialog: {
      showErrorBox: (...args) => {
        calls.error = args;
      },
      showMessageBox() {},
    },
  };
  const htmlPath = path.join(bundle, "dist", "index.html");
  const filesystem = {
    access: async (file) => assert.equal(file, htmlPath),
    stat: async (file) => {
      if (file !== htmlPath) throw new Error("ENOENT");
      return { isFile: () => true };
    },
    readFile: async () => Buffer.from("<h1>Bundled UI</h1>"),
  };
  const source = await readFile("desktop/main.cjs", "utf8");
  vm.runInNewContext(source, {
    require: (id) =>
      id === "electron"
        ? electron
        : id === "node:fs/promises"
          ? filesystem
          : id === "./policy.cjs"
            ? require("../desktop/policy.cjs")
            : require(id),
    // The production shell must ignore even a deliberately hostile environment URL.
    process: {
      platform: process.platform,
      env: { VFXAI_DEV_URL: "https://untrusted.invalid/" },
    },
    Response,
    Headers,
    console: { log() {}, error() {} },
  });
  await calls.started;
  assert.equal(calls.exit, undefined);
  return { calls, session, htmlPath };
}

test("packaged shell wiring loads bundled assets and ignores development environment", async () => {
  const { calls } = await shellFixture();
  assert.equal(calls.url, "vfxai://app/index.html");
  assert.equal(calls.shown, true);
  assert.equal(calls.options.width, 1366);
  assert.equal(calls.options.height, 728);
  assert.equal(calls.options.webPreferences.sandbox, true);
  assert.equal(calls.options.webPreferences.nodeIntegration, false);
  assert.equal(calls.options.webPreferences.devTools, false);
  assert.equal(calls.open().action, "deny");
  assert.equal(calls.permissionCheck(), false);
  calls.permission(null, "camera", (granted) => assert.equal(granted, false));
  calls.request({ url: "https://example.com" }, (result) =>
    assert.equal(result.cancel, true),
  );
  const response = await calls.protocol({ url: calls.url, method: "GET" });
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "<h1>Bundled UI</h1>");
  assert.match(response.headers.get("Content-Type"), /text\/html/);
  assert.ok(
    response.headers
      .get("Content-Security-Policy")
      .includes("connect-src 'none'"),
  );
  assert.equal(
    (await calls.protocol({ url: "vfxai://app/missing.js", method: "GET" }))
      .status,
    404,
  );
  assert.equal(
    (await calls.protocol({ url: calls.url, method: "POST" })).status,
    405,
  );
  assert.equal(
    (
      await calls.protocol({
        url: "vfxai://app/%2e%2e%2fpackage.json",
        method: "GET",
      })
    ).status,
    404,
  );
  assert.equal(
    await (await calls.protocol({ url: calls.url, method: "HEAD" })).text(),
    "",
  );
});

test("desktop download wiring configures Save As only for trusted plan blobs", async () => {
  const { calls, session } = await shellFixture();
  const item = Object.assign(new EventEmitter(), {
    getURL: () => "blob:vfxai://app/test",
    getMimeType: () => "application/json",
    setSaveDialogOptions: (options) => {
      calls.save = options;
    },
  });
  let prevented = false;
  const event = {
    preventDefault: () => {
      prevented = true;
    },
  };
  session.emit("will-download", event, item, calls.window.webContents);
  assert.equal(prevented, false);
  assert.equal(path.basename(calls.save.defaultPath), "effect.vfx.json");
  assert.equal(calls.save.filters[0].extensions[0], "json");
  item.getMimeType = () => "application/octet-stream";
  session.emit("will-download", event, item, calls.window.webContents);
  assert.equal(prevented, true);
  prevented = false;
  item.getURL = () => "https://example.com/untrusted.exe";
  session.emit("will-download", event, item, calls.window.webContents);
  assert.equal(prevented, true);
});
