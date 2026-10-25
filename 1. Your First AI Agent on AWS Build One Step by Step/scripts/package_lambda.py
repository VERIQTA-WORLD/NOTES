"""Run from the project root using the project virtualenv Python."""
from pathlib import Path
import shutil
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
target=root/"build/lambda"
if target.exists():
    shutil.rmtree(target)
target.mkdir(parents=True)
subprocess.run([sys.executable,"-m","pip","install","-r",str(root/"code/requirements.txt"),"--target",str(target)],check=True)
shutil.copytree(root/"code/aws_agent",target/"aws_agent",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
print("Lambda package directory:",target)
