"""Exercise one short-lived role session without printing or writing its credentials."""
import json
import os
import subprocess
import sys
import lab

def main():
    lab.check_identity();role=lab.output('01','ExerciseRoleArn')
    session=lab.aws(['sts','assume-role','--role-arn',role,'--role-session-name','veriqta-permission-test','--duration-seconds','900'])['Credentials']
    env=dict(os.environ,AWS_ACCESS_KEY_ID=session['AccessKeyId'],AWS_SECRET_ACCESS_KEY=session['SecretAccessKey'],AWS_SESSION_TOKEN=session['SessionToken'],AWS_PAGER='')
    env.pop('AWS_PROFILE',None);env.pop('AWS_DEFAULT_PROFILE',None)
    def call(args):return subprocess.run(['aws',*args,'--region',os.environ['AWS_REGION'],'--output','json'],env=env,capture_output=True,text=True)
    allowed=call(['s3api','list-buckets']);denied=call(['ec2','describe-instances'])
    print(json.dumps({'s3_list_buckets_allowed':allowed.returncode==0,'ec2_describe_instances_denied':denied.returncode!=0 and ('UnauthorizedOperation' in denied.stderr or 'AccessDenied' in denied.stderr)},indent=2))
    if allowed.returncode or denied.returncode==0:raise RuntimeError('Permission exercise did not produce the expected allow/deny results')
    if not any(code in denied.stderr for code in ['UnauthorizedOperation','AccessDenied']):raise RuntimeError('EC2 request failed for a reason other than expected denial')
if __name__=='__main__':
    try:main()
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
