# The DevOps Side Project Playbook
## 10 Ideas That Get You Hired

**VERIQTA**

A strong DevOps project demonstrates a decision under failure: a release is rejected, unexpected infrastructure is identified, a database is recovered, or a security policy blocks an untrusted artifact. The result matters because another person can reproduce it and inspect the evidence.

This playbook develops ten projects from the first working baseline through a deliberate failure, an investigation, a recovery, and a portfolio demonstration. Each project includes the operational reasoning behind the commands. Build something small enough to understand, break it in a controlled way, and explain what the evidence proves.

## Contents

1. [Lab foundations](#lab-foundations)
2. [Project 01 — Deployment that rejects dangerous releases](#project-01--deployment-that-rejects-dangerous-releases)
3. [Project 02 — Cloud infrastructure drift detective](#project-02--cloud-infrastructure-drift-detective)
4. [Project 03 — Kubernetes failure investigation lab](#project-03--kubernetes-failure-investigation-lab)
5. [Project 04 — Cloud cost anomaly investigator](#project-04--cloud-cost-anomaly-investigator)
6. [Project 05 — Secrets leak prevention pipeline](#project-05--secrets-leak-prevention-pipeline)
7. [Project 06 — SLO-based production alerting](#project-06--slo-based-production-alerting)
8. [Project 07 — Self-service developer environment platform](#project-07--self-service-developer-environment-platform)
9. [Project 08 — Disaster recovery that proves backups work](#project-08--disaster-recovery-that-proves-backups-work)
10. [Project 09 — Container supply-chain trust gateway](#project-09--container-supply-chain-trust-gateway)
11. [Project 10 — Incident replay and root-cause evidence engine](#project-10--incident-replay-and-root-cause-evidence-engine)
12. [Portfolio and interview demonstration](#portfolio-and-interview-demonstration)
13. [Complete code reference](#complete-code-reference)

## Lab foundations

### The engineering cycle

For every project, record five things: the healthy baseline, the failure you introduced, the evidence that detected it, the change that recovered it, and the checks that confirmed recovery. A screenshot without a command, time range, and interpretation is weak evidence. A plausible explanation without a reproduction is still a hypothesis.

Use UTC in evidence and keep original timestamps. Record the application image digest, Git commit, namespace, environment variables that affect behavior, tool versions, and the exact workload. Compare like with like: equal traffic, comparable observation windows, and a known baseline.

### Workstation and tools

The shell examples use Bash. On Windows, use WSL2 with a Linux distribution and Docker integration. On macOS, Docker Desktop runs Linux containers in a virtual machine. On Linux, use Docker Engine and the Compose plugin. Allocate roughly 4 CPU cores, 8 GiB of memory and 15 GiB of free space for a small lab; run one heavy stack at a time if resources are limited.

| Tool | Used for | Installation reference |
|---|---|---|
| Python 3.12 and `venv` | Automation, reports and tests | [Python downloads](https://www.python.org/downloads/) |
| Git | Versioned portfolio and secret-history exercise | [Git installation](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) |
| Docker and Compose v2 | Local services and image builds | [Docker installation](https://docs.docker.com/engine/install/) |
| kind 0.27 or newer | Disposable local Kubernetes | [kind quick start](https://kind.sigs.k8s.io/docs/user/quick-start/) |
| kubectl compatible with the cluster | Kubernetes operations | [kubectl installation](https://kubernetes.io/docs/tasks/tools/) |
| Helm 3 | Cilium and policy-controller installation | [Helm installation](https://helm.sh/docs/intro/install/) |
| Terraform 1.10 or newer, below 2 | Infrastructure and native S3 locking | [Terraform installation](https://developer.hashicorp.com/terraform/install) |
| AWS CLI v2 | Optional AWS projects | [AWS CLI installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Gitleaks 8.24.3 | Local and CI secret scans | [Gitleaks releases](https://github.com/gitleaks/gitleaks/releases) |
| GnuPG | Encrypted recovery backups | [GnuPG downloads](https://gnupg.org/download/) |
| Syft, Trivy, Cosign 2.5.x | SBOM, scanning and image signatures | [Syft](https://github.com/anchore/syft#installation), [Trivy](https://trivy.dev/latest/getting-started/installation/), [Cosign](https://docs.sigstore.dev/cosign/system_config/installation/) |

The cluster examples use Kubernetes 1.32.2 as a fixed local exercise baseline, Cilium 1.18.2 and Kyverno chart 3.4.6. These pins make the exercises explicit; they are not a recommendation to operate an old cluster in production. For a team deployment, choose supported versions together, review release notes, update dependencies, and repeat the negative tests.

Run commands from this project directory unless a step explicitly changes directory:

```bash
python3 --version
git --version
docker version
docker compose version
git init
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r app/requirements.txt
python -m pip install 'boto3>=1.35,<2' 'pre-commit>=4,<5'
python -m unittest discover -s tests -v
mkdir -p artifacts
mkdir -p .private
chmod 700 .private
```

The analysis tools and offline tests use the Python standard library. The API image installs its database and telemetry dependencies during `docker build`. Boto3 is needed only for live AWS cost queries and optional S3 uploads. Pre-commit is needed only for the local secret hook.

Create lab passwords locally. The password files are excluded from Git and must never become portfolio artifacts:

```bash
python - <<'PY'
from pathlib import Path
import secrets
for name in ('db-password', 'backup-passphrase'):
    path = Path('.private') / name
    if not path.exists():
        path.write_text(secrets.token_urlsafe(40))
    path.chmod(0o600)
PY
```

Create the initial Git commit before building commit-tagged images. Use your own author identity when publishing a portfolio; these values are a training example:

```bash
git config user.name "Veriqta"
git config user.email "training@example.invalid"
git add .
git commit -m "Add Veriqta DevOps project baseline"
```

The API exposes `/healthz`, `/readyz`, `/api` and `/metrics`. Only `/api` contributes to request SLOs and release metrics. Health probes and metric scrapes do not inflate successful business traffic. Healthy responses are deterministic; setting `ERROR_EVERY=5` makes every fifth business request return HTTP 500. Optional PostgreSQL operations use a real bounded connection pool. There is no public administration endpoint for changing failure settings.

### Local Kubernetes with network isolation

Create this cluster once for Projects 01, 03, 07 and 09. The nodes remain NotReady until the CNI is installed. A NetworkPolicy object needs an enforcing network plugin; merely creating the object does not demonstrate isolation. The [kind networking configuration](https://kind.sigs.k8s.io/docs/user/configuration/) and [Cilium kind guide](https://docs.cilium.io/en/stable/installation/kind/) explain the CNI setup.

```bash
kind create cluster --name veriqta --config kubernetes/kind.yaml
helm repo add cilium https://helm.cilium.io/
helm repo update
helm upgrade --install cilium cilium/cilium --version 1.18.2 \
  --namespace kube-system --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=false --set operator.replicas=1 --wait --timeout 5m
kubectl --context kind-veriqta wait --for=condition=Ready nodes --all --timeout=180s
kubectl config use-context kind-veriqta
docker build -f app/Dockerfile -t veriqta-api:lab .
kind load docker-image veriqta-api:lab --name veriqta
```

Check the context before a failure injection or deletion. Keep these experiments in the named disposable cluster. If Pods remain Pending, inspect available memory, node conditions and CNI logs. If your network overlaps `10.244.0.0/16`, choose non-overlapping Pod and Service CIDRs in the kind configuration before creating the cluster.

Several Kubernetes manifests use JSON formatting with a `.yaml` extension. JSON is a valid YAML subset and `kubectl apply -f` reads these files directly.

### GitHub and AWS identity

Workflow examples live in `workflows/` so they can be studied without enabling scheduled jobs or publishing images. To activate a workflow in a GitHub repository, place the selected file under `.github/workflows/`, commit it and configure its repository variables. Public notes and code need no additional assembly for publication; workflow activation is a deployment step for the reader's own repository.

```bash
mkdir -p .github/workflows
cp workflows/build.yml .github/workflows/build.yml
cp workflows/secrets.yml .github/workflows/secrets.yml
```

For AWS work, use an isolated training account and an IAM Identity Center profile rather than long-lived keys. Confirm the account before creating resources:

```bash
aws configure sso --profile veriqta-lab
aws sso login --profile veriqta-lab
export AWS_PROFILE=veriqta-lab
export AWS_REGION=us-east-1
aws sts get-caller-identity
```

Cloud resources, object versions, Cost Explorer API requests and retained artifacts can incur charges. The default Kubernetes and Compose projects run locally. Provision the optional AWS portions only when you are ready to operate and remove them. Do not place credentials in Terraform variables, workflow YAML, screenshots, logs or command-line history.

## Project 01 — Deployment that rejects dangerous releases

### Scenario and design

CI is green, but the new API release fails customer requests. Build a deployment pipeline that treats runtime health as a release condition.

The path is GitHub Actions → versioned container registry image → stable and canary deployments in kind → Prometheus → release gate. Three stable replicas and one canary share the `api` Service. Kubernetes distributes connections among eligible endpoints; three-to-one replicas approximate a traffic split, but connection reuse means this is not an exact 25% request weight. A service mesh or an ingress with explicit weighted routing is the next step when precise traffic control matters.

The release policy requires a full healthy scrape window and at least 500 measured requests per version in the last five minutes, error fraction below 2%, p95 latency below 300 ms, a healthy stable baseline, and no more than a one-percentage-point error regression. A query error, missing series, zero traffic or non-finite value blocks promotion. A green unit test cannot establish runtime dependency health, capacity or user latency.

### Step 1 — Prove the decision logic offline

```bash
python tools/gate.py --fixture fixtures/canary-good.json
python tools/gate.py --fixture fixtures/canary-bad.json
```

The first command exits 0. The second exits 2 and reports a canary violation. Exit 1 means the tool could not obtain valid measurements. Do not turn a failed query into a successful release.

### Step 2 — Observe a healthy and a degraded API locally

```bash
docker compose up -d --build
curl --fail http://localhost:8080/api
python tools/load.py http://localhost:8080/api --requests 2000 --concurrency 5
python tools/load.py http://localhost:8082/api --requests 2000 --concurrency 5
```

Open Prometheus at `http://localhost:9090` and Grafana at `http://localhost:3000`. Wait for several scrapes. Run the two load commands again while observing the dashboard. For the five-minute gate, keep traffic active over a full five-minute window, then run `python tools/gate.py`. The live gate also checks healthy scrape history and freshness; a newly started target needs time to establish that history. A single burst or a scrape before the counters exist may produce insufficient data; that is a blocked release, not permission to lower the threshold.

PromQL error fraction for v2:

```promql
(sum(rate(http_requests_total{version="v2",code=~"5.."}[5m])) or vector(0))
/
sum(rate(http_requests_total{version="v2"}[5m]))
```

Latency comes from histogram buckets:

```promql
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket{version="v2"}[5m])))
```

An error count per second is a rate, not an error fraction. The denominator makes the policy comparable across traffic levels. Histogram p95 is an estimate whose resolution depends on the configured buckets.

### Step 3 — Deploy the canary in Kubernetes

Stop Compose first to release ports 8080 and 9090:

```bash
docker compose down
kubectl apply -f kubernetes/release.yaml
python tools/kube-prometheus.py > artifacts/kube-prometheus.yaml
kubectl apply -f artifacts/kube-prometheus.yaml
kubectl -n veriqta-release rollout status deployment/stable --timeout=180s
kubectl -n veriqta-release rollout status deployment/canary --timeout=180s
kubectl -n veriqta-release rollout status deployment/prometheus --timeout=180s
```

In three separate terminals, run the port forwards and leave them active:

```bash
kubectl -n veriqta-release port-forward service/stable 8080:8080
```

```bash
kubectl -n veriqta-release port-forward service/canary 8082:8080
```

```bash
kubectl -n veriqta-release port-forward service/prometheus 9090:9090
```

Prometheus discovers and scrapes each API Pod directly using a namespace-limited service account. Scraping a load-balanced Service would mix counters from different replicas and corrupt rate calculations. The `track` target label identifies stable versus canary for scrape-health checks; application metrics retain their version label.

Send traffic to both versions. Direct version Services give each measurement a known sample. To examine mixed traffic separately, port-forward `service/api` on port 8084 and load `http://localhost:8084/api`.

### Step 4 — Publish an immutable candidate

The build workflow runs tests, builds the API, publishes the commit tag to GHCR on main, and records the registry digest. Use your own registry account. For a local manual build:

```bash
export REGISTRY_OWNER=your-lowercase-github-name
export TAG=$(git rev-parse --short HEAD)
export TAGGED_IMAGE="ghcr.io/$REGISTRY_OWNER/veriqta-api:$TAG"
# Authenticate with a scoped registry token using docker login --password-stdin.
docker build -f app/Dockerfile -t "$TAGGED_IMAGE" .
docker push "$TAGGED_IMAGE"
export CANDIDATE_IMAGE=$(docker inspect --format='{{index .RepoDigests 0}}' "$TAGGED_IMAGE")
kubectl -n veriqta-release set image deployment/canary "api=$CANDIDATE_IMAGE"
kubectl -n veriqta-release rollout status deployment/canary --timeout=180s
```

Use a public training image or configure an `imagePullSecret` in the lab namespace for a private registry. A local single-architecture build must match the kind nodes; for mixed architectures use `docker buildx build --platform linux/amd64,linux/arm64 --push` and obtain the published index digest.

Keep `ERROR_EVERY=5` for the rejection challenge. Wait for a full new observation window after the candidate rollout and collect sufficient traffic. The release script verifies that the supplied digest matches the running canary Deployment. It promotes the tested Pod template, including its environment and probes, rather than changing only an image while silently keeping different runtime settings.

```bash
bash tools/release.sh
cat artifacts/release-decision.json
kubectl -n veriqta-release get deployments,pods
```

Expected failure result: the script rejects the candidate, scales the canary to zero, and leaves stable unchanged. The `api` Service continues serving stable Pods. An unavailable Prometheus must produce the same conservative deployment decision.

### Step 5 — Recover and demonstrate promotion

Restore a running canary with healthy settings, wait for its rollout, and gather an entirely fresh five-minute sample:

```bash
kubectl -n veriqta-release set env deployment/canary ERROR_EVERY=0
kubectl -n veriqta-release scale deployment/canary --replicas=1
kubectl -n veriqta-release rollout status deployment/canary --timeout=180s
# Repeat both load commands across the new five-minute observation window.
bash tools/release.sh
kubectl -n veriqta-release rollout status deployment/stable --timeout=180s
```

The demo allows runtime configuration to create and remove the failure. A production release should also bind configuration revisions to its release record. After promotion, stable runs the v2 template; this one-release exercise must be reset before another v1-to-v2 comparison. Export evidence, delete the namespace and reapply the baseline manifests when repeating it.

If a rollout fails after promotion starts, the script uses Deployment history to undo and waits for recovery. A successful rollout still requires post-promotion health observation; readiness and running replicas do not prove that customer requests meet the SLO.

**Verification and evidence:** retain the workflow, immutable image reference, manifests, traffic summaries, PromQL, rejected gate output, stable health during rejection, and a successful promotion. Record measured sample size and observation times. Interview answer: tests check known assertions before deployment; runtime gates add evidence about real request behavior and dependencies. Neither gives a universal guarantee of safety.

**Cleanup:** stop port forwards, run `kubectl delete namespace veriqta-release`, and remove unused training images from your registry according to its retention settings. For Compose, `docker compose down -v` also deletes the local Prometheus volume.

## Project 02 — Cloud infrastructure drift detective

### Scenario and design

Someone changes a security group in AWS without changing Terraform. Build a scheduled investigator that compares desired configuration with actual cloud state and reports the difference for review. It must never repair the infrastructure automatically.

Terraform state records known objects; configuration expresses intent; refreshed cloud data shows current reality. These are three different things. A plan may both observe a manual change and propose reverting it. Read `resource_drift` for observed changes and `resource_changes` for planned actions. Do not label the planned replacement value as the manual modification.

The backend is a private, encrypted, versioned S3 bucket with native `.tflock` locking. Terraform supports native S3 locking through `use_lockfile`; DynamoDB-based backend locking is deprecated. Keep existing teams' locking migrations coordinated rather than disabling locks during transition. See [Terraform S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3).

### Step 1 — Inspect a drift report offline

```bash
python tools/drift.py fixtures/drift.json > artifacts/drift-report.json
cat artifacts/drift-report.json
```

The fixture changes SSH from the private VPC CIDR to `0.0.0.0/0`. The report identifies the actual public exposure as high risk. Other changes remain unclassified and require review. A resource type alone cannot prove whether a change was expected, approved or harmless.

### Step 2 — Create state storage and isolated resources

Choose a globally unique bucket name. The bootstrap state stays local and must be retained privately so the backend infrastructure can be managed later.

```bash
export STATE_BUCKET="veriqta-state-your-unique-suffix"
terraform -chdir=terraform/bootstrap init
terraform -chdir=terraform/bootstrap plan \
  -var="region=$AWS_REGION" -var="bucket_name=$STATE_BUCKET"
terraform -chdir=terraform/bootstrap apply \
  -var="region=$AWS_REGION" -var="bucket_name=$STATE_BUCKET"
terraform -chdir=terraform/drift init \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config=key=drift/terraform.tfstate \
  -backend-config="region=$AWS_REGION" -backend-config=use_lockfile=true
export TF_VAR_region="$AWS_REGION"
terraform -chdir=terraform/drift plan
terraform -chdir=terraform/drift apply
```

Review each plan before applying. The stack creates a dedicated VPC and an unattached security group. It launches no instance, network address translation gateway or internet-facing server. Keep the group unattached during the public-SSH challenge.

### Step 3 — Introduce one controlled manual change

```bash
export SG_ID=$(terraform -chdir=terraform/drift output -raw security_group_id)
export RULE_ID=$(terraform -chdir=terraform/drift output -raw ingress_rule_id)
python - <<'PY'
import json, os
rule = [{'SecurityGroupRuleId': os.environ['RULE_ID'],
         'SecurityGroupRule': {'IpProtocol': 'tcp', 'FromPort': 22,
                               'ToPort': 22, 'CidrIpv4': '0.0.0.0/0'}}]
open('artifacts/drift-change.json','w').write(json.dumps(rule))
PY
aws ec2 modify-security-group-rules --group-id "$SG_ID" \
  --security-group-rules file://artifacts/drift-change.json
```

Record who made the change and its time. The AWS API requires an authenticated operator permitted to modify the lab group. The scheduled reviewer will use a different role that cannot modify EC2 resources.

### Step 4 — Handle plan exit codes correctly

```bash
set +e
terraform -chdir=terraform/drift plan -detailed-exitcode -out=review.tfplan
PLAN_STATUS=$?
set -e
case "$PLAN_STATUS" in
  0) echo 'No differences' ;;
  2) echo 'Differences need review' ;;
  *) echo 'Plan failed; do not call this a clean environment'; exit 1 ;;
esac
terraform -chdir=terraform/drift show -json review.tfplan > artifacts/plan.json
python tools/drift.py artifacts/plan.json > artifacts/drift-report.json
```

Exit 2 is a successful plan with changes. A shell using `set -e` must capture it deliberately. A plan error is missing evidence, not “no drift.” Plan JSON and state can contain sensitive data even when terminal output masks it; publish only a reviewed, redacted report.

### Step 5 — Use OIDC for scheduled review

Create or reuse the AWS account's GitHub OIDC provider with URL `https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com`, following [GitHub's AWS OIDC guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws). Do not create a duplicate provider. Obtain its ARN from IAM, then deploy the role template as an authorized administrator:

```bash
export OIDC_PROVIDER_ARN=arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com
export GITHUB_REPOSITORY_NAME=your-account/your-repository
aws cloudformation deploy --stack-name veriqta-review-role \
  --template-file aws/review-role.json --capabilities CAPABILITY_IAM \
  --parameter-overrides Repository="$GITHUB_REPOSITORY_NAME" Branch=main \
  OidcProviderArn="$OIDC_PROVIDER_ARN" StateBucket="$STATE_BUCKET"
aws cloudformation describe-stacks --stack-name veriqta-review-role \
  --query 'Stacks[0].Outputs'
cp workflows/drift.yml .github/workflows/drift.yml
```

Replace the example account ID. Set repository variables `AWS_REVIEW_ROLE_ARN`, `AWS_REGION`, and `STATE_BUCKET`. The trust policy matches the exact repository and main branch. A workflow that instead uses a GitHub Environment has a different OIDC subject and requires an intentional trust-policy update. Protect the trusted branch and workflow files.

The role can read EC2, query cost data, read this state object and manage its lock object. Lock writes are required for concurrency; they do not grant infrastructure mutation or state-object overwrite. Terraform initialization may create local provider metadata but does not create cloud resources. Commit the provider lock file after initialization for reproducible provider selection. For another infrastructure scope, revise read permissions explicitly.

To create review notifications from the sanitized result:

```bash
python tools/notify.py artifacts/drift-report.json --title 'Veriqta drift review'
```

This writes Slack JSON and an email draft without sending a message. The optional explicit delivery command in Project 04 can send a reviewed report to a configured Slack webhook.

The scheduled workflow runs at 06:23 UTC, supports manual runs, and creates a classification artifact. Scheduled GitHub workflows can be delayed and run from the default branch. This is periodic review, not immediate security monitoring. Email or Slack delivery should consume a sanitized report through a configured notification integration; the report is ready for a review ticket without exposing plan contents.

### Failure challenge, recovery and portfolio

Investigate whether the public SSH rule is attached anywhere, whether CloudTrail identifies the actor and API call, whether a change ticket exists, and whether the change needs to be reverted or adopted into configuration. Approval records supply the “expected change” classification; the detector does not invent it.

For the lab, review the Terraform plan and apply the desired private rule with the administrator profile. Run a second plan and verify exit 0. Capture both the unsafe observation and the clean follow-up. An intentional temporary incident change may need a time-limited exception with owner, rationale and expiry; automatically applying Terraform could undo a necessary mitigation.

**Evidence:** desired configuration, report, redacted plan excerpts, OIDC trust boundary, scheduled run, CloudTrail observation and reviewed resolution. **Interview answer:** drift detection reports a difference; remediation changes infrastructure and needs context, authority and a rollback plan.

**Cleanup:** `terraform -chdir=terraform/drift destroy` removes the lab rule, group and VPC after review. Delete the review-role CloudFormation stack. Keep state storage until all dependent resources are gone. To retire it, remove all object versions and delete markers deliberately, then destroy the bootstrap stack. Deleting only current objects does not empty a versioned bucket. Never destroy a backend still used by another stack.

## Project 03 — Kubernetes failure investigation lab

### Scenario and architecture

Build a small three-tier application: NGINX frontend → Python API → PostgreSQL, each addressed by a Service. Then diagnose five distinct failures using read-only evidence before changing the system.

`Running` describes a Pod lifecycle phase. `Ready` indicates whether a container should receive Service traffic. A readiness failure should remove traffic eligibility; a liveness failure restarts a container. Checking a remote database in liveness can trigger restart storms during a dependency outage. This API's liveness is process-only, while readiness includes a database check.

The database uses `emptyDir` deliberately: this is a disposable investigation lab, and recreating its Pod loses its data. It is not a persistence or recovery design. Project 08 handles durable database backup and restore separately.

### Step 1 — Create a healthy baseline

```bash
kubectl create namespace veriqta-failures
kubectl -n veriqta-failures create secret generic database \
  --from-file=password=.private/db-password
kubectl apply -f kubernetes/failures.yaml
kubectl -n veriqta-failures rollout status deployment/db --timeout=180s
kubectl -n veriqta-failures exec -i deployment/db -- \
  psql -U veriqta -d veriqta -v ON_ERROR_STOP=1 < recovery/init.sql
kubectl -n veriqta-failures rollout status deployment/api --timeout=180s
kubectl -n veriqta-failures rollout status deployment/web --timeout=180s
kubectl -n veriqta-failures get pods,services,endpointslices
kubectl -n veriqta-failures port-forward service/web 8083:80
```

In another terminal, `curl --fail http://localhost:8083/api` should return a record count of 3. The table is created after PostgreSQL starts; readiness checks connectivity, so a healthy readiness probe does not itself establish application-schema correctness. The business request tests that additional condition.

### Step 2 — Collect before modifying

```bash
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-baseline
```

The collector captures Pods, events, Services, EndpointSlices, Deployments, ReplicaSets, per-container current and previous logs, Pod descriptions and `kubectl top`. Each capture records its command exit status and stderr. Metrics Server is not installed by default in kind. A failing `top` command is an explicit evidence gap; install and validate Metrics Server if resource metrics are part of your demonstration. Do not present an empty capture as a successful measurement.

Logs can contain private information. Keep raw captures under `artifacts/`, review and sanitize any excerpts before publishing. Kubernetes events expire, so collect them during the failure.

### Step 3 — Diagnose five failures separately

**A. CrashLoopBackOff from startup configuration**

```bash
kubectl -n veriqta-failures set env deployment/api CRASH=true
kubectl -n veriqta-failures get pods -w
# Stop the watch once restart/backoff behavior is visible.
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-crash
kubectl -n veriqta-failures set env deployment/api CRASH-
kubectl -n veriqta-failures rollout status deployment/api --timeout=180s
```

Find the container's last termination state, restart count and previous logs. Backoff is a restart symptom; the startup configuration error explains this case. Avoid guessing from the Pod status alone.

**B. OOMKilled from a memory limit**

```bash
kubectl apply -f kubernetes/oom.yaml
kubectl -n veriqta-failures get pod oom -w
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-oom
kubectl -n veriqta-failures get pod oom \
  -o jsonpath='{.status.containerStatuses[0].state.terminated.reason}{"\n"}'
kubectl -n veriqta-failures delete pod oom
```

The isolated process allocates memory until it exceeds 32 MiB. Confirm the recorded termination reason and configured limit. Exit code 137 alone means SIGKILL and is not sufficient proof of an OOM event. Compare container limits with node pressure and, where available, resource metrics. Increasing limits without understanding demand may move the problem to the node.

**C. Service with no eligible endpoints**

```bash
kubectl -n veriqta-failures patch service api --type=merge \
  -p '{"spec":{"selector":{"component":"does-not-exist"}}}'
kubectl -n veriqta-failures get endpointslices \
  -l kubernetes.io/service-name=api -o yaml
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-selector
kubectl -n veriqta-failures patch service api --type=merge \
  -p '{"spec":{"selector":{"component":"api"}}}'
```

Compare the Service selector with actual Pod labels. A healthy process can be unreachable through a mismatched Service. `kubectl port-forward service/...` is not a complete test of cluster Service routing; test from the frontend or another Pod as well.

**D. Dependency DNS failure**

```bash
kubectl -n veriqta-failures set env deployment/api DB_HOST=missing-db
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-dns
kubectl -n veriqta-failures exec deployment/web -- nslookup db
kubectl -n veriqta-failures exec deployment/web -- nslookup missing-db
kubectl -n veriqta-failures set env deployment/api DB_HOST=db
kubectl -n veriqta-failures rollout status deployment/api --timeout=180s
```

The Alpine NGINX image includes BusyBox utilities; if your replacement image lacks `nslookup`, use a disposable DNS utility Pod. Compare a known Service name with the missing one. Check namespace qualification, `/etc/resolv.conf`, CoreDNS health and NetworkPolicy before concluding that DNS infrastructure is down. This challenge uses the wrong dependency name; changing CoreDNS would miss the cause.

**E. Running but NotReady**

```bash
kubectl -n veriqta-failures set env deployment/api READY=false
kubectl -n veriqta-failures get pods
kubectl -n veriqta-failures describe deployment api
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-readiness
kubectl -n veriqta-failures set env deployment/api READY-
kubectl -n veriqta-failures rollout status deployment/api --timeout=180s
```

The process stays alive but refuses readiness. Check readiness conditions and EndpointSlice `ready` fields. During a rolling update, old healthy Pods may continue serving because the new replicas never become ready. This is evidence that the rollout guard is working, not proof the new version succeeded.

### Additional challenge — Missing ConfigMap

```bash
kubectl -n veriqta-failures delete configmap web
kubectl -n veriqta-failures rollout restart deployment/web
python tools/collect.py --namespace veriqta-failures --output artifacts/failure-configmap
kubectl apply -f kubernetes/failures.yaml
kubectl -n veriqta-failures rollout status deployment/web --timeout=180s
```

Mount errors and startup events identify this configuration dependency. Reapplying the baseline also restores the API configuration; run one failure at a time and keep recovery actions explicit.

### Investigation decision tree

```text
Request fails
├─ Does DNS resolve the intended Service?
│  └─ No: verify name, namespace, resolver and DNS policy
├─ Does the Service select ready endpoints?
│  └─ No: compare selectors, Pod labels and readiness conditions
├─ Is the target process restarting or failing to start?
│  └─ Yes: termination state → previous logs → events/config/resources
└─ Is the process ready but requests fail?
   └─ Application logs → dependency connectivity → schema → latency/capacity
```

**Verification and evidence:** produce five incident reports using `templates/incident-report.md`, with sanitized captures, the specific failed assumption, recovery command and a healthy request afterward. Include the additional ConfigMap case if completing the extension. **Interview answer:** use endpoints, labels, readiness, logs, events, DNS and resources to narrow the failure before restarting or changing limits.

**Cleanup:** `kubectl delete namespace veriqta-failures`. The secret, database contents and all lab objects in that namespace are removed.

## Project 04 — Cloud cost anomaly investigator

### Scenario and design

Request volume looks stable, yet the bill increases. Build a read-only investigator that ranks the services and owners contributing to the change, creates a report, and prepares a notification for review. Keep recommendations separate from resource deletion or resizing.

Cost Explorer → daily grouped data → Python normalization → ranked CSV and Markdown → investigation and notification draft. The API supports two grouping dimensions in one request. Use `SERVICE` plus `LINKED_ACCOUNT`, then a separate query for `SERVICE` plus an activated owner tag. Read grouped costs from `Groups`, handle pagination, and retain the `Estimated` flag. See the [GetCostAndUsage API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_GetCostAndUsage.html).

### Step 1 — Analyze a known 40% increase

```bash
python tools/costs.py --fixture fixtures/costs.json \
  --start 2026-01-01 --split 2026-01-08 --end 2026-01-15 \
  --output artifacts/cost-example
cat artifacts/cost-example/report.md
```

The synthetic first week totals USD 1,420; the second totals USD 1,988. The increase is USD 568, or 40%. These amounts are training data, not a price quote or an actual account bill.

| Service | Previous week USD | Recent week USD | Increase USD |
|---|---:|---:|---:|
| EC2 | 420 | 635 | 215 |
| RDS | 280 | 350 | 70 |
| S3 | 150 | 200 | 50 |
| NAT Gateway | 310 | 430 | 120 |
| CloudWatch | 120 | 150 | 30 |
| Other | 140 | 223 | 83 |
| Total | 1,420 | 1,988 | 568 |

The report sorts absolute daily increases. Its individual review flag requires at least USD 1/day increase and at least 50% relative increase, or a new/nonpositive baseline. A 40% total rise still needs investigation even if some contributing rows do not cross the individual 50% flag. Ranking and alert thresholds answer different questions.

### Step 2 — Compare unequal windows correctly

Use a 30-day baseline followed by a non-overlapping seven-day recent period. Divide each total by its number of calendar days before calculating the change:

```text
baseline_daily = baseline_cost / baseline_days
recent_daily   = recent_cost / recent_days
daily_increase = recent_daily - baseline_daily
relative_change = daily_increase / baseline_daily × 100
```

Comparing a seven-day total directly with a 30-day total hides anomalies. Use `Decimal` for money. A zero baseline needs a “new cost” classification rather than division by zero. A negative baseline may reflect credits or adjustments, so percentage growth is not meaningful. Do not sum unlike usage units to explain cost; inspect usage types separately.

### Step 3 — Query AWS with read-only access

Enable Cost Explorer through the billing account and allow for data availability. Use a role with `ce:GetCostAndUsage`. The OIDC review role from Project 02 includes it; for local work, have an administrator assign the equivalent permission through your SSO profile. Organization management accounts can see member-account data, so scope who may run and read the report.

Generate dates relative to UTC. The exclusive end skips today and yesterday to reduce partial-day effects; billing data can still be revised later:

```bash
python - <<'PY' > .private/cost-dates.sh
from datetime import datetime, timezone, timedelta
end = datetime.now(timezone.utc).date() - timedelta(days=1)
split = end - timedelta(days=7)
start = split - timedelta(days=30)
for name,value in [('COST_START',start),('COST_SPLIT',split),('COST_END',end)]:
    print(f'export {name}={value}')
PY
source .private/cost-dates.sh
python tools/costs.py --start "$COST_START" --split "$COST_SPLIT" \
  --end "$COST_END" --group account --output artifacts/cost-account
python tools/costs.py --start "$COST_START" --split "$COST_SPLIT" \
  --end "$COST_END" --group tag:Owner --output artifacts/cost-owner
```

Activate the `Owner` cost allocation tag in billing before relying on it; historical coverage and activation delays matter. An empty owner value is an ownership gap to resolve, not permission to discard the cost. Use consistent cost metrics across both windows. This exercise uses UnblendedCost; organizations may instead need amortized views for commitments, with that choice clearly stated.

### Step 4 — Investigate contributors and recommendations

For the largest increases, inspect service usage types, resource inventories and deployment times. Check whether EC2 instance hours or sizes changed, whether RDS replicas or storage grew, whether S3 request/transfer/storage charges changed, whether NAT data processing rose, and whether log ingestion or retention increased. Stable request count does not imply stable data volume per request or stable background work.

Keep an investigation table with the cost observation, supporting usage evidence, proposed action, owner, expected benefit, risk and approval. Estimate savings from measured usage and the relevant current regional pricing; state assumptions and uncertainty. Do not claim savings until a later comparable billing period confirms them. A cost increase may be justified business growth, a one-time migration or a pricing/credit effect.

The generated report contains a notification draft. Fill in the responsible owner, evidence and next review time. Render a Slack payload and an email draft:

```bash
python tools/notify.py artifacts/cost-account/report.md --title 'Veriqta cost review'
```

The files are `artifacts/notifications/slack.json` and `email.eml`. The `.invalid` email addresses are placeholders; set actual approved sender/recipient details in your mail system. For Slack delivery, create an incoming webhook through the workspace's approved process, save its URL in `.private/slack-webhook` with mode 600, review the report, then explicitly send it:

```bash
python tools/notify.py artifacts/cost-account/report.md --title 'Veriqta cost review' \
  --webhook-file .private/slack-webhook --send-webhook
```

Keep this step optional in schedules until recipients and alert thresholds are agreed. The URL is a secret and must never appear in logs or public examples. Redact account IDs, resource names and commercial data before making portfolio examples public. A scheduled GitHub workflow or host scheduler can invoke the same command; authenticate with a short-lived role and publish only sanitized summaries. Route real email or chat alerts through the organization's approved integration.

**Failure challenge:** use the fixture to explain the 40% increase, identify the largest contributors, find an owner gap, and distinguish measured causes from open questions. **Verification:** reconcile daily sums, confirm non-overlapping windows, review estimated data, test a new service and a zero baseline, and demonstrate that no remediation API was called. **Evidence:** Python, fixture, ranked CSV, report, notification example, investigation and recommendation table. **Interview answer:** detection identifies a change; investigation connects it to usage and ownership before proposing an action.

**Cleanup:** there are no resources to delete for offline analysis. Remove any schedules you enabled, retire unused roles, and apply a retention policy to private billing reports.

## Project 05 — Secrets leak prevention pipeline

### Scenario and controls

A developer commits a credential. Build prevention at the workstation and in CI, then rehearse containment. A local hook improves feedback, but it can be bypassed. A required CI check and repository branch protection provide a second control. Short-lived OIDC credentials reduce the need for stored AWS keys.

The lab uses a deliberately recognizable synthetic marker that cannot authenticate to AWS or any external service. A custom Gitleaks rule guarantees that the training marker has a defined detection contract. Default provider-specific rules remain enabled. Never use a live credential to prove a scanner works.

### Step 1 — Enable scanning

```bash
gitleaks version
gitleaks dir --redact --config security/gitleaks.toml .
cp security/pre-commit-config.yaml .pre-commit-config.yaml
pre-commit install
# Initialize a Git repository first if this is a new portfolio workspace.
# git init
cp workflows/secrets.yml .github/workflows/secrets.yml
```

Run `git init` before `pre-commit install` when no repository exists. For an existing repository, review its hook configuration before replacing it. The local hook scans staged changes. The workflow fetches complete available history and scans all fetched refs with redaction. Configure branch protection to require the secret check; merely adding a workflow does not prevent a privileged user from bypassing branch rules.

[Gitleaks CLI documentation](https://github.com/gitleaks/gitleaks) distinguishes Git-history scans from directory scans. Scanning only the working tree misses secrets removed from the latest file but retained in commits.

### Step 2 — Create a disposable leak challenge

```bash
export CHALLENGE_DIR=$(mktemp -u /tmp/veriqta-secrets.XXXXXXXX)
python tools/secret-challenge.py "$CHALLENGE_DIR"
gitleaks git --redact --config "$PWD/security/gitleaks.toml" "$CHALLENGE_DIR"
```

The final command should exit nonzero with the training rule ID and a redacted finding. The repository contains only a fake marker. Keep it outside the handbook and portfolio repository so demonstrations do not create permanent training findings in unrelated history. If you prefer to choose a path yourself, pass a new, nonexistent directory to the script; it refuses to overwrite an existing path.

Capture a redacted failure and the rule identity. Do not copy the full canary value into public evidence. The scanner rule and generator are included; the generated value is not required in the publication.

### Step 3 — Prove that deleting the latest file is insufficient

```bash
git -C "$CHALLENGE_DIR" rm example.env
git -C "$CHALLENGE_DIR" -c user.name=Veriqta \
  -c user.email=training@example.invalid commit -m 'Remove synthetic credential file'
gitleaks git --redact --config "$PWD/security/gitleaks.toml" "$CHALLENGE_DIR"
```

The history scan still fails because the earlier commit contains the marker. A clean directory scan after deletion would not establish clean history. The training repository can now be deleted; no real credential needs revocation in this exercise.

### Step 4 — Rehearse a real incident response

If the finding were real, revoke or disable the exposed credential immediately, then issue a replacement through an approved secure channel. Update dependent workloads and verify they use the replacement. Check its permissions and lifetime. Review provider audit logs for unexpected use during the exposure window, including the period before detection.

Identify every likely copy: Git commits and branches, forks, CI logs, build artifacts, package caches, container layers, tickets and pasted messages. Coordinate any history rewrite with repository owners after revocation; rewriting history cannot invalidate copies or revoke access. Remove unnecessary copies, rerun scanning, document remaining exposure and verify service recovery.

For the portfolio, write a **simulated rotation** record describing the sequence and evidence that would be required. Do not claim an actual AWS key was rotated when only a canary was used.

### Step 5 — Replace persistent CI AWS keys with OIDC

Use the exact repository and branch trust conditions from Project 02 and `configure-aws-credentials` in the workflow. Grant only the operations required for that job. Pull requests from untrusted forks must not receive a deployment identity. Protect the workflow path and branch because a trusted workflow able to assume a role is part of the security boundary.

No `AWS_ACCESS_KEY_ID` or secret access key needs to be stored for this integration. Registry publication should use its own scoped, short-lived workflow token. Secrets needed at runtime belong in an appropriate secret store with access controls and rotation, not in a Docker build argument or committed `.env` file.

**Failure challenge:** a synthetic committed marker blocks the scan; deleting it in a later commit does not clear the history finding. **Verification:** staged scan, history scan, required CI status, redacted evidence and a documented containment sequence. **Evidence:** Gitleaks config, hook, workflow, failed check, simulated rotation and OIDC policy. **Interview answer:** removal from source is one cleanup task; revocation limits continuing access and is the immediate containment step.

**Cleanup:** remove the disposable challenge directory after confirming its path. Keep the hook and required CI checks in a real repository. Never add a broad allowlist simply to make a failing scan green; an approved false-positive suppression should identify a specific finding and reason.

## Project 06 — SLO-based production alerting

### Scenario and definitions

A CPU alert fires while users are fine; another incident hurts users without high CPU. Build alerting around successful requests and latency, then connect a real alert to a runbook and a recovery check.

An SLI is a measured indicator. An SLO is its target over a window. An error budget is the allowed bad fraction or count. An SLA is an external commitment and may have contractual consequences. This lab uses a 99.9% request-availability objective over 30 days, so the allowed error fraction is `0.001`.

For this API, availability means an `/api` response below 500; all business responses enter the denominator. The app currently returns 200, 500 or 503 on that path. In another service, define whether client errors, cancellations and timeouts belong in the denominator. Prometheus cannot observe requests that never reach the instrumented server; add an external probe or gateway telemetry when that matters.

The flow is API metrics → Prometheus rules → Alertmanager grouping/routing → local receiver. Grafana queries Prometheus directly. It does not receive metrics from Alertmanager.

### Step 1 — Start the stack and validate configuration

Stop any Project 01 port forwards and Compose services using the same ports. Then:

```bash
docker compose up -d --build
docker run --rm --entrypoint promtool \
  -v "$PWD/monitoring:/config:ro" -w /config prom/prometheus:v3.5.0 \
  check rules rules.yml
docker run --rm --entrypoint promtool \
  -v "$PWD/monitoring:/config:ro" -w /config prom/prometheus:v3.5.0 \
  test rules rules.test.yml
```

The included rule tests check healthy and high-error counter series. Add tests for your eventual traffic volumes and maintenance conditions. Validate Alertmanager configuration with the image's `amtool check-config /etc/alertmanager/alertmanager.yml` in the running container.

```bash
docker compose exec alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

### Step 2 — Calculate burn rate correctly

```text
burn_rate = observed_error_fraction / allowed_error_fraction
          = observed_error_fraction / 0.001
```

A 1% error fraction burns a 99.9% availability budget at 10 times the sustainable rate. The fast-burn rule requires both the five-minute and one-hour error fractions to exceed `14.4 × 0.001 = 0.0144`, plus at least 100 requests over five minutes, sustained for one minute. The two windows reduce sensitivity to a brief spike while retaining a recent signal. For a 30-day budget, 14.4× sustained for one hour spends approximately 2% of the budget under a time-based approximation; request-weighted burn varies with traffic.

A separate telemetry warning reports when no API scrape target is reachable. Loss of instrumentation should not be interpreted as perfect availability. The lab's warning detects total target loss; extend it with per-target and expected-target inventory checks for a real deployment.

### Step 3 — Generate traffic and inspect the SLI

The canary starts with every fifth request failing. Send traffic to both endpoints while inspecting the dashboard:

```bash
python tools/load.py http://localhost:8080/api --requests 10000 --concurrency 5 --pause .05
python tools/load.py http://localhost:8082/api --requests 10000 --concurrency 5 --pause .05
curl --fail http://localhost:9090/api/v1/alerts
docker compose logs --no-log-prefix receiver
```

The load commands are sequential here; use two terminals to maintain both streams together. Repeat across the observation window. Open `/alerts` in Prometheus and the Alertmanager interface at `http://localhost:9093`. Capture when the rule becomes pending, when it fires, when the receiver logs the notification, and which measurements support it.

The long window does not require an hour of stored samples before Prometheus evaluates a rate, but a newly started service has incomplete one-hour history. Warm up a healthy baseline before a realistic incident and label short lab observation windows accurately. Do not present a two-minute lab as proof of a 30-day SLO.

### Step 4 — Interpret the dashboard

The supplied dashboard shows request rate, five-minute availability, p95 latency, request-weighted budget remaining over available 30-day samples, and database-pool metrics when the DB-enabled API is used. With the basic API, pool panels are empty because no pool exists.

A 30-day query on a fresh Prometheus volume has only the retained history available. Use at least 30 days of suitable retention and stable metric semantics for a real rolling 30-day report. Counter resets are handled by `rate` and `increase`, but missing scrapes, instrumentation changes and absent traffic still need interpretation. Do not clip a negative remaining budget to zero in an investigation: it shows how far the service has overspent.

Latency p95 below 300 ms is a useful diagnostic and release gate; a formal latency SLO should instead define a good-request threshold ratio, such as requests within 300 ms divided by eligible requests. The histogram includes a 0.3-second bucket for that purpose:

```promql
sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
/
sum(rate(http_request_duration_seconds_count[5m]))
```

### Step 5 — Recover and verify resolution

```bash
ERROR_EVERY=0 docker compose up -d --force-recreate canary
python tools/load.py http://localhost:8082/api --requests 10000 --concurrency 5 --pause .05
docker compose logs --no-log-prefix receiver
```

Continue healthy traffic. The alert does not resolve immediately: error samples must age out or be diluted in both windows, then Alertmanager must send the resolved notification. Record actual detection and resolution times instead of promising a fixed sub-five-minute result from a five-minute window.

**Runbook:** confirm the affected business path, request volume and error fraction; compare stable/canary and recent changes; check dependencies and pool capacity; reject or roll back a demonstrated bad release; verify healthy traffic and receiver resolution; preserve evidence and open prevention work. High CPU can support diagnosis, but it should not substitute for customer-impact evidence.

**Failure challenge and evidence:** show a sustained business-error increase, pending/firing/resolved states, dashboard, rule tests, local notification and recovery. The local receiver sends nothing externally. Configure real notification destinations and on-call ownership only as a separate operational integration. **Interview answer:** an SLO alert links action to budget consumption and user outcomes; CPU indicates resource behavior that may or may not affect users.

**Cleanup:** `docker compose down -v` removes the lab and its local monitoring history. Preserve sanitized evidence before deleting the volume.

## Project 07 — Self-service developer environment platform

### Scenario and security boundary

Developers need disposable environments without a platform engineer manually creating each namespace. Build a Python CLI that provisions a namespace with ownership, a bounded lifetime, quotas, default resources, limited developer RBAC, network isolation and a sample workload. Add a scheduled sweeper so expiry is enforced automatically.

A label such as `ttl=7d` does not delete anything by itself. Expiry is an ISO 8601 annotation read by the sweeper. Labels identify platform-managed namespaces; the controller also validates the name prefix, owner and expiry before deletion.

This is an **administrator-operated platform lab**. The CLI runs with the caller's Kubernetes identity. Supplying `--owner reader` is metadata, not authentication. A team-facing service needs an authenticated API that derives the owner from the caller, an authorization model, request validation, durable audit records and a constrained provisioning identity. Do not hand a cluster-admin kubeconfig to developers and treat the CLI's ownership check as a security boundary.

### Step 1 — Render and inspect an environment

```bash
python tools/environments.py create --name veriqta-env-demo \
  --owner reader --hours 24 > artifacts/environment.yaml
```

Inspect the rendered objects before provisioning. A server dry run does not persist the Namespace for subsequent namespaced objects, so validate those objects against a real disposable namespace when testing admission rules.

The namespace enforces restricted Pod Security Admission. The developer Role permits viewing Pods/logs/Services/events and managing Deployments, but does not permit changing namespace labels, quotas, NetworkPolicies, Roles, RoleBindings or Secrets. Quotas apply to the namespace in aggregate. Resource defaults keep a small deployment from failing due to absent resource declarations.

### Step 2 — Create and inspect

```bash
python tools/environments.py create --name veriqta-env-demo \
  --owner reader --hours 24 --apply
kubectl -n veriqta-env-demo rollout status deployment/demo --timeout=180s
kubectl get namespace veriqta-env-demo -o yaml
kubectl -n veriqta-env-demo get resourcequota,limitrange,networkpolicy,role,rolebinding
```

The CLI refuses to take over an existing namespace. If creating a later resource fails, collect the error, inspect the partly created namespace, and either repair it as an administrator or delete the managed environment and retry. A production service should record provisioning state and support idempotent reconciliation.

### Step 3 — Prove authorization limits

As a cluster administrator, test impersonation:

```bash
kubectl auth can-i get pods --as=reader -n veriqta-env-demo
kubectl auth can-i patch deployments --as=reader -n veriqta-env-demo
kubectl auth can-i get secrets --as=reader -n veriqta-env-demo
kubectl auth can-i patch networkpolicies --as=reader -n veriqta-env-demo
kubectl auth can-i get pods --as=reader -n kube-system
```

Expected results are yes, yes, no, no, no. Impersonation requires its own administrator permission. It does not create a user or issue credentials; a real identity provider must authenticate `reader`. The actual user must run with their own kubeconfig and should be unable to impersonate others.

The Role permits Deployment changes, so also consider service account selection, volume types and admission controls. Denying direct `get secrets` access does not prevent a workload editor from referencing a Secret in that namespace and reading it through a container. Keep privileged credentials out of developer-controlled namespaces, or enforce additional admission restrictions on Secret references. Restricted Pod Security prevents privileged containers and host access in this namespace. Do not install a more privileged service account in the same namespace without revisiting developer permissions.

### Step 4 — Prove resource and network isolation

Attempt an oversized workload using the developer identity:

```bash
kubectl -n veriqta-env-demo --as=reader set resources deployment/demo \
  --requests=cpu=4,memory=8Gi --limits=cpu=4,memory=8Gi
kubectl -n veriqta-env-demo get replicasets,pods
kubectl -n veriqta-env-demo get events --sort-by=.metadata.creationTimestamp
```

The Deployment update may be accepted, while its ReplicaSet fails to create Pods because the requests exceed namespace quota. Capture the quota rejection in events. “Deployment accepted” and “workload admitted and running” are separate outcomes. Restore the original bounds:

```bash
kubectl -n veriqta-env-demo --as=reader set resources deployment/demo \
  --requests=cpu=100m,memory=64Mi --limits=cpu=500m,memory=256Mi
kubectl -n veriqta-env-demo rollout status deployment/demo --timeout=180s
python tools/environments.py create --name veriqta-env-other \
  --owner another-reader --hours 24 --apply
```

Run a same-namespace request and DNS resolution from the existing API container:

```bash
kubectl -n veriqta-env-demo exec deployment/demo -- python -c \
  'import urllib.request; print(urllib.request.urlopen("http://demo:8080/api",timeout=3).status)'
kubectl -n veriqta-env-demo exec deployment/demo -- python -c \
  'import socket; print(socket.gethostbyname("demo.veriqta-env-other.svc.cluster.local"))'
kubectl -n veriqta-env-demo exec deployment/demo -- python -c \
  'import urllib.request; print(urllib.request.urlopen("http://demo.veriqta-env-other.svc.cluster.local:8080/api",timeout=3).status)'
```

Expected outcomes: same-namespace HTTP succeeds; DNS for the other namespace resolves; cross-namespace HTTP times out. DNS permission does not imply permission to reach the resolved service. The policy allows same-namespace TCP 8080 and DNS to CoreDNS; all other traffic is denied for selected Pods. If cross-namespace HTTP succeeds, investigate CNI enforcement and additional additive NetworkPolicies. A policy manifest alone is not a passing isolation test.

### Step 5 — Enforce expiry automatically

```bash
docker build -f platform/Dockerfile -t veriqta-platform:lab .
kind load docker-image veriqta-platform:lab --name veriqta
kubectl apply -f platform/sweeper.yaml
python tools/environments.py sweep
```

The CronJob runs every five minutes, lists managed namespaces and deletes expired ones. Its cluster role can delete namespaces, so keep this controller confined to the disposable lab. Kubernetes RBAC cannot constrain namespace deletion by arbitrary label; production designs need an additional authorization or admission boundary and careful controller hardening.

For an immediate controlled expiry test, an administrator can set a past expiry on the disposable demo:

```bash
kubectl annotate namespace veriqta-env-demo \
  veriqta.io/expires-at=2020-01-01T00:00:00Z --overwrite
python tools/environments.py sweep
# This preview should identify only the expired managed environment.
kubectl -n veriqta-platform create job --from=cronjob/expire-environments expire-test
kubectl -n veriqta-platform wait --for=condition=Complete job/expire-test --timeout=180s
kubectl -n veriqta-platform logs job/expire-test
kubectl get namespace veriqta-env-demo
```

The final get should report NotFound after namespace finalization completes. Deletion uses API UID and resource-version preconditions so a newly recreated namespace is not removed and an ownership or expiry edit made after collection causes a conflict instead of an outdated deletion. Invalid/missing expiry, missing ownership, unmanaged labels and names outside the prefix are skipped. The offline tests exercise these guards.

### Audit, evidence and recovery

CLI JSON output records requested actions and the supplied owner. It is useful application evidence, but it is not an authoritative record of who authenticated to Kubernetes. Use Kubernetes audit logging, protected log storage and the organization's identity provider to establish actual actors and policy changes. Event history is also not a substitute for an API audit trail.

Capture namespace ownership, quotas, authorization denials, a blocked cross-namespace connection, the scheduled cleanup job and deletion evidence. Explain why a developer cannot extend their own expiry or remove isolation under this Role. For a real service, add approval for longer lifetimes, notification before expiry, storage preservation policy and controller failure alerts.

**Interview answer:** self-service works when the platform supplies safe defaults and enforces boundaries; a namespace name and an owner flag are not enough. **Cleanup:** delete the remaining environment with `python tools/environments.py delete --name veriqta-env-other --owner another-reader --apply`, then remove `platform/sweeper.yaml` with `kubectl delete -f`. Namespace deletion also deletes its namespaced resources; decide persistence rules before adopting this pattern for real data.

## Project 08 — Disaster recovery that proves backups work

### Scenario and recovery objectives

A scheduled backup job succeeds every night. Can the database actually be recovered, and within the required time? Build encrypted backups, independent restore tests, data validation, application checks and a measured recovery report.

A recovery point objective (RPO) is the maximum acceptable data loss expressed in time. A recovery time objective (RTO) is the maximum acceptable restoration time. A retention policy describes how long backups remain available; it does not demonstrate recoverability. A restore test must prove that the archive is readable, the database accepts it, important records match and the application can use the restored data.

The local path is PostgreSQL → custom-format `pg_dump` → encrypted backup envelope → separate restored database → content comparison → API validation. Optional S3 adds encrypted, versioned off-host storage. A Kubernetes CronJob implementation follows the local exercise.

### Step 1 — Start source and recovery databases

```bash
docker compose -f recovery/compose.yaml up -d --build
# Inspect health and wait for both databases before continuing.
docker compose -f recovery/compose.yaml ps
docker compose -f recovery/compose.yaml exec -T db \
  psql -U veriqta -d veriqta -c 'TABLE veriqta_records;'
```

The source contains three known records. The recovered API initially cannot serve business requests because the restored database has no table yet. It should recover after a successful restore without changing the API's database host.

### Step 2 — Create encrypted backups

Pause all writers for this small exercise. The tool compares rows before and after `pg_dump` and rejects an observed change, but this check is not a substitute for a transactionally shared snapshot under concurrent writes. For an active production database, keep an exported PostgreSQL snapshot transaction open, pass its snapshot ID to `pg_dump --snapshot`, validate from that same snapshot, or use an appropriate physical backup/PITR system.

```bash
python tools/recovery.py backup \
  --passphrase-file .private/backup-passphrase
ls artifacts/backups
```

The filename ends in `.tar.gpg`. Inside the encrypted envelope are a custom-format `.dump` and expected record data. Custom-format dumps are restored with `pg_restore`, not `psql -f`. A `.sql.gz` containing plain SQL would instead need decompression and `psql`; choose one format and keep its extension and restore command consistent.

Plaintext temporary files stay under a private temporary directory and are deleted when the tool exits normally. Protect the workstation, temporary filesystem and passphrase backup as part of the design. Losing the passphrase makes the encrypted backup unusable. Keep recovery key material separately from the data and test authorized access to it.

The tool writes a `.partial` encrypted file first and renames it only after successful encryption. A completed filename therefore indicates a finished encryption step; it still does not prove restoration.

### Step 3 — Restore to an independent target

Choose the completed backup explicitly:

```bash
export BACKUP_FILE=artifacts/backups/replace-with-completed-filename.tar.gpg
python tools/recovery.py restore --file "$BACKUP_FILE" \
  --passphrase-file .private/backup-passphrase
curl --fail http://localhost:8085/api
cat artifacts/backups/restore-report.json
```

The tool decrypts the envelope, reads only the expected regular archive members, clears the **separate `restored` service's** schema, restores with `--exit-on-error`, and compares all seeded records and timestamps. Do not repoint that disposable target at a real database. The API should return HTTP 200 with `records: 3`.

The report's `restore_validation_seconds` measures restore and content validation, not detection, environment provisioning, download or application recovery. For an end-to-end RTO, start the timer at the incident's agreed service-loss point and stop only after business operations are verified. Record both the component duration and the full recovery duration.

### Step 4 — Simulate actual data loss

Deleting a database Pod usually does not destroy a database stored on a persistent volume. To test restoration, deliberately remove a table in the disposable source database after preserving backups and recording its contents:

```bash
docker compose -f recovery/compose.yaml exec -T db psql -U veriqta -d veriqta \
  -v ON_ERROR_STOP=1 -c "INSERT INTO veriqta_records(id,name) VALUES (4,'after-backup');"
docker compose -f recovery/compose.yaml exec -T db psql -U veriqta -d veriqta \
  -c 'SELECT id,name,committed_at FROM veriqta_records ORDER BY id;'
date -u +%Y-%m-%dT%H:%M:%SZ > artifacts/backups/disaster-start.txt
docker compose -f recovery/compose.yaml exec -T db psql -U veriqta -d veriqta \
  -v ON_ERROR_STOP=1 -c 'DROP TABLE veriqta_records;'
python tools/recovery.py restore --file "$BACKUP_FILE" \
  --passphrase-file .private/backup-passphrase
curl --fail http://localhost:8085/api
```

The restored database contains three records, so the post-backup fourth record is lost. That is expected evidence of the backup's recovery boundary, not a zero-data-loss result. Measure RPO from a known consistent backup point or transaction recovery point relative to the incident cutoff. The timestamp of an old row is not automatically the database recovery point. For this quiesced lab, record the backup interval and the later insert explicitly; a single backup-completion timestamp only approximates the recovery boundary.

A sample target might be RPO ≤24 hours and RTO ≤30 minutes. Fill in actual results from your run, including lost rows and application checks. A logical dump cannot provide recovery of transactions committed after its snapshot; WAL archiving and point-in-time recovery address a different requirement.

### Step 5 — Reject a corrupt backup and use a prior verified one

Create a second backup before the destructive challenge when repeating the exercise, then keep both copies. A corrupt archive must fail before it can be declared usable:

```bash
cp "$BACKUP_FILE" artifacts/backups/corrupt.tar.gpg
python - <<'PY'
from pathlib import Path
p=Path('artifacts/backups/corrupt.tar.gpg')
data=p.read_bytes()
p.write_bytes(data[:len(data)//2])
PY
python tools/recovery.py restore --file artifacts/backups/corrupt.tar.gpg \
  --passphrase-file .private/backup-passphrase
# Expected: nonzero exit. Select an earlier completed backup that passed a restore test.
python tools/recovery.py restore --file "$BACKUP_FILE" \
  --passphrase-file .private/backup-passphrase
```

The corrupted-file command must fail; do not put it into an unconditional success chain. The recovery tool does not automatically pick “latest” because a filename does not establish that a backup is verified. Maintain a private backup catalog of source, point-in-time boundary, storage location/version and last successful restore test. A fallback to an older backup may increase data loss and breach RPO; report that tradeoff.

### Step 6 — Add versioned off-host storage

```bash
aws cloudformation deploy --stack-name veriqta-backups \
  --template-file aws/backup-bucket.json
export BACKUP_BUCKET=$(aws cloudformation describe-stacks --stack-name veriqta-backups \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' --output text)
python tools/recovery.py backup --passphrase-file .private/backup-passphrase \
  --bucket "$BACKUP_BUCKET"
aws s3api get-bucket-versioning --bucket "$BACKUP_BUCKET"
aws s3api list-object-versions --bucket "$BACKUP_BUCKET" --prefix postgres/
```

The bucket blocks public access, requires secure transport, enables versioning, uses server-side encryption and has a 30-day current/noncurrent-version lifecycle. Client encryption protects the contents before upload. S3 lifecycle expiration and versioning are not protection against every destructive administrator action; evaluate Object Lock, separate-account copies and recovery-role isolation for stronger requirements.

The uploader needs `s3:PutObject` on `arn:aws:s3:::YOUR_BUCKET/postgres/*`. A recovery identity needs `s3:ListBucket` constrained to that prefix, `s3:GetObject`, and `s3:GetObjectVersion` if selecting a version. Adding a KMS key requires its relevant encrypt/decrypt permissions and a key recovery plan. Keep upload, restore and deletion authority separate where practical.

Retrieve an exact version into a new private filename before restoring:

```bash
aws s3api get-object --bucket "$BACKUP_BUCKET" \
  --key postgres/replace-with-object-name.tar.gpg \
  --version-id replace-with-version-id artifacts/backups/downloaded.tar.gpg
python tools/recovery.py restore --file artifacts/backups/downloaded.tar.gpg \
  --passphrase-file .private/backup-passphrase
```

### Step 7 — Schedule and restore in Kubernetes

The host-side schedule in `recovery/backup.cron` uses `flock` to prevent overlapping runs. Set the actual absolute project path, test the command under the scheduler's identity and environment, use a known timezone, restrict logs, and monitor job failure and backup age. macOS does not include Linux `flock` by default; use the Kubernetes scheduler below or a platform-appropriate lock and scheduler.

For Kubernetes, the supplied manifest creates separate persistent source/recovery databases, an encrypted backup PVC, a daily UTC CronJob and an administrator-operated restore utility Pod:

```bash
docker build -f recovery/Dockerfile -t veriqta-backup:lab .
kind load docker-image veriqta-backup:lab --name veriqta
kubectl create namespace veriqta-recovery
kubectl -n veriqta-recovery create secret generic database \
  --from-file=password=.private/db-password
kubectl -n veriqta-recovery create secret generic backup-encryption \
  --from-file=passphrase=.private/backup-passphrase
kubectl apply -f recovery/kubernetes.yaml
kubectl -n veriqta-recovery rollout status deployment/db --timeout=180s
kubectl -n veriqta-recovery rollout status deployment/restored --timeout=180s
kubectl -n veriqta-recovery exec -i deployment/db -- \
  psql -U veriqta -d veriqta -v ON_ERROR_STOP=1 < recovery/init.sql
kubectl -n veriqta-recovery create job --from=cronjob/database-backup backup-test
kubectl -n veriqta-recovery wait --for=condition=Complete job/backup-test --timeout=300s
kubectl -n veriqta-recovery logs job/backup-test
kubectl -n veriqta-recovery wait --for=condition=Ready pod/restore-tool --timeout=180s
kubectl -n veriqta-recovery exec restore-tool -- ls /backups
```

Select one completed `.dump.gpg` filename. Inside the utility Pod, decrypt and restore the custom dump to the separate target:

```bash
kubectl -n veriqta-recovery exec -it restore-tool -- bash
```

Run inside that shell, replacing the filename:

```bash
set -euo pipefail
export GNUPGHOME=/tmp/gnupg
mkdir -p "$GNUPGHOME"
gpg --batch --yes --pinentry-mode loopback --passphrase-file /encryption/passphrase \
  --decrypt --output /tmp/restore.dump /backups/replace-with-completed-file.dump.gpg
psql -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
pg_restore --no-owner --no-privileges --exit-on-error --dbname=veriqta /tmp/restore.dump
psql -v ON_ERROR_STOP=1 -c 'SELECT id,name FROM veriqta_records ORDER BY id;'
psql -v ON_ERROR_STOP=1 -c "BEGIN; INSERT INTO veriqta_records(id,name) VALUES (99,'recovery-write-test'); ROLLBACK;"
rm /tmp/restore.dump
exit
```

The utility Pod's `PGHOST` is `restored`, so these statements target the recovery database. Check it with `printenv PGHOST` before a destructive schema operation. Compare rows with a pre-disaster capture and test a client connection. To verify the application through the cluster, port-forward the recovery database to local port 55432 and run the API against it:

```bash
# Terminal 1
kubectl -n veriqta-recovery port-forward service/restored 55432:5432
```

```bash
# Terminal 2, with the virtual environment active
export DB_HOST=127.0.0.1 DB_PORT=55432 DB_USER=veriqta DB_NAME=veriqta
export DB_PASSWORD=$(cat .private/db-password)
python app/api.py
```

```bash
# Terminal 3
curl --fail http://localhost:8080/api
```

Stop the API after the check and unset `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` and `DB_PASSWORD` in that terminal. Use a free local port 8080 by stopping the earlier Compose stack. The Kubernetes CronJob stores encrypted backups locally on the PVC by default. For off-host storage, the backup image supports `BACKUP_BUCKET`; use a Kubernetes platform with workload identity and a scoped AWS role before enabling it. A local kind cluster does not automatically have an AWS workload identity. Do not inject permanent cloud keys to make the exercise appear integrated.

A ReadWriteOnce backup volume can constrain Pod placement on multi-node storage systems. The default kind local-path storage keeps the utility and backup jobs near their provisioned volume; inspect scheduling and PVC events if a job cannot mount it. This local volume is not disaster-independent storage. Use the S3 path or another independent backup location to survive cluster loss.

**Evidence and interview defense:** retain scripts, schedule, encrypted-storage design, successful and corrupt-archive tests, row and application checks, measured RTO/RPO and fallback results. Explain why a completed backup job and a retention setting do not establish recovery. **Cleanup:** stop API/port forwards; `docker compose -f recovery/compose.yaml down -v`; delete the `veriqta-recovery` namespace. The S3 template retains its bucket when the stack is deleted. Remove all versions/delete markers only after deciding to retire the lab backups, then delete the retained bucket. Keep a usable recovery copy until cleanup is complete.

## Project 09 — Container supply-chain trust gateway

### Scenario and trust model

An image passes a vulnerability scan but came from an untrusted build process. Build a gateway that distinguishes known-vulnerability checks from artifact authenticity and enforces the latter at Kubernetes admission.

The flow is build/publish → immutable digest → Syft SBOM → Trivy scan → Cosign signature → signed provenance → verification → Kyverno admission. An SBOM inventories components; a vulnerability scanner compares them with known advisories; a signature establishes that an approved identity or key signed particular bytes; provenance describes a build. None of these controls alone proves that an application is safe.

The lab uses an encrypted local Cosign key so the trust boundary is visible. For a team pipeline, keep signing authority in a controlled builder, KMS or a carefully constrained keyless identity. If anyone can obtain the approved key or invoke the trusted signer on arbitrary images, admission cannot distinguish their malicious image from an approved one.

### Step 1 — Build and publish a versioned image

Use your own registry repository and a public training package for uncomplicated cluster access:

```bash
export REGISTRY_OWNER=your-lowercase-github-name
export RELEASE_TAG=$(git rev-parse --short HEAD)
export TAGGED_IMAGE="ghcr.io/$REGISTRY_OWNER/veriqta-api:$RELEASE_TAG"
docker build -f app/Dockerfile -t "$TAGGED_IMAGE" .
docker push "$TAGGED_IMAGE"
export IMAGE_REF=$(docker inspect --format='{{index .RepoDigests 0}}' "$TAGGED_IMAGE")
printf '%s\n' "$IMAGE_REF"
```

A tag can be moved; use the resulting `registry/repository@sha256:...` reference for scanning, signing and deployment. If publishing a multi-platform image, resolve and verify the published image index and relevant platform manifests consistently.

### Step 2 — Inspect the SBOM and vulnerabilities

```bash
mkdir -p artifacts/supply-chain
syft "$IMAGE_REF" -o spdx-json > artifacts/supply-chain/sbom.spdx.json
trivy image --format json --output artifacts/supply-chain/vulnerabilities.json "$IMAGE_REF"
trivy image --severity HIGH,CRITICAL --exit-code 1 "$IMAGE_REF"
```

Inspect component names, versions, package ecosystems, scanner database age, fixed versions and runtime exposure. A successful scan command without `--exit-code` may still report vulnerabilities; enforce the decision explicitly. A failed registry pull or unavailable vulnerability database is a scan failure, not “zero vulnerabilities.”

The exercise blocks HIGH and CRITICAL findings. An evolving base image may fail this gate; rebuild with reviewed dependency updates and rerun. Do not alter the threshold just to reproduce a green screenshot. MEDIUM findings need triage and a documented decision; LOW and UNKNOWN results still need appropriate review. UNKNOWN is not proof of harmlessness.

### Step 3 — Generate a signing key and demonstrate rejection first

```bash
cosign version
cosign generate-key-pair --output-key-prefix .private/cosign
# Use a strong passphrase at the prompt; keep the private key and passphrase separate.
cosign verify --key .private/cosign.pub "$IMAGE_REF"
```

A fresh unsigned digest should fail verification. If the digest has already been signed with this key, create a distinct challenge image by adding a harmless build label, publish a new tag, resolve its new digest and repeat. Signatures are associated with image identity, not just the tag; reusing an already signed digest does not create an unsigned challenge.

The public key may be shared as policy material. The private key must stay in protected storage. For scripted signing, Cosign can use `COSIGN_PASSWORD` supplied through a protected execution environment; do not commit it or type its value into a recorded shell command. Interactive prompts are acceptable for this local lab.

### Step 4 — Install an actual admission verifier

A `ValidatingWebhookConfiguration` that names a rule is not a verifier by itself. It needs a reachable TLS service, a controller implementing signature checks, trusted CA configuration and a fail-closed policy. Install Kyverno to provide that implementation:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm upgrade --install kyverno kyverno/kyverno --version 3.4.6 \
  --namespace kyverno --create-namespace --wait --timeout 5m
kubectl -n kyverno get deployments
kubectl create namespace veriqta-trust
python tools/trust-policy.py > artifacts/trust-policy.yaml
kubectl apply -f artifacts/trust-policy.yaml
kubectl get clusterpolicy veriqta-signed-images
```

This policy is scoped to the lab namespace and checks **all** image references there, not just one preferred registry. Otherwise an attacker could choose a different registry that fails to match the rule. It requires the approved public key, resolves tags to digests and verifies digest binding. `failurePolicy: Fail` prevents a verifier outage from silently admitting images in scope. The pinned chart uses the `ClusterPolicy` API; review Kyverno's API migration guidance before upgrading to a different policy generation. See [Kyverno image verification](https://kyverno.io/docs/policy-types/cluster-policy/verify-images/overview/).

The default public transparency-log verification is retained. The signer and verifier need registry and relevant transparency-service connectivity. Private registries additionally need appropriate controller image-verification credentials and workload pull credentials; those are different consumers. Do not disable verification to mask an authentication or networking failure.

### Step 5 — Attempt the unsigned image

```bash
kubectl -n veriqta-trust run unsigned --image="$IMAGE_REF" --restart=Never
```

Expected result: admission rejects the Pod because a valid approved signature is absent. Capture the API error and the policy/controller evidence. If the Pod is admitted, stop the exercise and investigate whether the policy is Ready, whether it matches this namespace and resource, whether enforcement is enabled, and whether the image was already signed. Deleting an accepted Pod afterward does not make the admission test pass.

For controller-based workloads, rejection may appear when the controller creates a Pod rather than when the Deployment itself is accepted. Check ReplicaSet events and policy reports as well as the top-level `kubectl apply` result. Cluster administrators who can modify policy remain inside the trust boundary.

### Step 6 — Sign, attest and verify the same digest

Run the complete scan/sign/attestation sequence:

```bash
bash tools/supply-chain.sh
```

The script runs Syft, writes a full Trivy report, enforces the HIGH/CRITICAL gate, signs the immutable image, verifies the signature, signs a SLSA-v1-shaped provenance predicate, and verifies that attestation. The predicate records the local Git commit, image reference, operator builder identity and invocation time.

This is operator-authored provenance for learning. It does not establish a SLSA assurance level or an isolated build. Signing a claim does not establish that its contents are true. Stronger provenance is generated by a trusted builder from controlled inputs and verified against expected source, builder identity and build parameters.

The supplied admission policy enforces the approved image signature. Attestation verification is an explicit pipeline step in this project; the policy does not claim to enforce every provenance field. To extend admission to provenance, add tested attestation conditions for an approved builder and source, then prove that a correctly signed but wrong-builder predicate is denied. Keep the signature and provenance trust models consistent.

```bash
cosign verify --key .private/cosign.pub "$IMAGE_REF"
cosign verify-attestation --key .private/cosign.pub \
  --type https://slsa.dev/provenance/v1 "$IMAGE_REF"
kubectl -n veriqta-trust run approved --image="$IMAGE_REF" \
  --restart=Never --port=8080
kubectl -n veriqta-trust wait --for=condition=Ready pod/approved --timeout=180s
kubectl -n veriqta-trust port-forward pod/approved 8087:8080
```

In another terminal, `curl --fail http://localhost:8087/api` should return a healthy response. A valid signature with a failed image pull is a different problem; inspect Pod events and registry access instead of weakening admission.

### Pipeline integration and exception management

`workflows/trust.yml` is a complete manually triggered build/scan/sign workflow. It runs only from main and uses the protected GitHub Environment `veriqta-release`. Configure required reviewers and allowed release branches on that environment before enabling it. Add environment secrets `COSIGN_PRIVATE_KEY`, `COSIGN_PUBLIC_KEY` and `COSIGN_PASSWORD` from the training key pair, then activate the workflow:

```bash
cp workflows/trust.yml .github/workflows/trust.yml
```

The job uses a scoped registry token, tests the code, builds and publishes the commit image, scans its resolved digest, signs only after the scan gate succeeds, verifies the signature/attestation and retains verification artifacts. The key file is created privately on the ephemeral runner and removed on exit. The environment's secret access and the main-branch workflow are part of the signing authority. For production, prefer an isolated signing service or narrowly constrained keyless builder instead of a downloadable long-lived signing key. The workflow publishes to GHCR; review package visibility and registry access before attempting cluster deployment.

The build workflow from Project 01 provides tests and image publication. Add scanning and trusted signing after publication and before any deployment. Grant registry writes and signing authority only to the protected release job; pull-request test jobs need neither. In GitHub Actions, use a protected environment or branch, short-lived OIDC identity, minimal token permissions and immutable action references reviewed by your organization. Store SBOM, scan result and verified provenance with the digest they describe.

A release verification job can run the provided script once the runner has Syft, Trivy, Cosign and an approved signing identity. An encrypted local key is suitable for the lab; copying it into an untrusted PR runner defeats the control. For keyless signing, configure verifier issuer and exact workflow identity before changing the signing command; accepting any GitHub certificate is too broad.

Use `templates/security-exception.md` for an exact digest, finding, owner, independent approver, compensating controls, expiry and removal evidence. A ConfigMap listing “allowed images” does not create a working exception mechanism unless a policy controller explicitly reads and enforces it. This lab does not automatically grant exceptions. An administrator must review a narrow policy change separately; avoid wildcard registry bypasses. Expiry needs an enforcing process, not just a date in a document.

| Finding | Exercise decision |
|---|---|
| CRITICAL vulnerability | Block; remediate and rescan |
| HIGH vulnerability | Block; require a reviewed remediation/exception process |
| MEDIUM vulnerability | Triage exposure, document action and owner |
| LOW / UNKNOWN | Review context; do not infer safety solely from severity |
| Missing or invalid approved signature | Block admission |
| Unknown builder / unsupported provenance claim | Block release approval pending investigation |

**Failure challenge and evidence:** show a clean-enough vulnerability scan but unsigned-image rejection, then approved-key signature verification, signed-image admission and application health. Include SBOM, scan database context, image digest, attestation, policy, rejection output and controlled-exception design. **Interview answer:** scanners address known component flaws; authenticity controls establish whether an artifact came through a trusted release authority. A clean scan does not establish trusted origin.

**Cleanup:** stop the port forward; delete `veriqta-trust`, then `kubectl delete clusterpolicy veriqta-signed-images`. Uninstall Kyverno only after removing policies that depend on it: `helm uninstall kyverno -n kyverno`. Review and remove registry images/signatures through registry retention controls, and retire the training private key securely. Do not delete a shared policy controller used by other workloads.

## Project 10 — Incident replay and root-cause evidence engine

### Scenario and evidence model

The outage ends, but application logs, deployment history, cluster events and traces are scattered. Build a small engine that normalizes timestamps, correlates service identity, produces a structured timeline and prepares a postmortem with evidence references and unresolved questions.

The data path is microservices → application logs / Kubernetes events / OpenTelemetry traces / deployment records → normalization → UTC ordering → Markdown, JSON and HTML timeline → postmortem. Fluent Bit can collect container logs continuously; kubectl captures targeted evidence during a lab. OpenTelemetry spans connect request work with dependency operations. Git and CI metadata identify the actual deployed change.

Temporal order narrows an investigation. It does not establish causation. A rollout before an outage is evidence of sequence, not proof of responsibility. Clock skew, aggregated events, delayed ingestion, retries and incomplete history all affect interpretation.

### Step 1 — Reconstruct a known incident offline

```bash
python tools/replay.py \
  --logs fixtures/incident/logs --events fixtures/incident/events \
  --traces fixtures/incident/traces --deployments fixtures/incident/deployments \
  --output artifacts/incident-example
```

Read `timeline.md`, `timeline.json`, `timeline.html` and `postmortem.md` in the output directory. The records are synthetic examples. The tool preserves evidence file and record/line references, converts timezone-aware timestamps to UTC, rejects naive timestamps, and lists missing or unsupported evidence instead of pretending it was collected.

The supported inputs are structured application JSON/JSONL, Kubernetes EventList JSON, OTLP JSON traces with `resourceSpans`, and deployment records with timestamps. Kubernetes DeploymentList input yields current condition observations; it cannot reconstruct every historical rollout. Use CI release records or a deployment audit stream for history.

### Step 2 — Start real request, database and trace collection

```bash
mkdir -p artifacts/incident/traces artifacts/incident/logs \
  artifacts/incident/events artifacts/incident/deployments
chmod 700 artifacts/incident
docker compose -f incident/compose.yaml up -d --build
docker compose -f incident/compose.yaml ps
python tools/load.py http://localhost:8086/api --requests 1000 \
  --concurrency 10 --pause .02 > artifacts/incident/baseline-load.json
curl --fail http://localhost:8086/metrics > artifacts/incident/baseline-metrics.txt
```

The Compose stack uses a healthy database, a real Psycopg connection pool, OpenTelemetry spans and the Collector's file exporter. The API's DB connection span includes both waiting for a pool connection and the query. Additional pool statistics help distinguish pool wait from actual database execution time. A long combined span by itself cannot prove the database server query was slow.

The Collector writes OTLP JSON to `artifacts/incident/traces/traces.jsonl`. Its lab container runs as root only to simplify writing the bind-mounted exercise directory; use an assigned writable UID and tighter filesystem permissions in an operated deployment. The OTLP receiver is not published to the host. The API endpoints are bound to localhost.

### Step 3 — Record deployments as they happen

A current Deployment manifest is not a release history. Record the controlled changes explicitly with UTC time and Git identity:

```bash
python - <<'PY' > artifacts/incident/deployments/baseline.json
import datetime,json,subprocess
print(json.dumps({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'service':'api','event':'baseline deployment',
 'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'pool_size':8,'db_hold_seconds':0.01,'retries':0}))
PY
```

If this is a new repository, commit the baseline before using `git rev-parse`. Retain the actual image digest for registry-based deployments. Record timestamps immediately before and after the rollout when it takes measurable time.

### Step 4 — Introduce connection-pool exhaustion under load

The bad revision reduces the pool to two connections, holds each query for one second and permits two retries after the first attempt. Incoming concurrency exceeds that capacity:

```bash
python - <<'PY' > artifacts/incident/deployments/bad-pool.json
import datetime,json
print(json.dumps({'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'service':'api','event':'bad-pool deployment begins','pool_size':2,
 'db_hold_seconds':1,'retries':2}))
PY
INCIDENT_VERSION=bad-pool POOL_SIZE=2 DB_HOLD=1 DB_RETRIES=2 \
  docker compose -f incident/compose.yaml up -d --force-recreate api
python tools/load.py http://localhost:8086/api --requests 300 \
  --concurrency 20 --pause 0 > artifacts/incident/bad-load.json
curl --fail http://localhost:8086/metrics > artifacts/incident/bad-metrics.txt
docker compose -f incident/compose.yaml logs --no-color --no-log-prefix api \
  > artifacts/incident/logs/api.log
```

Inspect HTTP 503s, `PoolTimeout` class names, repeated attempts, pool queue/wait statistics and `db.pool-and-query` spans. The script's `--pause` value is a per-worker delay between requests, not a global requests-per-second setting. Use the reported elapsed time to calculate actual achieved throughput.

Retries can multiply backend demand. Keep the client load tool's retries disabled so the application's retry behavior is visible. The application retry limit is bounded; an uncontrolled retry loop would obscure the original pressure and prolong recovery.

### Step 5 — Recover with controlled comparisons

Test one change at a time with the same workload. First remove retries while keeping the small pool and long hold time. Then restore a bounded pool and eliminate the injected hold. Capture each result:

```bash
INCIDENT_VERSION=no-retries POOL_SIZE=2 DB_HOLD=1 DB_RETRIES=0 \
  docker compose -f incident/compose.yaml up -d --force-recreate api
python tools/load.py http://localhost:8086/api --requests 300 \
  --concurrency 20 --pause 0 > artifacts/incident/no-retries-load.json
curl --fail http://localhost:8086/metrics > artifacts/incident/no-retries-metrics.txt
docker compose -f incident/compose.yaml logs --no-color --no-log-prefix api \
  > artifacts/incident/logs/no-retries.log
INCIDENT_VERSION=recovered POOL_SIZE=8 DB_HOLD=.01 DB_RETRIES=0 \
  docker compose -f incident/compose.yaml up -d --force-recreate api
python tools/load.py http://localhost:8086/api --requests 300 \
  --concurrency 20 --pause 0 > artifacts/incident/recovered-load.json
curl --fail http://localhost:8086/metrics > artifacts/incident/recovered-metrics.txt
docker compose -f incident/compose.yaml logs --no-color --no-log-prefix api \
  > artifacts/incident/logs/recovered.log
```

Recreating a container discards that container's local log history, so export logs before every recreation. The commands above preserve the bad logs before the first change and each intermediate phase before the next. The Collector persists trace output independently. Allow its batch exporter to flush after traffic, then stop the API gracefully before taking a final trace copy if needed.

Do not treat “increase the pool” as a universal production fix. Check database connection limits, number of replicas, query duration, lock contention, timeout budgets and admission/load shedding. For example, eight connections per API Pod across 50 replicas consumes a different database budget from eight in a single-Pod lab. A well-bounded pool, shorter work, fewer retries and capacity-aware concurrency can address different parts of the problem.

### Step 6 — Reproduce and collect in Kubernetes

The Kubernetes variant supplies the same frontend, API and database plus a Collector, trace PVC and a read-only trace utility Pod. Use a separate namespace so its evidence belongs to this incident:

```bash
kubectl create namespace veriqta-incident
kubectl -n veriqta-incident create secret generic database \
  --from-file=password=.private/db-password
kubectl apply -f incident/kubernetes.yaml
kubectl -n veriqta-incident rollout status deployment/db --timeout=180s
kubectl -n veriqta-incident exec -i deployment/db -- \
  psql -U veriqta -d veriqta -v ON_ERROR_STOP=1 < recovery/init.sql
kubectl -n veriqta-incident rollout status deployment/collector --timeout=180s
kubectl -n veriqta-incident rollout status deployment/api --timeout=180s
kubectl -n veriqta-incident wait --for=condition=Ready pod/trace-reader --timeout=180s
kubectl -n veriqta-incident port-forward service/api 8088:8080
```

In another terminal, collect a healthy workload, introduce the pool change, then collect the bad workload:

```bash
mkdir -p artifacts/kube-incident/{logs,events,traces,deployments}
python tools/load.py http://localhost:8088/api --requests 300 --concurrency 20 \
  > artifacts/kube-incident/baseline-load.json
kubectl -n veriqta-incident set env deployment/api \
  VERSION=bad-pool POOL_SIZE=2 DB_HOLD=1 DB_RETRIES=2
kubectl -n veriqta-incident rollout status deployment/api --timeout=180s
```

A port-forward selects one Pod and may disconnect when that Pod is replaced. Restart the port-forward after each rollout before continuing:

```bash
python tools/load.py http://localhost:8088/api --requests 300 --concurrency 20 \
  > artifacts/kube-incident/bad-load.json
kubectl -n veriqta-incident logs deployment/api --timestamps \
  > artifacts/kube-incident/logs/bad-api.log
kubectl -n veriqta-incident get events -o json \
  > artifacts/kube-incident/events/cluster-events.json
kubectl -n veriqta-incident get deployments -o json \
  > artifacts/kube-incident/deployments/cluster-deployments.json
python tools/collect.py --namespace veriqta-incident \
  --output artifacts/kube-incident/capture
kubectl -n veriqta-incident set env deployment/api \
  VERSION=recovered POOL_SIZE=8 DB_HOLD=.01 DB_RETRIES=0
kubectl -n veriqta-incident rollout status deployment/api --timeout=180s
```

Restart the port-forward again, repeat the workload into `recovered-load.json`, and export recovered API logs to a separate file. Wait for the span batch exporter to flush and then export traces:

```bash
kubectl -n veriqta-incident exec trace-reader -- cat /data/traces.jsonl \
  > artifacts/kube-incident/traces/cluster-traces.jsonl
python tools/replay.py --logs artifacts/kube-incident/logs \
  --events artifacts/kube-incident/events --traces artifacts/kube-incident/traces \
  --deployments artifacts/kube-incident/deployments --output artifacts/kube-incident/report
```

For continuous log collection, the optional Fluent Bit DaemonSet reads only Veriqta incident container log paths and emits JSON to stdout:

```bash
kubectl apply -f incident/fluent-bit.yaml
kubectl -n veriqta-incident rollout status daemonset/fluent-bit --timeout=180s
kubectl -n veriqta-incident logs -l app=fluent-bit --all-containers=true --tail=30
```

The configuration uses Docker/CRI multiline parsing. Host log access is sensitive; the DaemonSet mounts logs read-only and has no Kubernetes API token. Its stdout demonstrates collection but is not durable centralized retention. Configure an authenticated destination, retention and record-size limits before operating it for a team. The timeline tool consumes the structured API exports above; a centralized Fluent Bit pipeline must unwrap container records and preserve the application timestamp before forwarding into the same normalized schema.

Keep the Compose and Kubernetes timelines separate unless the incident deliberately spans both systems. The Compose experiment has no Kubernetes events; report that evidence gap rather than mixing unrelated events into its causal narrative. Deployment condition snapshots still need CI/audit release records for complete historical attribution.

### Step 7 — Build the live timeline and postmortem

```bash
python tools/replay.py \
  --logs artifacts/incident/logs --events artifacts/incident/events \
  --traces artifacts/incident/traces --deployments artifacts/incident/deployments \
  --output artifacts/incident/report
```

Read the evidence gaps first. A malformed input file is reported as a gap and may omit that file's records; retain the original and repair the export before claiming completeness. OTLP trace IDs can be encoded differently by exporters; normalize hexadecimal/base64 representations before asserting that a text ID joins two records. Compare service names, request IDs, timestamps and trace attributes as supporting context.

The HTML output escapes untrusted content. The Markdown and JSON outputs retain evidence references, but raw logs and trace attributes still need a privacy review. Avoid collecting authorization headers, passwords, customer payloads or connection strings in the first place. The API logs only exception class names rather than full connection exceptions.

Complete the generated postmortem with:

1. The user-visible impact and actual start/recovery interval.
2. A timeline with source references and clock/collection limits.
3. The leading hypothesis and competing explanations.
4. Evidence from request outcomes, pool statistics, logs and traces.
5. Controlled reproduction and before/after comparisons under the same load.
6. Root cause confidence, contributing factors and unresolved questions.
7. What helped, what delayed recovery, and actions with owner, due date and an acceptance test.

A reliable conclusion might be: the controlled bad configuration caused pool saturation and request failures under the recorded load; removing retries reduced amplification, and restoring short-held bounded work recovered the service. That is narrower and more defensible than claiming a deployment timestamp alone proves a production root cause.

**Failure challenge and evidence:** reproduce the pool-exhaustion failure, correlate requests with dependency spans and logs, compare retry behavior, recover, and generate a traceable incident report. **Interview answer:** corroborate a hypothesis across independent signals, reproduce it where possible, and eliminate it through a controlled change; preserve uncertainty when evidence is incomplete.

**Cleanup:** `docker compose -f incident/compose.yaml down -v`; remove the Kubernetes variant with `kubectl delete namespace veriqta-incident` after exporting evidence. Restrict and eventually delete raw evidence according to its retention policy. Keep only reviewed, sanitized examples in the public portfolio.

## Portfolio and interview demonstration

Choose a project whose failure you can explain without reading commands from the screen. Show the architecture, demonstrate the healthy baseline, introduce the controlled failure, interpret the evidence, recover and rerun the acceptance checks. A short, reproducible demonstration is more convincing than a list of installed tools.

Use `templates/portfolio.md` for each repository. Include setup prerequisites, exact commands, architecture and trust boundaries, one failure scenario, detection/recovery evidence, tradeoffs, cleanup and a clear next improvement. Identify synthetic examples as synthetic and measured results as measured. Do not claim production operation, cost savings, uptime, security assurance or recovery targets that the demonstration has not established.

| Project | Main engineering decision | Minimum evidence |
|---|---|---|
| 01 | Reject an unhealthy runtime candidate | Healthy baseline, failed gate, stable continuity, promotion/rollback |
| 02 | Investigate cloud drift without blind repair | Actual drift direction, reviewed resolution, clean follow-up |
| 03 | Diagnose from evidence before changing Pods | Five distinct reports and recovered business requests |
| 04 | Rank normalized cost contributors | Reconciled totals, window math, owners and recommendations |
| 05 | Prevent and contain credential exposure | Redacted staged/history findings and response sequence |
| 06 | Alert on user-facing budget burn | Rule tests, firing/resolution, receiver and runbook |
| 07 | Enforce environment boundaries and expiry | Quota/RBAC/network denials and automated deletion |
| 08 | Demonstrate recoverability | Independent restore, content/app checks, RTO/RPO and corruption fallback |
| 09 | Require approved artifact authenticity | Scan result, unsigned denial, valid signature and signed admission |
| 10 | Support an incident conclusion with evidence | UTC timeline, logs/traces, controlled comparisons and postmortem |

When asked what you would improve, be specific: a precisely weighted canary router, event-driven drift alerts, deeper resource telemetry, cost-owner inventory, centralized secret revocation, longer SLO history, authenticated provisioning, WAL-based point-in-time recovery, isolated builder provenance, or durable incident evidence collection. Explain which risk the improvement addresses and how you would verify it.

The final standard is simple: another engineer can reproduce the result, understand the decision and see where the evidence ends.

## Complete code reference

The following files form the implementation used in the projects. Each heading links to the corresponding companion file.

### [.gitignore](.gitignore)

````text
.venv/
__pycache__/
*.pyc
.env
.private/
artifacts/
.terraform/
*.tfstate*
*.tfplan
*.auto.tfvars
cosign.key
````

### [app/Dockerfile](app/Dockerfile)

````dockerfile
FROM python:3.12-slim-bookworm
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/api.py .
USER 10001:10001
EXPOSE 8080
CMD ["python", "-u", "api.py"]
````

### [app/api.py](app/api.py)

````python
"""Veriqta instrumented API: deterministic release errors and optional real DB pool."""
import contextlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.getenv('VERSION', 'v1')
if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', VERSION):
    raise ValueError('VERSION must be a short metric-safe identifier')
ERROR_EVERY = int(os.getenv('ERROR_EVERY', '0'))
DB_RETRIES = int(os.getenv('DB_RETRIES', '0'))
DB_HOLD = float(os.getenv('DB_HOLD', '.01'))
if not 0 <= ERROR_EVERY <= 10000 or not 0 <= DB_RETRIES <= 3 or not 0 <= DB_HOLD <= 5:
    raise ValueError('Failure settings exceed the bounded lab range')
READY = os.getenv('READY', 'true') == 'true'
BUCKETS = (.05, .1, .3, .5, 1, 2, 5, 10, float('inf'))
LOCK = threading.Lock()
COUNTS, HIST, TOTAL = {}, [0] * len(BUCKETS), 0.0
REQUESTS = 0
POOL = None
TRACER = None
if os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    provider = TracerProvider(resource=Resource.create({'service.name': 'veriqta-api', 'service.version': VERSION}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    TRACER = trace.get_tracer('veriqta.api')
if os.getenv('DB_HOST'):
    from psycopg_pool import ConnectionPool
    # Keyword arguments avoid DSN interpolation and keep passwords out of logs.
    POOL = ConnectionPool('', min_size=1, max_size=int(os.getenv('POOL_SIZE', '8')),
        timeout=float(os.getenv('POOL_TIMEOUT', '.25')),
        kwargs={'host': os.environ['DB_HOST'], 'dbname': os.getenv('DB_NAME', 'veriqta'),
                'user': os.getenv('DB_USER', 'veriqta'), 'password': os.environ['DB_PASSWORD'],
                'connect_timeout': 3, 'port': int(os.getenv('DB_PORT', '5432'))}, open=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def log(event, **fields):
    if TRACER:
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            fields.setdefault('trace_id', f'{context.trace_id:032x}')
            fields.setdefault('span_id', f'{context.span_id:016x}')
    print(json.dumps({'timestamp': now(), 'service': 'api', 'version': VERSION,
                      'event': event, **fields}), flush=True)

def span(name):
    return TRACER.start_as_current_span(name) if TRACER else contextlib.nullcontext(None)

def business():
    global REQUESTS
    with LOCK:
        REQUESTS += 1
        seq = REQUESTS
    if ERROR_EVERY and seq % ERROR_EVERY == 0:
        return 500, {'status': 'error', 'version': VERSION}
    if POOL:
        retries = DB_RETRIES
        for attempt in range(retries + 1):
            try:
                with span('db.pool-and-query') as s:
                    if s: s.set_attribute('db.system', 'postgresql')
                    with POOL.connection() as conn:
                        conn.execute('SELECT pg_sleep(%s)', (DB_HOLD,))
                        count = conn.execute('SELECT count(*) FROM veriqta_records').fetchone()[0]
                return 200, {'status': 'ok', 'version': VERSION, 'records': count}
            except Exception as exc:
                # Class names only: connection exceptions may contain host names/credentials.
                log('db_attempt_failed', attempt=attempt + 1, error_type=type(exc).__name__)
                if attempt == retries:
                    return 503, {'status': 'db_unavailable', 'version': VERSION}
                time.sleep(.02 * (attempt + 1))
    return 200, {'status': 'ok', 'version': VERSION}

def observe(code, elapsed):
    global TOTAL
    with LOCK:
        COUNTS[str(code)] = COUNTS.get(str(code), 0) + 1
        TOTAL += elapsed
        for i, bound in enumerate(BUCKETS):
            if elapsed <= bound: HIST[i] += 1

def metrics():
    with LOCK:
        lines = ['# TYPE http_requests_total counter']
        for code, value in sorted(COUNTS.items()):
            lines.append(f'http_requests_total{{version="{VERSION}",code="{code}"}} {value}')
        lines.append('# TYPE http_request_duration_seconds histogram')
        for bound, value in zip(BUCKETS, HIST):
            le = '+Inf' if bound == float('inf') else str(bound)
            lines.append(f'http_request_duration_seconds_bucket{{version="{VERSION}",le="{le}"}} {value}')
        lines += [f'http_request_duration_seconds_count{{version="{VERSION}"}} {sum(COUNTS.values())}',
                  f'http_request_duration_seconds_sum{{version="{VERSION}"}} {TOTAL}']
        if POOL:
            for key, value in POOL.get_stats().items():
                lines.append(f'db_pool_{key}{{version="{VERSION}"}} {value}')
        return '\n'.join(lines) + '\n'

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/metrics':
            self.reply(200, metrics().encode(), 'text/plain; version=0.0.4'); return
        if path == '/healthz':
            self.reply(200, b'alive'); return
        if path == '/readyz':
            healthy = READY
            if healthy and POOL:
                try:
                    with POOL.connection(timeout=.2) as conn: conn.execute('SELECT 1')
                except Exception: healthy = False
            self.reply(200 if healthy else 503, b'ready' if healthy else b'not ready'); return
        if path != '/api':
            self.reply(404, b'not found'); return
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        with span('GET /api') as s:
            code, body = business()
            elapsed = time.monotonic() - started
            observe(code, elapsed)
            trace_id = f'{s.get_span_context().trace_id:032x}' if s else None
            if s:
                s.set_attribute('http.response.status_code', code)
                s.set_attribute('request.id', request_id)
            log('request', code=code, duration_seconds=round(elapsed, 6),
                request_id=request_id, trace_id=trace_id)
            self.reply(code, json.dumps(body).encode())
    def reply(self, code, payload, content_type='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try: self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError): pass

if __name__ == '__main__':
    if os.getenv('CRASH') == 'true': raise SystemExit('Veriqta simulated startup configuration failure')
    log('startup')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
````

### [app/requirements.txt](app/requirements.txt)

````text
psycopg[binary]==3.2.9
psycopg-pool==3.2.6
opentelemetry-sdk==1.34.1
opentelemetry-exporter-otlp-proto-grpc==1.34.1
````

### [aws/backup-bucket.json](aws/backup-bucket.json)

````json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta encrypted versioned recovery bucket",
  "Resources": {
    "Backups": {
      "Type": "AWS::S3::Bucket",
      "DeletionPolicy": "Retain",
      "UpdateReplacePolicy": "Retain",
      "Properties": {
        "VersioningConfiguration": {
          "Status": "Enabled"
        },
        "BucketEncryption": {
          "ServerSideEncryptionConfiguration": [
            {
              "ServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
              }
            }
          ]
        },
        "PublicAccessBlockConfiguration": {
          "BlockPublicAcls": true,
          "IgnorePublicAcls": true,
          "BlockPublicPolicy": true,
          "RestrictPublicBuckets": true
        },
        "LifecycleConfiguration": {
          "Rules": [
            {
              "Id": "retention",
              "Status": "Enabled",
              "ExpirationInDays": 30,
              "NoncurrentVersionExpiration": {
                "NoncurrentDays": 30
              },
              "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 1
              }
            }
          ]
        }
      }
    },
    "TransportPolicy": {
      "Type": "AWS::S3::BucketPolicy",
      "Properties": {
        "Bucket": {
          "Ref": "Backups"
        },
        "PolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Deny",
              "Principal": "*",
              "Action": "s3:*",
              "Resource": [
                {
                  "Fn::GetAtt": [
                    "Backups",
                    "Arn"
                  ]
                },
                {
                  "Fn::Sub": "${Backups.Arn}/*"
                }
              ],
              "Condition": {
                "Bool": {
                  "aws:SecureTransport": "false"
                }
              }
            }
          ]
        }
      }
    }
  },
  "Outputs": {
    "BucketName": {
      "Value": {
        "Ref": "Backups"
      }
    }
  }
}
````

### [aws/review-role.json](aws/review-role.json)

````json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta read-only drift and cost investigation role",
  "Parameters": {
    "Repository": {
      "Type": "String",
      "AllowedPattern": "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    },
    "Branch": {
      "Type": "String",
      "Default": "main"
    },
    "OidcProviderArn": {
      "Type": "String"
    },
    "StateBucket": {
      "Type": "String"
    }
  },
  "Resources": {
    "ReviewRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "MaxSessionDuration": 3600,
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Federated": {
                  "Ref": "OidcProviderArn"
                }
              },
              "Action": "sts:AssumeRoleWithWebIdentity",
              "Condition": {
                "StringEquals": {
                  "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                  "token.actions.githubusercontent.com:sub": {
                    "Fn::Sub": "repo:${Repository}:ref:refs/heads/${Branch}"
                  }
                }
              }
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "review",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": [
                    "ec2:Describe*",
                    "ce:GetCostAndUsage"
                  ],
                  "Resource": "*"
                },
                {
                  "Effect": "Allow",
                  "Action": "s3:ListBucket",
                  "Resource": {
                    "Fn::Sub": "arn:${AWS::Partition}:s3:::${StateBucket}"
                  }
                },
                {
                  "Effect": "Allow",
                  "Action": "s3:GetObject",
                  "Resource": {
                    "Fn::Sub": "arn:${AWS::Partition}:s3:::${StateBucket}/drift/terraform.tfstate"
                  }
                },
                {
                  "Effect": "Allow",
                  "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                  ],
                  "Resource": {
                    "Fn::Sub": "arn:${AWS::Partition}:s3:::${StateBucket}/drift/terraform.tfstate.tflock"
                  }
                }
              ]
            }
          }
        ]
      }
    }
  },
  "Outputs": {
    "RoleArn": {
      "Value": {
        "Fn::GetAtt": [
          "ReviewRole",
          "Arn"
        ]
      }
    }
  }
}
````

### [compose.yaml](compose.yaml)

````yaml
name: veriqta-release
services:
  stable:
    build: {context: ., dockerfile: app/Dockerfile}
    image: veriqta-api:lab
    environment: {VERSION: v1}
    ports: ["127.0.0.1:8080:8080"]
  canary:
    pull_policy: never
    image: veriqta-api:lab
    environment: {VERSION: v2, ERROR_EVERY: "${ERROR_EVERY:-5}"}
    ports: ["127.0.0.1:8082:8080"]
    depends_on: [stable]
  prometheus:
    image: prom/prometheus:v3.5.0
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/rules.yml:/etc/prometheus/rules.yml:ro
      - prometheus-data:/prometheus
    ports: ["127.0.0.1:9090:9090"]
  alertmanager:
    image: prom/alertmanager:v0.28.1
    volumes: ["./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro"]
    ports: ["127.0.0.1:9093:9093"]
  receiver:
    image: python:3.12-slim-bookworm
    command: [python, -u, /receiver.py]
    volumes: ["./monitoring/receiver.py:/receiver.py:ro"]
  grafana:
    image: grafana/grafana:12.1.0
    environment: {GF_AUTH_ANONYMOUS_ENABLED: "true", GF_AUTH_ANONYMOUS_ORG_ROLE: Viewer}
    volumes:
      - ./monitoring/grafana-datasource.yml:/etc/grafana/provisioning/datasources/prometheus.yml:ro
      - ./monitoring/grafana-provider.yml:/etc/grafana/provisioning/dashboards/provider.yml:ro
      - ./monitoring/dashboard.json:/var/lib/grafana/dashboards/veriqta.json:ro
    ports: ["127.0.0.1:3000:3000"]
volumes:
  prometheus-data:
````

### [fixtures/canary-bad.json](fixtures/canary-bad.json)

````json
{
  "v1": {
    "requests": 1000,
    "error_ratio": 0,
    "p95_seconds": 0.1
  },
  "v2": {
    "requests": 1000,
    "error_ratio": 0.2,
    "p95_seconds": 0.1
  }
}
````

### [fixtures/canary-good.json](fixtures/canary-good.json)

````json
{
  "v1": {
    "requests": 1000,
    "error_ratio": 0,
    "p95_seconds": 0.1
  },
  "v2": {
    "requests": 1000,
    "error_ratio": 0.001,
    "p95_seconds": 0.12
  }
}
````

### [fixtures/costs.json](fixtures/costs.json)

````json
[
  {
    "date": "2026-01-01",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-02",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-03",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-04",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-05",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-06",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-07",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "60.0"
  },
  {
    "date": "2026-01-08",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-09",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-10",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-11",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-12",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-13",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-14",
    "service": "EC2",
    "owner": "veriqta-platform",
    "usd": "90.71428571428571"
  },
  {
    "date": "2026-01-01",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-02",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-03",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-04",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-05",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-06",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-07",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "40.0"
  },
  {
    "date": "2026-01-08",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-09",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-10",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-11",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-12",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-13",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-14",
    "service": "RDS",
    "owner": "veriqta-data",
    "usd": "50.0"
  },
  {
    "date": "2026-01-01",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-02",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-03",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-04",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-05",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-06",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-07",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-08",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-09",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-10",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-11",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-12",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-13",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-14",
    "service": "S3",
    "owner": "veriqta-platform",
    "usd": "28.571428571428573"
  },
  {
    "date": "2026-01-01",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-02",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-03",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-04",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-05",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-06",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-07",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "44.285714285714285"
  },
  {
    "date": "2026-01-08",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-09",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-10",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-11",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-12",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-13",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-14",
    "service": "NAT Gateway",
    "owner": "veriqta-data",
    "usd": "61.42857142857143"
  },
  {
    "date": "2026-01-01",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-02",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-03",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-04",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-05",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-06",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-07",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "17.142857142857142"
  },
  {
    "date": "2026-01-08",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-09",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-10",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-11",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-12",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-13",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-14",
    "service": "CloudWatch",
    "owner": "veriqta-platform",
    "usd": "21.428571428571427"
  },
  {
    "date": "2026-01-01",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-02",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-03",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-04",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-05",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-06",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-07",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "20.0"
  },
  {
    "date": "2026-01-08",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-09",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-10",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-11",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-12",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-13",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  },
  {
    "date": "2026-01-14",
    "service": "Other",
    "owner": "veriqta-data",
    "usd": "31.857142857142858"
  }
]
````

### [fixtures/drift.json](fixtures/drift.json)

````json
{
  "resource_drift": [
    {
      "address": "aws_vpc_security_group_ingress_rule.ssh",
      "change": {
        "actions": [
          "update"
        ],
        "before": {
          "cidr_ipv4": "10.42.0.0/16",
          "ip_protocol": "tcp",
          "from_port": 22,
          "to_port": 22
        },
        "after": {
          "cidr_ipv4": "0.0.0.0/0",
          "ip_protocol": "tcp",
          "from_port": 22,
          "to_port": 22
        }
      }
    }
  ],
  "resource_changes": [
    {
      "address": "aws_vpc_security_group_ingress_rule.ssh",
      "change": {
        "actions": [
          "update"
        ],
        "before": {
          "cidr_ipv4": "0.0.0.0/0"
        },
        "after": {
          "cidr_ipv4": "10.42.0.0/16"
        }
      }
    }
  ]
}
````

### [fixtures/incident/deployments/sample.json](fixtures/incident/deployments/sample.json)

````json
{
  "timestamp": "2026-01-15T10:12:00Z",
  "service": "api",
  "event": "deployment bad-pool revision abc123"
}
````

### [fixtures/incident/events/sample.json](fixtures/incident/events/sample.json)

````json
{
  "kind": "EventList",
  "items": [
    {
      "metadata": {
        "creationTimestamp": "2026-01-15T10:12:00Z"
      },
      "lastTimestamp": "2026-01-15T10:12:00Z",
      "reason": "ScalingReplicaSet",
      "message": "New API ReplicaSet created",
      "involvedObject": {
        "name": "api"
      }
    }
  ]
}
````

### [fixtures/incident/logs/sample.json](fixtures/incident/logs/sample.json)

````json
{
  "timestamp": "2026-01-15T10:14:21Z",
  "service": "api",
  "event": "db_attempt_failed",
  "error_type": "PoolTimeout",
  "trace_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
````

### [fixtures/incident/traces/sample.json](fixtures/incident/traces/sample.json)

````json
{
  "resourceSpans": [
    {
      "resource": {
        "attributes": [
          {
            "key": "service.name",
            "value": {
              "stringValue": "api"
            }
          }
        ]
      },
      "scopeSpans": [
        {
          "spans": [
            {
              "name": "db.pool-and-query",
              "traceId": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              "startTimeUnixNano": "1768472061000000000",
              "endTimeUnixNano": "1768472061250000000",
              "attributes": [
                {
                  "key": "error.type",
                  "value": {
                    "stringValue": "PoolTimeout"
                  }
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
````

### [incident/compose.yaml](incident/compose.yaml)

````yaml
name: veriqta-incident
services:
  db:
    image: postgres:17-bookworm
    environment:
      POSTGRES_DB: veriqta
      POSTGRES_USER: veriqta
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes: ["../recovery/init.sql:/docker-entrypoint-initdb.d/init.sql:ro"]
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U veriqta -d veriqta"]
      interval: 3s
      retries: 30
  api:
    build: {context: .., dockerfile: app/Dockerfile}
    image: veriqta-api:lab
    environment:
      VERSION: "${INCIDENT_VERSION:-baseline}"
      DB_HOST: db
      DB_HOLD: "${DB_HOLD:-0.01}"
      POOL_SIZE: "${POOL_SIZE:-8}"
      POOL_TIMEOUT: "0.25"
      DB_RETRIES: "${DB_RETRIES:-0}"
      OTEL_EXPORTER_OTLP_ENDPOINT: http://collector:4317
      OTEL_EXPORTER_OTLP_INSECURE: "true"
    entrypoint: [sh, -c, 'export DB_PASSWORD="$$(cat /run/secrets/db_password)"; exec python -u api.py']
    secrets: [db_password]
    ports: ["127.0.0.1:8086:8080"]
    depends_on:
      db: {condition: service_healthy}
  collector:
    image: otel/opentelemetry-collector-contrib:0.130.1
    command: [--config=/etc/otelcol/config.yaml]
    user: "0:0"
    volumes:
      - ./otel.yaml:/etc/otelcol/config.yaml:ro
      - ../artifacts/incident/traces:/data
secrets:
  db_password: {file: ../.private/db-password}
````

### [incident/fluent-bit.conf](incident/fluent-bit.conf)

````text
[SERVICE]
    Flush 1
    Log_Level info
[INPUT]
    Name tail
    Path /var/log/containers/*veriqta*.log
    Tag kube.veriqta
    multiline.parser docker, cri
    Read_from_Head true
[OUTPUT]
    Name stdout
    Match *
    Format json_lines
````

### [incident/fluent-bit.yaml](incident/fluent-bit.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "ConfigMap",
      "metadata": {
        "name": "fluent-bit",
        "namespace": "veriqta-incident"
      },
      "data": {
        "fluent-bit.conf": "[SERVICE]\n    Flush 1\n    Log_Level info\n[INPUT]\n    Name tail\n    Path /var/log/containers/*_veriqta-incident_*.log\n    Tag kube.veriqta\n    multiline.parser docker, cri\n    Read_from_Head true\n[OUTPUT]\n    Name stdout\n    Match *\n    Format json_lines\n"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "DaemonSet",
      "metadata": {
        "name": "fluent-bit",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "matchLabels": {
            "app": "fluent-bit"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "fluent-bit"
            }
          },
          "spec": {
            "automountServiceAccountToken": false,
            "tolerations": [
              {
                "operator": "Exists"
              }
            ],
            "containers": [
              {
                "name": "fluent-bit",
                "image": "cr.fluentbit.io/fluent/fluent-bit:4.0.7",
                "args": [
                  "-c",
                  "/config/fluent-bit.conf"
                ],
                "securityContext": {
                  "runAsUser": 0,
                  "readOnlyRootFilesystem": true,
                  "allowPrivilegeEscalation": false
                },
                "resources": {
                  "requests": {
                    "cpu": "25m",
                    "memory": "32Mi"
                  },
                  "limits": {
                    "cpu": "200m",
                    "memory": "128Mi"
                  }
                },
                "volumeMounts": [
                  {
                    "name": "logs",
                    "mountPath": "/var/log",
                    "readOnly": true
                  },
                  {
                    "name": "config",
                    "mountPath": "/config",
                    "readOnly": true
                  }
                ]
              }
            ],
            "volumes": [
              {
                "name": "logs",
                "hostPath": {
                  "path": "/var/log",
                  "type": "Directory"
                }
              },
              {
                "name": "config",
                "configMap": {
                  "name": "fluent-bit"
                }
              }
            ]
          }
        }
      }
    }
  ]
}
````

### [incident/kubernetes.yaml](incident/kubernetes.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "Namespace",
      "metadata": {
        "name": "veriqta-incident"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "replicas": 1,
        "strategy": {
          "type": "Recreate"
        },
        "selector": {
          "matchLabels": {
            "app": "db"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "db"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "db",
                "image": "postgres:17-bookworm",
                "env": [
                  {
                    "name": "POSTGRES_DB",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  }
                ],
                "ports": [
                  {
                    "containerPort": 5432
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "data",
                    "mountPath": "/var/lib/postgresql/data"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                  },
                  "limits": {
                    "cpu": "1",
                    "memory": "512Mi"
                  }
                },
                "readinessProbe": {
                  "exec": {
                    "command": [
                      "pg_isready",
                      "-U",
                      "veriqta"
                    ]
                  },
                  "periodSeconds": 5
                }
              }
            ],
            "volumes": [
              {
                "name": "data",
                "persistentVolumeClaim": {
                  "claimName": "db-data"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "app": "db"
        },
        "ports": [
          {
            "port": 5432
          }
        ]
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "api",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "replicas": 1,
        "selector": {
          "matchLabels": {
            "component": "api"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "api",
              "version": "v1",
              "component": "api"
            }
          },
          "spec": {
            "automountServiceAccountToken": false,
            "containers": [
              {
                "name": "api",
                "image": "veriqta-api:lab",
                "imagePullPolicy": "IfNotPresent",
                "ports": [
                  {
                    "containerPort": 8080
                  }
                ],
                "env": [
                  {
                    "name": "VERSION",
                    "value": "v1"
                  },
                  {
                    "name": "DB_HOST",
                    "value": "db"
                  },
                  {
                    "name": "DB_NAME",
                    "value": "veriqta"
                  },
                  {
                    "name": "DB_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "DB_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  },
                  {
                    "name": "POOL_SIZE",
                    "value": "8"
                  },
                  {
                    "name": "DB_HOLD",
                    "value": ".01"
                  },
                  {
                    "name": "DB_RETRIES",
                    "value": "0"
                  },
                  {
                    "name": "OTEL_EXPORTER_OTLP_ENDPOINT",
                    "value": "http://collector:4317"
                  },
                  {
                    "name": "OTEL_EXPORTER_OTLP_INSECURE",
                    "value": "true"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "50m",
                    "memory": "64Mi"
                  },
                  "limits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                  }
                },
                "readinessProbe": {
                  "httpGet": {
                    "path": "/readyz",
                    "port": 8080
                  },
                  "periodSeconds": 3
                },
                "livenessProbe": {
                  "httpGet": {
                    "path": "/healthz",
                    "port": 8080
                  },
                  "periodSeconds": 10
                },
                "securityContext": {
                  "runAsNonRoot": true,
                  "runAsUser": 10001,
                  "allowPrivilegeEscalation": false,
                  "capabilities": {
                    "drop": [
                      "ALL"
                    ]
                  },
                  "seccompProfile": {
                    "type": "RuntimeDefault"
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "api",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "component": "api"
        },
        "ports": [
          {
            "port": 8080
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "ConfigMap",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-incident"
      },
      "data": {
        "default.conf": "server { listen 80; location / { proxy_pass http://api:8080; } }\n"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "matchLabels": {
            "app": "web"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "web"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "web",
                "image": "nginx:1.28-alpine",
                "ports": [
                  {
                    "containerPort": 80
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "config",
                    "mountPath": "/etc/nginx/conf.d"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "25m",
                    "memory": "32Mi"
                  },
                  "limits": {
                    "cpu": "200m",
                    "memory": "128Mi"
                  }
                }
              }
            ],
            "volumes": [
              {
                "name": "config",
                "configMap": {
                  "name": "web"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "app": "web"
        },
        "ports": [
          {
            "port": 80
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "PersistentVolumeClaim",
      "metadata": {
        "name": "db-data",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "accessModes": [
          "ReadWriteOnce"
        ],
        "resources": {
          "requests": {
            "storage": "1Gi"
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "PersistentVolumeClaim",
      "metadata": {
        "name": "traces",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "accessModes": [
          "ReadWriteOnce"
        ],
        "resources": {
          "requests": {
            "storage": "1Gi"
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "ConfigMap",
      "metadata": {
        "name": "collector",
        "namespace": "veriqta-incident"
      },
      "data": {
        "config.yaml": "receivers:\n  otlp:\n    protocols:\n      grpc: {endpoint: '0.0.0.0:4317'}\nprocessors:\n  batch: {timeout: 1s}\nexporters:\n  file: {path: /data/traces.jsonl}\nservice:\n  pipelines:\n    traces:\n      receivers: [otlp]\n      processors: [batch]\n      exporters: [file]\n"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "collector",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "replicas": 1,
        "strategy": {
          "type": "Recreate"
        },
        "selector": {
          "matchLabels": {
            "app": "collector"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "collector"
            }
          },
          "spec": {
            "securityContext": {
              "runAsUser": 10001,
              "runAsGroup": 10001,
              "fsGroup": 10001
            },
            "automountServiceAccountToken": false,
            "containers": [
              {
                "name": "collector",
                "image": "otel/opentelemetry-collector-contrib:0.130.1",
                "args": [
                  "--config=/config/config.yaml"
                ],
                "volumeMounts": [
                  {
                    "name": "config",
                    "mountPath": "/config"
                  },
                  {
                    "name": "data",
                    "mountPath": "/data"
                  }
                ],
                "ports": [
                  {
                    "containerPort": 4317
                  }
                ]
              }
            ],
            "volumes": [
              {
                "name": "config",
                "configMap": {
                  "name": "collector"
                }
              },
              {
                "name": "data",
                "persistentVolumeClaim": {
                  "claimName": "traces"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "collector",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "selector": {
          "app": "collector"
        },
        "ports": [
          {
            "port": 4317
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Pod",
      "metadata": {
        "name": "trace-reader",
        "namespace": "veriqta-incident"
      },
      "spec": {
        "automountServiceAccountToken": false,
        "restartPolicy": "Never",
        "securityContext": {
          "runAsUser": 10001,
          "runAsGroup": 10001,
          "fsGroup": 10001
        },
        "containers": [
          {
            "name": "reader",
            "image": "python:3.12-slim-bookworm",
            "command": [
              "sleep",
              "infinity"
            ],
            "volumeMounts": [
              {
                "name": "data",
                "mountPath": "/data",
                "readOnly": true
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "data",
            "persistentVolumeClaim": {
              "claimName": "traces"
            }
          }
        ]
      }
    }
  ]
}
````

### [incident/otel.yaml](incident/otel.yaml)

````yaml
receivers:
  otlp:
    protocols:
      grpc: {endpoint: '0.0.0.0:4317'}
processors:
  batch: {timeout: 1s}
exporters:
  file: {path: /data/traces.jsonl}
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [file]
````

### [kubernetes/failures.yaml](kubernetes/failures.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "Namespace",
      "metadata": {
        "name": "veriqta-failures"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "replicas": 1,
        "strategy": {
          "type": "Recreate"
        },
        "selector": {
          "matchLabels": {
            "app": "db"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "db"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "db",
                "image": "postgres:17-bookworm",
                "env": [
                  {
                    "name": "POSTGRES_DB",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  }
                ],
                "ports": [
                  {
                    "containerPort": 5432
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "data",
                    "mountPath": "/var/lib/postgresql/data"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "100m",
                    "memory": "128Mi"
                  },
                  "limits": {
                    "cpu": "1",
                    "memory": "512Mi"
                  }
                },
                "readinessProbe": {
                  "exec": {
                    "command": [
                      "pg_isready",
                      "-U",
                      "veriqta"
                    ]
                  },
                  "periodSeconds": 5
                }
              }
            ],
            "volumes": [
              {
                "name": "data",
                "emptyDir": {}
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "selector": {
          "app": "db"
        },
        "ports": [
          {
            "port": 5432
          }
        ]
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "api",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "replicas": 1,
        "selector": {
          "matchLabels": {
            "component": "api"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "api",
              "version": "v1",
              "component": "api"
            }
          },
          "spec": {
            "automountServiceAccountToken": false,
            "containers": [
              {
                "name": "api",
                "image": "veriqta-api:lab",
                "imagePullPolicy": "IfNotPresent",
                "ports": [
                  {
                    "containerPort": 8080
                  }
                ],
                "env": [
                  {
                    "name": "VERSION",
                    "value": "v1"
                  },
                  {
                    "name": "DB_HOST",
                    "value": "db"
                  },
                  {
                    "name": "DB_NAME",
                    "value": "veriqta"
                  },
                  {
                    "name": "DB_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "DB_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "50m",
                    "memory": "64Mi"
                  },
                  "limits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                  }
                },
                "readinessProbe": {
                  "httpGet": {
                    "path": "/readyz",
                    "port": 8080
                  },
                  "periodSeconds": 3
                },
                "livenessProbe": {
                  "httpGet": {
                    "path": "/healthz",
                    "port": 8080
                  },
                  "periodSeconds": 10
                },
                "securityContext": {
                  "runAsNonRoot": true,
                  "runAsUser": 10001,
                  "allowPrivilegeEscalation": false,
                  "capabilities": {
                    "drop": [
                      "ALL"
                    ]
                  },
                  "seccompProfile": {
                    "type": "RuntimeDefault"
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "api",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "selector": {
          "component": "api"
        },
        "ports": [
          {
            "port": 8080
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "ConfigMap",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-failures"
      },
      "data": {
        "default.conf": "server { listen 80; location / { proxy_pass http://api:8080; } }\n"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "selector": {
          "matchLabels": {
            "app": "web"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "web"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "web",
                "image": "nginx:1.28-alpine",
                "ports": [
                  {
                    "containerPort": 80
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "config",
                    "mountPath": "/etc/nginx/conf.d"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "25m",
                    "memory": "32Mi"
                  },
                  "limits": {
                    "cpu": "200m",
                    "memory": "128Mi"
                  }
                }
              }
            ],
            "volumes": [
              {
                "name": "config",
                "configMap": {
                  "name": "web"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "web",
        "namespace": "veriqta-failures"
      },
      "spec": {
        "selector": {
          "app": "web"
        },
        "ports": [
          {
            "port": 80
          }
        ]
      }
    }
  ]
}
````

### [kubernetes/kind.yaml](kubernetes/kind.yaml)

````yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    image: kindest/node:v1.32.2
  - role: worker
    image: kindest/node:v1.32.2
networking:
  disableDefaultCNI: true
````

### [kubernetes/oom.yaml](kubernetes/oom.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "Pod",
  "metadata": {
    "name": "oom",
    "namespace": "veriqta-failures"
  },
  "spec": {
    "restartPolicy": "Never",
    "containers": [
      {
        "name": "allocate",
        "image": "python:3.12-slim-bookworm",
        "command": [
          "python",
          "-c",
          "import time; blocks=[]\nwhile True:\n blocks.append(bytearray(8*1024*1024)); time.sleep(.1)"
        ],
        "resources": {
          "requests": {
            "memory": "16Mi",
            "cpu": "10m"
          },
          "limits": {
            "memory": "32Mi",
            "cpu": "100m"
          }
        }
      }
    ]
  }
}
````

### [kubernetes/release.yaml](kubernetes/release.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "Namespace",
      "metadata": {
        "name": "veriqta-release"
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "stable",
        "namespace": "veriqta-release"
      },
      "spec": {
        "replicas": 3,
        "selector": {
          "matchLabels": {
            "component": "stable"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "api",
              "version": "v1",
              "component": "stable"
            }
          },
          "spec": {
            "automountServiceAccountToken": false,
            "containers": [
              {
                "name": "api",
                "image": "veriqta-api:lab",
                "imagePullPolicy": "IfNotPresent",
                "ports": [
                  {
                    "containerPort": 8080
                  }
                ],
                "env": [
                  {
                    "name": "VERSION",
                    "value": "v1"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "50m",
                    "memory": "64Mi"
                  },
                  "limits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                  }
                },
                "readinessProbe": {
                  "httpGet": {
                    "path": "/readyz",
                    "port": 8080
                  },
                  "periodSeconds": 3
                },
                "livenessProbe": {
                  "httpGet": {
                    "path": "/healthz",
                    "port": 8080
                  },
                  "periodSeconds": 10
                },
                "securityContext": {
                  "runAsNonRoot": true,
                  "runAsUser": 10001,
                  "allowPrivilegeEscalation": false,
                  "capabilities": {
                    "drop": [
                      "ALL"
                    ]
                  },
                  "seccompProfile": {
                    "type": "RuntimeDefault"
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "canary",
        "namespace": "veriqta-release"
      },
      "spec": {
        "replicas": 1,
        "selector": {
          "matchLabels": {
            "component": "canary"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "api",
              "version": "v2",
              "component": "canary"
            }
          },
          "spec": {
            "automountServiceAccountToken": false,
            "containers": [
              {
                "name": "api",
                "image": "veriqta-api:lab",
                "imagePullPolicy": "IfNotPresent",
                "ports": [
                  {
                    "containerPort": 8080
                  }
                ],
                "env": [
                  {
                    "name": "VERSION",
                    "value": "v2"
                  },
                  {
                    "name": "ERROR_EVERY",
                    "value": "5"
                  }
                ],
                "resources": {
                  "requests": {
                    "cpu": "50m",
                    "memory": "64Mi"
                  },
                  "limits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                  }
                },
                "readinessProbe": {
                  "httpGet": {
                    "path": "/readyz",
                    "port": 8080
                  },
                  "periodSeconds": 3
                },
                "livenessProbe": {
                  "httpGet": {
                    "path": "/healthz",
                    "port": 8080
                  },
                  "periodSeconds": 10
                },
                "securityContext": {
                  "runAsNonRoot": true,
                  "runAsUser": 10001,
                  "allowPrivilegeEscalation": false,
                  "capabilities": {
                    "drop": [
                      "ALL"
                    ]
                  },
                  "seccompProfile": {
                    "type": "RuntimeDefault"
                  }
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "api",
        "namespace": "veriqta-release"
      },
      "spec": {
        "selector": {
          "app": "api"
        },
        "ports": [
          {
            "port": 8080,
            "targetPort": 8080
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "stable",
        "namespace": "veriqta-release"
      },
      "spec": {
        "selector": {
          "component": "stable"
        },
        "ports": [
          {
            "port": 8080,
            "targetPort": 8080
          }
        ]
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "canary",
        "namespace": "veriqta-release"
      },
      "spec": {
        "selector": {
          "component": "canary"
        },
        "ports": [
          {
            "port": 8080,
            "targetPort": 8080
          }
        ]
      }
    }
  ]
}
````

### [monitoring/alertmanager.yml](monitoring/alertmanager.yml)

````yaml
route:
  receiver: lab
  group_by: [alertname, service]
  group_wait: 10s
  group_interval: 30s
  repeat_interval: 1h
receivers:
  - name: lab
    webhook_configs:
      - url: http://receiver:8081/
        send_resolved: true
````

### [monitoring/dashboard.json](monitoring/dashboard.json)

````json
{
  "title": "Veriqta service reliability",
  "uid": "veriqta-slo",
  "schemaVersion": 39,
  "version": 1,
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "refresh": "5s",
  "panels": [
    {
      "id": 1,
      "title": "Request rate",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "sum(rate(http_requests_total[5m]))",
          "refId": "A"
        }
      ]
    },
    {
      "id": 2,
      "title": "Availability (5m)",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "1 - service:error_ratio:5m",
          "refId": "A"
        }
      ]
    },
    {
      "id": 3,
      "title": "p95 latency seconds",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 0,
        "y": 8,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum by(le) (rate(http_request_duration_seconds_bucket[5m])))",
          "refId": "A"
        }
      ]
    },
    {
      "id": 4,
      "title": "30d request-weighted budget remaining",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 12,
        "y": 8,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "1 - ((sum(increase(http_requests_total{code=~\"5..\"}[30d])) or vector(0)) / sum(increase(http_requests_total[30d]))) / 0.001",
          "refId": "A"
        }
      ]
    },
    {
      "id": 5,
      "title": "Pool connections",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 0,
        "y": 16,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "db_pool_pool_size",
          "refId": "A"
        }
      ]
    },
    {
      "id": 6,
      "title": "Pool wait seconds cumulative",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "veriqta-prom"
      },
      "gridPos": {
        "x": 12,
        "y": 16,
        "w": 12,
        "h": 8
      },
      "targets": [
        {
          "expr": "db_pool_requests_wait_ms / 1000",
          "refId": "A"
        }
      ]
    }
  ]
}
````

### [monitoring/grafana-datasource.yml](monitoring/grafana-datasource.yml)

````yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: veriqta-prom
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
````

### [monitoring/grafana-provider.yml](monitoring/grafana-provider.yml)

````yaml
apiVersion: 1
providers:
  - name: Veriqta
    type: file
    options: {path: /var/lib/grafana/dashboards}
````

### [monitoring/prometheus.yml](monitoring/prometheus.yml)

````yaml
global:
  scrape_interval: 5s
  evaluation_interval: 15s
rule_files: [/etc/prometheus/rules.yml]
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]
scrape_configs:
  - job_name: api
    static_configs:
      - targets: ["stable:8080"]
        labels: {track: stable}
      - targets: ["canary:8080"]
        labels: {track: canary}
````

### [monitoring/receiver.py](monitoring/receiver.py)

````python
"""Local Alertmanager receiver; never forwards notifications externally."""
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 1000000:self.send_error(413);return
        data=json.loads(self.rfile.read(size))
        print(json.dumps(data),flush=True)
        self.send_response(204);self.end_headers()
HTTPServer(('0.0.0.0',8081),Handler).serve_forever()
````

### [monitoring/rules.test.yml](monitoring/rules.test.yml)

````yaml
rule_files: [rules.yml]
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: 'http_requests_total{version="v1",code="200"}'
        values: '0+90x70'
      - series: 'http_requests_total{version="v1",code="500"}'
        values: '0+10x70'
    alert_rule_test:
      - eval_time: 65m
        alertname: VeriqtaFastErrorBudgetBurn
        exp_alerts:
          - exp_labels: {severity: page, service: api}
            exp_annotations:
              summary: API is consuming the availability error budget rapidly
              runbook: See Project 06 in the Veriqta handbook
  - interval: 1m
    input_series:
      - series: 'http_requests_total{version="v1",code="200"}'
        values: '0+1000x70'
      - series: 'http_requests_total{version="v1",code="500"}'
        values: '0+0x70'
    alert_rule_test:
      - eval_time: 65m
        alertname: VeriqtaFastErrorBudgetBurn
        exp_alerts: []
````

### [monitoring/rules.yml](monitoring/rules.yml)

````yaml
groups:
  - name: veriqta-slo
    rules:
      - record: service:error_ratio:5m
        expr: (sum(rate(http_requests_total{code=~"5.."}[5m])) or vector(0)) / sum(rate(http_requests_total[5m]))
      - record: service:error_ratio:1h
        expr: (sum(rate(http_requests_total{code=~"5.."}[1h])) or vector(0)) / sum(rate(http_requests_total[1h]))
      - alert: VeriqtaFastErrorBudgetBurn
        expr: service:error_ratio:5m > (14.4 * 0.001) and service:error_ratio:1h > (14.4 * 0.001) and sum(increase(http_requests_total[5m])) >= 100
        for: 1m
        labels: {severity: page, service: api}
        annotations:
          summary: API is consuming the availability error budget rapidly
          runbook: See Project 06 in the Veriqta handbook
      - alert: VeriqtaTelemetryMissing
        expr: absent(up{job="api"}) or max(up{job="api"}) == 0
        for: 2m
        labels: {severity: warning, service: telemetry}
        annotations: {summary: No reachable API scrape targets}
````

### [platform/Dockerfile](platform/Dockerfile)

````dockerfile
FROM registry.k8s.io/kubectl:v1.32.2 AS kubectl
FROM python:3.12-slim-bookworm
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl
COPY tools/environments.py /environments.py
ENV HOME=/tmp
USER 10001:10001
ENTRYPOINT ["python", "/environments.py"]
````

### [platform/sweeper.yaml](platform/sweeper.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "Namespace",
      "metadata": {
        "name": "veriqta-platform"
      }
    },
    {
      "apiVersion": "v1",
      "kind": "ServiceAccount",
      "metadata": {
        "name": "sweeper",
        "namespace": "veriqta-platform"
      }
    },
    {
      "apiVersion": "rbac.authorization.k8s.io/v1",
      "kind": "ClusterRole",
      "metadata": {
        "name": "veriqta-environment-sweeper"
      },
      "rules": [
        {
          "apiGroups": [
            ""
          ],
          "resources": [
            "namespaces"
          ],
          "verbs": [
            "get",
            "list",
            "delete"
          ]
        }
      ]
    },
    {
      "apiVersion": "rbac.authorization.k8s.io/v1",
      "kind": "ClusterRoleBinding",
      "metadata": {
        "name": "veriqta-environment-sweeper"
      },
      "roleRef": {
        "apiGroup": "rbac.authorization.k8s.io",
        "kind": "ClusterRole",
        "name": "veriqta-environment-sweeper"
      },
      "subjects": [
        {
          "kind": "ServiceAccount",
          "name": "sweeper",
          "namespace": "veriqta-platform"
        }
      ]
    },
    {
      "apiVersion": "batch/v1",
      "kind": "CronJob",
      "metadata": {
        "name": "expire-environments",
        "namespace": "veriqta-platform"
      },
      "spec": {
        "schedule": "*/5 * * * *",
        "concurrencyPolicy": "Forbid",
        "successfulJobsHistoryLimit": 1,
        "failedJobsHistoryLimit": 2,
        "jobTemplate": {
          "spec": {
            "activeDeadlineSeconds": 120,
            "backoffLimit": 1,
            "template": {
              "spec": {
                "serviceAccountName": "sweeper",
                "restartPolicy": "Never",
                "containers": [
                  {
                    "name": "sweep",
                    "image": "veriqta-platform:lab",
                    "imagePullPolicy": "IfNotPresent",
                    "args": [
                      "sweep",
                      "--apply"
                    ],
                    "resources": {
                      "requests": {
                        "cpu": "25m",
                        "memory": "32Mi"
                      },
                      "limits": {
                        "cpu": "200m",
                        "memory": "128Mi"
                      }
                    }
                  }
                ]
              }
            }
          }
        }
      }
    }
  ]
}
````

### [recovery/Dockerfile](recovery/Dockerfile)

````dockerfile
FROM postgres:17-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gnupg awscli && rm -rf /var/lib/apt/lists/*
COPY recovery/kube-backup.sh /backup.sh
ENTRYPOINT ["bash", "/backup.sh"]
````

### [recovery/backup.cron](recovery/backup.cron)

````text
# Host-side Linux cron example. Replace /opt/veriqta-playbook with the actual absolute path.
# The same OS account must own the passphrase, Docker access, and optional AWS identity.
17 2 * * * cd /opt/veriqta-playbook && /usr/bin/flock -n .private/backup.lock .venv/bin/python tools/recovery.py backup --passphrase-file .private/backup-passphrase >> .private/backup.log 2>&1
````

### [recovery/compose.yaml](recovery/compose.yaml)

````yaml
name: veriqta-recovery
services:
  db:
    image: postgres:17-bookworm
    environment:
      POSTGRES_DB: veriqta
      POSTGRES_USER: veriqta
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes:
      - data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U veriqta -d veriqta"]
      interval: 3s
      retries: 30
  restored:
    image: postgres:17-bookworm
    environment:
      POSTGRES_DB: veriqta
      POSTGRES_USER: veriqta
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes: ["restore-data:/var/lib/postgresql/data"]
    healthcheck:
      test: [CMD-SHELL, "pg_isready -U veriqta -d veriqta"]
      interval: 3s
      retries: 30
  api:
    build: {context: .., dockerfile: app/Dockerfile}
    image: veriqta-api:lab
    environment:
      VERSION: recovered
      DB_HOST: restored
      DB_NAME: veriqta
      DB_USER: veriqta
    entrypoint: [sh, -c, 'export DB_PASSWORD="$$(cat /run/secrets/db_password)"; exec python -u api.py']
    secrets: [db_password]
    ports: ["127.0.0.1:8085:8080"]
    depends_on:
      restored: {condition: service_healthy}
secrets:
  db_password: {file: ../.private/db-password}
volumes:
  data:
  restore-data:
````

### [recovery/init.sql](recovery/init.sql)

````sql
CREATE TABLE IF NOT EXISTS veriqta_records (
 id integer PRIMARY KEY,
 name text NOT NULL,
 committed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO veriqta_records(id,name) VALUES (1,'veriqta-alpha'),(2,'veriqta-beta'),(3,'veriqta-gamma') ON CONFLICT DO NOTHING;
````

### [recovery/kube-backup.sh](recovery/kube-backup.sh)

````bash
#!/usr/bin/env bash
set -euo pipefail
umask 077
export GNUPGHOME=/tmp/gnupg
mkdir -p "$GNUPGHOME"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stamp=$(date -u +%Y%m%dT%H%M%S%NZ)
pg_dump --format=custom --no-owner --no-privileges > "$work/database.dump"
gpg --batch --yes --pinentry-mode loopback --passphrase-file /encryption/passphrase \
  --symmetric --cipher-algo AES256 --output "/backups/$stamp.dump.gpg.partial" "$work/database.dump"
mv "/backups/$stamp.dump.gpg.partial" "/backups/$stamp.dump.gpg"
if [[ -n "${BACKUP_BUCKET:-}" ]]; then
  aws s3 cp "/backups/$stamp.dump.gpg" "s3://$BACKUP_BUCKET/postgres/$stamp.dump.gpg" --sse AES256
fi
printf 'Completed encrypted backup %s\n' "$stamp"
````

### [recovery/kubernetes.yaml](recovery/kubernetes.yaml)

````yaml
{
  "apiVersion": "v1",
  "kind": "List",
  "items": [
    {
      "apiVersion": "v1",
      "kind": "Namespace",
      "metadata": {
        "name": "veriqta-recovery"
      }
    },
    {
      "apiVersion": "v1",
      "kind": "PersistentVolumeClaim",
      "metadata": {
        "name": "db-data",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "accessModes": [
          "ReadWriteOnce"
        ],
        "resources": {
          "requests": {
            "storage": "1Gi"
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "PersistentVolumeClaim",
      "metadata": {
        "name": "restore-data",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "accessModes": [
          "ReadWriteOnce"
        ],
        "resources": {
          "requests": {
            "storage": "1Gi"
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "PersistentVolumeClaim",
      "metadata": {
        "name": "backups",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "accessModes": [
          "ReadWriteOnce"
        ],
        "resources": {
          "requests": {
            "storage": "1Gi"
          }
        }
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "replicas": 1,
        "strategy": {
          "type": "Recreate"
        },
        "selector": {
          "matchLabels": {
            "app": "db"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "db"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "db",
                "image": "postgres:17-bookworm",
                "env": [
                  {
                    "name": "POSTGRES_DB",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "data",
                    "mountPath": "/var/lib/postgresql/data"
                  }
                ],
                "readinessProbe": {
                  "exec": {
                    "command": [
                      "pg_isready",
                      "-U",
                      "veriqta"
                    ]
                  },
                  "periodSeconds": 5
                }
              }
            ],
            "volumes": [
              {
                "name": "data",
                "persistentVolumeClaim": {
                  "claimName": "db-data"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "db",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "selector": {
          "app": "db"
        },
        "ports": [
          {
            "port": 5432
          }
        ]
      }
    },
    {
      "apiVersion": "apps/v1",
      "kind": "Deployment",
      "metadata": {
        "name": "restored",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "replicas": 1,
        "strategy": {
          "type": "Recreate"
        },
        "selector": {
          "matchLabels": {
            "app": "restored"
          }
        },
        "template": {
          "metadata": {
            "labels": {
              "app": "restored"
            }
          },
          "spec": {
            "containers": [
              {
                "name": "db",
                "image": "postgres:17-bookworm",
                "env": [
                  {
                    "name": "POSTGRES_DB",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_USER",
                    "value": "veriqta"
                  },
                  {
                    "name": "POSTGRES_PASSWORD",
                    "valueFrom": {
                      "secretKeyRef": {
                        "name": "database",
                        "key": "password"
                      }
                    }
                  }
                ],
                "volumeMounts": [
                  {
                    "name": "data",
                    "mountPath": "/var/lib/postgresql/data"
                  }
                ],
                "readinessProbe": {
                  "exec": {
                    "command": [
                      "pg_isready",
                      "-U",
                      "veriqta"
                    ]
                  },
                  "periodSeconds": 5
                }
              }
            ],
            "volumes": [
              {
                "name": "data",
                "persistentVolumeClaim": {
                  "claimName": "restore-data"
                }
              }
            ]
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Service",
      "metadata": {
        "name": "restored",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "selector": {
          "app": "restored"
        },
        "ports": [
          {
            "port": 5432
          }
        ]
      }
    },
    {
      "apiVersion": "batch/v1",
      "kind": "CronJob",
      "metadata": {
        "name": "database-backup",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "schedule": "17 2 * * *",
        "timeZone": "Etc/UTC",
        "concurrencyPolicy": "Forbid",
        "successfulJobsHistoryLimit": 2,
        "failedJobsHistoryLimit": 2,
        "jobTemplate": {
          "spec": {
            "backoffLimit": 1,
            "activeDeadlineSeconds": 300,
            "template": {
              "spec": {
                "automountServiceAccountToken": false,
                "restartPolicy": "Never",
                "containers": [
                  {
                    "name": "backup",
                    "image": "veriqta-backup:lab",
                    "imagePullPolicy": "IfNotPresent",
                    "env": [
                      {
                        "name": "PGHOST",
                        "value": "db"
                      },
                      {
                        "name": "PGDATABASE",
                        "value": "veriqta"
                      },
                      {
                        "name": "PGUSER",
                        "value": "veriqta"
                      },
                      {
                        "name": "PGPASSWORD",
                        "valueFrom": {
                          "secretKeyRef": {
                            "name": "database",
                            "key": "password"
                          }
                        }
                      }
                    ],
                    "volumeMounts": [
                      {
                        "name": "backups",
                        "mountPath": "/backups"
                      },
                      {
                        "name": "encryption",
                        "mountPath": "/encryption",
                        "readOnly": true
                      },
                      {
                        "name": "temporary",
                        "mountPath": "/tmp"
                      }
                    ],
                    "resources": {
                      "requests": {
                        "cpu": "100m",
                        "memory": "128Mi"
                      },
                      "limits": {
                        "cpu": "1",
                        "memory": "384Mi"
                      }
                    }
                  }
                ],
                "volumes": [
                  {
                    "name": "backups",
                    "persistentVolumeClaim": {
                      "claimName": "backups"
                    }
                  },
                  {
                    "name": "encryption",
                    "secret": {
                      "secretName": "backup-encryption",
                      "defaultMode": 256
                    }
                  },
                  {
                    "name": "temporary",
                    "emptyDir": {
                      "medium": "Memory",
                      "sizeLimit": "256Mi"
                    }
                  }
                ]
              }
            }
          }
        }
      }
    },
    {
      "apiVersion": "v1",
      "kind": "Pod",
      "metadata": {
        "name": "restore-tool",
        "namespace": "veriqta-recovery"
      },
      "spec": {
        "automountServiceAccountToken": false,
        "restartPolicy": "Never",
        "containers": [
          {
            "name": "tools",
            "image": "veriqta-backup:lab",
            "imagePullPolicy": "IfNotPresent",
            "command": [
              "sleep",
              "infinity"
            ],
            "env": [
              {
                "name": "PGHOST",
                "value": "restored"
              },
              {
                "name": "PGDATABASE",
                "value": "veriqta"
              },
              {
                "name": "PGUSER",
                "value": "veriqta"
              },
              {
                "name": "PGPASSWORD",
                "valueFrom": {
                  "secretKeyRef": {
                    "name": "database",
                    "key": "password"
                  }
                }
              }
            ],
            "volumeMounts": [
              {
                "name": "backups",
                "mountPath": "/backups"
              },
              {
                "name": "encryption",
                "mountPath": "/encryption",
                "readOnly": true
              },
              {
                "name": "temporary",
                "mountPath": "/tmp"
              }
            ]
          }
        ],
        "volumes": [
          {
            "name": "backups",
            "persistentVolumeClaim": {
              "claimName": "backups"
            }
          },
          {
            "name": "encryption",
            "secret": {
              "secretName": "backup-encryption",
              "defaultMode": 256
            }
          },
          {
            "name": "temporary",
            "emptyDir": {
              "medium": "Memory",
              "sizeLimit": "256Mi"
            }
          }
        ]
      }
    }
  ]
}
````

### [security/gitleaks.toml](security/gitleaks.toml)

````toml
title = "Veriqta secret prevention"
[extend]
useDefault = true
[[rules]]
id = "veriqta-training-canary"
description = "Synthetic training credential marker"
regex = '''VERIQTA_CANARY_[A-Z0-9]{24}'''
keywords = ["VERIQTA_CANARY_"]
````

### [security/pre-commit-config.yaml](security/pre-commit-config.yaml)

````yaml
repos:
  - repo: local
    hooks:
      - id: gitleaks
        name: Veriqta staged secret scan
        entry: gitleaks git --pre-commit --staged --redact --config security/gitleaks.toml
        language: system
        pass_filenames: false
````

### [templates/incident-report.md](templates/incident-report.md)

````markdown
# Veriqta failure investigation

## User-visible symptom and scope

## Start, detection, mitigation and recovery times (UTC)

## Evidence
| Observation | Evidence location | Interpretation | Confidence |
|---|---|---|---|

## Competing hypotheses

## Smallest controlled change

## Before / after verification

## Root cause and contributing factors

## Prevention and follow-up
| Action | Owner | Due | Acceptance check |
|---|---|---|---|
````

### [templates/portfolio.md](templates/portfolio.md)

````markdown
# Veriqta project portfolio

## Problem and intended users

## Architecture and trust boundaries

## Reproduce the baseline

## Introduce one controlled failure

## Detection and evidence

## Recovery and measured result

## Limits and tradeoffs

## Cleanup

## Interview demonstration
Explain the failure, show the evidence that separated competing explanations, demonstrate recovery, and describe one improvement you would make before operating this for a team.
````

### [templates/security-exception.md](templates/security-exception.md)

````markdown
# Veriqta security exception

| Field | Decision |
|---|---|
| Exact image digest | |
| Finding / policy rule | |
| Business reason | |
| Exposure and exploitability evidence | |
| Compensating controls | |
| Requester | |
| Independent approver | |
| Expiry UTC | |
| Remediation owner and due date | |
| Verification and removal evidence | |

An entry in this document does not change cluster policy. An administrator must review and implement any narrowly scoped policy change separately. Wildcard registry bypasses and indefinite exceptions are prohibited in this exercise.
````

### [terraform/bootstrap/main.tf](terraform/bootstrap/main.tf)

````hcl
terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" { region = var.region }
variable "region" { type = string }
variable "bucket_name" { type = string }
resource "aws_s3_bucket" "state" { bucket = var.bucket_name }
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
output "bucket" { value = aws_s3_bucket.state.id }
````

### [terraform/drift/main.tf](terraform/drift/main.tf)

````hcl
terraform {
  required_version = ">= 1.10, < 2.0"
  backend "s3" {}
  required_providers { aws = { source = "hashicorp/aws", version = "~> 6.0" } }
}
provider "aws" { region = var.region }
variable "region" { type = string }
resource "aws_vpc" "lab" {
  cidr_block = "10.42.0.0/16"
  tags = { Name = "veriqta-drift-lab", Owner = "veriqta" }
}
resource "aws_security_group" "lab" {
  name_prefix = "veriqta-drift-"
  description = "Unattached drift exercise security group"
  vpc_id = aws_vpc.lab.id
  tags = { Name = "veriqta-drift-lab" }
}
resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.lab.id
  ip_protocol = "tcp"
  from_port = 22
  to_port = 22
  cidr_ipv4 = "10.42.0.0/16"
}
output "security_group_id" { value = aws_security_group.lab.id }
output "ingress_rule_id" { value = aws_vpc_security_group_ingress_rule.ssh.id }
````

### [tests/test_tools.py](tests/test_tools.py)

````python
import datetime,importlib.util,json,pathlib,tempfile,unittest,io
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
gate=load('gate','tools/gate.py');drift=load('drift','tools/drift.py');costs=load('costs','tools/costs.py');env=load('env','tools/environments.py');replay=load('replay','tools/replay.py');api=load('api','app/api.py')
class Tools(unittest.TestCase):
    def test_release_good_and_bad(self):
        for file,expected in [('canary-good.json',True),('canary-bad.json',False)]:
            data=json.loads((ROOT/'fixtures'/file).read_text());self.assertEqual(gate.decide(data['v1'],data['v2'])[0],expected)
    def test_missing_traffic_and_nan_block(self):
        good={'requests':1000,'error_ratio':0,'p95_seconds':.1}
        for bad in ({**good,'requests':0},{**good,'error_ratio':float('nan')},{**good,'p95_seconds':.31}):self.assertFalse(gate.decide(good,bad)[0])
        self.assertFalse(gate.decide({**good,'error_ratio':.03},good)[0])
    def test_drift_direction(self):
        data=json.loads((ROOT/'fixtures/drift.json').read_text());self.assertEqual(drift.classify(data)['observed_drift'][0]['risk'],'high')
        data['resource_drift'][0]['change']['after']['cidr_ipv4']='10.42.0.0/16'
        self.assertEqual(drift.classify(data)['observed_drift'][0]['risk'],'unclassified')
    def test_normalized_costs(self):
        rows=[{'date':'2026-01-01','service':'EC2','owner':'a','usd':'300'},{'date':'2026-01-31','service':'EC2','owner':'a','usd':'70'}]
        r=costs.compare(rows,'2026-01-01','2026-01-31','2026-02-07')[0]
        self.assertEqual(r['baseline_per_day'],r['recent_per_day']);self.assertFalse(r['flag'])
    def test_cost_fixture_forty_percent(self):
        from decimal import Decimal
        r=costs.compare(json.loads((ROOT/'fixtures/costs.json').read_text()),'2026-01-01','2026-01-08','2026-01-15')
        b=sum(x['baseline_per_day'] for x in r);a=sum(x['recent_per_day'] for x in r)
        self.assertAlmostEqual(float((a-b)/b),.4)
    def test_expiry_and_scope(self):
        now=datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc)
        ns=env.render('veriqta-env-demo','reader',1,now)['items'][0]
        self.assertFalse(env.expired(ns,now));self.assertTrue(env.expired(ns,now+datetime.timedelta(hours=2)))
        ns['metadata']['name']='kube-system';self.assertFalse(env.expired(ns,now+datetime.timedelta(hours=2)))
        with self.assertRaises(ValueError):env.render('default','reader',24)
        with self.assertRaises(ValueError):env.render('veriqta-env-demo','reader',0)
    def test_timeline_utc_and_html_escape(self):
        self.assertEqual(replay.timestamp('2026-01-01T01:00:00+01:00').hour,0)
        with self.assertRaises(ValueError):replay.timestamp('2026-01-01T01:00:00')
        with tempfile.TemporaryDirectory() as directory:
            timeline,gaps=replay.build({s:ROOT/'fixtures/incident'/s for s in ('logs','events','traces','deployments')},directory)
            self.assertEqual(len(timeline),4);self.assertFalse(gaps)
            self.assertEqual(timeline,sorted(timeline,key=lambda r:(r['timestamp'],r['source'],r['evidence'])))
    def test_request_metrics_and_deterministic_errors(self):
        previous=api.ERROR_EVERY;api.ERROR_EVERY=5;api.REQUESTS=0
        results=[api.business()[0] for _ in range(10)]
        self.assertEqual(results.count(500),2)
        api.COUNTS={};api.HIST=[0]*len(api.BUCKETS);api.TOTAL=0
        api.observe(200,.2);api.observe(500,.4)
        data=api.metrics();self.assertIn('le="0.3"} 1',data);self.assertIn('code="500"} 1',data)
        api.ERROR_EVERY=previous
    def test_http_routes_in_memory(self):
        class Handler(api.Handler):
            def __init__(self,path):self.path=path;self.wfile=io.BytesIO();self.status=None;self.headers={}
            def send_response(self,code):self.status=code
            def send_header(self,key,value):self.headers[key]=value
            def end_headers(self):pass
        with patch.object(api,'log'):
            for path,expected in [('/api',200),('/healthz',200),('/readyz',200),('/metrics',200),('/missing',404)]:
                handler=Handler(path);handler.do_GET();self.assertEqual(handler.status,expected)
                self.assertEqual(int(handler.headers['Content-Length']),len(handler.wfile.getvalue()))
    def test_gate_scrape_failure_blocks(self):
        with patch.object(gate,'query',return_value=0):
            with self.assertRaises(ValueError):gate.sample('http://unused','v2')
        with patch.object(gate,'query',side_effect=[1,60,20]):
            with self.assertRaises(ValueError):gate.sample('http://unused','v1')
    def test_uid_delete_precondition(self):
        ns={'metadata':{'name':'veriqta-env-test','uid':'original-uid','resourceVersion':'123'}}
        with patch.object(env,'kube') as call:
            env.delete(ns)
            self.assertEqual(call.call_args.kwargs['body']['preconditions']['uid'],'original-uid')
            self.assertEqual(call.call_args.kwargs['body']['preconditions']['resourceVersion'],'123')
            self.assertEqual(call.call_args.args[2],'/api/v1/namespaces/veriqta-env-test')
    def test_retry_budget_is_bounded(self):
        class BrokenPool:
            def connection(self):raise RuntimeError('do not log secret details')
        with patch.object(api,'POOL',BrokenPool()), patch.object(api,'ERROR_EVERY',0), patch.object(api,'DB_RETRIES',2), patch.object(api,'log') as log, patch.object(api.time,'sleep'):
            self.assertEqual(api.business()[0],503)
            self.assertEqual(log.call_count,3)
            self.assertNotIn('secret',str(log.call_args_list))
    def test_replay_escapes_untrusted_html_and_reports_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);logs=root/'logs';logs.mkdir()
            (logs/'a.json').write_text(json.dumps({'timestamp':'2026-01-01T00:00:00Z','service':'api','event':'<script>alert(1)</script>'}))
            output=root/'report'
            rows,gaps=replay.build({'logs':logs,'events':root/'absent'},output)
            self.assertEqual(len(rows),1);self.assertEqual(len(gaps),1)
            self.assertNotIn('<script>',(output/'timeline.html').read_text())
    def test_expiry_invalid_time_and_missing_owner(self):
        ns=env.render('veriqta-env-test','reader',1)['items'][0]
        ns['metadata']['annotations']['veriqta.io/expires-at']='2020-01-01T00:00:00'
        self.assertFalse(env.expired(ns))
        ns['metadata']['annotations']['veriqta.io/expires-at']='2020-01-01T00:00:00Z'
        del ns['metadata']['annotations']['veriqta.io/owner']
        self.assertFalse(env.expired(ns))
if __name__=='__main__':unittest.main()
````

### [tools/collect.py](tools/collect.py)

````python
"""Read-only Kubernetes evidence collector. Records unavailable evidence explicitly."""
import argparse,datetime,json,pathlib,re,subprocess

def capture(ns,out):
    if not re.fullmatch(r'veriqta-[a-z0-9-]+',ns): raise ValueError('Veriqta lab namespace required')
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    out.chmod(0o700)
    def run(name,args):
        r=subprocess.run(['kubectl','-n',ns,*args],capture_output=True,text=True,timeout=45)
        (out/name).write_text(r.stdout)
        (out/(name+'.status.json')).write_text(json.dumps({'exit_code':r.returncode,'stderr':r.stderr}))
        return r
    for resource in ('pods','events','services','endpointslices','deployments','replicasets'):
        run(resource+'.json',['get',resource,'-o','json'])
    run('top.txt',['top','pods'])
    pods=json.loads((out/'pods.json').read_text() or '{"items":[]}')
    for pod in pods.get('items',[]):
        name=pod['metadata']['name']
        run(name+'.describe.txt',['describe','pod',name])
        for container in pod['spec'].get('containers',[]):
            for previous in (False,True):
                suffix='.previous' if previous else ''
                run(name+'.'+container['name']+suffix+'.log',['logs',name,'-c',container['name'],'--timestamps','--since=2h',*(['--previous'] if previous else [])])
    (out/'collection.json').write_text(json.dumps({'namespace':ns,'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--output',required=True);a=p.parse_args();capture(a.namespace,a.output)
````

### [tools/costs.py](tools/costs.py)

````python
"""Cost Explorer daily aggregation, normalized comparison, Markdown report."""
import argparse,csv,datetime,json
from decimal import Decimal
from pathlib import Path

def fetch(start,end,second):
    import boto3
    client=boto3.client('ce',region_name='us-east-1')
    params={'TimePeriod':{'Start':start,'End':end},'Granularity':'DAILY','Metrics':['UnblendedCost'],
      'GroupBy':[{'Type':'DIMENSION','Key':'SERVICE'}, {'Type':'TAG' if second.startswith('tag:') else 'DIMENSION','Key':second[4:] if second.startswith('tag:') else 'LINKED_ACCOUNT'}]}
    rows=[];estimated=set()
    while True:
        response=client.get_cost_and_usage(**params)
        for day in response['ResultsByTime']:
            date=day['TimePeriod']['Start']
            if day.get('Estimated'):estimated.add(date)
            for group in day['Groups']:
                metric=group['Metrics']['UnblendedCost']
                if metric['Unit']!='USD':raise ValueError('This report requires USD; do not mix currencies')
                rows.append({'date':date,'service':group['Keys'][0],'owner':group['Keys'][1], 'usd':metric['Amount']})
        token=response.get('NextPageToken')
        if not token:break
        params['NextPageToken']=token
    return rows,sorted(estimated)

def compare(rows,start,split,end):
    start,split,end=map(datetime.date.fromisoformat,(start,split,end))
    if not start<split<end:raise ValueError('Require start < split < end, using exclusive end')
    days=((split-start).days,(end-split).days);totals={}
    for row in rows:
        date=datetime.date.fromisoformat(row['date'])
        if not start<=date<end:continue
        key=(row['service'],row['owner']); values=totals.setdefault(key,[Decimal(0),Decimal(0)])
        values[int(date>=split)]+=Decimal(row['usd'])
    result=[]
    for (service,owner),(before,after) in totals.items():
        b,a=before/days[0],after/days[1]; delta=a-b
        pct=(delta/b*100) if b>0 else None
        flag=delta>=Decimal('1') and (pct is None or pct>=50)
        result.append({'service':service,'owner':owner,'baseline_per_day':b,'recent_per_day':a,'increase_per_day':delta,'percent':pct,'flag':flag})
    return sorted(result,key=lambda x:x['increase_per_day'],reverse=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture');p.add_argument('--start',required=True);p.add_argument('--split',required=True);p.add_argument('--end',required=True)
    p.add_argument('--group',default='account');p.add_argument('--output',default='artifacts/costs');a=p.parse_args()
    if a.group!='account' and not a.group.startswith('tag:'):p.error('--group account or tag:Owner')
    rows=json.load(open(a.fixture)) if a.fixture else None
    estimated=[]
    if rows is None:rows,estimated=fetch(a.start,a.end,a.group)
    report=compare(rows,a.start,a.split,a.end)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    fields=['service','owner','baseline_per_day','recent_per_day','increase_per_day','percent','flag']
    with (out/'ranking.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(report)
    def money(n):return f'{n:.2f}'
    before=sum((r['baseline_per_day'] for r in report),Decimal(0));after=sum((r['recent_per_day'] for r in report),Decimal(0))
    lines=['# Veriqta cost investigation',f'\nUTC periods: [{a.start}, {a.split}) and [{a.split}, {a.end}).',
      f'\nDaily total: USD {money(before)} → {money(after)}. Change: '+(f'{(after-before)/before*100:.2f}%' if before>0 else 'new baseline')+'.',
      '\nEstimated dates: '+(', '.join(estimated) or 'none reported')+'.',
      '\n| Service | Account / tag | Baseline USD/day | Recent USD/day | Increase USD/day | Change | Review |',
      '|---|---|---:|---:|---:|---:|---|']
    for r in report:
        clean=lambda s:str(s).replace('|','/').replace('\n',' ')
        pct='new / nonpositive baseline' if r['percent'] is None else f"{r['percent']:.2f}%"
        lines.append(f"| {clean(r['service'])} | {clean(r['owner'])} | {money(r['baseline_per_day'])} | {money(r['recent_per_day'])} | {money(r['increase_per_day'])} | {pct} | {'investigate' if r['flag'] else 'ranked'} |")
    lines+=['\n## Investigation','Check usage type, resource inventory, traffic, deployments, allocation tags, discounts and credits. A cost increase alone does not establish its cause.',
      '\n## Notification draft','Owner: assign from inventory. Impact: use the ranked increases above. Next action: review the largest contributors and record approved recommendations.']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    print(out/'report.md')
if __name__=='__main__':main()
````

### [tools/drift.py](tools/drift.py)

````python
"""Classify observed Terraform drift; never apply infrastructure changes."""
import argparse,json

def public_ssh(value):
    if not isinstance(value,dict):return False
    if value.get('cidr_ipv4')=='0.0.0.0/0' or value.get('cidr_ipv6')=='::/0':
        protocol=str(value.get('ip_protocol',''))
        low=value.get('from_port');high=value.get('to_port')
        if protocol=='-1' or (protocol in ('tcp','6') and isinstance(low,int) and isinstance(high,int) and low<=22<=high):return True
    for rule in value.get('ingress',[]) or []:
        if not isinstance(rule,dict):continue
        if '0.0.0.0/0' in (rule.get('cidr_blocks') or []) or '::/0' in (rule.get('ipv6_cidr_blocks') or []):
            if rule.get('protocol')=='-1' or (rule.get('protocol') in ('tcp','6') and rule.get('from_port',99)<=22<=rule.get('to_port',0)):return True
    return False

def classify(plan):
    result=[]
    for resource in plan.get('resource_drift',[]):
        change=resource['change']
        actual=change.get('after') or {}
        result.append({'address':resource['address'],'classification':'review-required',
          'risk':'high' if public_ssh(actual) else 'unclassified',
          'observation':'current cloud state allows public SSH' if public_ssh(actual) else 'observed cloud state differs from recorded state',
          'actions':change['actions']})
    return {'observed_drift':result,'planned_changes':[{'address':r['address'],'actions':r['change']['actions']} for r in plan.get('resource_changes',[]) if r['change']['actions']!=['no-op']],
       'decision':'human review required; no automatic apply'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan');a=p.parse_args()
    print(json.dumps(classify(json.load(open(a.plan))),indent=2))
````

### [tools/environments.py](tools/environments.py)

````python
"""Administrator-operated platform lab with ownership checks and automatic expiry."""
import argparse,datetime,json,re,subprocess
NOW=lambda:datetime.datetime.now(datetime.timezone.utc)
MANAGED={'veriqta.io/managed-by':'environment-platform'}

def kube(*args,body=None):
    result=subprocess.run(['kubectl',*args],input=json.dumps(body) if body is not None else None,text=True,capture_output=True,check=True,timeout=60)
    return json.loads(result.stdout) if result.stdout.strip().startswith(('{','[')) else result.stdout

def name_ok(name):return bool(re.fullmatch(r'veriqta-env-[a-z0-9](?:[a-z0-9-]{0,36}[a-z0-9])?',name))

def render(name,owner,hours,now=None):
    if not name_ok(name):raise ValueError('name must be veriqta-env- plus a short DNS name')
    if not re.fullmatch(r'[a-zA-Z0-9@._-]{1,80}',owner):raise ValueError('invalid owner')
    if not 1<=hours<=168:raise ValueError('TTL must be 1..168 hours')
    expiry=((now or NOW())+datetime.timedelta(hours=hours)).isoformat()
    namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':name,'labels':{**MANAGED,'pod-security.kubernetes.io/enforce':'restricted'},'annotations':{'veriqta.io/owner':owner,'veriqta.io/expires-at':expiry}}}
    def resource(kind,name_,spec=None,api='v1',**extra):
        value={'apiVersion':api,'kind':kind,'metadata':{'name':name_,'namespace':name}}
        if spec is not None:value['spec']=spec
        value.update(extra);return value
    policy={'podSelector':{},'policyTypes':['Ingress','Egress'],
      'ingress':[{'from':[{'podSelector':{}}],'ports':[{'protocol':'TCP','port':8080}]}],
      'egress':[{'to':[{'podSelector':{}}],'ports':[{'protocol':'TCP','port':8080}]},
        {'to':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}},'podSelector':{'matchLabels':{'k8s-app':'kube-dns'}}}], 'ports':[{'protocol':'UDP','port':53},{'protocol':'TCP','port':53}]}]}
    container={'name':'api','image':'veriqta-api:lab','imagePullPolicy':'IfNotPresent','ports':[{'containerPort':8080}],
      'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},
      'securityContext':{'runAsUser':10001,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}}
    return {'apiVersion':'v1','kind':'List','items':[namespace,
      resource('ResourceQuota','budget',{'hard':{'requests.cpu':'1','requests.memory':'512Mi','limits.cpu':'2','limits.memory':'1Gi','pods':'5'}}),
      resource('LimitRange','defaults',{'limits':[{'type':'Container','default':{'cpu':'500m','memory':'256Mi'},'defaultRequest':{'cpu':'100m','memory':'64Mi'}}]}),
      resource('NetworkPolicy','isolate',policy,'networking.k8s.io/v1'),
      resource('Role','developer',api='rbac.authorization.k8s.io/v1',rules=[{'apiGroups':[''],'resources':['pods','pods/log','services','events'],'verbs':['get','list','watch']},{'apiGroups':['apps'],'resources':['deployments','deployments/scale','replicasets'],'verbs':['get','list','watch','create','update','patch','delete']}]),
      resource('RoleBinding','developer',api='rbac.authorization.k8s.io/v1',roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'developer'},subjects=[{'kind':'User','name':owner,'apiGroup':'rbac.authorization.k8s.io'}]),
      resource('Deployment','demo',{'selector':{'matchLabels':{'app':'demo'}},'template':{'metadata':{'labels':{'app':'demo'}},'spec':{'automountServiceAccountToken':False,'containers':[container]}}},'apps/v1'),
      resource('Service','demo',{'selector':{'app':'demo'},'ports':[{'port':8080}]})]}

def expired(namespace,now=None):
    meta=namespace.get('metadata',{});name=meta.get('name','')
    if not name_ok(name) or meta.get('labels',{}).get('veriqta.io/managed-by')!='environment-platform':return False
    annotations=meta.get('annotations',{})
    if not annotations.get('veriqta.io/owner'):return False
    try:
        expiry=datetime.datetime.fromisoformat(annotations['veriqta.io/expires-at'].replace('Z','+00:00'))
        if expiry.tzinfo is None:return False
        return expiry<=(now or NOW())
    except (KeyError,ValueError,TypeError):return False

def delete(namespace):
    # UID and resource version bind deletion to the exact namespace revision reviewed.
    meta=namespace['metadata']
    body={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':meta['uid'],'resourceVersion':meta['resourceVersion']},'propagationPolicy':'Background'}
    kube('delete','--raw','/api/v1/namespaces/'+meta['name'],'-f','-',body=body)

def audit(action,name,owner):
    print(json.dumps({'timestamp':NOW().isoformat(),'action':action,'namespace':name,'owner':owner}))

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['create','delete','sweep']);p.add_argument('--name');p.add_argument('--owner');p.add_argument('--hours',type=int,default=24);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if a.action=='create':
        document=render(a.name or '',a.owner or '',a.hours)
        if a.apply:
            existing=subprocess.run(['kubectl','get','namespace',a.name,'-o','json','--ignore-not-found'],capture_output=True,text=True,check=True)
            if existing.stdout.strip():raise SystemExit('Namespace already exists; choose a new name')
            # Create namespace first; if it races, create fails rather than taking over another namespace.
            kube('create','-f','-',body=document['items'][0])
            kube('apply','-f','-',body={'apiVersion':'v1','kind':'List','items':document['items'][1:]})
            audit('create',a.name,a.owner)
        else:print(json.dumps(document,indent=2))
    elif a.action=='delete':
        if not name_ok(a.name or ''):p.error('invalid name')
        ns=kube('get','namespace',a.name,'-o','json');meta=ns['metadata']
        if meta.get('labels',{}).get('veriqta.io/managed-by')!='environment-platform' or meta.get('annotations',{}).get('veriqta.io/owner')!=a.owner:raise SystemExit('Ownership/management check failed')
        if a.apply:delete(ns)
        audit('delete' if a.apply else 'would-delete',a.name,a.owner)
    else:
        for ns in kube('get','namespaces','-l','veriqta.io/managed-by=environment-platform','-o','json')['items']:
            if expired(ns):
                if a.apply:delete(ns)
                audit('expire' if a.apply else 'would-expire',ns['metadata']['name'],ns['metadata']['annotations']['veriqta.io/owner'])
if __name__=='__main__':main()
````

### [tools/gate.py](tools/gate.py)

````python
"""Fail-closed canary gate. Exit 0 pass, 2 reject, 1 telemetry/input error."""
import argparse,json,math,urllib.parse,urllib.request

def decide(stable,canary,minimum=500):
    for name, data in [('stable',stable),('canary',canary)]:
        for key in ('requests','error_ratio','p95_seconds'):
            if key not in data or not isinstance(data[key],(float,int)) or not math.isfinite(data[key]):
                return False,f'{name}: missing/non-finite {key}'
        if data['requests'] < minimum: return False,f'{name}: insufficient traffic'
        if not 0 <= data['error_ratio'] <= 1 or data['p95_seconds'] < 0: return False,f'{name}: invalid measurement'
    if stable['error_ratio'] >= .02 or stable['p95_seconds'] >= .3:
        return False,'baseline unhealthy: pause release and investigate'
    if canary['error_ratio'] >= .02 or canary['p95_seconds'] >= .3:
        return False,'canary violates error/latency budget'
    if canary['error_ratio'] - stable['error_ratio'] > .01:
        return False,'canary regression exceeds one percentage point'
    return True,'canary meets release policy'

def query(base,expr):
    url=base.rstrip('/')+'/api/v1/query?'+urllib.parse.urlencode({'query':expr})
    with urllib.request.urlopen(url,timeout=10) as response: data=json.load(response)
    if data.get('status') != 'success': raise ValueError('Prometheus query failed')
    result=data['data']['result']
    if len(result)!=1: raise ValueError('expected exactly one measurement')
    value=float(result[0]['value'][1])
    if not math.isfinite(value): raise ValueError('missing or non-finite telemetry')
    return value

def sample(base,version):
    if version not in ('v1','v2'):raise ValueError('unknown version')
    target='stable' if version=='v1' else 'canary'
    health='{job="api",track="'+target+'"}'
    if query(base,'min(min_over_time(up'+health+'[5m]))') != 1 or query(base,'min(count_over_time(up'+health+'[5m]))') < 55:
        raise ValueError(target+': require five minutes of healthy scrapes')
    if query(base,'max(time() - timestamp(up'+health+'))') > 15:
        raise ValueError(target+': stale scrape telemetry')
    match='{version="'+version+'"}'
    allreq='sum(increase(http_requests_total'+match+'[5m]))'
    errors='sum(increase(http_requests_total{version="'+version+'",code=~"5.."}[5m]))'
    return {'requests':query(base,allreq),
      'error_ratio':query(base,'('+errors+' or vector(0)) / '+allreq),
      'p95_seconds':query(base,'histogram_quantile(0.95, sum by(le) (rate(http_request_duration_seconds_bucket'+match+'[5m])))')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--prometheus',default='http://localhost:9090');p.add_argument('--fixture')
    a=p.parse_args()
    try:
        data=json.load(open(a.fixture)) if a.fixture else {v:sample(a.prometheus,v) for v in ('v1','v2')}
        passed,reason=decide(data['v1'],data['v2'])
        print(json.dumps({'passed':passed,'reason':reason,'measurements':data},indent=2))
        return 0 if passed else 2
    except Exception as exc:
        print(json.dumps({'passed':False,'reason':str(exc)}));return 1
if __name__=='__main__':raise SystemExit(main())
````

### [tools/kube-prometheus.py](tools/kube-prometheus.py)

````python
"""Render in-cluster Prometheus. Run from package root."""
import json,pathlib
ns='veriqta-release'
config=pathlib.Path('monitoring/prometheus.yml').read_text().split('alerting:',1)[0]
config += """scrape_configs:
  - job_name: api
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [veriqta-release]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: api
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        action: keep
        regex: '8080'
      - source_labels: [__meta_kubernetes_pod_label_component]
        target_label: track
      - source_labels: [__meta_kubernetes_pod_name]
        target_label: pod
"""
items=[{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'prometheus','namespace':ns},'data':{'prometheus.yml':config,'rules.yml':pathlib.Path('monitoring/rules.yml').read_text()}},
{'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'prometheus','namespace':ns},'spec':{'selector':{'matchLabels':{'app':'prometheus'}},'template':{'metadata':{'labels':{'app':'prometheus'}},'spec':{'serviceAccountName':'prometheus','containers':[{'name':'prometheus','image':'prom/prometheus:v3.5.0','ports':[{'containerPort':9090}],'volumeMounts':[{'name':'config','mountPath':'/etc/prometheus'}]}],'volumes':[{'name':'config','configMap':{'name':'prometheus'}}]}}}},
{'apiVersion':'v1','kind':'Service','metadata':{'name':'prometheus','namespace':ns},'spec':{'selector':{'app':'prometheus'},'ports':[{'port':9090}]}}]
items += [
{'apiVersion':'v1','kind':'ServiceAccount','metadata':{'name':'prometheus','namespace':ns}},
{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':{'name':'prometheus-discovery','namespace':ns},'rules':[{'apiGroups':[''],'resources':['pods'],'verbs':['get','list','watch']}]},
{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':{'name':'prometheus-discovery','namespace':ns},'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'prometheus-discovery'},'subjects':[{'kind':'ServiceAccount','name':'prometheus','namespace':ns}]}]
print(json.dumps({'apiVersion':'v1','kind':'List','items':items},indent=2))
````

### [tools/load.py](tools/load.py)

````python
"""Bounded HTTP load. No implicit retries; HTTP error responses are measured."""
import argparse, collections, concurrent.futures, json, time, urllib.error, urllib.request

def request(url):
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            response.read(); code = response.status
    except urllib.error.HTTPError as exc:
        exc.read(); code = exc.code
    except (urllib.error.URLError, TimeoutError): code = 0
    return code, time.monotonic() - start

def main():
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--requests',type=int,default=1000)
    p.add_argument('--concurrency',type=int,default=10);p.add_argument('--pause',type=float,default=.02)
    a=p.parse_args()
    if not 1 <= a.requests <= 100000 or not 1 <= a.concurrency <= 100: p.error('bounded load: 1..100000 requests; 1..100 workers')
    def run(_):
        result=request(a.url);time.sleep(a.pause);return result
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as executor:
        results=list(executor.map(run,range(a.requests)))
    latencies=sorted(t for _,t in results)
    print(json.dumps({'requests':len(results),'codes':dict(collections.Counter(c for c,_ in results)),
       'p95_seconds':latencies[max(0, int(.95*len(latencies)+.999)-1)],
       'elapsed_seconds':time.monotonic()-start},indent=2))
if __name__=='__main__':main()
````

### [tools/notify.py](tools/notify.py)

````python
"""Render review notifications; delivery requires an explicit send option."""
import argparse,json,os,pathlib,urllib.request,urllib.parse
from email.message import EmailMessage

def main():
    p=argparse.ArgumentParser();p.add_argument('report');p.add_argument('--title',default='Veriqta engineering review');p.add_argument('--output',default='artifacts/notifications')
    p.add_argument('--webhook-file');p.add_argument('--send-webhook',action='store_true');a=p.parse_args()
    report=pathlib.Path(a.report).read_text();out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
    payload={'text':a.title+'\n'+report[:3500]+'\nReview the full report before taking action.'}
    (out/'slack.json').write_text(json.dumps(payload,indent=2))
    email=EmailMessage();email['Subject']=a.title;email['From']='veriqta@example.invalid';email['To']='reviewer@example.invalid';email.set_content(report)
    (out/'email.eml').write_text(email.as_string())
    if a.send_webhook:
        if not a.webhook_file:p.error('--webhook-file required to send')
        path=pathlib.Path(a.webhook_file)
        if os.stat(path).st_mode & 0o077:raise SystemExit('Webhook file must be private (mode 600)')
        url=path.read_text().strip();parsed=urllib.parse.urlparse(url)
        if parsed.scheme!='https' or parsed.hostname!='hooks.slack.com':raise SystemExit('An HTTPS Slack incoming-webhook URL is required')
        request=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=10) as response:
                if response.status!=200:raise RuntimeError('Unexpected response')
        except Exception:raise SystemExit('Notification delivery failed; inspect the integration without logging its secret URL')
        print('Review notification delivered')
    else:print('Notification drafts written; no message sent')
if __name__=='__main__':main()
````

### [tools/recovery.py](tools/recovery.py)

````python
"""Encrypted logical backups and verified restore into a separate disposable DB."""
import argparse,datetime,json,os,pathlib,subprocess,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-f',str(ROOT/'recovery/compose.yaml')]

def sql(service,statement):
    result=subprocess.run(COMPOSE+['exec','-T',service,'psql','-X','-A','-t','-v','ON_ERROR_STOP=1','-U','veriqta','-d','veriqta','-c',statement],capture_output=True,text=True,check=True)
    return result.stdout.strip()

def fingerprint(service):
    # Content comparison lives inside the encrypted backup envelope, not in a public manifest.
    return sql(service,"SELECT coalesce(json_agg(t ORDER BY id)::text,'[]') FROM (SELECT id,name,committed_at FROM veriqta_records) t;")

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('--file');p.add_argument('--passphrase-file',required=True);p.add_argument('--directory',default='artifacts/backups');p.add_argument('--bucket');a=p.parse_args()
    key=pathlib.Path(a.passphrase_file).resolve()
    if not key.is_file() or os.stat(key).st_mode & 0o077:raise SystemExit('Passphrase file must exist with mode 600 or stricter')
    out=pathlib.Path(a.directory);out.mkdir(mode=0o700,parents=True,exist_ok=True)
    crypt=['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(key)]
    with tempfile.TemporaryDirectory(prefix='veriqta-restore-') as temp:
        temp=pathlib.Path(temp)
        if a.action=='backup':
            # Quiesce writes for this small exercise. For concurrent systems, use an exported snapshot.
            backup_started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            before=fingerprint('db')
            with (temp/'database.dump').open('wb') as stream:
                subprocess.run(COMPOSE+['exec','-T','db','pg_dump','-U','veriqta','-d','veriqta','-Fc','--no-owner','--no-privileges'],stdout=stream,check=True)
            after=fingerprint('db')
            if before!=after:raise SystemExit('Data changed during backup; pause writers and retry')
            metadata={'backup_started_at':backup_started_at,'backup_completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expected_rows':json.loads(after)}
            (temp/'metadata.json').write_text(json.dumps(metadata))
            import tarfile
            with tarfile.open(temp/'backup.tar','w') as archive:
                archive.add(temp/'database.dump',arcname='database.dump');archive.add(temp/'metadata.json',arcname='metadata.json')
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            target=out/(stamp+'.tar.gpg');pending=target.with_suffix('.partial')
            subprocess.run(crypt+['--symmetric','--cipher-algo','AES256','--output',str(pending),str(temp/'backup.tar')],check=True)
            pending.replace(target)
            if a.bucket:
                import boto3
                response=boto3.client('s3').put_object(Bucket=a.bucket,Key='postgres/'+target.name,Body=target.read_bytes(),ServerSideEncryption='AES256')
                print(json.dumps({'object':'postgres/'+target.name,'version_id':response.get('VersionId')}))
            print(target)
        else:
            if not a.file:raise SystemExit('--file required; choose a completed backup explicitly')
            started=time.monotonic()
            subprocess.run(crypt+['--decrypt','--output',str(temp/'backup.tar'),a.file],check=True)
            import tarfile
            with tarfile.open(temp/'backup.tar') as archive:
                # Read exact expected regular files only; never extract arbitrary archive paths.
                for name in ('database.dump','metadata.json'):
                    member=archive.getmember(name)
                    if not member.isfile():raise SystemExit('Invalid archive member')
                    (temp/name).write_bytes(archive.extractfile(member).read())
            metadata=json.loads((temp/'metadata.json').read_text())
            # This affects only the separate restored service, never the source db service.
            sql('restored','DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
            with (temp/'database.dump').open('rb') as stream:
                subprocess.run(COMPOSE+['exec','-T','restored','pg_restore','-U','veriqta','-d','veriqta','--no-owner','--no-privileges','--exit-on-error'],stdin=stream,check=True)
            actual=json.loads(fingerprint('restored'))
            passed=actual==metadata['expected_rows']
            report={'content_matches':passed,'restored_rows':len(actual),'restore_validation_seconds':time.monotonic()-started,'backup_started_at':metadata.get('backup_started_at'),'backup_completed_at':metadata['backup_completed_at'],'rto_note':'Add detection, provisioning, retrieval and application recovery time to measure end-to-end RTO.'}
            (out/'restore-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
            if not passed:raise SystemExit(2)
if __name__=='__main__':main()
````

### [tools/release.sh](tools/release.sh)

````bash
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
````

### [tools/replay.py](tools/replay.py)

````python
"""Normalize logs, Kubernetes events, OTLP traces and deployment records to evidence."""
import argparse,datetime,html,json,pathlib

def timestamp(value):
    if isinstance(value,int) or (isinstance(value,str) and value.isdigit()):
        return datetime.datetime.fromtimestamp(int(value)/1e9,datetime.timezone.utc)
    t=datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('timestamp lacks timezone')
    return t.astimezone(datetime.timezone.utc)

def normalize(data,source,reference):
    output=[]
    def add(time,service,event,trace_id=''):
        output.append({'timestamp':timestamp(time).isoformat(),'source':source,'service':str(service),'event':str(event),'trace_id':trace_id or '', 'evidence':reference})
    if source=='traces':
        for resource in data.get('resourceSpans',[]):
            attrs={a['key']:a['value'].get('stringValue','') for a in resource.get('resource',{}).get('attributes',[])}
            for scope in resource.get('scopeSpans',[]):
                for span in scope.get('spans',[]):
                    duration=(int(span['endTimeUnixNano'])-int(span['startTimeUnixNano']))/1e9
                    add(span['startTimeUnixNano'],attrs.get('service.name','unknown'),f"{span['name']} duration={duration:.6f}s attributes={json.dumps(span.get('attributes',[]),sort_keys=True)}",span.get('traceId',''))
    elif source=='events' and data.get('kind') in ('EventList','List'):
        for event in data.get('items',[]):
            time=event.get('eventTime') or event.get('lastTimestamp') or event['metadata']['creationTimestamp']
            involved=event.get('involvedObject') or event.get('regarding',{})
            add(time,involved.get('name','unknown'),event.get('reason','')+': '+event.get('message',event.get('note','')))
    elif source=='deployments' and data.get('kind')=='DeploymentList':
        for deployment in data['items']:
            meta=deployment['metadata']
            for condition in deployment.get('status',{}).get('conditions',[]):
                if condition.get('lastUpdateTime'):
                    add(condition['lastUpdateTime'],meta['name'],f"deployment condition {condition['type']}={condition['status']}; current generation={meta.get('generation')}; images="+','.join(c['image'] for c in deployment['spec']['template']['spec']['containers']))
    elif 'timestamp' in data:
        add(data['timestamp'],data.get('service','unknown'),data.get('event','')+' '+json.dumps({k:v for k,v in data.items() if k not in ('timestamp','service','event')},sort_keys=True),data.get('trace_id',''))
    else:raise ValueError('unsupported record shape')
    return output

def records(path):
    text=path.read_text()
    try:return [(1,json.loads(text))]
    except json.JSONDecodeError:
        result=[]
        for line_number,line in enumerate(text.splitlines(),1):
            if not line.strip():continue
            # kubectl --timestamps prefixes RFC3339; Compose --no-log-prefix does not.
            if not line.lstrip().startswith('{') and ' {' in line:line=line[line.index(' {')+1:]
            result.append((line_number,json.loads(line)))
        return result

def build(inputs,out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True);timeline=[];gaps=[]
    for source,directory in inputs.items():
        files=sorted(p for p in pathlib.Path(directory).rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log'))
        if not files:gaps.append(f'{source}: no input files')
        for file in files:
            try:
                for line,data in records(file):
                    try:timeline.extend(normalize(data,source,str(file)+f':{line}'))
                    except (ValueError,KeyError,TypeError) as exc:gaps.append(f'{file}:{line}: {exc}')
            except (ValueError,OSError,TypeError) as exc:gaps.append(f'{file}: {exc}')
    timeline.sort(key=lambda r:(r['timestamp'],r['source'],r['evidence']))
    (out/'timeline.json').write_text(json.dumps(timeline,indent=2))
    def clean(value):
        text=html.escape(str(value).replace('|','/').replace('\n',' '),quote=False)
        for char in ('\\','`','[',']','*','_'):
            text=text.replace(char,'\\'+char)
        return text
    lines=['# Veriqta incident timeline','\nAll times UTC. Ordering shows correlation; causal claims require controlled reproduction and independent evidence.','\n| UTC | Source | Service | Observation | Evidence |','|---|---|---|---|---|']
    for r in timeline:lines.append('| '+' | '.join(clean(r[k]) for k in ('timestamp','source','service','event','evidence'))+' |')
    lines+=['\n## Evidence gaps',*['- '+g for g in gaps]]
    (out/'timeline.md').write_text('\n'.join(lines)+'\n')
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('timestamp','source','service','event','evidence'))+'</tr>' for r in timeline)
    (out/'timeline.html').write_text('<!doctype html><meta charset="utf-8"><title>Veriqta incident timeline</title><h1>Veriqta incident timeline</h1><p>Correlation is not proof of causation. All times UTC.</p><table><tr><th>UTC</th><th>Source</th><th>Service</th><th>Observation</th><th>Evidence</th></tr>'+rows+'</table><h2>Evidence gaps</h2><pre>'+html.escape('\n'.join(gaps))+'</pre>')
    (out/'postmortem.md').write_text('# Veriqta incident review\n\n## Summary\n\n## User impact and duration\n\n## Timeline\nSee [timeline](timeline.md).\n\n## Leading hypothesis and evidence\n\n## Controlled reproduction and recovery comparison\n\n## Root cause confidence and alternative explanations\n\n## Contributing factors\n\n## What went well\n\n## What did not go well\n\n## Actions\n| Action | Owner | Due date | Verification |\n|---|---|---|---|\n\n## Unresolved questions\n')
    return timeline,gaps
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for source in ('logs','events','traces','deployments'):p.add_argument('--'+source,required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    timeline,gaps=build({k:getattr(a,k) for k in ('logs','events','traces','deployments')},a.output)
    print(json.dumps({'records':len(timeline),'gaps':len(gaps)}))
    if not timeline:raise SystemExit(2)
````

### [tools/secret-challenge.py](tools/secret-challenge.py)

````python
"""Create a synthetic credential canary in a disposable Git repository."""
import pathlib,secrets,string,subprocess,sys
path=pathlib.Path(sys.argv[1]).resolve()
if path.exists():raise SystemExit('Choose a new temporary directory')
path.mkdir(mode=0o700,parents=True)
subprocess.run(['git','init',str(path)],check=True,stdout=subprocess.DEVNULL)
marker='VERIQTA_'+'CANARY_'+''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(24))
(path/'example.env').write_text('VERIQTA_DEMO_TOKEN='+marker+'\n')
for args in (['add','example.env'],['-c','user.name=Veriqta','-c','user.email=training@example.invalid','commit','-m','Add synthetic credential challenge']):
    subprocess.run(['git','-C',str(path),*args],check=True,stdout=subprocess.DEVNULL)
print('Synthetic challenge repository created. Scan with redaction enabled.')
````

### [tools/supply-chain.sh](tools/supply-chain.sh)

````bash
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
````

### [tools/trust-policy.py](tools/trust-policy.py)

````python
"""Render enforced Kyverno signature policy for all images in one lab namespace."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--key',default='.private/cosign.pub');a=p.parse_args()
key=pathlib.Path(a.key).read_text()
if 'BEGIN PUBLIC KEY' not in key:raise SystemExit('Cosign public key required')
policy={'apiVersion':'kyverno.io/v1','kind':'ClusterPolicy','metadata':{'name':'veriqta-signed-images'},'spec':{'validationFailureAction':'Enforce','failurePolicy':'Fail','background':False,'rules':[{'name':'require-approved-signature','match':{'any':[{'resources':{'kinds':['Pod'],'namespaces':['veriqta-trust']}}]},'verifyImages':[{'imageReferences':['*'],'mutateDigest':True,'verifyDigest':True,'required':True,'attestors':[{'count':1,'entries':[{'keys':{'publicKeys':key}}]}]}]}]}}
print(json.dumps(policy,indent=2))
````

### [workflows/build.yml](workflows/build.yml)

````yaml
name: Veriqta API build
on:
  push:
    branches: [main]
  pull_request:
permissions: {contents: read}
jobs:
  check:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v5
      - run: python3 -m unittest discover -s tests -v
      - run: docker build -f app/Dockerfile -t veriqta-api:test .
  publish:
    if: github.event_name == 'push'
    needs: check
    runs-on: ubuntu-24.04
    permissions: {contents: read, packages: write}
    steps:
      - uses: actions/checkout@v5
      - name: Build and publish commit tag
        env: {TOKEN: '${{ secrets.GITHUB_TOKEN }}'}
        run: |
          set -euo pipefail
          owner="${GITHUB_REPOSITORY_OWNER,,}"
          image="ghcr.io/$owner/veriqta-api:$GITHUB_SHA"
          printf '%s' "$TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
          docker build -f app/Dockerfile -t "$image" .
          docker push "$image"
          docker inspect --format='{{index .RepoDigests 0}}' "$image" >> "$GITHUB_STEP_SUMMARY"
````

### [workflows/drift.yml](workflows/drift.yml)

````yaml
name: Veriqta drift review
on:
  workflow_dispatch:
  schedule:
    - cron: '23 6 * * *'
permissions: {contents: read, id-token: write}
concurrency: {group: veriqta-drift, cancel-in-progress: false}
jobs:
  review:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v5
      - uses: hashicorp/setup-terraform@v3
        with: {terraform_version: 1.10.5, terraform_wrapper: false}
      - uses: aws-actions/configure-aws-credentials@v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_REVIEW_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: Plan and classify
        env:
          STATE_BUCKET: ${{ vars.STATE_BUCKET }}
          TF_VAR_region: ${{ vars.AWS_REGION }}
        shell: bash
        run: |
          set -euo pipefail
          mkdir -p artifacts
          terraform -chdir=terraform/drift init -backend-config="bucket=$STATE_BUCKET" -backend-config=key=drift/terraform.tfstate -backend-config="region=$TF_VAR_region" -backend-config=use_lockfile=true
          set +e
          terraform -chdir=terraform/drift plan -input=false -detailed-exitcode -out=review.tfplan > artifacts/plan.log 2>&1
          rc=$?
          set -e
          if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ]; then
            echo 'Terraform plan failed; inspect the restricted runner log.' >&2
            exit 1
          fi
          terraform -chdir=terraform/drift show -json review.tfplan > artifacts/plan.json
          python3 tools/drift.py artifacts/plan.json > artifacts/drift-report.json
          cat artifacts/drift-report.json
          if [ "$rc" -eq 2 ]; then echo 'Review required: infrastructure differences detected.' >> "$GITHUB_STEP_SUMMARY"; fi
      - uses: actions/upload-artifact@v4
        with:
          name: drift-classification
          path: artifacts/drift-report.json
          retention-days: 7
````

### [workflows/secrets.yml](workflows/secrets.yml)

````yaml
name: Veriqta secret checks
on: [push, pull_request, workflow_dispatch]
permissions: {contents: read}
jobs:
  scan:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v5
        with: {fetch-depth: 0}
      - name: Scan all fetched history
        run: docker run --rm -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo -v "$PWD:/repo" -w /repo zricethezav/gitleaks:v8.24.3 git --redact --config security/gitleaks.toml --log-opts=--all .
````

### [workflows/trust.yml](workflows/trust.yml)

````yaml
name: Veriqta trusted release
on: workflow_dispatch
permissions: {contents: read}
concurrency: {group: veriqta-trusted-release, cancel-in-progress: false}
jobs:
  release:
    if: github.ref == 'refs/heads/main'
    environment: veriqta-release
    runs-on: ubuntu-24.04
    permissions: {contents: read, packages: write}
    steps:
      - uses: actions/checkout@v5
      - run: python3 -m unittest discover -s tests -v
      - uses: sigstore/cosign-installer@v3.9.2
        with: {cosign-release: v2.5.3}
      - name: Build, scan and sign approved digest
        env:
          TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SIGNING_KEY: ${{ secrets.COSIGN_PRIVATE_KEY }}
          PUBLIC_KEY: ${{ secrets.COSIGN_PUBLIC_KEY }}
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        shell: bash
        run: |
          set -euo pipefail
          umask 077
          mkdir -p .private
          trap 'rm -f .private/cosign.key' EXIT
          printf '%s' "$SIGNING_KEY" > .private/cosign.key
          printf '%s' "$PUBLIC_KEY" > .private/cosign.pub
          owner="${GITHUB_REPOSITORY_OWNER,,}"
          image="ghcr.io/$owner/veriqta-api:$GITHUB_SHA"
          printf '%s' "$TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin
          docker build -f app/Dockerfile -t "$image" .
          docker push "$image"
          export IMAGE_REF=$(docker inspect --format='{{index .RepoDigests 0}}' "$image")
          syft() { docker run --rm --user 0 -e DOCKER_CONFIG=/root/.docker -v "$HOME/.docker:/root/.docker:ro" anchore/syft:v1.27.1 "$@"; }
          trivy() {
            # The script supplies an output path; mount the working tree for its JSON file.
            docker run --rm --user 0 -e DOCKER_CONFIG=/root/.docker -v "$HOME/.docker:/root/.docker:ro" -v "$PWD:/workspace" -w /workspace aquasec/trivy:0.65.0 "$@"
          }
          export -f syft trivy
          bash tools/supply-chain.sh
          printf 'Approved image: `%s`\n' "$IMAGE_REF" >> "$GITHUB_STEP_SUMMARY"
      - uses: actions/upload-artifact@v4
        with:
          name: release-verification
          path: artifacts/supply-chain/
          retention-days: 14
````
