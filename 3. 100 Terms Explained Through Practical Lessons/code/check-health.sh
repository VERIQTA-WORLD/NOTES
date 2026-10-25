#!/usr/bin/env bash
# Run with bash. HTTP failures and connection errors are expected during retry.
set -u
set -o pipefail
health_url="${1:-http://127.0.0.1:8000/health}"
for attempt in 1 2 3 4 5; do
  if curl --fail --silent --show-error --connect-timeout 2 --max-time 3 "$health_url"; then
    printf '\nHealth check passed\n'
    exit 0
  fi
  printf 'Attempt %s failed\n' "$attempt" >&2
  sleep 1
done
printf 'Health check failed after five attempts\n' >&2
exit 1
