# Milestone 1 delivery report

> Historical report for the original foundation. The subsequent desktop conversion is documented in [desktop-conversion.md](desktop-conversion.md); current launch/build instructions are in [windows-desktop.md](windows-desktop.md). Browser-only/native-packaging statements below describe the original delivery, not the current source.

## Inspection before implementation

- Repository: `Raaniscool/VFXAI`, checkout `/home/user/VFXAI`.
- Session branch: `arena/8b465cbe-vfxai`, based on `152809d` (`Initial commit`).
- Initial state: clean worktree; only `README.md` containing `# VFXAI`. No existing engine, package manifest, CI, assets, or application to replace.
- Inspected: branch/status, tracked files, top-level tree, last commits, remotes, tools, hardware, and GitHub authentication. No branch switch, remote change, or merge occurred.
- Available: Node 22.22.3, npm 10.9.8, Python 3.11.2, git and GitHub CLI 2.23.0. Python is not required by this implementation.
- Sandbox: Linux x86_64, two logical CPUs, approximately 3.8 GiB memory, no swap, no detected NVIDIA utility or preinstalled browser. This is not a Windows test machine and no dedicated GPU capability is assumed.
- Existing remote: `origin` points to `Raaniscool/VFXAI`. GitHub CLI reported available authentication; push permissions were not exercised.
- Arena saves workspace changes automatically. Saving is not committing or pushing. Git publishing can use the configured remote/session branch when requested. No pre-existing GitHub Actions workflow was found.

## Implemented scope

A local-browser procedural workbench, runnable on Node 22.12+:

1. Versioned strict JSON Schema with explicit authoring defaults and supported ranges.
2. Independent Designer interface that explicitly reports unavailable; no fake prompt generation.
3. Reasoner with real schema, id, timeline, ring geometry and resource checks.
4. Builder that revalidates input, constructs seeded lightning/particle descriptors, and samples animation mathematically.
5. Verifier that checks constructed properties/counts/finite vectors, timeline samples and budget consistency against the input plan.
6. Single-attempt orchestration: rejects invalid plans; never runs generated code or silently retries.
7. Live Three.js/WebGL2 preview with actual meshes, torus rings, line geometry, and point buffers; orbit/zoom, pause/replay, speed, loop, seeking and grid/camera controls.
8. Manual plan loading, read-only JSON inspection, JSON download and example restore. Invalid or oversized input leaves the current effect unchanged.
9. Automated tests, a dependency lockfile, documentation and a new CI definition.

The authored 1.5-second example constructs five layers: core, eight arcs, two rings and 96 particles. The full effect uses 13 render objects and 1,912 vertices. With all objects active plus the ground grid, the real renderer reports 14 draw calls.

## Acceptance evidence

| Criterion                        | Verified evidence                                                                                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Documented setup                 | `npm ci` executed successfully from the lockfile; README gives Windows-compatible commands.                                                                |
| Valid structured plan loads      | Bundled example passes schema/reasoning; browser smoke loads another manual name/seed and rejects invalid/oversized/malformed input.                       |
| Animated procedural effect       | Pure tests confirm seeded geometry, timing, expansion, gravity and absolute-time seeking.                                                                  |
| Actual functional preview        | Chromium/software WebGL test confirms visible blue canvas pixels and exact active draw counts; playback and seeking work. No screenshot substitute.        |
| Automated core tests             | 13 Node test groups pass. Negative cases include malformed schemas, bad numeric properties, spatial/timeline conflicts, budgets and damaged constructions. |
| Clear architecture / entry point | Independent organs and preview adapter; `npm run dev`, `npm run build`, `npm run preview`.                                                                 |
| Honest README                    | Describes working manual-plan pipeline and explicitly lists AI, training, native desktop, artistic evaluation and Roblox omissions.                        |

## Commands actually executed and results

- `npm ci`: **pass** (24 packages installed; lockfile usable).
- `npm test`: **13/13 passing**, zero skipped. An initial test expected 1,916 vertices; corrected to the actual 1,912 and reran successfully.
- `npm run build`: **pass**, Vite 7.3.7. JavaScript bundle 651.49 KB minified / 173.80 KB gzipped, CSS 14.93 KB / 4.20 KB gzipped. Known warning: one chunk exceeds 500 KB, primarily Three.js. No build failure.
- `npm audit`: **0 reported vulnerabilities** at execution time. Initial dependency advisories were resolved by updating Ajv and Vite before final checks.
- `npm run test:browser`: **pass against both the Vite development server and the built production preview**. Tests exercise real canvas pixels, draw counts, playback/seek, grid/reset camera, plan tab, valid/invalid/malformed/oversized uploads, download/restore, non-looping completion/replay, 390px responsive layout, reduced motion and explicit no-WebGL fallback. No unexpected browser console/page errors.
- `git diff --check`: **pass** for tracked changes; new source files are also inspected through build/tests.
- HTTP request with an Arena-style `.e2b.app` Host header: **200**. Both preview servers bound to `0.0.0.0` without platform host/embedding warnings.
- Desktop and mobile browser screenshots were inspected as diagnostics. They remain ignored under `.artifacts/` and are not offered as a substitute for the interactive preview.

### Browser test environment

Arena permits npm/GitHub traffic but not Playwright's normal browser-download CDN. For this execution only, Chromium 138.0.2 was downloaded via the npm package `@sparticuz/chromium` into an ignored temporary `node_modules/.browser-tools` directory; Chromium and its bundled system libraries were extracted to `/tmp`. The test was run with:

```sh
LD_LIBRARY_PATH=/tmp/al2023/lib:/tmp \
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/tmp/chromium \
npm run test:browser
```

The production check additionally set `VFX_TEST_URL=http://127.0.0.1:4173`. Software rendering used SwiftShader. These sandbox test artifacts are not project dependencies and are not committed; `/tmp` does not persist. `npm ci` subsequently removed the temporary npm package. On a normal Windows machine use the documented Playwright installation if you want to run browser tests. Running the app itself does not require Chromium or Playwright installation.

The new GitHub Actions workflow covers Linux/Windows unit/build checks and a Linux production-browser smoke test, but **no remote CI run or Windows runtime test is claimed**. Windows portability is based on standard Node/npm/browser APIs and remains to be confirmed on a real Windows PC or published CI run.

## Limitations / deliberately not implemented

- A browser app, not a packaged native desktop application.
- Four component types, one effect family, fixed animation presets; no arbitrary keyframes, relationships, beams or trails.
- No prompt interpretation, neural model, training code/dataset, checkpoints, automatic corrections, or feedback capture.
- No inline property editor; edit a manual JSON file and load it.
- Structural verification and sampled animation checks, not artistic evaluation or an exhaustive proof of all rendered behavior.
- Preview resource estimates are not Roblox object counts or realtime frame-time guarantees on limited PCs.
- No Luau/Studio plugin export or Studio testing. JSON download is only a plan.
- Browser must support WebGL2; no dedicated GPU is required by the app design, but software rendering speed varies. Hardware and Windows performance have not been benchmarked.

## Files changed

Original `README.md` expanded; no original file was removed. Added:

```text
.gitignore
.github/workflows/ci.yml
package.json
package-lock.json
vite.config.js
index.html
schemas/plan-v1.schema.json
examples/lightning-burst.vfx.json
src/main.js
src/style.css
src/pipeline.js
src/engine/math.js
src/engine/preview.js
src/organs/designer.js
src/organs/reasoner.js
src/organs/builder.js
src/organs/verifier.js
tests/foundation.test.js
tests/browser-smoke.js
docs/architecture.md
docs/milestone-1.md
```

Generated `dist/`, installed `node_modules/`, diagnostic screenshots, logs, and browser binaries are excluded from Git. No datasets or checkpoints were generated.

## Publishing status and next step

**Workspace changes only on `arena/8b465cbe-vfxai`. No local commit, push, pull request, branch merge or successful GitHub publication was performed.** The original branch strategy and origin are unchanged. GitHub authentication appeared available; there was no need to request credentials.

The development server remains available as **VFX Forge** in Arena's live preview. The separate production-check server was stopped after verification.

Recommended next milestone: review this foundation first, then explicitly approve **Milestone 2: narrow rule-based prompt interpretation** using the existing plan contract and regression tests. It has not been implemented.
