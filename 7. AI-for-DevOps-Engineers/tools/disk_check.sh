#!/usr/bin/env bash
# Exit: 0 below threshold, 1 threshold reached, 2 input/measurement failure.
set -euo pipefail
threshold=${DISK_THRESHOLD:-80}
if [[ ! "$threshold" =~ ^[0-9]{1,3}$ ]] || (( 10#$threshold < 1 || 10#$threshold > 100 )); then
  echo 'DISK_THRESHOLD must be an integer from 1 to 100' >&2; exit 2
fi
if (($# == 0)); then set -- /; fi
status=0
for mount in "$@"; do
  if ! measurement=$(LC_ALL=C df -Pk -- "$mount" 2>/dev/null); then
    printf 'ERROR unable to measure %s\n' "$mount" >&2;status=2;continue
  fi
  usage=$(printf '%s\n' "$measurement" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
  if [[ ! "$usage" =~ ^[0-9]+$ ]]; then
    printf 'ERROR invalid disk measurement for %s\n' "$mount" >&2;status=2;continue
  fi
  if (( 10#$usage >= 10#$threshold )); then
    printf 'WARNING %s is %s%% full (threshold %s%%)\n' "$mount" "$usage" "$threshold"
    if ((status==0)); then status=1; fi
  else printf 'OK %s is %s%% full\n' "$mount" "$usage"; fi
done
exit "$status"
