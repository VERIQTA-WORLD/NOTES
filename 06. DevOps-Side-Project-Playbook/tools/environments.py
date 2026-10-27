"""Administrator-operated platform lab with ownership checks and automatic expiry."""
import argparse,datetime,json,re,subprocess
NOW=lambda:datetime.datetime.now(datetime.timezone.utc)
MANAGED={'veriqta.io/managed-by':'environment-platform'}

def kube(*args,body=None):
    result=subprocess.run(['kubectl',*args],input=json.dumps(body) if body is not None else None,text=True,capture_output=True,check=True,timeout=60)
    return json.loads(result.stdout) if result.stdout.strip().startswith(('{','[')) else result.stdout

def name_ok(name):return bool(re.fullmatch(r'veriqta-env-[a-z0-9](?:[a-z0-9-]{0,36}[a-z0-9])?',name))

def render(name,owner,hours,now=None):
    if not name_ok(name):raise ValueError('name must be veriqta-env- plus a short DNS name')
    if not re.fullmatch(r'[a-zA-Z0-9@._-]{1,80}',owner):raise ValueError('invalid owner')
    if not 1<=hours<=168:raise ValueError('TTL must be 1..168 hours')
    expiry=((now or NOW())+datetime.timedelta(hours=hours)).isoformat()
    namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':name,'labels':{**MANAGED,'pod-security.kubernetes.io/enforce':'restricted'},'annotations':{'veriqta.io/owner':owner,'veriqta.io/expires-at':expiry}}}
    def resource(kind,name_,spec=None,api='v1',**extra):
        value={'apiVersion':api,'kind':kind,'metadata':{'name':name_,'namespace':name}}
        if spec is not None:value['spec']=spec
        value.update(extra);return value
    policy={'podSelector':{},'policyTypes':['Ingress','Egress'],
      'ingress':[{'from':[{'podSelector':{}}],'ports':[{'protocol':'TCP','port':8080}]}],
      'egress':[{'to':[{'podSelector':{}}],'ports':[{'protocol':'TCP','port':8080}]},
        {'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}},'podSelector':{'matchLabels':{'k8s-app':'kube-dns'}}}], 'ports':[{'protocol':'UDP','port':53},{'protocol':'TCP','port':53}]}]}
    container={'name':'api','image':'veriqta-api:lab','imagePullPolicy':'IfNotPresent','ports':[{'containerPort':8080}],
      'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
      'securityContext':{'runAsUser':10001,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}}
    return {'apiVersion':'v1','kind':'List','items':[namespace,
      resource('ResourceQuota','budget',{'hard':{'requests.cpu':'1','requests.memory':'512Mi','limits.cpu':'2','limits.memory':'1Gi','pods':'5'}}),
      resource('LimitRange','defaults',{'limits':[{'type':'Container','default':{'cpu':'500m','memory':'256Mi'},'defaultRequest':{'cpu':'100m','memory':'64Mi'}}]}),
      resource('NetworkPolicy','isolate',policy,'networking.k8s.io/v1'),
      resource('Role','developer',api='rbac.authorization.k8s.io/v1',rules=[{'apiGroups':[''],'resources':['pods','pods/log','services','events'],'verbs':['get','list','watch']},{'apiGroups':['apps'],'resources':['deployments','deployments/scale','replicasets'],'verbs':['get','list','watch','create','update','patch','delete']}]),
      resource('RoleBinding','developer',api='rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'developer'},subjects=[{'kind':'User','name':owner,'apiGroup':'rbac.authorization.k8s.io'}]),
      resource('Deployment','demo',{'selector':{'matchLabels':{'app':'demo'}},'template':{'metadata':{'labels':{'app':'demo'}},'spec':{'automountServiceAccountToken':False,'containers':[container]}}},'apps/v1'),
      resource('Service','demo',{'selector':{'app':'demo'},'ports':[{'port':8080}]})]}

def expired(namespace,now=None):
    meta=namespace.get('metadata',{});name=meta.get('name','')
    if not name_ok(name) or meta.get('labels',{}).get('veriqta.io/managed-by')!='environment-platform':return False
    annotations=meta.get('annotations',{})
    if not annotations.get('veriqta.io/owner'):return False
    try:
        expiry=datetime.datetime.fromisoformat(annotations['veriqta.io/expires-at'].replace('Z','+00:00'))
        if expiry.tzinfo is None:return False
        return expiry<=(now or NOW())
    except (KeyError,ValueError,TypeError):return False

def delete(namespace):
    # UID and resource version bind deletion to the exact namespace revision reviewed.
    meta=namespace['metadata']
    body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':meta['uid'],'resourceVersion':meta['resourceVersion']},'propagationPolicy':'Background'}
    kube('delete','--raw','/api/v1/namespaces/'+meta['name'],'-f','-',body=body)

def audit(action,name,owner):
    print(json.dumps({'timestamp':NOW().isoformat(),'action':action,'namespace':name,'owner':owner}))

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['create','delete','sweep']);p.add_argument('--name');p.add_argument('--owner');p.add_argument('--hours',type=int,default=24);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.action=='create':
        document=render(a.name or '',a.owner or '',a.hours)
        if a.apply:
            existing=subprocess.run(['kubectl','get','namespace',a.name,'-o','json','--ignore-not-found'],capture_output=True,text=True,check=True)
            if existing.stdout.strip():raise SystemExit('Namespace already exists; choose a new name')
            # Create namespace first; if it races, create fails rather than taking over another namespace.
            kube('create','-f','-',body=document['items'][0])
            kube('apply','-f','-',body={'apiVersion':'v1','kind':'List','items':document['items'][1:]})
            audit('create',a.name,a.owner)
        else:print(json.dumps(document,indent=2))
    elif a.action=='delete':
        if not name_ok(a.name or ''):p.error('invalid name')
        ns=kube('get','namespace',a.name,'-o','json');meta=ns['metadata']
        if meta.get('labels',{}).get('veriqta.io/managed-by')!='environment-platform' or meta.get('annotations',{}).get('veriqta.io/owner')!=a.owner:raise SystemExit('Ownership/management check failed')
        if a.apply:delete(ns)
        audit('delete' if a.apply else 'would-delete',a.name,a.owner)
    else:
        for ns in kube('get','namespaces','-l','veriqta.io/managed-by=environment-platform','-o','json')['items']:
            if expired(ns):
                if a.apply:delete(ns)
                audit('expire' if a.apply else 'would-expire',ns['metadata']['name'],ns['metadata']['annotations']['veriqta.io/owner'])
if __name__=='__main__':main()
