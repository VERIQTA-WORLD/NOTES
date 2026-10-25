import copy
import io
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aws_agent.config import Settings
from aws_agent.agent import Agent
from aws_agent.tools import Tools
from aws_agent.memory import DynamoMemory, ConflictError, compact, session_key
from aws_agent.handler import parse_request, lambda_handler
from aws_agent.aws import call_read

SETTINGS=Settings("us-east-1","test-model",("us-east-1",),"training-bucket","/aws/lambda/test","sessions")

def answer(text="Done", reason="end_turn"):
    return {"stopReason":reason,"output":{"message":{"role":"assistant","content":[{"text":text}]}},
            "usage":{"inputTokens":10,"outputTokens":5,"totalTokens":15}}

def tool_response(uses):
    return {"stopReason":"tool_use","output":{"message":{"role":"assistant","content":[{"text":"Checking."}]+[{"toolUse":u} for u in uses]}}}

class FakeError(Exception):
    def __init__(self,code):
        self.response={"Error":{"Code":code}}

class FakeClient:
    def __init__(self, responses=None):
        self.responses=list(responses or []);self.requests=[]
    def converse(self,**kwargs):
        self.requests.append(copy.deepcopy(kwargs));return self.responses.pop(0)
    def describe_instances(self,**kwargs):
        self.requests.append(kwargs)
        return {"Reservations":[]}
    def list_buckets(self,**kwargs):
        self.requests.append(kwargs)
        return {"Buckets":[{"Name":"training-bucket"}]}
    def describe_alarms(self,**kwargs):
        return {"MetricAlarms":[],"CompositeAlarms":[]}
    def get_metric_statistics(self,**kwargs):
        self.requests.append(kwargs);return {"Datapoints":[]}

class Factory:
    def __init__(self,client):self.c=client;self.calls=[]
    def client(self,service,region,deadline):
        self.calls.append((service,region));return self.c

class AgentTests(unittest.TestCase):
    def make(self,responses):
        client=FakeClient(responses);factory=Factory(client)
        return Agent(SETTINGS,factory,Tools(SETTINGS,factory)),client,factory
    def test_direct_answer(self):
        a,c,f=self.make([answer()]);r=a.turn("Explain EC2")
        self.assertEqual(r["reply"],"Done");self.assertEqual(r["tool_calls"],0)
        self.assertEqual(c.requests[0]["system"][0]["text"][:3],"You")
    def test_tool_use_not_first_block_and_id_pairing(self):
        use={"toolUseId":"t1","name":"list_s3_buckets","input":{}}
        a,c,f=self.make([tool_response([use]),answer("training-bucket")]);r=a.turn("List buckets")
        self.assertEqual(r["tool_calls"],1)
        messages=[r for r in c.requests if "messages" in r][1]["messages"]
        self.assertEqual(messages[-2]["role"],"assistant")
        self.assertEqual(messages[-1]["content"][0]["toolResult"]["toolUseId"],"t1")
        self.assertEqual(messages[-1]["content"][0]["toolResult"]["status"],"success")
    def test_multiple_tools_all_receive_results(self):
        uses=[{"toolUseId":"a","name":"list_s3_buckets","input":{}},
              {"toolUseId":"b","name":"list_ec2_instances","input":{}}]
        a,c,f=self.make([tool_response(uses),answer()]);r=a.turn("Inspect AWS")
        self.assertEqual(r["tool_calls"],2)
        self.assertEqual(len([r for r in c.requests if "messages" in r][1]["messages"][-1]["content"]),2)
    def test_unknown_tool_returns_error_without_aws_write(self):
        a,c,f=self.make([tool_response([{"toolUseId":"x","name":"delete_bucket","input":{}}]),answer("Unavailable")])
        a.turn("Delete a bucket")
        result=[r for r in c.requests if "messages" in r][1]["messages"][-1]["content"][0]["toolResult"]
        self.assertEqual(result["status"],"error")
        self.assertTrue(all(service=="bedrock-runtime" for service,region in f.calls))
    def test_usage_summed(self):
        a,c,f=self.make([answer()]);self.assertEqual(a.turn("Hello")["usage"]["totalTokens"],15)
    def test_empty_prompt_rejected_without_model(self):
        a,c,f=self.make([])
        with self.assertRaises(ValueError):a.turn("  ")
        self.assertFalse(f.calls)
    def test_incomplete_answer_rejected(self):
        a,c,f=self.make([answer(reason="max_tokens")])
        with self.assertRaises(ValueError):a.turn("Explain")
    def test_duplicate_tool_ids_rejected(self):
        u={"toolUseId":"same","name":"list_s3_buckets","input":{}}
        a,c,f=self.make([tool_response([u,u])])
        with self.assertRaises(ValueError):a.turn("List buckets")
    def test_tool_limit(self):
        uses=[{"toolUseId":str(i),"name":"list_s3_buckets","input":{}} for i in range(6)]
        a,c,f=self.make([tool_response(uses)])
        with self.assertRaises(ValueError):a.turn("Inspect")
    def test_history_not_mutated(self):
        a,c,f=self.make([answer()]);history=[{"role":"user","content":[{"text":"Earlier"}]},{"role":"assistant","content":[{"text":"OK"}]}]
        old=copy.deepcopy(history);a.turn("Next",history);self.assertEqual(history,old)

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.client=FakeClient();self.factory=Factory(self.client);self.tools=Tools(SETTINGS,self.factory)
    def run_tool(self,name,args):return self.tools.execute(name,args,time.monotonic()+20)
    def test_empty_ec2(self):
        r=self.run_tool("list_ec2_instances",{});self.assertEqual(r["data"]["count_returned"],0)
    def test_state_filter(self):
        self.run_tool("list_ec2_instances",{"state":"running"})
        self.assertEqual(self.client.requests[0]["Filters"][0]["Values"],["running"])
    def test_bad_region_no_client_created(self):
        self.assertFalse(self.run_tool("list_ec2_instances",{"region":"invalid"})["ok"])
        self.assertFalse(self.factory.calls)
    def test_extra_parameter_rejected(self):
        self.assertFalse(self.run_tool("list_s3_buckets",{"delete":True})["ok"])
    def test_cpu_requires_valid_id(self):
        self.assertFalse(self.run_tool("get_ec2_cpu",{"instance_id":"bad"})["ok"])
    def test_cpu_dimensions_and_missing_data(self):
        r=self.run_tool("get_ec2_cpu",{"instance_id":"i-0123456789abcdef0"})
        self.assertTrue(r["data"]["no_data"])
        self.assertEqual(self.client.requests[0]["Dimensions"][0]["Name"],"InstanceId")
    def test_s3_wrong_prefix(self):
        self.assertFalse(self.run_tool("read_s3_text",{"key":"private/password"})["ok"])
    def test_read_s3_closes_body(self):
        body=io.BytesIO(b"Training data")
        self.client.get_object=lambda **kw:{"ContentLength":13,"Body":body}
        self.assertTrue(self.run_tool("read_s3_text",{"key":"notes/demo.txt"})["ok"])
        self.assertTrue(body.closed)
    def test_aws_access_denied_is_safe(self):
        def denied(**kwargs):raise FakeError("AccessDenied")
        self.client.list_buckets=denied
        r=self.run_tool("list_s3_buckets",{})
        self.assertFalse(r["ok"]);self.assertFalse(r["retryable"])
    def test_pagination_and_cap(self):
        self.client.list_buckets=lambda **kw:{"Buckets":[{"Name":f"bucket-{i}"} for i in range(31)],"ContinuationToken":"more"}
        r=self.run_tool("list_s3_buckets",{})
        self.assertEqual(len(r["data"]["buckets"]),30);self.assertTrue(r["data"]["truncated"])
    def test_boolean_not_integer(self):
        self.assertFalse(self.run_tool("read_agent_logs",{"minutes":True})["ok"])

class FakeTable:
    def __init__(self):self.items={}
    def get_item(self,Key,**kwargs):return {"Item":self.items.get(Key["pk"])} if Key["pk"] in self.items else {}
    def put_item(self,Item,**kwargs):
        old=self.items.get(Item["pk"])
        expected=kwargs.get("ExpressionAttributeValues",{}).get(":v")
        if (expected is None and old) or (expected is not None and (not old or old["version"]!=expected)):
            raise FakeError("ConditionalCheckFailedException")
        self.items[Item["pk"]]=Item

class MemoryTests(unittest.TestCase):
    def test_owner_isolation(self):
        self.assertNotEqual(session_key("alice","same"),session_key("bob","same"))
    def test_roundtrip_and_conflict(self):
        m=DynamoMemory(FakeTable());m.save("alice","session",[[{"role":"user","content":[{"text":"Hi"}]}]],0)
        turns,version=m.load("alice","session");self.assertEqual(version,1)
        self.assertTrue(turns)
        with self.assertRaises(ConflictError):m.save("alice","session",[],0)
    def test_expired_item_not_used(self):
        table=FakeTable();m=DynamoMemory(table);m.save("a","s",[[{"text":"old"}]],0)
        table.items[session_key("a","s")]["expires_at"]=0
        self.assertEqual(m.load("a","s"),([],1))
    def test_compact_whole_turns(self):
        self.assertEqual(compact([[i] for i in range(5)]),[[2],[3],[4]])

class AuthTests(unittest.TestCase):
    def event(self):
        return {"requestContext":{"authorizer":{"jwt":{"claims":{"sub":"alice"},"scopes":["agent/chat"]}}},
                "body":json.dumps({"message":"List buckets","session_id":"a-long-session-id-123"})}
    def test_valid_payload(self):self.assertEqual(parse_request(self.event())[0],"alice")
    def test_no_identity(self):
        e=self.event();e["requestContext"]={}
        with self.assertRaises(PermissionError):parse_request(e)
    def test_cannot_supply_owner(self):
        e=self.event();b=json.loads(e["body"]);b["owner"]="bob";e["body"]=json.dumps(b)
        with self.assertRaises(ValueError):parse_request(e)
    def test_missing_scope(self):
        e=self.event();e["requestContext"]["authorizer"]["jwt"]["scopes"]=[]
        with self.assertRaises(PermissionError):parse_request(e)
    def test_handler_unauthenticated_does_not_create_sdk(self):
        with patch("aws_agent.handler.Factory") as factory, patch("builtins.print"):
            r=lambda_handler({},None)
        self.assertEqual(r["statusCode"],401);factory.assert_not_called()

class RetryTests(unittest.TestCase):
    def test_permanent_failure_not_retried(self):
        calls=[]
        def op():calls.append(1);raise FakeError("AccessDenied")
        with self.assertRaises(FakeError):call_read(op,time.monotonic()+10)
        self.assertEqual(len(calls),1)
    def test_transient_failure_retried_once(self):
        calls=[]
        def op():
            calls.append(1)
            if len(calls)==1:raise FakeError("ThrottlingException")
            return "ok"
        with patch("aws_agent.aws.time.sleep"):
            self.assertEqual(call_read(op,time.monotonic()+10),"ok")
        self.assertEqual(len(calls),2)

if __name__=="__main__":unittest.main()
