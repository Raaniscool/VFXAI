# VFXAI Windows desktop — build and launch

## Current delivery status (read first)

A Windows x64 installer and portable application have now been **built and passed real-Electron smoke tests on a Windows GitHub runner**. Download the **`VFXAI-Windows-x64`** artifact from the [successful run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095). The [direct artifact ZIP link](https://api.github.com/repos/Raaniscool/VFXAI/actions/artifacts/11951170634/zip) may ask you to sign in to GitHub. It is about 212 MiB and retained for 30 days. This is a CI artifact, not a permanent GitHub Release.

The source is published on [the Arena branch](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai). The automated Windows run launched both the source entry and packaged executable, checked the bundled UI/WebGL effect and plan operations, built the installer/portable targets, and tested the packaged `.exe`. **It has not been manually installed and checked on your own PC**; native dialogs, installation/uninstallation, and local graphics/performance still need user-machine checks.

## Simplest way to launch the prebuilt app

1. Open the [successful Windows desktop run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095) and download **Artifacts → `VFXAI-Windows-x64`**. Sign in to GitHub if prompted.
2. In your Downloads folder, right-click the ZIP and choose **Extract All**.
3. For the quickest launch, double-click **`VFXAI-0.2.0-x64-portable.exe`**. Or run **`VFXAI-0.2.0-x64-setup.exe`** and follow the wizard; after setup, start **VFXAI** from the Start menu or desktop shortcut.

The portable build does not need installation. Neither prebuilt app needs Node.js, a separate web server, or Internet to run. These are **unsigned personal builds**, so Windows SmartScreen may warn about an unknown publisher. Do not disable Defender or other security protections broadly.

## Build from source instead

Use a **Windows 10/11 x64 PC** with Internet access, enough free disk space for Node dependencies and Electron, and working graphics drivers.

1. Install **Node.js 22.12 or newer** (current LTS recommended). Node includes npm. Close and reopen any terminals after installation.
2. Download the source ZIP from [the Arena branch](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai) using **Code → Download ZIP**. Extract it into a writable folder, such as `Documents\VFXAI`; do not launch files from inside the ZIP.
3. Double-click **`BUILD_WINDOWS.bat`** in the extracted folder. It installs locked dependencies, runs tests, builds the renderer, and creates both Windows targets. The first build needs Internet for Electron and packaging downloads.
4. On success, open the `release` folder. The expected outputs are:

   ```text
   release\VFXAI-0.2.0-x64-setup.exe
   release\VFXAI-0.2.0-x64-portable.exe
   ```

5. Double-click either EXE as described above. Do not run installers copied from other sources.

Running a successfully built/packaged EXE requires no Node, manual web server, browser window, Internet, or paid AI service.

## Simplest development launch

Double-click **`START_VFXAI.bat`** in the source folder. It checks Node, installs missing development dependencies, and opens a native Electron window. It starts and owns an internal, available-port, loopback-only Vite server automatically. **You do not manually start a separate server.** Closing the desktop window stops that development server. The console is normal for a development launch, not part of the packaged app.

After updating the source/lockfile, run `npm ci` (or run `BUILD_WINDOWS.bat`) to refresh installed dependencies. The development launcher checks for missing tools; it is not a dependency-version updater.

## Equivalent terminal commands

Run these in the source folder. In PowerShell, if script policy blocks `npm.ps1`, use `npm.cmd` instead of changing system execution policy.

| Command                     | Purpose                                                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `npm ci`                    | Install exact development/build dependencies from the lockfile                                                                 |
| `npm run desktop:dev`       | Start Vite automatically and launch Electron with hot reload                                                                   |
| `npm run build`             | Build bundled renderer assets into `dist/`                                                                                     |
| `npm run desktop:start`     | Launch Electron against the built `dist/`; **no server** (run `build` first)                                                   |
| `npm run desktop:build`     | Build assets + unpacked desktop app for the current OS in `release/`                                                           |
| `npm run dist:win`          | Build assets + Windows x64 NSIS installer **and** portable EXE                                                                 |
| `npm run dist:win:portable` | Build assets + only the Windows x64 portable target                                                                            |
| `npm test`                  | 23 foundation, desktop policy, validator parity, and mocked shell wiring tests                                                 |
| `npm run test:desktop`      | Real Electron startup/WebGL/file-operation smoke test using built assets; requires downloaded Electron and a graphical session |
| `npm run dev`               | Existing optional browser development preview (not desktop launch)                                                             |
| `npm run preview`           | Existing optional browser production preview                                                                                   |

For a quick source-based **offline-style desktop startup**, `npm run build` followed by `npm run desktop:start` loads `vfxai://app/index.html` from your disk, not HTTP. It still requires the development Electron runtime to have downloaded successfully at least once. Installed/portable builds already include that runtime.

`desktop:build` on Windows creates `release\win-unpacked\VFXAI.exe` plus supporting files. To move that unpacked build you must copy **the entire `win-unpacked` folder**, not just its `.exe`. Prefer the installer or portable artifact for distribution. Linux `desktop:build` is not a Windows package. Build Windows distributions on Windows; cross-building may require Wine and is not the supported recipe here.

## Artifact lifecycle

The **`VFXAI-Windows-x64`** ZIP is attached to the [successful Actions run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095). The direct [artifact ZIP link](https://api.github.com/repos/Raaniscool/VFXAI/actions/artifacts/11951170634/zip) may require you to sign in. GitHub retains it for 30 days. It is a CI artifact, **not** a permanent GitHub Release; no release or code-signing certificate is configured.

## What remains the same

The VFX Forge workbench inside the native VFXAI window reuses:

- Three.js core, lightning, rings, particles, camera and playback controls.
- Version 1.0 editable construction plans and deterministic animation.
- Manual Load plan, Save plan, Plan JSON, validation and restoration.
- Separate Designer, Reasoner, Builder and Verifier modules.

**Load plan** opens the system file picker. **Save plan** requests a native Save As dialog for JSON, rather than an automatic browser download folder. The automated desktop smoke test bypasses the dialog by choosing a test destination; dialog appearance and cancellation still need a manual Windows check. The JSON plan is not a Roblox export.

The Designer remains an explicit unavailable interface. There is no trained neural network, no new AI milestone, and no new Roblox exporter in this conversion.

## Desktop security / implementation

- `desktop/main.cjs` owns the native window, app lifecycle, menus, protocol and plan-save handling.
- `desktop/policy.cjs` provides independently tested URL, download and asset-path policies.
- Production uses the internal secure/standard `vfxai://app` protocol backed by bundled `dist/` files inside `app.asar`. This is **not a listening web server**. Packaged startup ignores development-URL environment variables.
- `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true`, `webSecurity: true`, no preload bridge, and no renderer filesystem/Node APIs.
- External navigation, popups, webviews, remote networking and permission requests are denied. No general-purpose IPC or execution of model-generated code.
- Script CSP is `script-src 'self'`, without `unsafe-eval`. Ajv normally compiles a schema using `new Function`, so Vite precompiles the exact same schema into standalone validation functions. Node tests still use the original Ajv validation path, and parity tests compare the results. This changes how the validator is bundled, not the construction-plan rules.
- Renderer CSS uses style attributes, so style CSP permits `unsafe-inline` for styles only. There is no equivalent inline/eval exception for scripts.
- Production renderer packages only bundled assets and desktop bootstrap code. Three.js, Ajv, Electron's development CLI, Playwright and electron-builder are build dependencies, not shipped `node_modules` trees. Electron's runtime itself is included by the packager.
- A second instance focuses the existing window. Closing the final window exits on Windows. Help → About accurately states the unimplemented AI/export scope.

## Troubleshooting and manual Windows acceptance

- **Node not found / old version:** install Node LTS, reopen the launcher, and ensure Node/npm are in PATH.
- **Download or certificate failure:** verify network access to npm, GitHub and GitHub release/CDN hosts. Corporate proxies may require your organization's trusted CA setup. Do not turn off TLS validation. Arena's restricted network is not proof that your Windows build will fail.
- **Blank/unsupported 3D preview:** the bundled renderer needs WebGL2. Update graphics drivers, then relaunch. Software rendering may be slower. Do not disable sandbox/web security as a workaround. A visible WebGL error is not a completed preview.
- **Installed app cannot find renderer:** reinstall from a successful full installer/portable build. For source, run `npm run build` first.
- **Node dependencies after an update:** run `npm ci`. Do not copy a Linux `node_modules` folder to Windows.
- **Large download/application:** Electron bundles Chromium and Node. This is intentionally a native desktop shell around the reusable web renderer, not a rewrite into a smaller native graphics engine. Memory/startup performance on the target PC is not yet benchmarked.

The CI runner has verified source-entry Electron startup, bundled rendering, and packaged executable startup. For your PC, still check launching with no Vite server, orbit/play/seek, load valid and invalid JSON plans, save/cancel native dialogs, reload, close/relaunch, open a second instance, and uninstall the installer build. The user-machine dialog, installation, and performance checks have not been performed.
