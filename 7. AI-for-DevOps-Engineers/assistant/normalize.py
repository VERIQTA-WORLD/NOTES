"""Extract only reviewed fields; arbitrary logs and Pod specs never become model context."""
import json,re,math
EVENTS={'startup','startup_failed','request','dependency_failed'}
ERRORS={'missing_app_config','database_unavailable','injected_failure'}
def short(value):return str(value)[:120]
def normalize(action,raw):
    if action=='logs':
        records=[];skipped=0
        for line in raw.splitlines():
            try:
                d=json.loads(line[line.index('{'):]);event=d.get('event')
                if event not in EVENTS:skipped+=1;continue
                record={'event':event}
                if isinstance(d.get('timestamp'),str) and re.fullmatch(r'[0-9T:Z.+-]{10,40}',d['timestamp']):record['timestamp']=d['timestamp']
                if d.get('error_kind') in ERRORS:record['error_kind']=d['error_kind']
                if type(d.get('status')) is int and 100<=d['status']<=599:record['status']=d['status']
                if d.get('path') in ('/api/users','/health'):record['path']=d['path']
                if isinstance(d.get('duration_seconds'),(float,int)) and math.isfinite(d['duration_seconds']) and 0<=d['duration_seconds']<=60:record['duration_seconds']=d['duration_seconds']
                if re.fullmatch(r'[a-f0-9]{32}',str(d.get('trace_id',''))):record['trace_id']=d['trace_id']
                records.append(record)
            except (ValueError,TypeError):skipped+=1
        return {'records':records,'skipped_unstructured_lines':skipped}
    data=json.loads(raw)
    if action=='pod_status':
        return {'name':short(data['metadata']['name']),'phase':short(data.get('status',{}).get('phase','unknown')),
          'containers':[{'name':short(c['name']),'ready':bool(c.get('ready')),'restarts':c.get('restartCount',0),
            'state':next(iter(c.get('state',{})),'unknown'),'reason':short(next(iter(c.get('state',{}).values()),{}).get('reason',''))} for c in data.get('status',{}).get('containerStatuses',[])]}
    if action=='deployments':
        items=[]
        for d in data.get('items',[]):
            containers=[]
            for c in d['spec']['template']['spec']['containers']:
                public={e['name']:e.get('value','reference') for e in c.get('env',[]) if e['name'] in ('DB_HOST','DB_PORT','RELEASE','READINESS_CHECK_DB')}
                public={k:short(v) if re.fullmatch(r'[A-Za-z0-9._-]{1,120}',str(v)) else '[unavailable]' for k,v in public.items()}
                containers.append({'name':short(c['name']),'settings':public})
            items.append({'name':short(d['metadata']['name']),'desired':d['spec'].get('replicas',1),'ready':d.get('status',{}).get('readyReplicas',0),'containers':containers})
        return {'deployments':items}
    if action=='events':
        return {'events':[{'reason':short(e.get('reason','unknown')),'type':short(e.get('type','unknown')),'count':e.get('count',1),'timestamp':short(e.get('eventTime') or e.get('lastTimestamp') or e.get('metadata',{}).get('creationTimestamp','unknown'))} for e in data.get('items',[])[-100:]]}
    if action=='services':
        return {'services':[{'name':short(s['metadata']['name']),'ports':[{'port':p['port'],'targetPort':short(p.get('targetPort',p['port']))} for p in s['spec'].get('ports',[])]} for s in data.get('items',[])]}
    if action=='endpointslices':
        endpoints=[e for s in data.get('items',[]) for e in s.get('endpoints',[])]
        return {'endpoint_count':len(endpoints),'ready_endpoint_count':sum(e.get('conditions',{}).get('ready') is True for e in endpoints)}
    raise ValueError('unsupported action')
