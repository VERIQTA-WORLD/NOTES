"""Opt-in live read + model check, not collected by unittest discovery."""
import os
import subprocess
import sys
if os.getenv("RUN_LIVE_AWS")!="yes":
    raise SystemExit("Set RUN_LIVE_AWS=yes only in your intended learning account; calls may be billed.")
for args in (["--tool","list_s3_buckets"],["--prompt","List my S3 buckets using the tool. Report an empty result honestly."]):
    subprocess.run([sys.executable,"-m","aws_agent.cli",*args],check=True)
