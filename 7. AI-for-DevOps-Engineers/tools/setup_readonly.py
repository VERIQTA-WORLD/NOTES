"""Human-admin setup for an expiring namespace-limited identity in local kind."""
import argparse,json,pathlib,subprocess,urllib.parse
ALLOWED={'veriqta-app','veriqta-staging','veriqta-prod'}
def run(*args):
    return subprocess.check_output(['kubectl','--context','kind-veriqta-ai',*args],text=True,timeout=30)
def main():
    p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--output',default='.private/assistant.kubeconfig.json');a=p.parse_args()
    if a.namespace not in ALLOWED:p.error('Veriqta lab namespace required')
    current=json.loads(run('config','view','--raw','--minify','-o','json'))
    cluster=current['clusters'][0]['cluster']
    if urllib.parse.urlsplit(cluster['server']).hostname not in ('127.0.0.1','localhost'):raise SystemExit('Local kind only')
    ns=a.namespace;name='veriqta-assistant'
    def obj(kind,api='v1',**extra):return {'apiVersion':api,'kind':kind,'metadata':{'name':name,'namespace':ns},**extra}
    items=[obj('ServiceAccount'),obj('Role','rbac.authorization.k8s.io/v1',rules=[
      {'apiGroups':[''],'resources':['pods','pods/log','events','services'],'verbs':['get','list','watch']},
      {'apiGroups':['apps'],'resources':['deployments','replicasets'],'verbs':['get','list','watch']},
      {'apiGroups':['discovery.k8s.io'],'resources':['endpointslices'],'verbs':['get','list','watch']}]),
      obj('RoleBinding','rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':name},subjects=[{'kind':'ServiceAccount','name':name,'namespace':ns}])]
    subprocess.run(['kubectl','--context','kind-veriqta-ai','apply','-f','-'],input=json.dumps({'apiVersion':'v1','kind':'List','items':items}),text=True,check=True,timeout=30)
    token=run('-n',ns,'create','token',name,'--duration=15m').strip()
    config={'apiVersion':'v1','kind':'Config','current-context':'veriqta-readonly',
      'clusters':[{'name':'veriqta-local','cluster':{'server':cluster['server'],'certificate-authority-data':cluster['certificate-authority-data']}}],
      'users':[{'name':'veriqta-reader','user':{'token':token}}],
      'contexts':[{'name':'veriqta-readonly','context':{'cluster':'veriqta-local','user':'veriqta-reader','namespace':ns}}]}
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.parent.chmod(0o700)
    target.write_text(json.dumps(config));target.chmod(0o600)
    print('Short-lived read-only kubeconfig written privately; refresh when expired')
if __name__=='__main__':main()
