const {
  app,
  BrowserWindow,
  Menu,
  dialog,
  protocol,
  session,
  screen,
} = require("electron");
const path = require("node:path");
const fs = require("node:fs/promises");
const {
  APP_URL,
  WINDOW_SECURITY,
  parseDevURL,
  assetPath,
  isAllowedRequest,
  isAllowedNavigation,
  isPlanDownload,
  contentSecurityPolicy,
} = require("./policy.cjs");

protocol.registerSchemesAsPrivileged([
  {
    scheme: "vfxai",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
    },
  },
]);
app.setName("VFXAI");
app.setAppUserModelId("com.vfxai.forge");
let mainWindow;
let devURL;
const log = (message) => console.log(`[VFXAI] ${message}`);

async function createWindow() {
  const workArea = screen.getPrimaryDisplay().workAreaSize;
  mainWindow = new BrowserWindow({
    title: "VFXAI — VFX Forge",
    width: Math.min(1440, workArea.width),
    height: Math.min(1000, workArea.height),
    minWidth: Math.min(900, workArea.width),
    minHeight: Math.min(650, workArea.height),
    backgroundColor: "#0b0e14",
    show: false,
    webPreferences: { ...WINDOW_SECURITY, devTools: !app.isPackaged },
  });
  mainWindow.on("page-title-updated", (event) => event.preventDefault());
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isAllowedNavigation(url, devURL)) event.preventDefault();
  });
  mainWindow.webContents.on("will-attach-webview", (event) =>
    event.preventDefault(),
  );
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    log(`Renderer stopped: ${details.reason}`);
    dialog.showErrorBox(
      "VFXAI renderer stopped",
      "Close and reopen VFXAI. If the 3D viewport fails, update your graphics drivers.",
    );
  });
  mainWindow.webContents.on(
    "did-fail-load",
    (_event, code, description, url, isMainFrame) => {
      if (isMainFrame && code !== -3)
        log(`Load failed (${code}): ${description} ${url}`);
    },
  );
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  await mainWindow.loadURL(devURL || APP_URL);
  log(
    `Desktop ready (${devURL ? "development server" : "bundled assets; no server"})`,
  );
}

async function start() {
  // A packaged executable never accepts a development URL from the environment.
  devURL = !app.isPackaged ? parseDevURL(process.env.VFXAI_DEV_URL) : null;
  const root = path.join(app.getAppPath(), "dist");
  if (!devURL) await fs.access(path.join(root, "index.html"));
  const csp = contentSecurityPolicy(devURL);
  protocol.handle("vfxai", async (request) => {
    if (!["GET", "HEAD"].includes(request.method))
      return new Response("Method not allowed", { status: 405 });
    const file = assetPath(root, request.url);
    if (!file) return new Response("Not found", { status: 404 });
    try {
      const types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
        ".woff2": "font/woff2",
      };
      if (!(await fs.stat(file)).isFile())
        return new Response("Not found", { status: 404 });
      const body = request.method === "HEAD" ? null : await fs.readFile(file);
      const headers = new Headers({
        "Content-Type": types[path.extname(file)],
      });
      headers.set("Content-Security-Policy", csp);
      headers.set("X-Content-Type-Options", "nosniff");
      return new Response(body, { status: 200, headers });
    } catch {
      return new Response("Not found", { status: 404 });
    }
  });
  const ses = session.defaultSession;
  ses.setPermissionRequestHandler((_contents, _permission, callback) =>
    callback(false),
  );
  ses.setPermissionCheckHandler(() => false);
  ses.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !isAllowedRequest(details.url, devURL) });
  });
  ses.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [csp],
      },
    });
  });
  ses.on("will-download", (event, item, contents) => {
    if (
      contents !== mainWindow?.webContents ||
      !isPlanDownload(item.getURL(), devURL) ||
      item.getMimeType() !== "application/json"
    ) {
      event.preventDefault();
      return;
    }
    // Existing renderer creates a JSON Blob; Chromium provides a native Save As dialog.
    item.setSaveDialogOptions({
      title: "Save VFX construction plan",
      defaultPath: path.join(app.getPath("documents"), "effect.vfx.json"),
      filters: [{ name: "VFX plan (JSON)", extensions: ["json"] }],
    });
    item.once("done", (_event, state) => {
      if (state !== "completed" && state !== "cancelled") {
        log(`Plan save ${state}`);
        dialog.showErrorBox(
          "Could not save plan",
          "Choose a writable folder and try saving the plan again.",
        );
      }
    });
  });
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      { label: "File", submenu: [{ role: "quit" }] },
      {
        label: "View",
        submenu: [
          { role: "reload" },
          { role: "resetZoom" },
          { role: "zoomIn" },
          { role: "zoomOut" },
          { role: "togglefullscreen" },
          ...(!app.isPackaged ? [{ role: "toggleDevTools" }] : []),
        ],
      },
      {
        label: "Help",
        submenu: [
          {
            label: "About VFXAI",
            click: () =>
              dialog.showMessageBox(mainWindow, {
                type: "info",
                title: "About VFXAI",
                message: `VFXAI ${app.getVersion()} — VFX Forge`,
                detail:
                  "Procedural VFX foundation. Designer not implemented; no trained neural network. Roblox export is not implemented.",
              }),
          },
        ],
      },
    ]),
  );
  await createWindow();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app
    .whenReady()
    .then(start)
    .catch((error) => {
      console.error("[VFXAI] Desktop startup failed:", error);
      dialog.showErrorBox(
        "VFXAI could not start",
        `${error.message}\n\nFor source builds, run npm run build first. For an installed copy, reinstall VFXAI.`,
      );
      app.exit(1);
    });
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0)
      createWindow().catch((error) => {
        console.error("[VFXAI] Window startup failed:", error);
        app.exit(1);
      });
  });
}
