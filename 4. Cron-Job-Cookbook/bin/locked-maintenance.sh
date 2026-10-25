#!/bin/bash
# Linux: util-linux flock and GNU coreutils timeout.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/runtime/locks"
exec /usr/bin/flock --nonblock --conflict-exit-code 75 \
  "$ROOT/runtime/locks/linux-maintenance.lock" \
  /usr/bin/timeout --kill-after=5s 60s \
  "${VERIQTA_PYTHON:-/usr/bin/python3}" "$ROOT/code/run_job.py" linux-maintenance --timeout 50 -- maintenance
