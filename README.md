# VFXAI — local trainable VFX-plan experiment

VFXAI is a small Windows-friendly source project for experimenting with a **real, randomly initialized, locally trainable neural network** that maps text prompts to structured Roblox-style VFX construction plans. The existing Three.js workbench previews only validated plan-v1 output.

This is a development/source project, **not a packaged desktop app**. Electron, EXE/installer packaging, auto-updaters, pretrained models, cloud inference, and paid AI services are not part of the active workflow.

## PowerShell workflow (recommended on Windows)

Install **64-bit Python 3.11** and **Node.js 22.12 or newer** once, then open PowerShell at the repository root. Internet is needed for the first dependency install.

### First-time setup (once per checkout)

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

This creates the Python environment in `.venv` and installs the locked Python and Node dependencies. On first launch, the API initializes a dataset and an untrained baseline if needed; it does not overwrite an existing active dataset or trained checkpoint. You can also run `& .\.venv\Scripts\python.exe -m vfxai.cli init` explicitly if you want to initialize before launching.

### Start the app (one command)

```powershell
& .\.venv\Scripts\python.exe -m vfxai.dev
```

This starts the Python API on `127.0.0.1:8765` and the Vite/Three.js development preview on `127.0.0.1:5173`, opens the browser after both are ready, and keeps the services attached to this PowerShell window. Press **Ctrl+C** here to stop them. Vite hot-reloads frontend edits; restart this command after Python code changes. Launch does not reinstall packages or rebuild `dist`.

For a built, non-hot-reloading preview instead, run `npm run build` once after frontend changes, then `& .\.venv\Scripts\python.exe -m vfxai.server`. That server serves the built UI and API on port 8765. `& .\.venv\Scripts\python.exe -m vfxai.server --api-only --no-browser` is available when you intentionally want only the local API; the normal development command above starts the API and Vite together.

### Train and test

```powershell
& .\.venv\Scripts\python.exe -m vfxai.cli train --epochs 20 --batch-size 16 --learning-rate 0.003
```

To run checks and evaluate the active checkpoint (the init step is optional after the first app launch):

```powershell
& .\.venv\Scripts\python.exe -m vfxai.cli init
& .\.venv\Scripts\python.exe -m unittest discover -s tests-python -v
npm test
npm run build
& .\.venv\Scripts\python.exe -m vfxai.cli test
```

### Update source without resetting training

Edit files in this checkout as usual; no ZIP re-download, reinstall, or data migration is needed for source-only edits. For remote source updates, use Git in the **same checkout**—only on a clean branch that tracks its upstream:

```powershell
git status
git pull --ff-only
```

Do not delete `.venv` or the user-data directory. Reinstall dependencies only when their manifests change:

```powershell
# Only if requirements.txt changed:
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Only if package.json or package-lock.json changed:
npm ci
```

Datasets, checkpoints, experiments, generation records, and feedback are outside build output and source files. On Windows they live in `%LOCALAPPDATA%\VFXAI\`; `VFXAI_DATA_DIR` can override that location. Setup and normal source updates do not delete this folder. Back it up before manually removing it. If you deliberately want to continue using an older project-local `.vfxai` data folder, set this in the PowerShell session before running VFXAI: `$env:VFXAI_DATA_DIR = (Join-Path (Get-Location) ".vfxai")`. The browser must support WebGL2 for the 3D view; plan JSON remains inspectable if WebGL is unavailable.

The `.bat` files remain as optional legacy launchers; the recommended workflow does not use them. `BUILD_WINDOWS.bat` does not package an EXE.

## What the first model really does

- `vfxai/model.py` implements a compact NumPy MLP: hashed text features → a tanh hidden layer → category, component-presence, and numeric heads. Parameters start from seeded **random weights**; training runs actual forward propagation, a weighted classification/BCE/MSE loss, manual backpropagation, global gradient clipping, and Adam updates.
- The model has 10 learned prompt categories, 4 component-presence outputs, and 45 learned structured numeric values. Text features are deterministic signed hashes of words, word pairs, and character n-grams. There are no downloaded embeddings or pretrained weights. Effect type, component IDs, name, and resource defaults are supplied by the adapter/schema rather than predicted by additional neural heads.
- A deterministic adapter maps those learned head outputs into the existing JSON plan 1.0 contract. This is **not arbitrary JSON-token generation**. Raw head values and invalid candidates are retained. No fallback example replaces a failed prediction, and generated code is never executed.
- Training data is reproducibly generated and locally stored. Plans are checked against the checked-in JSON schema and Reasoner resource/timing rules. Prompt-family groups are split before training into train, validation, and held-out test. Run reports compare an untrained checkpoint with a trained checkpoint on the same test prompts.
- Feedback ratings are records only. A valid supported example must be **explicitly approved** before a future run can include it; training on approved feedback is an additional opt-in.

### Strict first-version limitations

Plan version 1.0 only supports `effectType: radial-burst` and `core`, `ring`, `lightning`, and `particles`. The first model supervises at most one component of each type. “Beam,” “trail,” aura, charge, and orbit prompt categories are approximated using these radial primitives. The current schema/renderer cannot express true linear beam paths, trails, rotation/orbits, Roblox assets, or staged charge sequences. The model and synthetic data do **not** establish artistic quality. Loss, schema validity, component/category agreement, and resource checks are not a beauty score or a Roblox Studio compatibility test.

See [the model, dataset, training, and evaluation notes](docs/python-model.md) and [the version-1 plan schema](docs/architecture.md).

## Additional local commands

Run these from the repository root when you need to generate a new dataset or inspect checkpoints:

```powershell
& .\.venv\Scripts\python.exe -m vfxai.cli generate-dataset --count 1000 --seed 2026
& .\.venv\Scripts\python.exe -m vfxai.cli checkpoints
& .\.venv\Scripts\python.exe -m vfxai.cli test
```

`generate-dataset` creates a new versioned dataset and makes it active; existing dataset files and checkpoints remain in the user-data folder. For API-only work, the dev launcher already starts the loopback API that Vite proxies. `npm run dev` by itself starts only the preview and therefore needs a separately running API.

## Tests, environment, and current verification

The project has Python unit/integration tests for dataset determinism and splits, schema/resource checks, real gradient/optimizer updates, checkpoint round-trips, explicit feedback approval, local API/CSP boundaries, and an end-to-end training/evaluation run. JavaScript tests cover the plan schema, deterministic Builder/preview, Verifier, and Python Designer bridge. GitHub Actions includes Linux/Windows **source** checks; it no longer builds an Electron executable.

In the current development environment, Python 3.11 and Node 22 are available. The Python suite and JavaScript suite can run here, and Vite can build the UI. **PowerShell and Wine are not available in this environment**, so the PowerShell workflow and actual Windows process cleanup are not claimed as locally tested. The Windows Actions workflow uses PowerShell for future source checks; no Windows result is claimed until it runs.

## Historical files

Some `desktop/`, `electron-builder.yml`, `scripts/desktop-dev.mjs`, and desktop reports/tests remain as historical source from an earlier experiment. They are not active dependencies, npm commands, CI packaging steps, or part of the supported start path. No EXE or installer is created by the current workflow.
