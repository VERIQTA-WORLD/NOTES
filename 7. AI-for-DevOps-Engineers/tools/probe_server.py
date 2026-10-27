"""Local deterministic endpoints for timeout/HTTP probe exercises."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import time
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=='/slow':time.sleep(2)
        code=500 if self.path=='/error' else 404 if self.path=='/missing' else 302 if self.path=='/redirect' else 200
        self.send_response(code)
        if code==302:self.send_header('Location','/ok')
        self.end_headers()
        try:self.wfile.write(b'Veriqta HTTP exercise\n')
        except (BrokenPipeError,ConnectionResetError):pass
ThreadingHTTPServer(('127.0.0.1',8090),Handler).serve_forever()
