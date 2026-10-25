"""Flask entry point using the same lab routes and logging behavior."""
import logging
import os
import time
from flask import Flask,g,jsonify,request
from logging_core import configure_logging,emit,handle,request_id,startup_check,safe_text

app=Flask(__name__)
log=configure_logging(os.getenv("LOG_DIR","logs"))
startup_check(log)
@app.before_request
def before_request():
    g.started=time.monotonic();g.request_id=request_id(request.headers.get("X-Request-ID"))
@app.route("/",defaults={"path":""})
@app.route("/<path:path>")
def route(path):
    status,body=handle("/"+path,g.request_id,log)
    return jsonify(body),status
@app.after_request
def after_request(response):
    response.headers["X-Request-ID"]=g.request_id
    emit(log,logging.ERROR if response.status_code>=500 else logging.WARNING if response.status_code>=400 else logging.INFO,
         "request_completed","Request completed",request_id=g.request_id,path=request.path,status=response.status_code,
         duration_ms=round((time.monotonic()-g.started)*1000,3),
         client_ip=request.remote_addr,user_agent=safe_text(request.headers.get("User-Agent","")))
    return response
if __name__=="__main__":
    app.run(host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","5000")),debug=False)
