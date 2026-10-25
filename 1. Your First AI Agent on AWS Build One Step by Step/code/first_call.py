"""One real, billed model request; no tools in this first step."""
import json
import time
from aws_agent.config import Settings
from aws_agent.aws import Factory, call_read
s=Settings.from_env();deadline=time.monotonic()+20
client=Factory().client("bedrock-runtime",s.region,deadline)
response=call_read(client.converse,deadline,modelId=s.model_id,
    system=[{"text":"Explain cloud concepts accurately and briefly."}],
    messages=[{"role":"user","content":[{"text":"Explain DevOps in simple terms."}]}],
    inferenceConfig={"maxTokens":256})
for block in response["output"]["message"]["content"]:
    if "text" in block:print(block["text"])
print("Stop:",response["stopReason"])
print("Usage:",json.dumps(response.get("usage",{}),indent=2))
