#!/usr/bin/env bash
set -euo pipefail
log_dir=${1:-./artifacts/veriqta-logs}
if [[ -z "$log_dir" || "$log_dir" == / ]]; then echo 'Choose a dedicated log directory' >&2;exit 2;fi
umask 077
mkdir -p -- "$log_dir"
[[ -d "$log_dir" && -w "$log_dir" ]] || { echo 'Log directory unavailable' >&2;exit 1; }
printf 'Log directory ready: %s\n' "$log_dir"
