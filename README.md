# VFXAI Desktop · VFX Forge

A Windows desktop foundation for **real, procedurally constructed VFX**. The existing Vite + Three.js workbench runs inside an Electron native window. Effects are built from editable JSON plans, geometry, seeded lightning and particles—not AI-generated images/videos.

**Version 0.2.0: desktop conversion of Milestone 1.** The Designer is still explicitly unavailable. No trained neural network, prompt interpretation, model training, property editor or Roblox exporter has been added.

> **Build status:** desktop source and packaging are implemented, but **no compiled Windows `.exe` is attached or remotely published**. Arena's restricted network blocked Electron runtime/downloads, so native Electron startup and Windows installation could not be verified here. See [Windows build instructions and status](docs/windows-desktop.md).

## Get a normal Windows application

1. On a Windows 10/11 **x64** PC, install **Node.js 22.12+** (current LTS recommended).
2. Extract the delivered **`VFXAI-0.2.0-source.zip`**, or use this repository's current workspace source. Don't run from inside a ZIP.
3. Double-click **`BUILD_WINDOWS.bat`**. It installs locked dependencies, runs the automated tests and builds both Windows targets. Internet is needed for the first build.
4. When it finishes, open either:

   ```text
   release\VFXAI-0.2.0-x64-setup.exe      ← installer, Start menu + desktop shortcut
   release\VFXAI-0.2.0-x64-portable.exe   ← double-click without installing
   ```

**The resulting EXEs include Electron and load bundled files directly. End users do not need Node.js, a browser, Vite, a manually started server, Internet, an account or a paid AI service to run them.** These are unsigned personal builds; only run source/builds you trust. No signing or auto-update service is configured.

Alternatively, after this source is published, the new **Windows desktop** GitHub Actions workflow can produce downloadable artifacts. Look under the successful run's **`VFXAI-Windows-x64`** artifact. **No such run or artifact has been created by this Arena delivery.** Full details, troubleshooting, security and manual Windows acceptance steps are in [docs/windows-desktop.md](docs/windows-desktop.md).

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

Verified in Arena for the desktop conversion:

- **23/23 Node test groups pass:** original schema/engine/verification checks plus desktop policies, standalone validator equivalence and shell wiring tests using explicit Electron doubles.
- **WebGL browser smoke passes** on development and production builds: actual canvas pixels, draw counts, playback, seek, grid/camera, JSON, valid/invalid/oversized input, download, mobile layout, reduced motion and no-WebGL fallback. Production uses the strict script CSP needed by the desktop shell.
- **Production web build passes.** Three.js still produces a non-fatal >500 KB chunk warning (about 137 KB gzipped JavaScript after build-time schema compilation).
- **Native desktop smoke was attempted but blocked:** the Electron binary could not download in Arena. Windows portable packaging parsed the configuration and reached runtime packaging, then failed on download/certificate verification. No EXE was produced; no Windows test passed is claimed.

`tests/desktop-smoke.mjs` and `.github/workflows/windows-desktop.yml` are ready to exercise real source-entry Electron and the packaged Windows executable where downloads and a graphical session are available. They do not silently substitute mocks or skip native failures. The shell wiring unit tests **are mocks**, not native-runtime proof.

The sandbox has two CPUs and about 4 GB RAM, with no Windows environment. Electron adds Chromium/Node disk and memory overhead. WebGL2 is needed, through supported hardware or software rendering. Target-PC performance, native dialogs, installation and uninstallation remain to be checked on Windows.

The current dependency audit reports moderate **development/packaging-tool** transitive advisories; `npm audit --omit=dev` reports zero. The packaged app does not ship those build-tool `node_modules`. Review tooling updates before broad distribution; don't force breaking dependency upgrades or disable security checks to package.

### Optional browser tests

Keep `npm run dev` running in another terminal, then:

```sh
npx playwright install chromium
npm run test:browser
```

Linux may need `npx playwright install --with-deps chromium`. Running VFXAI does not require Playwright. `VFX_TEST_URL` selects a production preview, and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` selects an existing test browser. In Arena, the live web preview is a renderer demonstration, **not a streamed Windows desktop session**.

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

Work remains on **`arena/8b465cbe-vfxai`**. Existing foundation work is preserved. No branch switch, merge, commit, push, PR, GitHub Release, or remote CI run was performed for this conversion. Arena workspace saving is not publishing. All packaging scripts explicitly use `--publish never`; the Windows workflow only uploads build artifacts after successful checks.
