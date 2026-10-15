# VFXAI Windows desktop — build and launch

## Current delivery status (read first)

The Electron source conversion and Windows packaging configuration are implemented. **There is no compiled Windows installer or portable `.exe` available yet.** Arena's local runtime and package downloads were blocked, and the first published Windows Actions run failed during real Electron startup before packaging. No Windows installer/portable artifact was produced; Windows installation and GPU behavior are not verified.

The **`VFXAI-0.2.0-source.zip` is complete source, not an installed application**. Extract it first. The source is published on [the Arena branch](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai). The failed [Windows Actions run](https://github.com/Raaniscool/VFXAI/actions/runs/38687347082) did not publish a download artifact. The source can still be built on Windows using the steps below.

## Simplest way to get a real Windows program from source

Use a **Windows 10/11 x64 PC** with Internet access, enough free disk space for Node dependencies and Electron, and working graphics drivers. These are the configured targets, not a claim that Windows execution was verified in Arena.

1. Install **Node.js 22.12 or newer** (a current LTS is recommended). Node includes npm. Close and reopen any existing terminals after installing it.
2. Extract `VFXAI-0.2.0-source.zip` into a normal writable folder, such as `Documents\VFXAI`. Do not launch files from inside the ZIP. Avoid a protected `Program Files` source directory.
3. Double-click **`BUILD_WINDOWS.bat`** in that folder.
4. Wait for dependencies, tests, Vite, and electron-builder to finish. Initial builds download Electron and packaging tools from the Internet; they are much larger than the VFX source. Leave the console open and read any error if it stops.
5. On success, the launcher opens the **`release`** folder containing:

   ```text
   release\VFXAI-0.2.0-x64-setup.exe
   release\VFXAI-0.2.0-x64-portable.exe
   ```

6. Choose one:
   - **Installer:** double-click `VFXAI-0.2.0-x64-setup.exe`. Follow the installer, then launch **VFXAI** from the Start menu or desktop shortcut. It installs per user, not as an administrator/system service.
   - **Portable:** double-click `VFXAI-0.2.0-x64-portable.exe`. No installation wizard. It extracts its bundled runtime temporarily when launched and still uses a normal per-user application-data folder; “portable” does not mean settings never touch AppData.

**Running either built EXE does not require Node.js, npm, Vite, a web server, a browser window, an Internet connection, or a paid AI service.** Electron includes its own runtime. Node and downloads are build/development prerequisites only.

These are **unsigned personal builds**, not Microsoft-certified software. Windows SmartScreen or security tools may show an unknown-publisher warning. Only run source/builds you trust. Do not disable Defender, certificate validation, or other system protections to make a build work. Code-signing and auto-update infrastructure are outside this conversion.

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

## Getting an EXE from GitHub Actions

The **Windows desktop** workflow is in `.github/workflows/windows-desktop.yml`. It does not publish a release or modify branches. The source is already on [`arena/8b465cbe-vfxai`](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai); no merge is required.

The first run [failed at the real source-entry Electron startup check](https://github.com/Raaniscool/VFXAI/actions/runs/38687347082), before installer packaging, so it has **no `VFXAI-Windows-x64` artifact to download**. We are instrumenting that startup failure and will retry. After a successful run, open **Actions → Windows desktop**, select its `arena/8b465cbe-vfxai` run, then download **`VFXAI-Windows-x64`**. Extract the ZIP and run either EXE described above. Artifact retention is 30 days; GitHub generally requires you to be signed in for artifact downloads. A failed run is not a verified executable.

There is no honest direct installer URL to provide until that workflow or your Windows build succeeds. The workflow's manual Run button is available only if GitHub exposes it (typically after the workflow is present on the default branch); publishing a push to the current branch is sufficient and avoids changing branch strategy. No automatic GitHub Release, signing, update server, or upload to an external host is configured.

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

Before treating a Windows distribution as verified, run it on a real PC: launch with no Vite server, orbit and play/seek the effect, load a good and bad JSON plan, save and cancel native dialogs, reload, close/relaunch, open a second instance, and uninstall the installer build. Also verify the portable EXE on a machine without Node installed. These Windows-specific checks have not been performed in Arena.
