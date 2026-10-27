"""Normalize logs, Kubernetes events, OTLP traces and deployment records to evidence."""
import argparse,datetime,html,json,pathlib

def timestamp(value):
    if isinstance(value,int) or (isinstance(value,str) and value.isdigit()):
        return datetime.datetime.fromtimestamp(int(value)/1e9,datetime.timezone.utc)
    t=datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('timestamp lacks timezone')
    return t.astimezone(datetime.timezone.utc)

def normalize(data,source,reference):
    output=[]
    def add(time,service,event,trace_id=''):
        output.append({'timestamp':timestamp(time).isoformat(),'source':source,'service':str(service),'event':str(event),'trace_id':trace_id or '', 'evidence':reference})
    if source=='traces':
        for resource in data.get('resourceSpans',[]):
            attrs={a['key']:a['value'].get('stringValue','') for a in resource.get('resource',{}).get('attributes',[])}
            for scope in resource.get('scopeSpans',[]):
                for span in scope.get('spans',[]):
                    duration=(int(span['endTimeUnixNano'])-int(span['startTimeUnixNano']))/1e9
                    add(span['startTimeUnixNano'],attrs.get('service.name','unknown'),f"{span['name']} duration={duration:.6f}s attributes={json.dumps(span.get('attributes',[]),sort_keys=True)}",span.get('traceId',''))
    elif source=='events' and data.get('kind') in ('EventList','List'):
        for event in data.get('items',[]):
            time=event.get('eventTime') or event.get('lastTimestamp') or event['metadata']['creationTimestamp']
            involved=event.get('involvedObject') or event.get('regarding',{})
            add(time,involved.get('name','unknown'),event.get('reason','')+': '+event.get('message',event.get('note','')))
    elif source=='deployments' and data.get('kind')=='DeploymentList':
        for deployment in data['items']:
            meta=deployment['metadata']
            for condition in deployment.get('status',{}).get('conditions',[]):
                if condition.get('lastUpdateTime'):
                    add(condition['lastUpdateTime'],meta['name'],f"deployment condition {condition['type']}={condition['status']}; current generation={meta.get('generation')}; images="+','.join(c['image'] for c in deployment['spec']['template']['spec']['containers']))
    elif 'timestamp' in data:
        add(data['timestamp'],data.get('service','unknown'),data.get('event','')+' '+json.dumps({k:v for k,v in data.items() if k not in ('timestamp','service','event')},sort_keys=True),data.get('trace_id',''))
    else:raise ValueError('unsupported record shape')
    return output

def records(path):
    text=path.read_text()
    try:return [(1,json.loads(text))]
    except json.JSONDecodeError:
        result=[]
        for line_number,line in enumerate(text.splitlines(),1):
            if not line.strip():continue
            # kubectl --timestamps prefixes RFC3339; Compose --no-log-prefix does not.
            if not line.lstrip().startswith('{') and ' {' in line:line=line[line.index(' {')+1:]
            result.append((line_number,json.loads(line)))
        return result

def build(inputs,out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True);timeline=[];gaps=[]
    for source,directory in inputs.items():
        files=sorted(p for p in pathlib.Path(directory).rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log'))
        if not files:gaps.append(f'{source}: no input files')
        for file in files:
            try:
                for line,data in records(file):
                    try:timeline.extend(normalize(data,source,str(file)+f':{line}'))
                    except (ValueError,KeyError,TypeError) as exc:gaps.append(f'{file}:{line}: {exc}')
            except (ValueError,OSError,TypeError) as exc:gaps.append(f'{file}: {exc}')
    timeline.sort(key=lambda r:(r['timestamp'],r['source'],r['evidence']))
    (out/'timeline.json').write_text(json.dumps(timeline,indent=2))
    def clean(value):
        text=html.escape(str(value).replace('|','/').replace('\n',' '),quote=False)
        for char in ('\\','`','[',']','*','_'):
            text=text.replace(char,'\\'+char)
        return text
    lines=['# Veriqta incident timeline','\nAll times UTC. Ordering shows correlation; causal claims require controlled reproduction and independent evidence.','\n| UTC | Source | Service | Observation | Evidence |','|---|---|---|---|---|']
    for r in timeline:lines.append('| '+' | '.join(clean(r[k]) for k in ('timestamp','source','service','event','evidence'))+' |')
    lines+=['\n## Evidence gaps',*['- '+g for g in gaps]]
    (out/'timeline.md').write_text('\n'.join(lines)+'\n')
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('timestamp','source','service','event','evidence'))+'</tr>' for r in timeline)
    (out/'timeline.html').write_text('<!doctype html><meta charset="utf-8"><title>Veriqta incident timeline</title><h1>Veriqta incident timeline</h1><p>Correlation is not proof of causation. All times UTC.</p><table><tr><th>UTC</th><th>Source</th><th>Service</th><th>Observation</th><th>Evidence</th></tr>'+rows+'</table><h2>Evidence gaps</h2><pre>'+html.escape('\n'.join(gaps))+'</pre>')
    (out/'postmortem.md').write_text('# Veriqta incident review\n\n## Summary\n\n## User impact and duration\n\n## Timeline\nSee [timeline](timeline.md).\n\n## Leading hypothesis and evidence\n\n## Controlled reproduction and recovery comparison\n\n## Root cause confidence and alternative explanations\n\n## Contributing factors\n\n## What went well\n\n## What did not go well\n\n## Actions\n| Action | Owner | Due date | Verification |\n|---|---|---|---|\n\n## Unresolved questions\n')
    return timeline,gaps
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for source in ('logs','events','traces','deployments'):p.add_argument('--'+source,required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    timeline,gaps=build({k:getattr(a,k) for k in ('logs','events','traces','deployments')},a.output)
    print(json.dumps({'records':len(timeline),'gaps':len(gaps)}))
    if not timeline:raise SystemExit(2)
