"""Veriqta HTTP API example. No credentials or request bodies are logged."""
from datetime import datetime,timezone
import json
import os

def lambda_handler(event,context):
    request_id=getattr(context,'aws_request_id','local-test')
    if os.getenv('LAB_FAIL','false').lower()=='true':
        print(json.dumps({'event':'controlled_failure','request_id':request_id}))
        raise RuntimeError('Veriqta controlled monitoring exercise')
    method=event.get('requestContext',{}).get('http',{}).get('method','GET')
    body={'message':'Hello from Veriqta API','method':method,'request_id':request_id,
          'timestamp':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
    print(json.dumps({'event':'request_completed','request_id':request_id,'method':method,'status':200}))
    return {'statusCode':200,'headers':{'Content-Type':'application/json'},'body':json.dumps(body)}
