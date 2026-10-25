import argparse
import json
from pathlib import Path
import time
from .config import Settings
from .aws import Factory
from .tools import Tools
from .agent import Agent
from .memory import compact

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--prompt")
    parser.add_argument("--tool",choices=["list_ec2_instances","list_s3_buckets","list_cloudwatch_alarms","get_ec2_cpu","read_s3_text","read_agent_logs"])
    parser.add_argument("--args",default="{}")
    parser.add_argument("--memory-file",help="Optional plaintext local history; do not share it")
    args=parser.parse_args()
    settings=Settings.from_env();factory=Factory();tools=Tools(settings,factory)
    if args.tool:
        result=tools.execute(args.tool,json.loads(args.args),time.monotonic()+20)
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result["ok"] else 1)
    turns=[];path=Path(args.memory_file) if args.memory_file else None
    if path and path.exists():
        turns=json.loads(path.read_text())
    agent=Agent(settings,factory,tools)
    while True:
        prompt=args.prompt or input("You (exit to quit): ")
        if prompt.strip().lower()=="exit":break
        result=agent.turn(prompt,[m for turn in turns for m in turn])
        turns=compact(turns+[result["turn"]])
        print(result["reply"])
        print("Usage:",json.dumps(result["usage"]),"Tool calls:",result["tool_calls"])
        if path:
            path.write_text(json.dumps(turns))
            path.chmod(0o600)
        if args.prompt:break

if __name__=="__main__":
    main()
