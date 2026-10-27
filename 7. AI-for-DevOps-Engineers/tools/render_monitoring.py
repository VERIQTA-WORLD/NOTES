"""In-cluster per-Pod Prometheus discovery, with namespace-limited RBAC."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--namespace',choices=['veriqta-app','veriqta-staging','veriqta-prod'],required=True);a=p.parse_args();ns=a.namespace
config='''global:
  scrape_interval: 5s
  evaluation_interval: 15s
rule_files: [/etc/prometheus/rules.yml]
scrape_configs:
  - job_name: veriqta-api
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [NAMESPACE]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: veriqta-api
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        action: keep
        regex: '8000'
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
'''.replace('NAMESPACE',ns)
def obj(kind,name,spec=None,api='v1',**extra):
    d={'apiVersion':api,'kind':kind,'metadata':{'name':name,'namespace':ns}}
    if spec is not None:d['spec']=spec
    d.update(extra);return d
items=[obj('ServiceAccount','prometheus'),obj('Role','prometheus',api='rbac.authorization.k8s.io/v1',rules=[{'apiGroups':[''],'resources':['pods'],'verbs':['get','list','watch']}]),
 obj('RoleBinding','prometheus',api='rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'prometheus'},subjects=[{'kind':'ServiceAccount','name':'prometheus','namespace':ns}]),
 obj('ConfigMap','prometheus',data={'prometheus.yml':config,'rules.yml':pathlib.Path('monitoring/rules.yml').read_text()}),
 obj('Deployment','prometheus',{'selector':{'matchLabels':{'app':'prometheus'}},'template':{'metadata':{'labels':{'app':'prometheus'}},'spec':{'serviceAccountName':'prometheus','containers':[{'name':'prometheus','image':'prom/prometheus:v3.5.0','ports':[{'containerPort':9090}],'volumeMounts':[{'name':'config','mountPath':'/etc/prometheus'}]}],'volumes':[{'name':'config','configMap':{'name':'prometheus'}}]}}},'apps/v1'),
 obj('Service','prometheus',{'selector':{'app':'prometheus'},'ports':[{'port':9090}]})]
print(json.dumps({'apiVersion':'v1','kind':'List','items':items},indent=2))
