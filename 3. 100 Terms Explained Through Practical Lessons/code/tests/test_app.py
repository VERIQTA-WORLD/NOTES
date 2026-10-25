import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        app.READY_FILE = Path(cls.tmp.name) / "not-ready"
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()
    def get(self, path):
        try:
            return urlopen(self.base + path, timeout=3)
        except HTTPError as err:
            return err
    def test_home(self):
        with self.get("/") as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(json.load(r)["version"], app.VERSION)
    def test_health(self):
        with self.get("/health") as r:
            self.assertEqual(json.load(r)["status"], "alive")
    def test_readiness_failure_and_recovery(self):
        app.READY_FILE.touch()
        try:
            with self.get("/ready") as r:
                self.assertEqual(r.status, 503)
            with self.get("/health") as r:
                self.assertEqual(r.status, 200)
        finally:
            app.READY_FILE.unlink(missing_ok=True)
        with self.get("/ready") as r:
            self.assertTrue(json.load(r)["ready"])
    def test_missing(self):
        with self.get("/absent") as r:
            self.assertEqual(r.status, 404)
    def test_trace_header(self):
        with self.get("/") as r:
            self.assertEqual(len(r.headers["X-Trace-ID"]), 32)
    def test_metrics(self):
        with self.get("/") as r:
            r.read()
        with self.get("/metrics") as r:
            self.assertIn('lab_http_requests_total{status="200"}', r.read().decode())
if __name__ == "__main__":
    unittest.main()
