# Historical desktop conversion report — 0.2.0 (superseded)

> **Not the active product or workflow.** This report records an earlier Electron experiment. The current project is Python-first and local-browser-based; Electron/EXE/installer commands and results below are historical, inactive, and have not been reverified in the current checkout. Do not use this report as current Windows-test or publishing evidence.

## Inspection and preserved work

- Current branch stayed `arena/8b465cbe-vfxai`; original HEAD remained `152809d`.
- The existing Milestone 1 implementation was present as workspace changes, not a local commit. It was reused in place, not replaced with another repository.
- Inspected package/lockfile, Vite config, source, plan schema, browser tests, CI, remotes, branch/status/history and available hardware/tools.
- Available Node 22.22.3/npm 10.9.8, Linux x86_64, two CPUs, approximately 4 GB RAM. No Wine, NSIS system install, Windows environment or display server was detected.
- No later AI milestone was started. Designer remains unavailable; Reasoner, Builder and Verifier remain independent. The plan format, geometry generation, animation formulas and effect UI are unchanged.

## Implemented

- Electron 44.7.2 native window bootstrap, app lifecycle/single-instance handling, native menus, honest About text, startup error handling and JSON-save dialog integration.
- Bundled production assets served through a local in-process `vfxai://app` protocol. **No listening HTTP server in production.** The packaged app ignores `VFXAI_DEV_URL`.
- Sandboxed/isolated renderer without Node integration, preload bridge, webviews, external navigation, remote HTTP/WS requests or permission grants. Only same-app JSON Blob downloads are allowed.
- Strict script CSP without `unsafe-eval`; Vite precompiles the existing Ajv schema to standalone functions. Node validation rules remain the same and parity tests cover both code paths.
- Vite relative asset base, preserving optional browser preview while making the renderer usable as bundled desktop assets.
- Electron-builder 26.15.3 ASAR configuration with Windows x64 NSIS and portable targets; explicit output names, narrow file inclusion, unsigned personal-build settings, and `--publish never` in packaging scripts.
- `START_VFXAI.bat` and `BUILD_WINDOWS.bat`, with Node/path checks, spaces-safe working-directory handling, dependency setup and visible errors. BAT files have CRLF endings and a `.gitattributes` rule.
- Automatically owned loopback Vite + Electron development launcher. Closing the app closes the server; startup failure also closes it.
- Windows CI workflow for tests, source-entry native smoke, packaging, packaged-EXE native smoke and downloadable artifacts only after all native checks pass. The original foundation workflow remains intact. A Windows path-quoting issue in the first smoke attempt was fixed; the later complete Windows workflow passed.
- A complete source ZIP, excluding binaries/dependencies/credentials, plus a successful Windows Actions artifact with tested installer/portable builds.

## Tests actually executed

| Check                                                   | Result                                                                                                                                                                                                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm ci` / lockfile installation                        | Pass; Electron's npm package installs, but the actual Electron runtime download is lazy and blocked here                                                                                                                                                              |
| `npm test`                                              | **23/23 pass**, including the original 13 foundation groups, eight desktop policy/validator groups and two explicitly mocked shell-wiring groups                                                                                                                      |
| Extracted source ZIP tests and build                    | **Pass**: ZIP CRC validated, 38 source files extracted, tests and Vite build executed using the installed development dependencies. Not a Windows test                                                                                                                |
| `npm run build`                                         | **Pass**, relative bundled assets; approximately 558 KB JS / 137 KB gzipped. Non-fatal Three.js >500 KB chunk warning remains                                                                                                                                         |
| `npm run test:browser` against Vite dev                 | **Pass**, real Chromium/software WebGL pixel and UI checks                                                                                                                                                                                                            |
| Same browser test against production preview            | **Pass**, including the strict desktop-style CSP, with no unexpected browser errors                                                                                                                                                                                   |
| `node --check` for desktop/bootstrap scripts            | Pass                                                                                                                                                                                                                                                                  |
| `git diff --check`                                      | Pass for tracked changes; source/build/tests inspected new files                                                                                                                                                                                                      |
| `npm audit --omit=dev`                                  | **0 production dependency advisories**                                                                                                                                                                                                                                |
| Full `npm audit`                                        | **8 moderate development/packaging-tool transitive advisories**, involving the older `@electron/get` chain pulled by electron-builder (`global-agent`/`roarr`/`sprintf-js`). Not shipped as runtime node_modules; not force-overridden with unverified major versions |
| `npm run test:desktop`                                  | Local Arena launch is blocked by the Electron runtime download, but the source-entry real-Electron smoke passed on Windows Actions; the packaged EXE smoke passed too. [Successful run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095)                 |
| `npm run desktop:dev`                                   | Vite starts and cleans up after Electron-download failure; native window cannot launch in this environment                                                                                                                                                            |
| `npm run dist:win:portable`                             | Renderer builds, electron-builder accepts configuration and reaches `platform=win32 arch=x64 electron=44.7.2`; download then fails with `unable to verify the first certificate`. **No executable produced**                                                          |
| Windows installer / native dialogs / actual Windows GPU | Installer/portable packages built and the packaged app launched on a real Windows CI runner. Manual dialogs, installation/uninstallation and performance on the user PC remain unverified                                                                             |
| Remote GitHub Actions                                   | **Pass**: Windows build, source-entry smoke, packaged executable smoke and artifact upload passed; Linux/Windows foundation and browser jobs passed. [Build run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095)                                        |

The browser test used Chromium/SwiftShader, separately from Electron. Its pass proves browser renderer behavior only. The two mocked shell-wiring tests validate policy but are not themselves native-startup proof. Separately, the successful Windows Actions run exercised real Electron in both source-entry and packaged-app modes and built the Windows installer/portable artifacts.

Arena still cannot fetch Electron reliably, and its local portable-packaging attempt stopped at certificate verification; TLS checks were not disabled. Diagnostics from Windows CI exposed a trailing-backslash app path interacting with Playwright's Windows shell quoting; normalizing that path fixed the startup failure. No claim is made about manually installing the app or testing native dialogs on the user's PC.

## Files added for this conversion

```text
.gitattributes
START_VFXAI.bat
BUILD_WINDOWS.bat
electron-builder.yml
desktop/main.cjs
desktop/policy.cjs
scripts/check-node.cjs
scripts/desktop-dev.mjs
scripts/plan-validator-plugin.mjs
src/plan-validator.js
tests/desktop-policy.test.js
tests/desktop-shell.test.js
tests/desktop-smoke.mjs
.github/workflows/windows-desktop.yml
docs/windows-desktop.md
docs/desktop-conversion.md
```

Updated: `package.json`, `package-lock.json`, `vite.config.js`, `.gitignore`, `README.md`, and the Reasoner's validator import. Added historical/current-status notes to the two existing architecture/Milestone 1 documents. No original working effect component, schema, engine, browser test or foundation workflow was removed.

Generated source archive: `release/VFXAI-0.2.0-source.zip`, intentionally ignored by Git. No `dist/`, `node_modules/`, partial Windows build, private key or browser binary is included in the archive.

## Where to get/run Windows software

**The tested Windows app is available now** as the **`VFXAI-Windows-x64`** artifact from the [successful Windows Actions run](https://github.com/Raaniscool/VFXAI/actions/runs/38688547095). [Direct artifact ZIP](https://api.github.com/repos/Raaniscool/VFXAI/actions/artifacts/11951170634/zip); sign in to GitHub if prompted. It is about 212 MiB and expires after 30 days. The source remains published on [the current Arena branch](https://github.com/Raaniscool/VFXAI/tree/arena/8b465cbe-vfxai). To build it yourself on Windows, install Node 22.12+, download the branch source ZIP, extract it, and double-click **`BUILD_WINDOWS.bat`**. Expected outputs:

- `release\VFXAI-0.2.0-x64-setup.exe`: run installer, launch via Start menu/desktop shortcut.
- `release\VFXAI-0.2.0-x64-portable.exe`: double-click to launch directly.

After a successful build, neither EXE needs a separately started server or Node installation on the end-user machine. The CI artifact contains unsigned personal builds. Full download and launch steps are in [windows-desktop.md](windows-desktop.md).

## Repository / next action

**Source and docs are committed and pushed to `arena/8b465cbe-vfxai`; no PR, merge, or GitHub Release was created.** The successful Windows Actions run produced a downloadable artifact, retained for 30 days; packaging scripts do not publish GitHub Releases. Complete manual installer/portable/native-dialog checks on the target PC before treating the distribution as fully user-verified. No prompt interpretation, training, export, or later AI milestone is authorized or implemented by this conversion.
