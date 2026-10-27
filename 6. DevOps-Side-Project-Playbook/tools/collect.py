"""Read-only Kubernetes evidence collector. Records unavailable evidence explicitly."""
import argparse,datetime,json,pathlib,re,subprocess

def capture(ns,out):
    if not re.fullmatch(r'veriqta-[a-z0-9-]+',ns): raise ValueError('Veriqta lab namespace required')
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    out.chmod(0o700)
    def run(name,args):
        r=subprocess.run(['kubectl','-n',ns,*args],capture_output=True,text=True,timeout=45)
        (out/name).write_text(r.stdout)
        (out/(name+'.status.json')).write_text(json.dumps({'exit_code':r.returncode,'stderr':r.stderr}))
        return r
    for resource in ('pods','events','services','endpointslices','deployments','replicasets'):
        run(resource+'.json',['get',resource,'-o','json'])
    run('top.txt',['top','pods'])
    pods=json.loads((out/'pods.json').read_text() or '{"items":[]}')
    for pod in pods.get('items',[]):
        name=pod['metadata']['name']
        run(name+'.describe.txt',['describe','pod',name])
        for container in pod['spec'].get('containers',[]):
            for previous in (False,True):
                suffix='.previous' if previous else ''
                run(name+'.'+container['name']+suffix+'.log',['logs',name,'-c',container['name'],'--timestamps','--since=2h',*(['--previous'] if previous else [])])
    (out/'collection.json').write_text(json.dumps({'namespace':ns,'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--output',required=True);a=p.parse_args();capture(a.namespace,a.output)
