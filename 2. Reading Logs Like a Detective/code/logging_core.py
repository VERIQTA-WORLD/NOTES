"""Shared logging and application behavior for the Veriqta log lab."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import time
import uuid
from datetime import datetime, timezone

RID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")

def request_id(value):
    return value if isinstance(value,str) and RID.fullmatch(value) else uuid.uuid4().hex

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def safe_text(value, limit=200):
    return str(value).replace("\r"," ").replace("\n"," ").replace("\x1b"," ")[:limit]

class JsonFormatter(logging.Formatter):
    def format(self,record):
        data={"timestamp":utc_now(),"level":record.levelname,"service":"veriqta-api",
              "pid":os.getpid(),"event":getattr(record,"event","message"),
              "message":record.getMessage()}
        data.update(getattr(record,"fields",{}))
        if record.exc_info:
            data["exception"]=self.formatException(record.exc_info)
        return json.dumps(data,ensure_ascii=True,allow_nan=False)

class TextFormatter(logging.Formatter):
    def format(self,record):
        fields=getattr(record,"fields",{})
        text=f'{utc_now()} {record.levelname} [veriqta-api] pid={os.getpid()} request_id={fields.get("request_id","-")} event={getattr(record,"event","message")} {safe_text(record.getMessage())}'
        details=" ".join(f"{key}={safe_text(value)}" for key,value in fields.items() if key!="request_id")
        if details:text += " "+details
        if record.exc_info:text += "\n"+self.formatException(record.exc_info)
        return text

def configure_logging(directory=None):
    log=logging.getLogger("veriqta")
    log.setLevel(logging.INFO);log.propagate=False
    for handler in list(log.handlers):
        log.removeHandler(handler);handler.close()
    stream=logging.StreamHandler(sys.stdout);stream.setFormatter(JsonFormatter());log.addHandler(stream)
    if directory:
        path=Path(directory);path.mkdir(parents=True,exist_ok=True)
        for filename,formatter in [("app.log",TextFormatter()),("app.jsonl",JsonFormatter())]:
            handler=RotatingFileHandler(path/filename,maxBytes=1048576,backupCount=3,encoding="utf-8")
            handler.setFormatter(formatter);log.addHandler(handler)
    return log

def emit(log,level,event,message,**fields):
    log.log(level,message,extra={"event":event,"fields":fields})

def query_database(rid):
    # No real credentials are written to logs. Connections are short-lived in this lab.
    import psycopg
    with psycopg.connect(host=os.getenv("DB_HOST","db"),port=int(os.getenv("DB_PORT","5432")),
            dbname=os.getenv("DB_NAME","veriqta"),user=os.getenv("DB_USER","veriqta"),
            password=os.environ["DB_PASSWORD"],connect_timeout=2,
            application_name="veriqta-"+rid[:48],options="-c statement_timeout=2000") as conn:
        return conn.execute("SELECT 'Veriqta database reachable' AS result").fetchone()[0]

def startup_check(log):
    if os.getenv("REQUIRE_DB","0")=="1":
        if not os.getenv("DB_HOST") or not os.getenv("DB_PASSWORD"):
            emit(log,logging.ERROR,"config_invalid","Required database configuration is missing")
            raise ValueError("DB_HOST and DB_PASSWORD are required")
        try:
            query_database("startup")
        except Exception as exc:
            emit(log,logging.ERROR,"db_startup_failed","Database startup check failed",error_type=type(exc).__name__)
            raise RuntimeError("Database startup check failed") from None
    emit(log,logging.INFO,"startup","Veriqta Log Lab starting",require_db=os.getenv("REQUIRE_DB","0"))

def handle(path,rid,log):
    emit(log,logging.INFO,"request_started","Request received",request_id=rid,path=path)
    if path in {"/","/health"}:
        return 200,{"message":"Veriqta Log Lab is running","request_id":rid}
    if path=="/error":
        try:raise RuntimeError("Veriqta deliberate lab exception")
        except RuntimeError:
            log.exception("Deliberate lab exception",extra={"event":"lab_exception","fields":{"request_id":rid,"path":path}})
        return 500,{"error":"Deliberate lab failure","request_id":rid}
    if path=="/slow":
        time.sleep(0.3)
        emit(log,logging.WARNING,"slow_operation","Simulated slow operation",request_id=rid,path=path)
        return 200,{"message":"Slow operation completed","request_id":rid}
    if path=="/api/users":
        if os.getenv("REQUIRE_DB","0")!="1":
            return 200,{"users":[{"id":"veriqta-demo"}],"request_id":rid}
        try:
            result=query_database(rid)
            emit(log,logging.INFO,"db_query_ok","Database query completed",request_id=rid)
            return 200,{"result":result,"request_id":rid}
        except Exception as exc:
            emit(log,logging.ERROR,"db_query_failed","Database query failed",request_id=rid,error_type=type(exc).__name__)
            return 503,{"error":"Database unavailable","request_id":rid}
    return 404,{"error":"Route not found","request_id":rid}
