import json
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from vfxai import server as server_module


class LocalServerTests(unittest.TestCase):
    def test_server_module_entrypoint_selects_api_only_strict_port_mode(self):
        with patch.object(server_module, "serve") as serve:
            self.assertEqual(
                server_module.main(["--api-only", "--strict-port", "--no-browser", "--port", "8765"]),
                0,
            )
        serve.assert_called_once_with(
            host="127.0.0.1",
            port=8765,
            open_browser=False,
            serve_static=False,
            strict_port=True,
        )

    def test_api_only_server_needs_no_build_and_does_not_serve_ui(self):
        with TemporaryDirectory() as temporary:
            with patch.object(server_module, "DIST_DIR", Path(temporary)):
                app = server_module.VFXAIHTTPServer(
                    ("127.0.0.1", 0), server_module.VFXAIRequestHandler, serve_static=False
                )
                thread = threading.Thread(target=app.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{app.server_address[1]}"
                try:
                    with urlopen(base + "/api/health", timeout=3) as response:
                        self.assertTrue(json.loads(response.read())["ok"])
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(base + "/", timeout=3)
                    self.assertEqual(caught.exception.code, 404)
                finally:
                    app.shutdown()
                    app.server_close()
                    thread.join(timeout=3)

    def test_static_server_and_api_are_loopback_same_origin_and_csp_protected(self):
        with TemporaryDirectory() as temporary:
            dist = Path(temporary)
            (dist / "index.html").write_text("<!doctype html><title>local</title>", encoding="utf-8")
            with patch.object(server_module, "DIST_DIR", dist):
                app = server_module.VFXAIHTTPServer(("127.0.0.1", 0), server_module.VFXAIRequestHandler)
                thread = threading.Thread(target=app.serve_forever, daemon=True)
                thread.start()
                base = f"http://127.0.0.1:{app.server_address[1]}"
                try:
                    with urlopen(base + "/", timeout=3) as response:
                        body = response.read().decode("utf-8")
                        self.assertIn("<title>local</title>", body)
                        self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
                        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

                    with urlopen(base + "/api/health", timeout=3) as response:
                        health = json.loads(response.read())
                        self.assertTrue(health["ok"])
                        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), None)

                    generated = {"id": "gen-test", "category": "lightning", "validation": {"ok": False}}
                    request = Request(
                        base + "/api/generate",
                        data=json.dumps({"prompt": "test", "checkpoint_id": "unit", "seed": 9}).encode(),
                        headers={"Content-Type": "application/json", "Origin": base},
                        method="POST",
                    )
                    with patch.object(server_module, "generate_prediction", return_value=generated) as infer:
                        with urlopen(request, timeout=3) as response:
                            self.assertEqual(json.loads(response.read()), generated)
                        infer.assert_called_once_with("test", "unit", 9)

                    traversal = Request(base + "/%2e%2e/README.md")
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(traversal, timeout=3)
                    self.assertEqual(caught.exception.code, 404)

                    cross_origin = Request(
                        base + "/api/health",
                        data=b"{}",
                        headers={"Content-Type": "application/json", "Origin": "http://attacker.invalid"},
                        method="POST",
                    )
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(cross_origin, timeout=3)
                    self.assertEqual(caught.exception.code, 403)

                    foreign_host = Request(
                        base + "/api/health",
                        data=b"{}",
                        headers={"Content-Type": "application/json", "Host": "attacker.invalid"},
                        method="POST",
                    )
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(foreign_host, timeout=3)
                    self.assertEqual(caught.exception.code, 403)
                finally:
                    app.shutdown()
                    app.server_close()
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
