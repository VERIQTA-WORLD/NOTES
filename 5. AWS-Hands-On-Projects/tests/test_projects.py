"""Offline checks for application behavior, administrative helpers and template controls."""
import contextlib
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'container'),str(ROOT/'scripts')]
import lambda_function
from app_core import response
import check_site
import lab

class LambdaTests(unittest.TestCase):
    def setUp(self):self.context=type('Context',(),{'aws_request_id':'veriqta-request-1'})()
    def call(self,event=None):
        with contextlib.redirect_stdout(io.StringIO()):return lambda_function.lambda_handler(event or {},self.context)
    def test_success_contract(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):result=self.call({'requestContext':{'http':{'method':'GET'}}})
        self.assertEqual(result['statusCode'],200)
        self.assertEqual(result['headers']['Content-Type'],'application/json')
        self.assertEqual(json.loads(result['body'])['message'],'Hello from Veriqta API')
    def test_request_id(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):self.assertEqual(json.loads(self.call()['body'])['request_id'],'veriqta-request-1')
    def test_actual_timestamp(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):value=json.loads(self.call()['body'])['timestamp']
        self.assertIsNotNone(datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo)
    def test_controlled_failure_is_exception(self):
        with patch.dict(os.environ,{'LAB_FAIL':'true'}):
            with self.assertRaisesRegex(RuntimeError,'controlled'):self.call()
    def test_public_event_cannot_enable_failure(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):self.assertEqual(self.call({'LAB_FAIL':'true'})['statusCode'],200)
    def test_log_excludes_body(self):
        stream=io.StringIO()
        with patch.dict(os.environ,{'LAB_FAIL':'false'}),contextlib.redirect_stdout(stream):lambda_function.lambda_handler({'body':'private-body'},self.context)
        row=json.loads(stream.getvalue());self.assertEqual(row['request_id'],'veriqta-request-1');self.assertNotIn('private-body',stream.getvalue())

class ContainerTests(unittest.TestCase):
    def test_root(self):self.assertEqual(response('/'),({'message':'Hello from Veriqta on AWS','status':'success'},200))
    def test_health(self):self.assertEqual(response('/health'),({'status':'ok'},200))
    def test_missing(self):self.assertEqual(response('/missing')[1],404)

class SiteTests(unittest.TestCase):
    def test_site_complete(self):self.assertEqual(check_site.validate(),[])
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertTrue(check_site.validate(Path(tmp)))
    def test_broken_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ['index.html','about.html','style.css']:(p/name).write_text('')
            (p/'index.html').write_text('<img src="missing.png">')
            self.assertTrue(check_site.validate(p))
    def test_escape_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ['index.html','about.html','style.css']:(p/name).write_text('')
            (p/'index.html').write_text('<a href="../secret.txt">bad</a>');self.assertTrue(check_site.validate(p))

class HelperTests(unittest.TestCase):
    def test_account_mismatch(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':'111111111111'}),patch.object(lab,'aws',return_value={'Account':'222222222222','Arn':'arn:aws:iam::222222222222:role/test'}):
            with self.assertRaisesRegex(ValueError,'match'):lab.check_identity()
    def test_root_rejected(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':'111111111111'}),patch.object(lab,'aws',return_value={'Account':'111111111111','Arn':'arn:aws:iam::111111111111:root'}):
            with self.assertRaisesRegex(ValueError,'non-root'):lab.check_identity()
    def test_account_required(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':''}):
            with self.assertRaises(ValueError):lab.check_identity()
    def test_parameter_values_not_shell_parsed(self):
        value='name with spaces; $(false)'
        self.assertEqual(lab.parameters(['Name='+value]),[{'ParameterKey':'Name','ParameterValue':value}])
    def test_duplicate_parameter_rejected(self):
        with self.assertRaises(ValueError):lab.parameters(['Name=a','Name=b'])
    def test_unknown_project(self):
        with self.assertRaises(ValueError):lab.stack_name('../other')
    def test_deployment_defaults_to_review(self):
        calls=[]
        def fake(args,parsed=True):calls.append(args);return ''
        with patch.object(lab,'check_identity',return_value={}),patch.object(lab,'aws',side_effect=fake),patch.object(sys,'argv',['lab.py','deploy','07']),contextlib.redirect_stdout(io.StringIO()):lab.main()
        self.assertIn('--no-execute-changeset',calls[0])
    def test_execute_is_explicit(self):
        calls=[]
        def fake(args,parsed=True):calls.append(args);return ''
        with patch.object(lab,'check_identity',return_value={}),patch.object(lab,'aws',side_effect=fake),patch.object(sys,'argv',['lab.py','deploy','07','--execute']),contextlib.redirect_stdout(io.StringIO()):lab.main()
        self.assertNotIn('--no-execute-changeset',calls[0])
    def test_bucket_preview_does_not_mutate(self):
        calls=[]
        def fake(args,parsed=True):
            calls.append(args)
            if args[0]=='cloudformation':return {'StackResourceSummaries':[{'LogicalResourceId':'SiteBucket','PhysicalResourceId':'veriqta-test','ResourceType':'AWS::S3::Bucket'}]}
            if args[1]=='list-object-versions':return {'Versions':[{'Key':'index.html','VersionId':'1'}]}
            return {}
        with patch.object(lab,'physical',return_value='veriqta-test'),patch.object(lab,'aws',side_effect=fake),contextlib.redirect_stdout(io.StringIO()):lab.empty_bucket('02','SiteBucket')
        self.assertFalse(any(a[1] in {'delete-objects','abort-multipart-upload'} for a in calls))
    def test_bucket_must_be_stack_owned(self):
        with patch.object(lab,'physical',return_value='not-owned'),patch.object(lab,'aws',return_value={'StackResourceSummaries':[]}):
            with self.assertRaises(ValueError):lab.empty_bucket('02','SiteBucket',True)

class TemplateTests(unittest.TestCase):
    def load(self,prefix):return json.loads(next((ROOT/'infra').glob(prefix+'*.json')).read_text())
    def test_all_projects_have_templates(self):
        self.assertEqual(len(list((ROOT/'infra').glob('*.json'))),11)
        for number in range(1,11):self.assertTrue(list((ROOT/'infra').glob(f'{number:02}-*.json')))
    def test_references_and_dependencies(self):
        import re
        for path in (ROOT/'infra').glob('*.json'):
            t=json.loads(path.read_text());names=set(t['Resources'])|set(t.get('Parameters',{}))
            def walk(x):
                if isinstance(x,dict):
                    if 'Ref' in x:self.assertTrue(x['Ref'] in names or x['Ref'].startswith('AWS::'),(path,x))
                    if 'Fn::GetAtt' in x:self.assertIn(x['Fn::GetAtt'][0],t['Resources'])
                    if 'Fn::If' in x:self.assertIn(x['Fn::If'][0],t.get('Conditions',{}))
                    if 'Fn::Sub' in x and isinstance(x['Fn::Sub'],str):
                        for target in re.findall(r'\$\{([^}]+)\}',x['Fn::Sub']):self.assertTrue(target.split('.')[0] in names or target.startswith(('AWS::','!')),(path,target))
                    for value in x.values():walk(value)
                elif isinstance(x,list):
                    for value in x:walk(value)
            walk(t)
            for resource in t['Resources'].values():
                dependencies=resource.get('DependsOn',[])
                for name in ([dependencies] if isinstance(dependencies,str) else dependencies):self.assertIn(name,t['Resources'])
    def test_private_bucket_controls(self):
        for path in (ROOT/'infra').glob('*.json'):
            for resource in json.loads(path.read_text())['Resources'].values():
                if resource['Type']=='AWS::S3::Bucket':self.assertTrue(all(resource['Properties']['PublicAccessBlockConfiguration'].values()))
    def test_oac_distribution_scoped(self):
        t=self.load('02-');statement=t['Resources']['SitePolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(statement['Principal'],{'Service':'cloudfront.amazonaws.com'})
        self.assertIn('AWS:SourceArn',statement['Condition']['StringEquals'])
        self.assertEqual(t['Resources']['Oac']['Properties']['OriginAccessControlConfig']['SigningBehavior'],'always')
    def test_no_ssh_ingress(self):
        t=self.load('03-');rules=t['Resources']['WebSecurity']['Properties']['SecurityGroupIngress']
        self.assertEqual([r['FromPort'] for r in rules],[80])
        self.assertEqual(t['Resources']['WebInstance']['Properties']['MetadataOptions']['HttpTokens'],'required')
    def test_private_subnets_not_public(self):
        t=self.load('04-')
        for name in ['Private1','Private2']:self.assertFalse(t['Resources'][name]['Properties']['MapPublicIpOnLaunch'])
        self.assertEqual(t['Parameters']['EnableNatGateway']['Default'],'false')
        self.assertEqual(t['Resources']['NatGateway']['Condition'],'CreateNat')
    def test_api_inline_code_matches_source(self):
        t=self.load('05-');f=t['Resources']['Function']['Properties']
        self.assertEqual(f['Code']['ZipFile'],(ROOT/'code/lambda_function.py').read_text())
        self.assertEqual(f['Handler'],'index.lambda_handler')
    def test_database_key_contract(self):
        t=self.load('06-');p=t['Resources']['Tasks']['Properties']
        self.assertEqual(p['BillingMode'],'PAY_PER_REQUEST');self.assertEqual(p['KeySchema'],[{'AttributeName':'taskId','KeyType':'HASH'}])
        for path in (ROOT/'code').glob('task-*.json'):self.assertIn('S',json.loads(path.read_text())['taskId'])
    def test_execution_and_task_roles_separate(self):
        t=json.loads((ROOT/'infra/08-container.json').read_text())
        self.assertNotIn('Policies',t['Resources']['TaskRole']['Properties'])
        p=t['Resources']['TaskDefinition']['Properties'];self.assertNotEqual(p['ExecutionRoleArn'],p['TaskRoleArn'])
        self.assertEqual(p['RuntimePlatform']['CpuArchitecture'],'X86_64')
    def test_oidc_claims_scoped(self):
        t=self.load('09-');trust=t['Resources']['DeployRole']['Properties']['AssumeRolePolicyDocument']['Statement'][0]
        values=trust['Condition']['StringEquals'];self.assertEqual(values['token.actions.githubusercontent.com:aud'],'sts.amazonaws.com')
        self.assertIn('refs/heads/main',json.dumps(values['token.actions.githubusercontent.com:sub']))
    def test_optional_ssh_is_disabled_and_guarded(self):
        t=self.load('03-')
        self.assertEqual(t['Parameters']['EnableSsh']['Default'],'false')
        self.assertEqual(t['Resources']['SshIngress']['Condition'],'SshEnabled')
        self.assertIn('0.0.0.0/0',json.dumps(t['Rules']['SshKeyRequired']))
    def test_alarm_topic_allows_only_scoped_service(self):
        t=self.load('10-');s=t['Resources']['TopicPolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(s['Principal'],{'Service':'cloudwatch.amazonaws.com'})
        self.assertEqual(s['Action'],'sns:Publish')
        self.assertEqual(s['Condition']['ArnEquals']['aws:SourceArn'],{'Fn::GetAtt':['Errors','Arn']})
    def test_alarm_targets_errors(self):
        t=self.load('10-');p=t['Resources']['Errors']['Properties']
        self.assertEqual((p['MetricName'],p['Statistic'],p['Period']),('Errors','Sum',60))
        self.assertEqual(p['TreatMissingData'],'notBreaching')
if __name__=='__main__':unittest.main()
