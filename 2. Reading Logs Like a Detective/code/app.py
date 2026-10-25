"""Local standard-library HTTP entry point; binds to loopback by default."""
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from logging_core import configure_logging,emit,handle,request_id,startup_check,safe_text

LOG=None
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        started=time.monotonic()
        rid=request_id(self.headers.get("X-Request-ID"))
        path=urlsplit(self.path).path
        status,body=handle(path,rid,LOG)
        raw=json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("X-Request-ID",rid)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):
            emit(LOG,logging.WARNING,"client_disconnected","Client disconnected before response completed",request_id=rid)
        emit(LOG,logging.ERROR if status>=500 else logging.WARNING if status>=400 else logging.INFO,
             "request_completed","Request completed",request_id=rid,path=path,status=status,
             duration_ms=round((time.monotonic()-started)*1000,3),
             client_ip=self.client_address[0],user_agent=safe_text(self.headers.get("User-Agent","")))
    def log_message(self,*args):pass

def main():
    global LOG
    LOG=configure_logging(os.getenv("LOG_DIR","logs"))
    try:
        startup_check(LOG)
        host=os.getenv("HOST","127.0.0.1");port=int(os.getenv("PORT","5000"))
        server=ThreadingHTTPServer((host,port),Handler)
    except Exception as exc:
        emit(LOG,logging.ERROR,"startup_failed","Application could not start",error_type=type(exc).__name__)
        return 1
    emit(LOG,logging.INFO,"listening","HTTP listener ready",host=host,port=port)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();emit(LOG,logging.INFO,"shutdown","Application stopped")
    return 0

if __name__=="__main__":sys.exit(main())
