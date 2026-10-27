"""Summarize structured application logs without inventing causes or copying payloads."""
import argparse,collections,json,pathlib

def summarize(text):
    events=collections.Counter();codes=collections.Counter();paths=collections.Counter();times=[];gaps=0
    for line in text.splitlines():
        if not line.strip():continue
        try:
            start=line.index('{');record=json.loads(line[start:])
            event=record.get('event','unknown');events[event]+=1
            if record.get('timestamp'):times.append(record['timestamp'])
            if event=='request':
                codes[str(record['status'])]+=1
                if int(record['status'])>=500:paths[record.get('path','unknown')]+=1
        except (ValueError,TypeError,KeyError):gaps+=1
    requests=sum(codes.values());failures=sum(v for k,v in codes.items() if k.isdigit() and int(k)>=500)
    return {'events':dict(events),'http_status_counts':dict(codes),'error_paths':dict(paths),
       'requests_observed':requests,'errors_observed':failures,'error_fraction':failures/requests if requests else None,
       'first_timestamp':min(times) if times else None,'last_timestamp':max(times) if times else None,
       'unparsed_lines':gaps,'interpretation':'Counts describe the collected sample; inspect dependency evidence before assigning a cause.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file');a=p.parse_args();print(json.dumps(summarize(pathlib.Path(a.file).read_text()),indent=2))
