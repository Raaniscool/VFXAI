"""Loopback-only local HTTP UI/API. No cloud calls, CORS, or prompt telemetry."""

from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .checkpoints import list_checkpoints, load_checkpoint
from .config import (
    APP_VERSION,
    CATEGORIES,
    COMPONENT_TYPES,
    DEFAULT_BATCH_SIZE,
    DEFAULT_DATASET_COUNT,
    DEFAULT_DATASET_SEED,
    DEFAULT_EPOCHS,
    DEFAULT_HIDDEN_SIZE,
    DEFAULT_INIT_SEED,
    DEFAULT_LEARNING_RATE,
    DEFAULT_TRAIN_SEED,
)
from .dataset import (
    dataset_summary,
    generate_dataset,
    get_active_dataset_path,
    load_dataset,
    set_active_dataset,
)
from .evaluation import evaluate_model, save_predictions
from .feedback import approve_feedback, create_feedback, list_feedback
from .inference import compare_checkpoints, generate_prediction, generation_history, get_generation
from .paths import (
    CHECKPOINTS_DIR,
    DATASETS_DIR,
    DIST_DIR,
    EXPERIMENTS_DIR,
    LOGS_DIR,
    RUNTIME_DIR,
    SCHEMA_PATH,
    ensure_state_dirs,
)
from .training import list_experiments, read_training_status

MAX_REQUEST_BYTES = 1024 * 1024
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-src 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)


class VFXAIHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type["VFXAIRequestHandler"],
        serve_static: bool = True,
    ):
        super().__init__(address, handler)
        self.serve_static = serve_static
        self.training_process: subprocess.Popen[bytes] | None = None
        self.training_lock = threading.Lock()
        self.server_started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.default_checkpoint = f"random-seed-{DEFAULT_INIT_SEED}-h{DEFAULT_HIDDEN_SIZE}"


class VFXAIRequestHandler(SimpleHTTPRequestHandler):
    server: VFXAIHTTPServer
    protocol_version = "HTTP/1.1"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies or user prompts.
        sys.stdout.write("[VFXAI HTTP] " + format % args + "\n")

    def end_headers(self) -> None:
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urllib.parse.urlsplit(self.path)
        route = parsed.path
        if route.startswith("/api/"):
            try:
                self._api_get(route, urllib.parse.parse_qs(parsed.query))
            except Exception as error:
                self._json_response(500, {"error": f"{type(error).__name__}: {error}"})
            return
        if self.server.serve_static:
            self._serve_asset(route)
        else:
            self._text_response(404, "The API-only server does not serve the browser UI.")

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        route = parsed.path
        if route.startswith("/api/"):
            self._json_response(405, {"error": "HEAD is not supported for API endpoints."})
            return
        if self.server.serve_static:
            self._serve_asset(route, head=True)
        else:
            self._text_response(404, "The API-only server does not serve the browser UI.")

    def do_POST(self) -> None:  # noqa: N802
        host_header = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        if host_header not in {"127.0.0.1", "localhost"}:
            self._json_response(403, {"error": "The local API accepts loopback Host headers only."})
            return
        origin = self.headers.get("Origin")
        if origin:
            parsed_origin = urllib.parse.urlsplit(origin)
            if parsed_origin.scheme != "http" or parsed_origin.netloc.lower() != self.headers.get("Host", "").lower():
                self._json_response(403, {"error": "Cross-origin API requests are not accepted."})
                return
        route = urllib.parse.urlsplit(self.path).path
        if not route.startswith("/api/"):
            self._json_response(404, {"error": "Not found."})
            return
        try:
            payload = self._read_json()
            self._api_post(route, payload)
        except ValueError as error:
            self._json_response(400, {"error": str(error)})
        except FileNotFoundError as error:
            self._json_response(404, {"error": str(error)})
        except RuntimeError as error:
            self._json_response(409, {"error": str(error)})
        except Exception as error:
            self._json_response(500, {"error": f"{type(error).__name__}: {error}"})

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length.") from error
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("Request body exceeds the 1 MiB limit.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Request must be valid UTF-8 JSON: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError("Request JSON must be an object.")
        return payload

    def _api_get(self, route: str, query: dict[str, list[str]]) -> None:
        if route == "/api/health":
            self._json_response(200, {"ok": True, "version": APP_VERSION, "server_started": self.server.server_started})
        elif route == "/api/meta":
            self._json_response(
                200,
                {
                    "ok": True,
                    "version": APP_VERSION,
                    "default_checkpoint": self.server.default_checkpoint,
                    "categories": list(CATEGORIES),
                    "components": list(COMPONENT_TYPES),
                    "checkpoints": list_checkpoints(),
                    "dataset": dataset_summary(),
                    "training": read_training_status(),
                    "trained_scope": {
                        "effect_type": "radial-burst only",
                        "components": ["core", "ring", "lightning", "particles"],
                        "category_count": 10,
                        "neural_output": "category + component-presence + 45 continuous structured values",
                        "not_supported": ["arbitrary JSON token generation", "true beam/trail paths", "Roblox asset export", "artistic-quality scoring"],
                    },
                },
            )
        elif route == "/api/checkpoints":
            self._json_response(200, {"checkpoints": list_checkpoints()})
        elif route == "/api/dataset":
            datasets = []
            for path in sorted(DATASETS_DIR.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True):
                try:
                    manifest_path = path.with_suffix(".manifest.json")
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
                    datasets.append({"file": path.name, "count": manifest.get("actual_count"), "seed": manifest.get("seed"), "sha256": manifest.get("sha256"), "active": path == get_active_dataset_path()})
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
            self._json_response(200, {"active": dataset_summary(), "datasets": datasets})
        elif route == "/api/training/status":
            status = read_training_status()
            status["process_alive"] = self._training_alive(status)
            self._json_response(200, status)
        elif route == "/api/generations":
            limit = _query_int(query, "limit", 40, 1, 200)
            self._json_response(200, {"generations": generation_history(limit)})
        elif route == "/api/feedback":
            self._json_response(200, {"feedback": list_feedback()[:100]})
        elif route == "/api/experiments":
            limit = _query_int(query, "limit", 30, 1, 100)
            self._json_response(200, {"experiments": list_experiments(limit)})
        elif route == "/api/schema":
            self._json_response(200, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        else:
            self._json_response(404, {"error": "Unknown API endpoint."})

    def _api_post(self, route: str, payload: dict[str, Any]) -> None:
        if route == "/api/generate":
            record = generate_prediction(
                payload.get("prompt", ""),
                payload.get("checkpoint_id") or self.server.default_checkpoint,
                payload.get("seed", DEFAULT_INIT_SEED),
            )
            self._json_response(200, record)
        elif route == "/api/compare":
            prompt = payload.get("prompt", "")
            checkpoint_a = payload.get("checkpoint_a")
            checkpoint_b = payload.get("checkpoint_b")
            if not checkpoint_a or not checkpoint_b:
                raise ValueError("Select two checkpoints to compare.")
            report = compare_checkpoints(prompt, checkpoint_a, checkpoint_b, payload.get("seed", DEFAULT_INIT_SEED))
            self._json_response(200, report)
        elif route == "/api/dataset/generate":
            count = _payload_int(payload, "count", DEFAULT_DATASET_COUNT, 100, 5000)
            seed = _payload_int(payload, "seed", DEFAULT_DATASET_SEED, 0, 0xFFFFFFFF)
            path, manifest = generate_dataset(count, seed)
            set_active_dataset(path)
            self._json_response(201, {"path": str(path), "manifest": manifest, "activated": True})
        elif route == "/api/train/start":
            result = self._start_training(payload)
            self._json_response(202, result)
        elif route == "/api/train/control":
            action = payload.get("action")
            if action not in {"pause", "resume", "stop"}:
                raise ValueError("Training action must be pause, resume, or stop.")
            status = read_training_status()
            if status.get("status") not in {"starting", "running", "paused"}:
                raise RuntimeError("There is no active training run to control.")
            control_path = RUNTIME_DIR / "training-control.json"
            temporary = control_path.with_suffix(".tmp")
            control_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps({"action": "run" if action == "resume" else action, "updated_at": time.time()}) + "\n", encoding="utf-8")
            temporary.replace(control_path)
            self._json_response(200, {"ok": True, "action": action, "status": status})
        elif route == "/api/evaluate":
            result = self._evaluate(payload)
            self._json_response(200, result)
        elif route == "/api/feedback":
            generation_id = payload.get("generation_id")
            generation = get_generation(generation_id)
            if generation is None:
                raise FileNotFoundError(f"Generation not found: {generation_id}")
            corrected = payload.get("corrected_plan")
            record = create_feedback(
                generation,
                payload.get("rating", ""),
                payload.get("notes", ""),
                corrected_plan=corrected,
                corrected_plan_text=payload.get("corrected_plan_json"),
                category=payload.get("category"),
            )
            self._json_response(201, {"feedback": record, "message": "Saved locally. Ratings do not train the model until a valid example is explicitly approved."})
        elif route.startswith("/api/feedback/") and route.endswith("/approve"):
            feedback_id = route[len("/api/feedback/") : -len("/approve")].strip("/")
            approved = approve_feedback(feedback_id, get_active_dataset_path())
            self._json_response(200, {"feedback": approved, "message": "Approved for a future training run. It is not automatically applied."})
        else:
            self._json_response(404, {"error": "Unknown API endpoint."})

    def _start_training(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.server.training_lock:
            status = read_training_status()
            if status.get("status") in {"starting", "running", "paused"} and self._training_alive(status):
                raise RuntimeError("A training process is already active.")
            dataset_path = get_active_dataset_path()
            if dataset_path is None:
                raise FileNotFoundError("No dataset is active. Generate a dataset first.")
            load_dataset(dataset_path)
            epochs = _payload_int(payload, "epochs", DEFAULT_EPOCHS, 1, 1000)
            batch_size = _payload_int(payload, "batch_size", DEFAULT_BATCH_SIZE, 1, 128)
            hidden_size = _payload_int(payload, "hidden_size", DEFAULT_HIDDEN_SIZE, 16, 128)
            seed = _payload_int(payload, "seed", DEFAULT_TRAIN_SEED, 0, 0xFFFFFFFF)
            try:
                learning_rate = float(payload.get("learning_rate", DEFAULT_LEARNING_RATE))
            except (TypeError, ValueError) as error:
                raise ValueError("Learning rate must be a number.") from error
            if not 1e-5 <= learning_rate <= 0.1:
                raise ValueError("Learning rate must be between 0.00001 and 0.1.")
            resume = payload.get("resume_checkpoint") or None
            if resume:
                model, metadata, optimizer = load_checkpoint(resume)
                if metadata.get("kind") != "trained" or optimizer is None:
                    raise ValueError("Select a trained checkpoint with saved optimizer state to resume.")
                hidden_size = model.hidden_size
            include_feedback = bool(payload.get("include_feedback", False))
            run_id = time.strftime("run-%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:6]
            status_path = RUNTIME_DIR / "training.json"
            control_path = RUNTIME_DIR / "training-control.json"
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_path = LOGS_DIR / f"{run_id}.log"
            command = [
                sys.executable,
                "-m",
                "vfxai.cli",
                "train",
                "--dataset",
                str(dataset_path),
                "--epochs",
                str(epochs),
                "--batch-size",
                str(batch_size),
                "--learning-rate",
                str(learning_rate),
                "--seed",
                str(seed),
                "--hidden-size",
                str(hidden_size),
                "--status-path",
                str(status_path),
                "--control-path",
                str(control_path),
                "--run-id",
                run_id,
            ]
            if resume:
                command.extend(["--resume", resume])
            if include_feedback:
                command.append("--include-feedback")
            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            with log_path.open("ab") as log_stream:
                process = subprocess.Popen(
                    command,
                    cwd=str(Path(__file__).resolve().parents[1]),
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    start_new_session=(os.name != "nt"),
                )
            self.server.training_process = process
            temporary = control_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"action": "run", "updated_at": time.time()}) + "\n", encoding="utf-8")
            temporary.replace(control_path)
            return {
                "ok": True,
                "run_id": run_id,
                "pid": process.pid,
                "status": "starting",
                "log_file": str(log_path),
                "message": "Training runs locally in a background process. The UI polls progress; prompts and plans are not transmitted.",
            }

    def _training_alive(self, status: dict[str, Any]) -> bool:
        process = self.server.training_process
        if process is not None and process.poll() is None:
            return True
        pid = status.get("pid")
        try:
            if pid is not None:
                os.kill(int(pid), 0)
                return True
        except (OSError, ValueError, TypeError):
            return False
        return False

    def _evaluate(self, payload: dict[str, Any]) -> dict[str, Any]:
        dataset_path = get_active_dataset_path()
        if dataset_path is None:
            raise FileNotFoundError("No active dataset is available.")
        records = load_dataset(dataset_path)
        checkpoint_ids = [payload.get("checkpoint_id")]
        compare_id = payload.get("compare_checkpoint")
        if compare_id and compare_id != checkpoint_ids[0]:
            checkpoint_ids.append(compare_id)
        split = payload.get("split", "test")
        if split not in {"validation", "test"}:
            raise ValueError("Evaluation split must be validation or test.")
        evaluation_id = f"evaluation-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:6]}"
        output_dir = EXPERIMENTS_DIR / evaluation_id
        output_dir.mkdir(parents=True, exist_ok=False)
        reports: list[dict[str, Any]] = []
        for index, checkpoint_id in enumerate(checkpoint_ids):
            if not checkpoint_id:
                raise ValueError("Select a checkpoint to evaluate.")
            model, _, _ = load_checkpoint(checkpoint_id)
            report = evaluate_model(model, records, split, checkpoint_id, include_predictions=True)
            save_predictions(output_dir / f"{index}-{checkpoint_id}-predictions.jsonl", report.pop("predictions"))
            reports.append(report)
        comparison = None
        if len(reports) == 2:
            first, second = reports
            metric_keys = ("category_accuracy", "component_exact_match", "component_f1", "numeric_mae_normalized", "valid_plan_rate")
            comparison = {
                "same_held_out_prompts": first["example_count"] == second["example_count"],
                "checkpoint_a": first["checkpoint_id"],
                "checkpoint_b": second["checkpoint_id"],
                "metrics": {
                    key: {
                        "checkpoint_a": first[key],
                        "checkpoint_b": second[key],
                        "delta_b_minus_a": second[key] - first[key],
                    }
                    for key in metric_keys
                },
                "loss_total": {
                    "checkpoint_a": first["loss"]["total"],
                    "checkpoint_b": second["loss"]["total"],
                    "delta_b_minus_a": second["loss"]["total"] - first["loss"]["total"],
                },
                "artistic_quality_evaluated": False,
            }
        result = {
            "evaluation_id": evaluation_id,
            "dataset_file": dataset_path.name,
            "split": split,
            "reports": reports,
            "comparison": comparison,
            "output_directory": str(output_dir),
            "artistic_quality_evaluated": False,
        }
        (output_dir / "evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        return result

    def _serve_asset(self, request_path: str, head: bool = False) -> None:
        try:
            decoded = urllib.parse.unquote(request_path, errors="strict")
        except (UnicodeError, ValueError):
            self._text_response(400, "Bad request.")
            return
        if decoded in {"", "/"}:
            decoded = "/index.html"
        if "\\" in decoded or "\0" in decoded or any(part == ".." for part in decoded.split("/")):
            self._text_response(404, "Not found.")
            return
        relative = decoded.lstrip("/")
        target = (DIST_DIR / relative).resolve()
        root = DIST_DIR.resolve()
        if root not in target.parents and target != root:
            self._text_response(404, "Not found.")
            return
        if not target.is_file():
            self._text_response(404, "Not found.")
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._text_response(404, "Not found.")
            return
        content_type, _ = mimetypes.guess_type(target.name)
        if target.suffix == ".js":
            content_type = "text/javascript"
        if target.suffix == ".css":
            content_type = "text/css"
        if target.suffix == ".json":
            content_type = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        if target.parent.name == "assets" and target.name != "index.html":
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _json_response(self, status: int, payload: Any) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _text_response(self, status: int, text: str) -> None:
        encoded = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def _payload_int(payload: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(payload.get(key, default))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be an integer.") from error
    if number < minimum or number > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}.")
    return number


def _query_int(query: dict[str, list[str]], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(query.get(key, [str(default)])[0])
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be an integer.") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}.")
    return number


def _find_port(host: str, preferred: int) -> int:
    if preferred == 0:
        return 0
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError(f"No free local port in range {preferred}..{preferred + 49}.")


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    serve_static: bool = True,
    strict_port: bool = False,
) -> None:
    if host not in {"localhost", "127.0.0.1"}:
        try:
            if not ipaddress.ip_address(host).is_loopback or ":" in host:
                raise ValueError("VFXAI's API is local-only; host must be 127.0.0.1 or localhost.")
        except ValueError as error:
            if "local-only" in str(error):
                raise
            raise ValueError("VFXAI's API is local-only; host must be 127.0.0.1 or localhost.") from error
    if not 0 <= int(port) <= 65535:
        raise ValueError("Port must be between 0 and 65,535.")
    ensure_state_dirs()
    if serve_static and not (DIST_DIR / "index.html").is_file():
        raise FileNotFoundError("Built UI not found at dist/index.html. Run npm run build first, or use python -m vfxai.dev.")
    from .setup import initialize_project

    initialize_project()
    selected_port = int(port) if strict_port else _find_port(host, int(port))
    server = VFXAIHTTPServer((host, selected_port), VFXAIRequestHandler, serve_static=serve_static)
    actual_port = int(server.server_address[1])
    browser_host = "127.0.0.1" if host == "localhost" else host
    url = f"http://{browser_host}:{actual_port}/"
    if serve_static:
        print(f"[VFXAI] Local app ready: {url}")
        print("[VFXAI] Python model/API and built Three.js preview are running locally; press Ctrl+C to stop.")
    else:
        print(f"[VFXAI] Local API ready: {url} (API-only mode)")
    if open_browser and serve_static:
        try:
            opened = webbrowser.open(url, new=2)
            if not opened:
                print(f"[VFXAI] Browser did not open automatically; copy this address into your browser: {url}")
        except Exception as error:
            print(f"[VFXAI] Browser did not open automatically: {error}")
            print(f"[VFXAI] Copy this address into your browser: {url}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n[VFXAI] Shutting down local server.")
    finally:
        server.shutdown()
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the local VFXAI API and built browser UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--api-only", action="store_true", help="Serve only /api routes; useful with the Vite development server")
    parser.add_argument("--strict-port", action="store_true", help="Fail if the requested port is busy instead of selecting another port")
    args = parser.parse_args(argv)
    try:
        serve(
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
            serve_static=not args.api_only,
            strict_port=args.strict_port,
        )
    except (OSError, ValueError, RuntimeError, FileNotFoundError) as error:
        print(f"[VFXAI] Server startup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
