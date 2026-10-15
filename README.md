# VFXAI Desktop · VFX Forge

A Windows desktop foundation for **real, procedurally constructed VFX**. The existing Vite + Three.js workbench runs inside an Electron native window. Effects are built from editable JSON plans, geometry, seeded lightning and particles—not AI-generated images/videos.

**Version 0.2.0: desktop conversion of Milestone 1.** The Designer is still explicitly unavailable. No trained neural network, prompt interpretation, model training, property editor or Roblox exporter has been added.

> **Prebuilt Windows app:** a successful Windows build, including native Electron startup tests for both the source entry and packaged executable, is available from the [successful GitHub Actions run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095). Download its **`VFXAI-Windows-x64`** artifact (ZIP; sign in to GitHub if prompted). The artifact is retained for 30 days. This is an Actions download—not a permanent GitHub Release. See [Windows instructions](docs/windows-desktop.md).

## Download the prebuilt Windows application (easiest)

1. Open the [successful Windows desktop build](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095).
2. Under **Artifacts**, click **`VFXAI-Windows-x64`** to download the ZIP. Sign in to GitHub if prompted. The artifact is about 212 MiB and is retained for 30 days.
3. In Downloads, right-click the ZIP and choose **Extract All**.
4. To run without installing, double-click **`VFXAI-0.2.0-x64-portable.exe`**. Or run **`VFXAI-0.2.0-x64-setup.exe`** and then start VFXAI from the Start menu/desktop shortcut.

The packaged app includes Electron and loads its bundled files directly—**no Node.js, server, browser, or Internet connection is needed to run it**. These are unsigned personal builds; Windows SmartScreen may show an unknown-publisher warning. Don't disable security protections broadly.

## Build from source (optional)

On Windows 10/11 x64, install Node.js 22.12+, download the source ZIP from [the Arena branch](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai) (**Code → Download ZIP**), and extract it to a writable folder. Double-click **`BUILD_WINDOWS.bat`**. It installs locked dependencies, runs tests and builds the installer plus portable EXE. After a successful build they appear at:

```text
release\VFXAI-0.2.0-x64-setup.exe
release\VFXAI-0.2.0-x64-portable.exe
```

`START_VFXAI.bat` launches the development desktop and manages its server automatically; it is not needed to run the prebuilt app.

## Desktop development

On Windows, double-click **`START_VFXAI.bat`**. It checks Node, installs missing dependencies, and launches a native Electron window. Its development server starts/stops automatically with the app; no separate PowerShell server command is needed.

Equivalent commands from the source folder:

```sh
npm ci
npm run desktop:dev
```

To run the built renderer in Electron **without a development server**:

```sh
npm run build
npm run desktop:start
```

`desktop:start` requires the development Electron runtime to be downloaded. It loads `vfxai://app/index.html`, not an HTTP address. The packaged app uses this same bundled-assets startup path.

### Scripts

| Command                     | Purpose                                               |
| --------------------------- | ----------------------------------------------------- |
| `npm run desktop:dev`       | Automatically managed Vite + Electron development     |
| `npm run build`             | Build the renderer to `dist/`                         |
| `npm run desktop:start`     | Electron + prebuilt `dist/`, no server                |
| `npm run desktop:build`     | Unpacked desktop build for the current OS             |
| `npm run dist:win`          | Windows x64 installer + portable EXE under `release/` |
| `npm run dist:win:portable` | Windows x64 portable EXE only                         |
| `npm test`                  | Foundation + desktop policy/wiring/validator tests    |
| `npm run test:desktop`      | Real Electron smoke test; build renderer first        |
| `npm run dev`               | Original optional browser preview at port 5173        |
| `npm run preview`           | Original optional production web preview at port 4173 |
| `npm run test:browser`      | Existing actual-browser smoke test                    |

Windows distributions should be built on Windows (or the configured Windows runner). The Linux Arena environment is not a Windows runtime. `dist/`, `release/`, installed dependencies, logs and screenshots are ignored by Git.

## What is preserved and demonstrable

The manually authored **Azure detonation** plan remains the default effect:

- A white sphere core and additive glow shell.
- Eight seeded segmented blue lightning arcs.
- Two cyan/blue expanding shockwaves.
- 96 seeded particles with velocity and gravity.
- A 1.5-second animation, 13 effect render objects and 1,912 effect vertices.

Orbit, zoom, pause/replay, speed, looping, exact-time seeking, grid toggle and camera reset are retained. Reduced-motion preference starts a real frame paused. There are no remote image/texture/font assets.

**Plan JSON** shows the actual construction plan. **Load plan** accepts a manually edited JSON file up to 64 KiB; invalid input reports errors and preserves the current effect. **Save plan** saves JSON (a native Save As dialog in Electron), **not a Roblox asset**. **Restore example** reloads the original. If WebGL2 is unavailable, the app reports the blocker explicitly rather than substituting a screenshot.

## Tests and limitations

- **23/23 Node test groups pass** locally, including schema/engine/verification behavior, desktop policies, standalone validator parity and mocked shell wiring.
- **Browser WebGL smoke passes** on development and production builds, including effect pixels, playback/seek, JSON validation/save, responsive layout, reduced motion, no-WebGL handling and the strict desktop-style CSP.
- **Production build passes.** Three.js emits a non-fatal >500 KB chunk warning (about 137 KB gzipped JavaScript).
- **Windows GitHub Actions passed** on a real Windows runner: unit tests/build; source-entry Electron launch and bundled UI smoke; Windows x64 installer/portable packaging; and a second real-Electron smoke against the packaged `VFXAI.exe`. The automated smoke checked the viewport/WebGL effect, sandbox, plan validation, JSON save wiring and CSP. Download **`VFXAI-Windows-x64`** from the [successful run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095).
- The Windows artifact is unsigned. Native Save As dialogs, installation/uninstallation and performance on **your** PC still need manual acceptance. Windows SmartScreen may warn about an unknown publisher.
- Arena itself cannot fetch Electron's runtime reliably and its local Windows-package attempt hit certificate verification. That does not invalidate the successful Windows Actions build; use the artifact above or build on Windows.

The shell wiring unit tests are mocks, but they are separate from—and do not replace—the successful real-Electron Windows smoke tests.

The sandbox has two CPUs and about 4 GB RAM. Electron adds Chromium/Node disk and memory overhead. WebGL2 is needed via supported hardware or software rendering; performance and graphics drivers vary by PC.

The full npm audit has moderate **development/packaging-tool** transitive advisories; `npm audit --omit=dev` reports zero. Build tooling is not shipped as runtime `node_modules`.

### Optional browser tests

Keep `npm run dev` running in another terminal, then:

```sh
npx playwright install chromium
npm run test:browser
```

Linux may need `npx playwright install --with-deps chromium`. Running VFXAI does not require Playwright. `VFX_TEST_URL` selects a production preview, and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` selects an existing test browser. The live Arena preview is a renderer demonstration, **not a streamed Windows desktop session**.

## Architecture

```text
Electron native window (desktop/main.cjs)
  └── vfxai://app → bundled dist/ renderer (no web server)
        └── Manual plan → Reasoner → Builder → Verifier → Three.js preview

Designer.design(prompt) remains an explicit unavailable interface.
```

| Location                            | Responsibility                                                                        |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| `desktop/`                          | Electron lifecycle, menus, native-save handling, asset protocol and security policies |
| `electron-builder.yml`              | Windows x64 NSIS + portable targets; ASAR, file whitelist and output names            |
| `scripts/desktop-dev.mjs`           | Automatic loopback-only Vite/Electron development lifecycle                           |
| `scripts/plan-validator-plugin.mjs` | Build-time standalone Ajv generation; no runtime eval in renderer                     |
| `src/plan-validator.js`             | Original Ajv schema compilation for Node/tests                                        |
| `schemas/plan-v1.schema.json`       | Unchanged plan format, supported properties and ranges                                |
| `examples/lightning-burst.vfx.json` | Original manually authored proof-of-concept effect                                    |
| `src/organs/`                       | Separate Designer, Reasoner, Builder and Verifier                                     |
| `src/pipeline.js`                   | One bounded construction attempt; no automatic repair loop                            |
| `src/engine/`                       | Pure math and Three.js preview adapter                                                |
| `tests/`                            | Engine, browser and desktop tests                                                     |
| `.github/workflows/`                | Existing foundation checks plus Windows desktop build/artifact workflow               |

The Electron renderer is sandboxed, isolated, has no Node integration or preload bridge, and cannot navigate to remote pages. The engine itself remains independent of Electron. See [architecture and schema](docs/architecture.md), the historical [Milestone 1 report](docs/milestone-1.md), and [desktop conversion report](docs/desktop-conversion.md).

Structural checks are **not** artistic-quality evaluation, Roblox compatibility or measured realtime guarantees. Only one effect family and four component types are supported. No later AI milestone was started. Review the desktop conversion before proceeding to prompt interpretation, training or export.

## Repository / publishing status

The tested source is on **`arena/8b465cbe-vfxai`**. The successful Windows build is an Actions artifact, not a permanent GitHub Release, and expires after 30 days. No branch switch, merge, PR, or release was made. Packaging scripts explicitly use `--publish never`; the workflow uploads installers only after native smoke tests pass.
