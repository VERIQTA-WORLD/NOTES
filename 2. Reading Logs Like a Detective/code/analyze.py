"""Read-only JSONL and combined-access-log investigation commands."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import re
import sys

ACCESS=re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" (?P<status>\d{3}) (?P<bytes>\d+|-) "(?P<referrer>[^"]*)" "(?P<agent>[^"]*)"(?: (?P<seconds>[0-9.]+) (?P<request_id>[A-Za-z0-9_-]+))?$')
MONTHS={m:i for i,m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],1)}
def timestamp(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp must include UTC Z or an explicit offset")
    return dt.astimezone(timezone.utc)
def access_timestamp(value):
    # Month labels in this NGINX format are English regardless of reader locale.
    date,offset=value.split(" ")
    day,month,rest=date.split("/",2)
    year,hour,minute,second=rest.split(":")
    return timestamp(f"{year}-{MONTHS[month]:02d}-{int(day):02d}T{hour}:{minute}:{second}{offset[:3]}:{offset[3:]}")
def open_text(path):
    return gzip.open(path,"rt",encoding="utf-8") if str(path).endswith(".gz") else open(path,encoding="utf-8")
def read_json(paths):
    rows=[];invalid=0
    for path in paths:
        with open_text(path) as stream:
            for line_number,line in enumerate(stream,1):
                if not line.strip():continue
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError("Object required")
                    row=dict(row);dt=timestamp(row["timestamp"])
                    row["_time"]=dt;row["_file"]=str(path);row["_line"]=line_number
                    rows.append(row)
                except (ValueError,TypeError,KeyError,AttributeError):invalid+=1
    return rows,invalid

def access_summary(path):
    total=0;invalid=0;statuses=Counter();endpoints=Counter();minutes=Counter()
    with open_text(path) as stream:
        for line in stream:
            if not line.strip():continue
            m=ACCESS.fullmatch(line.rstrip("\n"))
            if not m:invalid+=1;continue
            try:dt=access_timestamp(m["time"])
            except (ValueError,KeyError):invalid+=1;continue
            status=int(m["status"]);total+=1;statuses[str(status)]+=1
            if status>=400:endpoints[f'{m["path"]} {status}']+=1
            if status>=500:minutes[dt.strftime("%Y-%m-%dT%H:%MZ")]+=1
    bad=sum(n for code,n in statuses.items() if 500<=int(code)<=599)
    return {"requests":total,"invalid_lines":invalid,"status_counts":dict(sorted(statuses.items())),
            "server_errors":bad,"server_error_percent":round(100*bad/total,3) if total else None,
            "failing_endpoints":dict(endpoints.most_common()),"server_errors_per_minute":dict(sorted(minutes.items()))}

def serial(row):
    return {**{k:v for k,v in row.items() if not k.startswith("_") and k not in {"timestamp","file","line"}},
            "timestamp":row["_time"].isoformat().replace("+00:00","Z"),
            "file":row["_file"],"line":row["_line"]}

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["summary","timeline","request","access"])
    p.add_argument("files",nargs="+");p.add_argument("--id");p.add_argument("--since");p.add_argument("--until")
    args=p.parse_args()
    if args.command=="access":
        if len(args.files)!=1:p.error("access requires one file")
        print(json.dumps(access_summary(args.files[0]),indent=2));return
    rows,invalid=read_json(args.files)
    start=timestamp(args.since) if args.since else None;end=timestamp(args.until) if args.until else None
    rows=[r for r in rows if (start is None or r["_time"]>=start) and (end is None or r["_time"]<end)]
    rows.sort(key=lambda r:(r["_time"],r["_file"],r["_line"]))
    if args.command=="summary":
        errors=Counter(r.get("event","unknown") for r in rows if r.get("level") in {"ERROR","FATAL","CRITICAL"})
        result={"events":len(rows),"invalid_lines":invalid,"levels":dict(Counter(r.get("level","unknown") for r in rows)),"error_events":dict(errors.most_common())}
        print(json.dumps(result,indent=2))
    else:
        if args.command=="request":
            if not args.id:p.error("request requires --id")
            rows=[r for r in rows if r.get("request_id")==args.id]
        for row in rows:print(json.dumps(serial(row)))
        if invalid:print(f"Skipped invalid lines: {invalid}",file=sys.stderr)
if __name__=="__main__":main()
