"""Generate public browser configuration from stack outputs; no credentials are written."""
from pathlib import Path
import argparse
import json
import subprocess
p=argparse.ArgumentParser();p.add_argument("stack");p.add_argument("--region",default="us-east-1");a=p.parse_args()
response=json.loads(subprocess.check_output(["aws","cloudformation","describe-stacks","--stack-name",a.stack,"--region",a.region]))
outputs={x["OutputKey"]:x["OutputValue"] for x in response["Stacks"][0]["Outputs"]}
config={k:outputs[k] for k in ["ApiBase","ClientId","LoginDomain","CallbackUrl"]}
dest=Path(__file__).resolve().parents[1]/"code/web/config.js"
dest.write_text("window.AGENT_CONFIG = "+json.dumps(config)+";\n")
print("Wrote",dest)
