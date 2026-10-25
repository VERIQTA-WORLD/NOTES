import base64
import json
import logging
import os
import re
import time
from .config import Settings
from .aws import Factory, error_code, DeadlineError
from .tools import Tools
from .agent import Agent
from .memory import DynamoMemory, ConflictError

LOG=logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

def reply(status, body):
    return {"statusCode":status,"headers":{"content-type":"application/json","cache-control":"no-store"},
            "body":json.dumps(body)}

def parse_request(event):
    # Claims are trusted only because API Gateway verifies JWTs before invoking.
    # Direct Lambda Invoke is an admin/test capability; do not grant it to app users.
    jwt=event.get("requestContext",{}).get("authorizer",{}).get("jwt",{})
    claims=jwt.get("claims",{})
    owner=claims.get("sub")
    scopes=jwt.get("scopes",claims.get("scope","").split())
    if not isinstance(owner,str) or not owner or "agent/chat" not in scopes:
        raise PermissionError("Authenticated agent/chat scope required")
    raw=event.get("body", "")
    if not isinstance(raw,str) or len(raw)>12000:
        raise ValueError("Invalid request body size")
    if event.get("isBase64Encoded"):
        raw=base64.b64decode(raw,validate=True).decode("utf-8")
    body=json.loads(raw)
    if not isinstance(body,dict) or set(body)-{"message","session_id"}:
        raise ValueError("Expected only message and session_id")
    message=body.get("message")
    session_id=body.get("session_id")
    if not isinstance(message,str) or not message.strip() or len(message)>2000:
        raise ValueError("Provide a message of 1-2000 characters")
    if not isinstance(session_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,80}",session_id):
        raise ValueError("Use a session_id of 16-80 letters, digits, underscores or hyphens")
    return owner,session_id,message

def lambda_handler(event,context):
    started=time.monotonic();status=500;usage={};tool_calls=0
    request_id=getattr(context,"aws_request_id","local-test")
    try:
        owner,session_id,message=parse_request(event)
        settings=Settings.from_env()
        factory=Factory()
        memory=DynamoMemory(factory.table(settings.table_name,settings.region))
        turns,version=memory.load(owner,session_id)
        history=[m for turn in turns for m in turn]
        remaining=getattr(context,"get_remaining_time_in_millis",lambda:28000)()/1000
        deadline=min(started+20,time.monotonic()+max(1,remaining-5))
        result=Agent(settings,factory,Tools(settings,factory)).turn(message,history,deadline)
        usage=result["usage"];tool_calls=result["tool_calls"]
        memory.save(owner,session_id,turns+[result["turn"]],version)
        status=200
        return reply(status,{"reply":result["reply"],"session_id":session_id,"usage":usage,"request_id":request_id})
    except PermissionError:
        status=401;return reply(status,{"error":"Authentication required","request_id":request_id})
    except ConflictError:
        status=409;return reply(status,{"error":"Concurrent session request; wait then retry","request_id":request_id})
    except DeadlineError:
        status=504;return reply(status,{"error":"Agent time budget exhausted; narrow your request","request_id":request_id})
    except (ValueError,UnicodeError):
        status=400;return reply(status,{"error":"Invalid input or incomplete model response; check configuration and narrow the request","request_id":request_id})
    except Exception as exc:
        LOG.error(json.dumps({"event":"agent_error","request_id":request_id,"error_code":error_code(exc)}))
        status=502;return reply(status,{"error":"AWS request failed; inspect the request ID in operational logs","request_id":request_id})
    finally:
        # No raw event, bearer token, prompt, user identity or tool output is logged.
        print(json.dumps({"event":"agent_request","request_id":request_id,"status":status,
            "duration_ms":round((time.monotonic()-started)*1000),"usage":usage,"tool_calls":tool_calls,
            "_aws":{"Timestamp":int(time.time()*1000),"CloudWatchMetrics":[{
                "Namespace":"VeriqtaAgent","Dimensions":[["Service"]],"Metrics":[
                    {"Name":"RequestCount","Unit":"Count"},
                    {"Name":"ErrorCount","Unit":"Count"},
                    {"Name":"DurationMs","Unit":"Milliseconds"}]}]},
            "Service":os.getenv("SERVICE_NAME","local"),"RequestCount":1,"ErrorCount":int(status>=400),
            "DurationMs":round((time.monotonic()-started)*1000)}))
