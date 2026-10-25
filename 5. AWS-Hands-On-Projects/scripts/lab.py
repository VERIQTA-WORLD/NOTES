"""Account-checked helpers for the Veriqta AWS projects. AWS CLI v2 required."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
TEMPLATES={'01':'01-security.json','02':'02-website.json','03':'03-ec2.json','04':'04-network.json','05':'05-api.json','06':'06-database.json','07':'07-infrastructure.json','08-registry':'08-registry.json','08':'08-container.json','09':'09-pipeline.json','10':'10-monitoring.json'}

def aws(args,parsed=True):
    region=os.environ.get('AWS_REGION')
    if not region:raise ValueError('Export AWS_REGION first')
    env=dict(os.environ,AWS_PAGER='',AWS_CLI_AUTO_PROMPT='off')
    result=subprocess.run(['aws',*args,'--region',region,'--output','json'],capture_output=True,text=True,env=env)
    if result.returncode:
        # Preserve AWS diagnostics for this administrative CLI; never print credentials.
        raise RuntimeError(result.stderr.strip() or 'AWS CLI request failed')
    return json.loads(result.stdout) if parsed and result.stdout.strip() else result.stdout

def check_identity():
    expected=os.environ.get('AWS_ACCOUNT_ID','')
    if not re.fullmatch(r'\d{12}',expected):raise ValueError('Export the intended 12-digit AWS_ACCOUNT_ID')
    identity=aws(['sts','get-caller-identity'])
    if identity['Account']!=expected:raise ValueError('Current credentials do not match AWS_ACCOUNT_ID')
    if identity['Arn'].endswith(':root'):raise ValueError('Use an approved non-root execution identity')
    return identity

def stack_name(project):
    if project not in TEMPLATES:raise ValueError('Unknown project')
    return 'veriqta-project-'+project

def parameters(values):
    result=[];seen=set()
    for value in values:
        key,separator,text=value.partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',key):raise ValueError('Parameters must use Name=Value')
        if key in seen:raise ValueError('Duplicate parameter: '+key)
        seen.add(key);result.append({'ParameterKey':key,'ParameterValue':text})
    return result

def output(project,key):
    data=aws(['cloudformation','describe-stacks','--stack-name',stack_name(project)])
    outputs={r['OutputKey']:r['OutputValue'] for r in data['Stacks'][0].get('Outputs',[])}
    if key not in outputs:raise ValueError('No such output: '+key)
    return outputs[key]

def physical(project,logical):
    data=aws(['cloudformation','describe-stack-resource','--stack-name',stack_name(project),'--logical-resource-id',logical])
    return data['StackResourceDetail']['PhysicalResourceId']

def empty_bucket(project,logical,execute=False):
    # Derive the bucket from the exact selected stack resource, not a caller-supplied bucket.
    name=physical(project,logical)
    resources=aws(['cloudformation','list-stack-resources','--stack-name',stack_name(project)])['StackResourceSummaries']
    match=[r for r in resources if r['LogicalResourceId']==logical and r['ResourceType']=='AWS::S3::Bucket']
    if len(match)!=1 or match[0]['PhysicalResourceId']!=name:raise ValueError('Selected resource is not a stack-owned bucket')
    versions=aws(['s3api','list-object-versions','--bucket',name])
    items=[{'Key':x['Key'],'VersionId':x['VersionId']} for kind in ['Versions','DeleteMarkers'] for x in versions.get(kind,[])]
    objects=aws(['s3api','list-objects-v2','--bucket',name]).get('Contents',[])
    uploads=aws(['s3api','list-multipart-uploads','--bucket',name]).get('Uploads',[])
    print(json.dumps({'bucket':name,'versions_and_markers':len(items),'visible_objects':len(objects),'multipart_uploads':len(uploads),'execute':execute}))
    if not execute:return
    for i in range(0,len(items),1000):
        result=aws(['s3api','delete-objects','--bucket',name,'--delete',json.dumps({'Objects':items[i:i+1000],'Quiet':True})])
        if result.get('Errors'):raise RuntimeError('Some object versions could not be deleted')
    # Handle unversioned objects or any objects whose versions were not listed.
    remaining=aws(['s3api','list-objects-v2','--bucket',name]).get('Contents',[])
    for i in range(0,len(remaining),1000):
        result=aws(['s3api','delete-objects','--bucket',name,'--delete',json.dumps({'Objects':[{'Key':x['Key']} for x in remaining[i:i+1000]],'Quiet':True})])
        if result.get('Errors'):raise RuntimeError('Some objects could not be deleted')
    for upload in uploads:aws(['s3api','abort-multipart-upload','--bucket',name,'--key',upload['Key'],'--upload-id',upload['UploadId']])
    # Versioned buckets can gain delete markers during deletion. Repeat only when needed.
    leftovers=aws(['s3api','list-object-versions','--bucket',name])
    if leftovers.get('Versions') or leftovers.get('DeleteMarkers') or aws(['s3api','list-objects-v2','--bucket',name]).get('Contents'):
        raise RuntimeError('Bucket changed during cleanup; stop writers and repeat the preview')

def task_ip(project):
    cluster=output(project,'ClusterName');service=output(project,'ServiceName')
    arns=aws(['ecs','list-tasks','--cluster',cluster,'--service-name',service])['taskArns']
    if not arns:raise ValueError('No service task is running; inspect ECS service events')
    tasks=aws(['ecs','describe-tasks','--cluster',cluster,'--tasks',*arns])['tasks']
    for task in tasks:
        if task.get('lastStatus')!='RUNNING':continue
        for attachment in task.get('attachments',[]):
            fields={d['name']:d['value'] for d in attachment.get('details',[])}
            if 'networkInterfaceId' in fields:
                eni=aws(['ec2','describe-network-interfaces','--network-interface-ids',fields['networkInterfaceId']])['NetworkInterfaces'][0]
                ip=eni.get('Association',{}).get('PublicIp')
                if ip:print(ip);return
    raise ValueError('No public address is ready')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['identity','validate','deploy','output','delete','empty-bucket','empty-registry','task-ip'])
    p.add_argument('project',nargs='?',choices=list(TEMPLATES));p.add_argument('key',nargs='?')
    p.add_argument('--param',action='append',default=[]);p.add_argument('--execute',action='store_true');a=p.parse_args()
    identity=check_identity()
    if a.action=='identity':print(json.dumps(identity,indent=2));return
    if not a.project:p.error('Choose a project')
    name=stack_name(a.project);file=ROOT/'infra'/TEMPLATES[a.project]
    if a.action=='validate':print(json.dumps(aws(['cloudformation','validate-template','--template-body','file://'+str(file)]),indent=2))
    elif a.action=='output':
        if not a.key:p.error('Provide an output key')
        print(output(a.project,a.key))
    elif a.action=='deploy':
        supplied=parameters(a.param)
        args=['cloudformation','deploy','--stack-name',name,'--template-file',str(file),'--capabilities','CAPABILITY_IAM','--tags','Project=Veriqta','Environment=Practice','--no-fail-on-empty-changeset']
        if supplied:args+=['--parameter-overrides',*[r['ParameterKey']+'='+r['ParameterValue'] for r in supplied]]
        if not a.execute:args+=['--no-execute-changeset']
        print(aws(args,parsed=False))
    elif a.action=='delete':
        if not a.execute:print('Preview: delete stack',name);return
        aws(['cloudformation','delete-stack','--stack-name',name]);aws(['cloudformation','wait','stack-delete-complete','--stack-name',name],parsed=False);print('Deleted',name)
    elif a.action=='empty-bucket':
        if not a.key:p.error('Provide the bucket logical resource ID')
        empty_bucket(a.project,a.key,a.execute)
    elif a.action=='empty-registry':
        if a.project!='08-registry':p.error('Select 08-registry')
        repository=output(a.project,'RepositoryName');images=aws(['ecr','list-images','--repository-name',repository]).get('imageIds',[])
        print(json.dumps({'repository':repository,'images':len(images),'execute':a.execute}))
        if a.execute:
            # Delete by unique digest so multiple tags cannot cause partial duplicate deletions.
            ids=[{'imageDigest':d} for d in sorted({r['imageDigest'] for r in images})]
            for i in range(0,len(ids),100):
                result=aws(['ecr','batch-delete-image','--repository-name',repository,'--image-ids',json.dumps(ids[i:i+100])])
                if result.get('failures'):raise RuntimeError('Some images could not be deleted')
    elif a.action=='task-ip':task_ip(a.project)
if __name__=='__main__':
    try:main()
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
