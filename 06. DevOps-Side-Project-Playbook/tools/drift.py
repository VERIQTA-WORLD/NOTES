"""Classify observed Terraform drift; never apply infrastructure changes."""
import argparse,json

def public_ssh(value):
    if not isinstance(value,dict):return False
    if value.get('cidr_ipv4')=='0.0.0.0/0' or value.get('cidr_ipv6')=='::/0':
        protocol=str(value.get('ip_protocol',''))
        low=value.get('from_port');high=value.get('to_port')
        if protocol=='-1' or (protocol in ('tcp','6') and isinstance(low,int) and isinstance(high,int) and low<=22<=high):return True
    for rule in value.get('ingress',[]) or []:
        if not isinstance(rule,dict):continue
        if '0.0.0.0/0' in (rule.get('cidr_blocks') or []) or '::/0' in (rule.get('ipv6_cidr_blocks') or []):
            if rule.get('protocol')=='-1' or (rule.get('protocol') in ('tcp','6') and rule.get('from_port',99)<=22<=rule.get('to_port',0)):return True
    return False

def classify(plan):
    result=[]
    for resource in plan.get('resource_drift',[]):
        change=resource['change']
        actual=change.get('after') or {}
        result.append({'address':resource['address'],'classification':'review-required',
          'risk':'high' if public_ssh(actual) else 'unclassified',
          'observation':'current cloud state allows public SSH' if public_ssh(actual) else 'observed cloud state differs from recorded state',
          'actions':change['actions']})
    return {'observed_drift':result,'planned_changes':[{'address':r['address'],'actions':r['change']['actions']} for r in plan.get('resource_changes',[]) if r['change']['actions']!=['no-op']],
       'decision':'human review required; no automatic apply'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');a=p.parse_args()
    print(json.dumps(classify(json.load(open(a.plan))),indent=2))
