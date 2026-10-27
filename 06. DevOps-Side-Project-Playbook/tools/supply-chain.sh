#!/usr/bin/env bash
# Run after authenticating Docker/Cosign to your registry; uses a protected local key.
set -euo pipefail
: "${IMAGE_REF:?Set an immutable registry/image@sha256:digest reference}"
[[ "$IMAGE_REF" == *@sha256:* ]] || { echo 'Digest required' >&2; exit 1; }
mkdir -p artifacts/supply-chain
syft "$IMAGE_REF" -o spdx-json > artifacts/supply-chain/sbom.spdx.json
trivy image --format json --output artifacts/supply-chain/vulnerabilities.json "$IMAGE_REF"
# A scan error or high/critical finding stops signing in this exercise.
trivy image --severity HIGH,CRITICAL --exit-code 1 "$IMAGE_REF"
cosign sign --yes --key .private/cosign.key "$IMAGE_REF"
cosign verify --key .private/cosign.pub "$IMAGE_REF" > artifacts/supply-chain/signature.json
# A signed predicate is metadata from this operator; it does not establish a SLSA level.
python3 - <<'PYCODE'
import datetime,json,os,subprocess
predicate={'buildDefinition':{'buildType':'https://veriqta.example.invalid/build/manual/v1',
 'externalParameters':{'image':os.environ['IMAGE_REF']},
 'resolvedDependencies':[{'uri':'git+local','digest':{'gitCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}}]},
 'runDetails':{'builder':{'id':'https://veriqta.example.invalid/builder/local-operator'},'metadata':{'invocationId':datetime.datetime.now(datetime.timezone.utc).isoformat()}}}
open('artifacts/supply-chain/provenance.json','w').write(json.dumps(predicate,indent=2))
PYCODE
cosign attest --yes --key .private/cosign.key --type https://slsa.dev/provenance/v1 --predicate artifacts/supply-chain/provenance.json "$IMAGE_REF"
cosign verify-attestation --key .private/cosign.pub --type https://slsa.dev/provenance/v1 "$IMAGE_REF" > artifacts/supply-chain/attestation.json
