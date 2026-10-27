#!/usr/bin/env bash
# One-release lab: the canary has v2 labels and the stable baseline has v1 labels.
set -euo pipefail
: "${CANDIDATE_IMAGE:?Set immutable candidate registry reference with @sha256 digest}"
[[ "$CANDIDATE_IMAGE" == *@sha256:* ]] || { echo 'Digest required' >&2; exit 1; }
[[ "$(kubectl config current-context)" == kind-veriqta ]] || { echo 'Select kind-veriqta' >&2; exit 1; }
mkdir -p artifacts
kubectl -n veriqta-release rollout status deployment/canary --timeout=180s
kubectl -n veriqta-release get deployment canary -o json > artifacts/candidate.json
python3 - <<'PYCODE'
import json,os
candidate=json.load(open('artifacts/candidate.json'))
c=candidate['spec']['template']['spec']['containers'][0]
if c['image'] != os.environ['CANDIDATE_IMAGE']:raise SystemExit('Candidate digest does not match observed canary')
if candidate['spec'].get('replicas',0)<1:raise SystemExit('Canary must be running')
# Promote the tested runtime template, including environment/probes/resources.
template=candidate['spec']['template']
template['metadata']['labels'].update({'component':'stable'})
json.dump({'spec':{'template':template}},open('artifacts/promotion.json','w'))
PYCODE
if python3 tools/gate.py > artifacts/release-decision.json; then
  kubectl -n veriqta-release patch deployment stable --type=merge --patch-file artifacts/promotion.json
  if ! kubectl -n veriqta-release rollout status deployment/stable --timeout=180s; then
    kubectl -n veriqta-release rollout undo deployment/stable
    kubectl -n veriqta-release rollout status deployment/stable --timeout=180s
    exit 1
  fi
  kubectl -n veriqta-release scale deployment/canary --replicas=0
else
  status=$?
  kubectl -n veriqta-release scale deployment/canary --replicas=0
  cat artifacts/release-decision.json
  exit "$status"
fi
