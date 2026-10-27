"""Local Alertmanager receiver; never forwards notifications externally."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 1000000:self.send_error(413);return
        data=json.loads(self.rfile.read(size))
        print(json.dumps(data),flush=True)
        self.send_response(204);self.end_headers()
HTTPServer(('0.0.0.0',8081),Handler).serve_forever()
