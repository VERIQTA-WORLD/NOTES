"""Summarize Terraform actions and replacement reasons; never approve/apply."""
import argparse,json

def review(plan):
    result=[]
    for item in plan.get('resource_changes',[]):
        change=item['change'];actions=change['actions']
        if actions==['no-op']:continue
        replacement='create' in actions and 'delete' in actions
        result.append({'address':item['address'],'actions':actions,'replacement':replacement,
          'replace_paths':change.get('replace_paths',[]),'action_reason':item.get('action_reason'),
          'unknown_after':bool(change.get('after_unknown'))})
    return {'changes':result,'requires_review':bool(result),'decision':'Review dependencies, downtime, data and rollback before approval.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');a=p.parse_args();print(json.dumps(review(json.load(open(a.plan))),indent=2))
