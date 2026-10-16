"""Run the local Python API and Vite source preview as one foreground app."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
API_URL = "http://127.0.0.1:8765"
PREVIEW_URL = "http://127.0.0.1:5173"


def _check_runtime() -> list[str]:
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Node.js 22.12+ and npm are required. Install them once, then reopen PowerShell.")
    try:
        version = subprocess.run([node, "--version"], check=True, capture_output=True, text=True).stdout.strip().lstrip("v")
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Could not run Node.js at {node!r}.") from error
    try:
        major, minor, *_ = (int(part) for part in version.split("."))
    except ValueError as error:
        raise RuntimeError(f"Could not parse Node.js version {version!r}.") from error
    if major < 22 or (major == 22 and minor < 12):
        raise RuntimeError(f"VFXAI requires Node.js 22.12 or newer; found {version}.")
    if not (ROOT / "node_modules" / "vite" / "bin" / "vite.js").is_file():
        raise RuntimeError("Vite is not installed. From the project root run: npm ci")
    return [npm]


def _api_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "vfxai.server",
        "--api-only",
        "--no-browser",
        "--strict-port",
        "--port",
        "8765",
    ]


def _vite_command(npm: str, host: str) -> list[str]:
    if os.name == "nt":
        command_shell = os.environ.get("COMSPEC", "cmd.exe")
        return [command_shell, "/d", "/s", "/c", f"npm.cmd run dev -- --host {host}"]
    return [npm, "run", "dev", "--", "--host", host]


def _spawn(command: Sequence[str], *, label: str) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {
        "cwd": ROOT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    print(f"[VFXAI] Starting {label}...", flush=True)
    return subprocess.Popen(list(command), **options)  # type: ignore[arg-type]


def _is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _wait_for(url: str, processes: Sequence[tuple[str, subprocess.Popen[bytes]]], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for label, process in processes:
            return_code = process.poll()
            if return_code is not None:
                raise RuntimeError(f"{label} exited during startup (exit code {return_code}).")
        if _is_ready(url):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {url}.")


def _stop(process: subprocess.Popen[bytes] | None, label: str) -> None:
    if process is None or process.poll() is not None:
        return
    print(f"[VFXAI] Stopping {label}...", flush=True)
    if os.name == "nt":
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=4)
            return
        except (OSError, subprocess.TimeoutExpired):
            taskkill = shutil.which("taskkill.exe") or "taskkill.exe"
            subprocess.run(
                [taskkill, "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=4)
            return
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def run(no_browser: bool = False, preview_host: str = "127.0.0.1") -> int:
    if preview_host not in {"127.0.0.1", "localhost", "0.0.0.0"}:
        raise RuntimeError("Preview host must be 127.0.0.1, localhost, or 0.0.0.0.")
    npm_commands = _check_runtime()
    children: list[tuple[str, subprocess.Popen[bytes]]] = []

    def stop_on_sigterm(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous_sigterm = signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        api = _spawn(_api_command(), label="Python API on 127.0.0.1:8765")
        children.append(("Python API", api))
        _wait_for(API_URL + "/api/health", children, timeout=90)

        vite = _spawn(_vite_command(npm_commands[0], preview_host), label=f"Vite preview on {preview_host}:5173")
        children.append(("Vite preview", vite))
        _wait_for(PREVIEW_URL + "/api/health", children, timeout=60)

        print(f"[VFXAI] Development app ready: {PREVIEW_URL}/", flush=True)
        print("[VFXAI] Frontend hot reload is enabled. Press Ctrl+C here to stop both services.", flush=True)
        if not no_browser:
            try:
                opened = webbrowser.open(PREVIEW_URL + "/", new=2)
                if not opened:
                    print(f"[VFXAI] Browser could not be opened automatically; open {PREVIEW_URL}/ manually.", flush=True)
            except Exception as error:
                print(f"[VFXAI] Browser did not open automatically: {error}", flush=True)
                print(f"[VFXAI] Open this URL manually: {PREVIEW_URL}/", flush=True)

        while True:
            for label, process in children:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"{label} stopped unexpectedly (exit code {return_code}).")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n[VFXAI] Stopping local development app.", flush=True)
        return 0
    finally:
        for label, process in reversed(children):
            _stop(process, label)
        signal.signal(signal.SIGTERM, previous_sigterm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start VFXAI's Python API and hot-reloading Three.js preview")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser (useful for automated checks)")
    parser.add_argument("--preview-host", default="127.0.0.1", help="Vite bind host; keep the default for local use")
    args = parser.parse_args(argv)
    try:
        return run(no_browser=args.no_browser, preview_host=args.preview_host)
    except (OSError, RuntimeError) as error:
        print(f"[VFXAI] Could not start development app: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
