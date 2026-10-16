# PowerShell development workflow on Windows

VFXAI is a local Python-backed browser app, not a packaged Electron desktop app. For ordinary development, use the existing checkout and PowerShell; no ZIP refresh or launcher batch files are needed.

## Requirements

- 64-bit Python 3.11 (`py -3.11` should work)
- Node.js 22.12 or newer (`node` and `npm` on `PATH`)
- PowerShell opened at the repository root

## First-time setup

Run once per checkout:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

The virtual environment stays in `.venv`. Python packages are pinned in `requirements.txt`; JavaScript packages are locked by `package-lock.json`. The API initializes the default synthetic dataset and random, untrained checkpoint only when missing; it preserves an existing active dataset and trained checkpoint. To initialize before launching, run `& .\.venv\Scripts\python.exe -m vfxai.cli init` once.

## Start, train, test

Start both API and hot-reloading Three.js preview with one command:

```powershell
& .\.venv\Scripts\python.exe -m vfxai.dev
```

The verified entry points in this checkout are `vfxai.server` for the loopback Python API and `npm run dev` for Vite. The app launcher supervises both: API `127.0.0.1:8765`, Vite `127.0.0.1:5173` (with `/api` proxied to the API). It opens the browser after both are ready, stays in the foreground, and stops its child processes when Ctrl+C is pressed. Frontend changes hot-reload; restart after Python changes. It does not run dependency installation or a production build.

Train the model:

```powershell
& .\.venv\Scripts\python.exe -m vfxai.cli train --epochs 20 --batch-size 16 --learning-rate 0.003
```

Run Python tests, JavaScript tests, a build, and held-out evaluation (`init` is safe to repeat):

```powershell
& .\.venv\Scripts\python.exe -m vfxai.cli init
& .\.venv\Scripts\python.exe -m unittest discover -s tests-python -v
npm test
npm run build
& .\.venv\Scripts\python.exe -m vfxai.cli test
```

For a standalone server that serves the built `dist/` UI, build first with `npm run build`, then run `& .\.venv\Scripts\python.exe -m vfxai.server`. It opens the local app on port 8765. The `--api-only --no-browser` options are intended for pairing the API with another local preview such as Vite.

## Updating code and dependencies

Make code edits in this checkout or, on a clean branch with an upstream configured, update source in place with Git:

```powershell
git status
git pull --ff-only
```

Vite reflects frontend saves; restart VFXAI after Python changes. Saved training state is not part of `dist/`, `node_modules/`, or `.venv/`:

- `%LOCALAPPDATA%\VFXAI\` by default on Windows
- An explicitly selected `VFXAI_DATA_DIR` if configured

If continuing data from an older project-local `.vfxai` folder, set this before launching from that checkout:

```powershell
$env:VFXAI_DATA_DIR = (Join-Path (Get-Location) ".vfxai")
```

Do not delete the state folder when updating source. Only reinstall when the corresponding manifest changes:

```powershell
# If requirements.txt changes:
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# If package.json or package-lock.json changes:
npm ci
```

The first dependency installation needs internet access. Running and training are local after setup. The active model starts with random, untrained weights; training is explicit. `.bat` files remain as optional legacy helpers, not the recommended workflow. Historical `desktop/` and Electron builder files are inactive and do not create an EXE or installer.

PowerShell and Wine are not installed in the current development environment, so the Windows command/session behavior and child-process cleanup have not been run locally. The Windows Actions workflow now uses PowerShell for dependency setup, entry-point help, tests, build, and training smoke checks; report Windows behavior as verified only after that workflow runs.
