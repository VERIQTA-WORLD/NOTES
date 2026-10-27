"""Render in-cluster Prometheus. Run from package root."""
import json,pathlib
ns='veriqta-release'
config=pathlib.Path('monitoring/prometheus.yml').read_text().split('alerting:',1)[0]
config += """scrape_configs:
  - job_name: api
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [veriqta-release]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: api
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        action: keep
        regex: '8080'
      - source_labels: [__meta_kubernetes_pod_label_component]
        target_label: track
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
"""
items=[{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'prometheus','namespace':ns},'data':{'prometheus.yml':config,'rules.yml':pathlib.Path('monitoring/rules.yml').read_text()}},
{'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'prometheus','namespace':ns},'spec':{'selector':{'matchLabels':{'app':'prometheus'}},'template':{'metadata':{'labels':{'app':'prometheus'}},'spec':{'serviceAccountName':'prometheus','containers':[{'name':'prometheus','image':'prom/prometheus:v3.5.0','ports':[{'containerPort':9090}],'volumeMounts':[{'name':'config','mountPath':'/etc/prometheus'}]}],'volumes':[{'name':'config','configMap':{'name':'prometheus'}}]}}}},
{'apiVersion':'v1','kind':'Service','metadata':{'name':'prometheus','namespace':ns},'spec':{'selector':{'app':'prometheus'},'ports':[{'port':9090}]}}]
items += [
{'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'prometheus','namespace':ns}},
{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'prometheus-discovery','namespace':ns},'rules':[{'apiGroups':[''],'resources':['pods'],'verbs':['get','list','watch']}]},
{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'prometheus-discovery','namespace':ns},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'prometheus-discovery'},'subjects':[{'kind':'ServiceAccount','name':'prometheus','namespace':ns}]}]
print(json.dumps({'apiVersion':'v1','kind':'List','items':items},indent=2))
