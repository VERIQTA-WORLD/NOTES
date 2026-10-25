"""Application contract and HTTP serialization tests; network integration is test_app.py."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

class OfflineTests(unittest.TestCase):
    def test_home_contract(self):
        status, kind, body = app.response("/")
        self.assertEqual(status, 200)
        self.assertEqual(kind, "application/json")
        self.assertEqual(body["version"], app.VERSION)
        self.assertTrue(body["message"])
    def test_liveness_contract(self):
        self.assertEqual(app.response("/health")[2], {"status": "alive"})
    def test_ready_without_marker(self):
        with tempfile.TemporaryDirectory() as d:
            old = app.READY_FILE
            try:
                app.READY_FILE = Path(d) / "marker"
                self.assertEqual(app.response("/ready")[0], 200)
            finally:
                app.READY_FILE = old
    def test_unready_does_not_fail_liveness(self):
        with tempfile.TemporaryDirectory() as d:
            old = app.READY_FILE
            try:
                app.READY_FILE = Path(d) / "marker"
                app.READY_FILE.touch()
                self.assertEqual(app.response("/ready")[0], 503)
                self.assertEqual(app.response("/health")[0], 200)
            finally:
                app.READY_FILE = old
    def test_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            old = app.READY_FILE
            try:
                app.READY_FILE = Path(d) / "marker"
                app.READY_FILE.touch()
                self.assertFalse(app.response("/ready")[2]["ready"])
                app.READY_FILE.unlink()
                self.assertTrue(app.response("/ready")[2]["ready"])
            finally:
                app.READY_FILE = old
    def test_missing_route(self):
        self.assertEqual(app.response("/absent")[0], 404)
    def test_metrics_shape(self):
        status, kind, body = app.response("/metrics")
        self.assertEqual(status, 200)
        self.assertIn("text/plain", kind)
        self.assertIn("# TYPE lab_http_requests_total counter", body)
        for s in ("200", "404", "503"):
            self.assertIn(f'lab_http_requests_total{{status="{s}"}}', body)
    def test_http_serialization_and_log_correlation(self):
        # Execute the actual handler against an in-memory output stream.
        handler = app.Handler.__new__(app.Handler)
        handler.path = "/?query=example"
        handler.request_version = "HTTP/1.1"
        handler.requestline = "GET /?query=example HTTP/1.1"
        handler.command = "GET"
        handler.wfile = io.BytesIO()
        logs = io.StringIO()
        with contextlib.redirect_stdout(logs):
            handler.do_GET()
        headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
        self.assertIn(b"200 OK", headers)
        self.assertEqual(json.loads(body)["version"], app.VERSION)
        event = json.loads(logs.getvalue())
        self.assertIn(event["trace_id"].encode(), headers)
        self.assertEqual(event["path"], "/")
        self.assertEqual(len(event["span_id"]), 16)
        self.assertGreaterEqual(event["duration_ms"], 0)

if __name__ == "__main__":
    unittest.main()
