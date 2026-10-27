"""Local evidence capture; raw evidence stays private and is never sent by this tool."""
import argparse,datetime,json,pathlib,subprocess
ALLOWED={'veriqta-app','veriqta-staging','veriqta-prod'}
def collect(namespace,output):
    if namespace not in ALLOWED:raise ValueError('Choose a Veriqta lab namespace')
    out=pathlib.Path(output);out.mkdir(parents=True,exist_ok=True);out.chmod(0o700)
    def run(name,args):
        try:
            result=subprocess.run(['kubectl','--context','kind-veriqta-ai','-n',namespace,*args],capture_output=True,text=True,timeout=30)
            (out/name).write_text(result.stdout)
            (out/(name+'.status.json')).write_text(json.dumps({'exit_code':result.returncode,'stderr':result.stderr}))
            return result.stdout if result.returncode==0 else ''
        except subprocess.TimeoutExpired:
            (out/(name+'.status.json')).write_text(json.dumps({'error':'collection_timeout'}));return ''
    for resource in ('pods','events','deployments','replicasets','services','endpointslices'):
        run(resource+'.json',['get',resource,'-o','json'])
    run('top.txt',['top','pods'])
    run('rollout-history.txt',['rollout','history','deployment/api'])
    data=json.loads((out/'pods.json').read_text() or '{"items":[]}')
    for pod in data.get('items',[]):
        name=pod['metadata']['name'];run(name+'.describe.txt',['describe','pod',name])
        for c in pod['spec'].get('containers',[]):
            for previous in (False,True):
                suffix='.previous' if previous else ''
                run(name+'.'+c['name']+suffix+'.log',['logs',name,'-c',c['name'],'--timestamps','--tail=200','--since=1h',*(['--previous'] if previous else [])])
    (out/'capture.json').write_text(json.dumps({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'namespace':namespace}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--output',required=True);a=p.parse_args();collect(a.namespace,a.output)
