"""Human-operated verification of every API Pod through a business request."""
import argparse,json,subprocess
ALLOWED={'veriqta-app','veriqta-staging','veriqta-prod'}
def verify(namespace,expected_error=None):
    if namespace not in ALLOWED:raise ValueError('Veriqta lab namespace required')
    base=['kubectl','--context','kind-veriqta-ai','-n',namespace]
    doc=json.loads(subprocess.check_output(base+['get','pods','-l','app=veriqta-api','-o','json'],text=True,timeout=15))
    ready=[p for p in doc['items'] if not p['metadata'].get('deletionTimestamp') and any(c.get('type')=='Ready' and c.get('status')=='True' for c in p.get('status',{}).get('conditions',[]))]
    desired=json.loads(subprocess.check_output(base+['get','deployment','api','-o','json'],text=True,timeout=15))['spec']['replicas']
    if len(ready)!=desired:raise RuntimeError('Ready Pod count does not match desired replicas')
    code="import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/users',timeout=5)); assert d['status']=='ok' and len(d['users'])==2; print('business request passed')"
    if expected_error==500:
        code="import json,urllib.request,urllib.error\ntry:\n urllib.request.urlopen('http://127.0.0.1:8000/api/users',timeout=5)\nexcept urllib.error.HTTPError as e:\n d=json.load(e); assert e.code==500 and d.get('error_kind')=='database_unavailable'; print('Expected database HTTP 500 confirmed')\nelse:\n raise SystemExit('Expected HTTP 500 was not observed')"
    for pod in ready:
        subprocess.run(base+['exec',pod['metadata']['name'],'-c','api','--','python','-c',code],check=True,timeout=15)
    print(json.dumps({'namespace':namespace,'ready_pods_checked':len(ready),'expected_http_status':expected_error or 200,'business_check':'expected outcome confirmed'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--expect-error',type=int,choices=[500]);a=p.parse_args();verify(a.namespace,a.expect_error)
