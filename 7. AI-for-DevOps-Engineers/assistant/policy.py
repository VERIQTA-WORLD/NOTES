"""Policy is enforced independently of model text and retrieved documents."""
import json,os,pathlib,re,selectors,signal,subprocess,time,urllib.parse
NAMESPACES={'veriqta-app','veriqta-staging','veriqta-prod'}
ACTIONS=('pod_status','events','logs','deployments','services','endpointslices')
class PolicyError(ValueError):pass

def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!={'question','actions'}:raise PolicyError('plan shape rejected')
    if not isinstance(plan['question'],str) or not 1<=len(plan['question'])<=2000:raise PolicyError('question size rejected')
    actions=plan['actions']
    if not isinstance(actions,list) or not 1<=len(actions)<=6 or any(not isinstance(a,str) for a in actions) or len(set(actions))!=len(actions):raise PolicyError('action count rejected')
    if any(a not in ACTIONS for a in actions):raise PolicyError('tool not allowed')
    return plan

def validate_target(namespace,pod):
    if namespace not in NAMESPACES:raise PolicyError('namespace not allowed')
    if not isinstance(pod,str) or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',pod):raise PolicyError('invalid Pod name')

def command(action,namespace,pod,kubeconfig):
    validate_target(namespace,pod)
    base=['kubectl','--kubeconfig',str(kubeconfig),'--context','veriqta-readonly','--request-timeout=10s','-n',namespace]
    templates={
      'pod_status':['get','pod',pod,'-o','json'],
      'events':['get','events','--field-selector','involvedObject.name='+pod,'-o','json'],
      'logs':['logs',pod,'-c','api','--tail=100','--since=1h','--limit-bytes=32768','--timestamps'],
      'deployments':['get','deployments','-l','app=veriqta-api','-o','json'],
      'services':['get','services','-o','json'],
      'endpointslices':['get','endpointslices','-l','kubernetes.io/service-name=api','-o','json']}
    if action not in templates:raise PolicyError('tool not allowed')
    return base+templates[action]

def validate_kubeconfig(path,namespace):
    path=pathlib.Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:raise PolicyError('use a private regular kubeconfig file')
    if path.stat().st_size>100000:raise PolicyError('kubeconfig size rejected')
    doc=json.loads(path.read_text())
    if doc.get('current-context')!='veriqta-readonly':raise PolicyError('unexpected context')
    if len(doc.get('users',[]))!=1 or set(doc['users'][0]['user'])!={'token'}:raise PolicyError('only a short-lived token identity is supported')
    if len(doc.get('contexts',[]))!=1 or doc['contexts'][0]['context'].get('namespace')!=namespace:raise PolicyError('namespace/context mismatch')
    if len(doc.get('clusters',[]))!=1:raise PolicyError('cluster count rejected')
    cluster=doc['clusters'][0]['cluster'];url=urllib.parse.urlsplit(cluster.get('server',''))
    if url.scheme!='https' or url.hostname not in ('127.0.0.1','localhost') or not cluster.get('certificate-authority-data') or cluster.get('insecure-skip-tls-verify'):raise PolicyError('only the verified local kind lab is supported')
    return path.resolve()

def bounded(argv,timeout=15,max_bytes=100000):
    # No shell, no model-selected flags, no inherited cloud or model credentials.
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','TMPDIR')}
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    selected=selectors.DefaultSelector();selected.register(process.stdout,selectors.EVENT_READ)
    start=time.monotonic();data=bytearray()
    try:
        while selected.get_map():
            if time.monotonic()-start>timeout:raise PolicyError('tool timeout')
            for key,_ in selected.select(.1):
                part=os.read(key.fd,4096)
                if not part:selected.unregister(key.fileobj);continue
                data.extend(part)
                if len(data)>max_bytes:raise PolicyError('tool output limit')
        return process.wait(timeout=1),data.decode(errors='replace')
    finally:
        selected.close()
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()
        process.stdout.close()
