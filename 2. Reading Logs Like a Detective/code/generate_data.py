"""Create deterministic Veriqta investigation datasets."""
from pathlib import Path
import json
import gzip
from datetime import datetime,timedelta,timezone

BASE=Path(__file__).resolve().parents[1]/"datasets"
def write(path,text):
    p=BASE/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8")
def jsonlines(rows):return "".join(json.dumps(r)+"\n" for r in rows)
def event(at,level,service,name,message,rid="veriqta-001",**extra):
    return dict(timestamp="2026-01-15T"+at+"Z",level=level,service=service,event=name,message=message,request_id=rid,**extra)
def access_line(i,status,path="/api/users",minute=0):
    stamp=f"15/Jan/2026:14:{minute:02d}:{i%60:02d} +0000"
    return f'198.51.100.10 - - [{stamp}] "GET {path} HTTP/1.1" {status} 100 "-" "veriqta-client/1.0" 0.010 veriqta-{i:04d}\n'
def main():
    rows=[event("10:15:20","INFO","web","startup","Server started"),
          event("10:16:05","INFO","db-client","db_connected","Connected to database"),
          event("10:17:12","ERROR","db-client","db_connection_lost","Connection lost"),
          event("10:17:30","INFO","web","db_retry","Retrying database connection"),
          event("10:18:05","INFO","db-client","db_connected","Connected to database")]
    write(Path("basics.jsonl"),jsonlines(rows))
    text="".join(f'{r["timestamp"]} {r["level"]} [{r["service"]}] request_id={r["request_id"]} {r["message"]}\n' for r in rows)
    write(Path("app.log"),text)
    with gzip.open(BASE/"app.log.1.gz","wt",encoding="utf-8") as f:f.write(text)
    write(Path("auth.log"),'2026-01-15T11:00:00Z INFO [auth] actor=veriqta-demo Login attempt\n2026-01-15T11:00:02Z WARN [auth] actor=veriqta-demo Invalid password\n2026-01-15T11:01:02Z ERROR [auth] actor=veriqta-demo Account locked after repeated failures\n')
    timeline=[event("14:21:05","INFO","proxy","request_received","Checkout request received"),
              event("14:21:10","INFO","api","request_started","Processing request"),
              event("14:21:12","INFO","api","payment_call","Calling payment service"),
              event("14:21:15","ERROR","db-client","db_connection_failed","Database connection refused"),
              event("14:21:18","WARN","payment","slow_dependency","Slow response while waiting for dependency"),
              event("14:21:20","ERROR","api","payment_timeout","Payment service timeout"),
              event("14:21:25","ERROR","api","order_failed","Failed to complete order"),
              event("14:21:30","ERROR","worker","retry_exhausted","Job failed: retry limit reached")]
    write(Path("timeline-unsorted.jsonl"),jsonlines([timeline[i] for i in [1,3,2,5,0,6,4,7]]))
    offset=[dict(timeline[3],timestamp="2026-01-15T16:21:15+02:00"),dict(timeline[2],timestamp="2026-01-15T09:21:12-05:00")]
    write(Path("mixed-offsets.jsonl"),jsonlines(offset))
    status=[200,200,404,500,200,500,200,404,502,200,500,200]
    paths=["/","/api/users","/missing","/api/users","/","/api/users","/health","/missing","/","/health","/api/orders","/"]
    write(Path("access.log"),"".join(access_line(i,s,p,i//6) for i,(s,p) in enumerate(zip(status,paths))))
    accessrows=[]
    for i,(s,p) in enumerate(zip(status,paths)):
        accessrows.append(event(f"14:{i//6:02d}:{i%60:02d}","ERROR" if s>=500 else "WARN" if s>=400 else "INFO",
            "veriqta-proxy","request_completed","Request completed",rid=f"veriqta-{i:04d}",status=s,path=p,duration_ms=10))
    write(Path("access.jsonl"),jsonlines(accessrows))
    write(Path("access-before.log"),"".join(access_line(i,500 if i<20 else 200,minute=i//60) for i in range(1000)))
    write(Path("access-after.log"),"".join(access_line(i,500 if i<5 else 200,minute=i//60) for i in range(100)))
    write(Path("malformed.jsonl"),jsonlines([rows[0]])+'not JSON\n'+json.dumps({"timestamp":"2026-01-15T10:00:00","level":"INFO"})+'\n')
    request="veriqta-checkout-42"
    proxy=[event("10:05:06","ERROR","proxy","request_completed","Upstream unavailable",request,status=502,path="/api/users",duration_ms=1),
           event("10:06:12","INFO","proxy","request_completed","Request completed","veriqta-recovery-1",status=200,path="/api/users",duration_ms=8)]
    app=[event("10:04:20","WARN","api","cache_miss","Cache miss; database fallback expected","unrelated-cache"),
         event("10:05:02","ERROR","api","db_connection_failed","Could not connect to database",request,error_code="ECONNREFUSED"),
         event("10:05:03","ERROR","api","startup_failed","Application exiting after failed startup check",request),
         event("10:06:10","INFO","api","db_connected","Database connection restored","veriqta-recovery-1")]
    db=[event("10:04:58","ERROR","postgres","write_failed","could not write to file pg_wal: No space left on device",request,error_code="ENOSPC"),
        event("10:04:59","FATAL","postgres","shutdown","Database shutting down after write failure",request),
        event("10:06:08","INFO","postgres","ready","Database is ready to accept connections","veriqta-recovery-1")]
    change=[event("09:55:00","INFO","deploy","config_change","Debug export job enabled without retention or size cap","veriqta-change-17")]
    kube=[event("09:40:00","WARN","kubelet","old_container_terminated","Previous analytics Pod OOMKilled; different workload","unrelated-analytics",pod="analytics-old"),
          event("10:05:05","WARN","kubelet","BackOff","Back-off restarting failed container api",request,pod="veriqta-api-incident")]
    for name,events in [("proxy",proxy),("app",app),("database",db),("changes",change),("kubernetes",kube)]:write(Path("challenge")/(name+".jsonl"),jsonlines(events))
    write(Path("challenge/proxy-error.log"),'2026/01/15 10:05:06 [error] 34#34: *12 connect() failed (111: Connection refused) while connecting to upstream, upstream: "http://app:8000/api/users"\n')
    write(Path("challenge/storage-before.txt"),'Captured: 2026-01-15T10:05:00Z\nFilesystem         Size Used Avail Use% Mounted on\n/dev/veriqta-data    10G  10G     0 100% /var/lib/postgresql/data\nExport job output: /var/lib/postgresql/data/debug-exports = 8G\n')
    write(Path("challenge/storage-after.txt"),'Captured: 2026-01-15T10:06:05Z\nFilesystem         Size Used Avail Use% Mounted on\n/dev/veriqta-data    10G   2G    8G  20% /var/lib/postgresql/data\nMitigation record: capped export job; moved reviewed disposable debug exports off database volume; retained database/WAL files intact.\n')
    write(Path("challenge/recovery.jsonl"),jsonlines([event("10:06:05","INFO","operator","mitigation","Export job disabled; approved disposable exports moved to separate storage","veriqta-recovery-1"),event("10:06:20","INFO","probe","verification","Three application/database reads succeeded; storage stable","veriqta-recovery-1")]))
    print("Veriqta datasets ready:",BASE)
if __name__=="__main__":main()
