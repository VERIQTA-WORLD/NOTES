"""Loopback-only endpoint for health-check exercises."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status=503 if (ROOT/'runtime/unhealthy').exists() else 200
        if self.path!='/health':status=404
        body=json.dumps({'status':'ok' if status==200 else 'unavailable','service':'veriqta-demo'}).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
if __name__=='__main__':
    print('Veriqta health endpoint: http://127.0.0.1:8050/health',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',8050),Handler)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
