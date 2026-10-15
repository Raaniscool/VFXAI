const path = require("node:path");

const APP_ORIGIN = "vfxai://app";
const APP_URL = `${APP_ORIGIN}/index.html`;
const WINDOW_SECURITY = Object.freeze({
  nodeIntegration: false,
  nodeIntegrationInWorker: false,
  contextIsolation: true,
  sandbox: true,
  webSecurity: true,
  allowRunningInsecureContent: false,
  webviewTag: false,
});

function parseDevURL(value) {
  if (!value) return null;
  const url = new URL(value);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    !url.port ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  ) {
    throw new Error("Desktop development URL must be http://127.0.0.1:<port>/");
  }
  return url.href;
}

function isAppURL(value) {
  try {
    const url = new URL(value);
    return (
      url.protocol === "vfxai:" &&
      url.host === "app" &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}

// Resolves only app-bundled assets. Never expose arbitrary filesystem paths.
function assetPath(root, value) {
  if (!isAppURL(value)) return null;
  try {
    const pathname = decodeURIComponent(new URL(value).pathname);
    if (
      pathname.includes("\\") ||
      pathname.includes("\0") ||
      pathname.split("/").includes("..")
    )
      return null;
    const file = path.resolve(
      root,
      `.${pathname === "/" ? "/index.html" : pathname}`,
    );
    const relative = path.relative(root, file);
    if (
      !relative ||
      relative === ".." ||
      relative.startsWith(`..${path.sep}`) ||
      path.isAbsolute(relative)
    )
      return null;
    if (
      ![
        ".html",
        ".js",
        ".css",
        ".json",
        ".svg",
        ".png",
        ".ico",
        ".woff2",
      ].includes(path.extname(file))
    )
      return null;
    return file;
  } catch {
    return null;
  }
}

function isAllowedRequest(value, devURL = null) {
  try {
    if (isPlanDownload(value, devURL)) return true;
    const url = new URL(value);
    if (isAppURL(value) || url.protocol === "data:") return true;
    if (!devURL) return false;
    const dev = new URL(devURL);
    return (
      !url.username &&
      !url.password &&
      url.host === dev.host &&
      (url.protocol === "http:" || url.protocol === "ws:")
    );
  } catch {
    return false;
  }
}

function isAllowedNavigation(value, devURL = null) {
  try {
    const url = new URL(value);
    if (url.search || !["/", "/index.html"].includes(url.pathname))
      return false;
    return devURL ? url.origin === new URL(devURL).origin : isAppURL(value);
  } catch {
    return false;
  }
}

function isPlanDownload(value, devURL = null) {
  const origin = devURL ? new URL(devURL).origin : APP_ORIGIN;
  return typeof value === "string" && value.startsWith(`blob:${origin}/`);
}

function contentSecurityPolicy(devURL = null) {
  const connections = devURL ? `'self' ws://${new URL(devURL).host}` : "'none'";
  return `default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src ${connections}; object-src 'none'; base-uri 'self'; frame-src 'none'; frame-ancestors 'none'; form-action 'none'`;
}

module.exports = {
  APP_ORIGIN,
  APP_URL,
  WINDOW_SECURITY,
  parseDevURL,
  assetPath,
  isAllowedRequest,
  isAllowedNavigation,
  isPlanDownload,
  contentSecurityPolicy,
};
