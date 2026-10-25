"""Local teaching server. No external Python dependencies; not a production server."""
import json
import os
from pathlib import Path
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

COUNTS = {"200": 0, "404": 0, "503": 0}
LOCK = threading.Lock()
VERSION = os.getenv("APP_VERSION", "1.0")
MESSAGE = os.getenv("APP_MESSAGE", "Hello from Veriqta")
READY_FILE = Path(os.getenv("NOT_READY_FILE", "/tmp/devops-not-ready"))

def response(path):
    if path == "/health":
        return 200, "application/json", {"status": "alive"}
    if path == "/ready":
        ready = not READY_FILE.exists()
        return (200 if ready else 503), "application/json", {"ready": ready}
    if path == "/":
        return 200, "application/json", {"message": MESSAGE, "version": VERSION}
    if path == "/metrics":
        with LOCK:
            counts = dict(COUNTS)
        lines = ["# HELP lab_http_requests_total Completed requests including probes.",
                 "# TYPE lab_http_requests_total counter"]
        lines += [f'lab_http_requests_total{{status="{s}"}} {n}' for s, n in counts.items()]
        return 200, "text/plain; version=0.0.4", "\n".join(lines) + "\n"
    return 404, "application/json", {"error": "not found"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        started = time.monotonic()
        path = urlsplit(self.path).path
        # One server span per request; this is a tracing teaching example,
        # not an OpenTelemetry exporter or a distributed tracing backend.
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        status, content_type, body = response(path)
        raw = (json.dumps(body) if isinstance(body, dict) else body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Trace-ID", trace_id)
        self.end_headers()
        self.wfile.write(raw)
        with LOCK:
            COUNTS[str(status)] += 1
        print(json.dumps({"event": "http_request", "path": path,
              "status": status, "trace_id": trace_id, "span_id": span_id,
              "duration_ms": round((time.monotonic()-started)*1000, 3)}), flush=True)
    def log_message(self, *args):
        pass

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(json.dumps({"event": "startup", "host": host, "port": port, "version": VERSION}), flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
