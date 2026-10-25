#!/bin/bash
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "${VERIQTA_PYTHON:-/usr/bin/python3}" "$ROOT/code/run_job.py" "$@"
