"""Plan, bounded collection, and analysis are separate explicit stages."""
import argparse,datetime,html,json,pathlib,uuid
from assistant.policy import ACTIONS,NAMESPACES,PolicyError,bounded,command,validate_kubeconfig,validate_plan,validate_target
from assistant.normalize import normalize
from assistant.retrieval import retrieve
from assistant.provider import request
from tools.sanitize import clean
ROOT=pathlib.Path(__file__).resolve().parents[1]

def read(path):
    path=pathlib.Path(path)
    if path.stat().st_size>200000:raise PolicyError('input size rejected')
    return json.loads(path.read_text())
def write(path,value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.parent.chmod(0o700)
    path.write_text(json.dumps(value,indent=2)+'\n');path.chmod(0o600)
def audit(path,event,**fields):
    p=pathlib.Path(path).parent/'audit.jsonl';p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a') as stream:stream.write(json.dumps({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':event,**fields})+'\n')
    p.chmod(0o600)

def collect(plan,namespace,pod,live=False,kubeconfig=None,runner=bounded):
    validate_plan(plan);validate_target(namespace,pod)
    if live:
        config=validate_kubeconfig(kubeconfig,namespace)
        for verb,resource in [('create','pods'),('patch','deployments'),('get','secrets')]:
            prefix=['kubectl','--kubeconfig',str(config),'--context','veriqta-readonly','--request-timeout=10s','-n',namespace]
            _,output=runner(prefix+['auth','can-i',verb,resource])
            if output.strip()!='no':raise PolicyError('identity must deny write and Secret access')
    result=[]
    for action in plan['actions']:
        if live:
            code,raw=runner(command(action,namespace,pod,config))
            if code:payload={'tool_error':True,'exit_code':code}
            else:
                try:payload=normalize(action,raw)
                except (ValueError,KeyError,TypeError):payload={'tool_error':True,'error':'unsupported evidence shape'}
        else:payload=read(ROOT/'fixtures/assistant'/f'{action}.json')
        result.append({'id':action,'data':payload})
    return {'mode':'live-readonly' if live else 'offline-fixture','namespace':namespace,'pod':pod,
      'question':clean(plan['question']),'evidence':result,'runbooks':retrieve(plan['question'])}

def validate_analysis(result,context):
    required={'summary','observations','hypotheses','proposed_change','requires_human_review','gaps'}
    if not isinstance(result,dict) or set(result)!=required or result['requires_human_review'] is not True:raise PolicyError('analysis shape/approval boundary rejected')
    if any(not isinstance(result[k],str) or len(result[k])>5000 for k in ('summary','proposed_change')) or not isinstance(result['gaps'],list) or any(not isinstance(g,str) for g in result['gaps']):raise PolicyError('analysis field types rejected')
    allowed={e['id'] for e in context['evidence']}|{r['id'] for r in context['runbooks']}
    for group in ('observations','hypotheses'):
        if not isinstance(result[group],list) or len(result[group])>12:raise PolicyError('analysis size rejected')
        for item in result[group]:
            fields={'text','evidence_ids'} if group=='observations' else {'claim','confidence','evidence_ids','next_check'}
            if not isinstance(item,dict) or set(item)!=fields:raise PolicyError('analysis item rejected')
            if any(not isinstance(item[k],str) for k in fields-{'evidence_ids'}):raise PolicyError('analysis text type rejected')
            if group=='hypotheses' and item['confidence'] not in ('low','medium','high'):raise PolicyError('confidence rejected')
            if not isinstance(item['evidence_ids'],list) or any(not isinstance(i,str) for i in item['evidence_ids']):raise PolicyError('citation type rejected')
            if not item.get('evidence_ids') or not set(item['evidence_ids'])<=allowed:raise PolicyError('unsupported citation rejected')
    if len(json.dumps(result))>20000:raise PolicyError('analysis too large')
    return result

def offline_analysis(context):
    available={e['id']:e['data'] for e in context['evidence']}
    observations=[]
    for key,data in available.items():
        observations.append({'text':f'{key}: '+json.dumps(data,sort_keys=True)[:1500],'evidence_ids':[key]})
    evidence_ids=[k for k in ('deployments','services','logs') if k in available]
    has_config='deployments' in available and 'services' in available
    claim='The configured API database port may not match the database Service.' if has_config else 'Database configuration and reachability remain unconfirmed with the selected evidence.'
    return {'summary':'Offline exercise: compare the collected request failures with database configuration and Service ports.',
      'observations':observations,'hypotheses':[{'claim':claim,'confidence':'medium' if has_config else 'low','evidence_ids':evidence_ids or [next(iter(available))],'next_check':'Compare DB_PORT with the database Service port and a controlled staging business request.'}],
      'proposed_change':'Prepare a reviewed configuration correction or a compatible rollback; this tool cannot execute it.',
      'requires_human_review':True,'gaps':['Offline fixtures are synthetic, not observations from your cluster.'] if context['mode']=='offline-fixture' else ['Offline template analysis is not a model inference; verify every claim against live evidence.']}

def provider_call(args,kind,payload):
    if args.provider=='openai':
        if not args.allow_provider_io:raise PolicyError('Review the context, then explicitly allow provider I/O')
        return request(kind,clean(payload))
    return None

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    propose=sub.add_parser('propose');propose.add_argument('--question',required=True);propose.add_argument('--output',required=True)
    collect_p=sub.add_parser('collect');collect_p.add_argument('--plan',required=True);collect_p.add_argument('--namespace',default='veriqta-prod');collect_p.add_argument('--pod',default='veriqta-api-example');collect_p.add_argument('--live',action='store_true');collect_p.add_argument('--kubeconfig');collect_p.add_argument('--output',required=True)
    analyze=sub.add_parser('analyze');analyze.add_argument('--input',required=True);analyze.add_argument('--output',required=True)
    for parser in (propose,analyze):
        parser.add_argument('--provider',choices=['offline','openai'],default='offline');parser.add_argument('--allow-provider-io',action='store_true')
    args=p.parse_args();operation=uuid.uuid4().hex
    try:
        if args.action=='propose':
            question=clean(args.question)
            validate_plan({'question':question,'actions':['pod_status']})
            plan=provider_call(args,'plan',{'question':question,'runbooks':retrieve(question)}) or {'question':question,'actions':list(ACTIONS)}
            write(args.output,validate_plan(plan));audit(args.output,'plan_prepared',operation=operation,provider=args.provider)
        elif args.action=='collect':
            context=collect(read(args.plan),args.namespace,args.pod,args.live,args.kubeconfig)
            write(args.output,context)
            for item in context['evidence']:audit(args.output,'tool_observed',operation=operation,namespace=args.namespace,pod=args.pod,tool=item['id'],normalized_result=item['data'])
        else:
            context=read(args.input)
            result=provider_call(args,'analysis',context) or offline_analysis(context)
            write(args.output,validate_analysis(result,context));audit(args.output,'analysis_prepared',operation=operation,provider=args.provider)
        print('Prepared '+str(args.output)+'; no changes executed')
    except Exception as exc:
        # Provider and kubectl exception bodies may contain sensitive context.
        print('Operation failed: '+type(exc).__name__+'. Check inputs, policy and identity without logging credentials.')
        raise SystemExit(1)
if __name__=='__main__':main()
