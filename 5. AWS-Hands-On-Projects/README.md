# 10 AWS Hands-On Projects for Beginners

## Build, Deploy, Configure, Troubleshoot, and Monitor

**VERIQTA**

Build practical AWS skills by creating working systems and investigating how they fail. These projects cover account security, a private-origin website, a Linux web server, cloud networking, a serverless API, a task database, infrastructure as code, containers, automated deployment, and incident monitoring.

Each project follows the same path: understand the architecture, prepare access, build the system, verify the result, investigate a controlled failure, restore service, and clean up the resources you own.

## Contents

1. [Secure your AWS environment](#project-01-secure-your-aws-environment)
2. [Host a static website on AWS](#project-02-host-a-static-website-on-aws)
3. [Deploy a Linux web server](#project-03-deploy-a-linux-web-server)
4. [Build your first VPC network](#project-04-build-your-first-vpc-network)
5. [Build a serverless API](#project-05-build-a-serverless-api)
6. [Create a cloud database](#project-06-create-a-cloud-database)
7. [Automate infrastructure deployment](#project-07-automate-infrastructure-deployment)
8. [Deploy a containerized application](#project-08-deploy-a-containerized-application)
9. [Build an automated deployment pipeline](#project-09-build-an-automated-deployment-pipeline)
10. [Monitor and investigate a cloud incident](#project-10-monitor-and-investigate-a-cloud-incident)

The [shared setup](#shared-setup), [cleanup plan](#final-cleanup-plan), [review answers](#review-questions-and-answers), and [complete code](#complete-code-and-configuration) support the projects.

# Shared setup

## Choose a practice account and region

Use an isolated learning account or an approved sandbox. Identify the account owner, selected region, permitted services, and budget before deployment. Keep a [resource register](exercises/resource-register.md) so every resource has an owner and cleanup plan.

AWS Free Tier eligibility depends on account plan, age, service, region, usage, and current offers. Do not assume a particular instance type or an entire project is free. Check the [current AWS account-plan and Free Tier terms](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html) and service pricing before deploying. Compute, public IPv4 addresses, storage, CloudFront, interface endpoints, NAT, logs, image storage/scanning, and requests can contribute to cost. A budget notification is not a guaranteed hard spending cap.

Examples use a commercial AWS account and a region such as `us-east-1`. Select a region with at least two standard Availability Zones and the services used by your chosen projects. Readers elsewhere can select another supported region. China and GovCloud partitions have different service availability, endpoints, and federation requirements; adapt those settings using the applicable service documentation.

## Install local tools

Use AWS CLI v2, Python 3.12 or newer, Git, and curl. Project 8 also needs Docker with a running daemon. Commands use Bash or Zsh; Windows readers can use Ubuntu through WSL2. Choose official installers for your platform and CPU architecture:

- [AWS CLI installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Python downloads](https://www.python.org/downloads/)
- [Git downloads](https://git-scm.com/downloads)
- [Docker installation](https://docs.docker.com/get-started/get-docker/)

Open a terminal in `Veriqta-AWS-Hands-On-Projects`. All local commands run from this directory unless a step explicitly says to run them inside EC2 or another environment.

```bash
aws --version
python3 --version
git --version
curl --version
mkdir -p build
python3 scripts/check_site.py
python3 -m unittest discover -s tests -v
```

The tests use standard-library fakes and local files. They do not create AWS resources. Docker dependencies are installed inside the image during its build.

## Authenticate and verify identity

Prefer IAM Identity Center or another approved federation flow with short-lived credentials. For an Identity Center profile:

```bash
aws configure sso --profile veriqta-learning
aws sso login --profile veriqta-learning
export AWS_PROFILE=veriqta-learning
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=YOUR_12_DIGIT_ACCOUNT_ID
python3 scripts/lab.py identity
```

Replace the account placeholder with the account ID independently confirmed in your account/sandbox. The helper compares it with STS and rejects root credentials. In CloudShell or another environment already using an approved role, use that credential chain instead of creating long-lived keys merely for these lessons.

Never paste access keys into source files, website assets, Docker images, GitHub variables, or screenshots. Expired sessions need reauthentication; increasing permissions will not fix expired credentials.

## Understand the execution identities

| Identity | Responsibility |
| --- | --- |
| Account owner/security administrator | Root protection, federation, billing access, and approved permissions |
| Project deployer | CloudFormation and the resource operations needed for selected projects |
| EC2 instance role | Systems Manager agent access |
| Lambda execution role | Writes the function’s execution logs |
| ECS execution role | Pulls the selected image and writes container logs |
| ECS task role | Application AWS access; none is needed for this demo |
| GitHub OIDC role | Uploads only the selected website and refreshes its distribution |

A read-only learning identity cannot create infrastructure. Ask the account administrator for a controlled project deployment role or approved CloudFormation service role. Permissions should cover the chosen template’s resources, needed `iam:PassRole` targets, and allowed regions. `CAPABILITY_IAM` acknowledges IAM resources in a template; it does not grant the caller permission to create them.

For `AccessDenied`, check the denied action/resource, identity policy, role trust, resource policy, session policy, permissions boundary, and organization controls. An explicit deny overrides an allow. Add the specific supported permission rather than attaching blanket administrator access as a troubleshooting shortcut.

## Work with the project helpers

`infra/` contains full CloudFormation templates. `code/`, `container/`, and `site/` contain the applications. The helper uses deterministic stack names, verifies the expected account, and resolves templates from its own location.

```bash
python3 scripts/lab.py validate 07
python3 scripts/lab.py deploy 07
```

`validate` calls AWS template validation. A deployment without `--execute` creates a change set for review; it does not execute that change set. Inspect the generated change set in CloudFormation, including replacements, IAM changes, and dependencies. Running the deployment again with `--execute` creates and executes the current proposed change:

```bash
python3 scripts/lab.py deploy 07 --execute
```

Use the project-specific commands below rather than deploying this example before reaching project 7. Review-only CREATE change sets can leave a stack in `REVIEW_IN_PROGRESS`; delete that unused stack if you abandon it. An empty change set is not a deployment failure.

Retrieve values without copying screenshots or hardcoding resource IDs:

```bash
python3 scripts/lab.py output 07 BucketName
```

AWS-side validation is not proof that every permission, quota, resource property, runtime, or network path will work. Read stack events and complete each live checkpoint.

## Dependency map

```text
Project 1: account controls and permission practice
Project 2: website ──────────────────────────────→ Project 9 pipeline
Project 3: standalone EC2 web server
Project 4: reusable VPC ─────────────────────────→ Project 8 Fargate
Project 5: Lambda API ──────────────────────────→ Project 10 monitoring
Project 6: task table
Project 7: small independent infrastructure exercise
```

Projects 2, 4, and 5 are reused later. Keep them only as long as needed, and delete consumers before their dependencies. Each project identifies what can be removed immediately and what should wait.

# Project 01. Secure your AWS environment

## What you will build

Protect the root identity, establish a short-lived learning/deployment identity, test an explicit allow and deny, inspect CloudTrail activity, and configure cost notifications. An optional trail stores ongoing management-event records in a private bucket.

```text
Person → MFA/federation → scoped role → AWS actions
                              ↓             ↓
                         permissions     audit evidence
Account spending → budget threshold → selected email
```

Root is the account’s privileged ownership identity. Use it only for tasks that require it, not daily project work. IAM users are durable account identities; roles are assumed for sessions, while role permissions and trust are separate policies. MFA adds another factor but does not make every attack impossible; protect recovery channels and prefer phishing-resistant methods where supported.

## Step 1. Protect access

1. Sign in through the account’s approved ownership process.
2. Protect the root email and recovery information; enable root MFA and securely maintain recovery options.
3. Avoid root access keys. Review existing keys and remove unused credentials through the account’s approved process.
4. Establish Identity Center/federation for regular work. If an IAM user is necessary, use an individually assigned identity, MFA, and scoped permissions.
5. Authenticate your approved project deployer and verify the expected account with `lab.py identity`.

A permissions boundary limits maximum identity permissions; it does not itself grant access. Temporary credentials expire, which reduces persistence but does not make broad permissions harmless.

## Step 2. Build the permission exercise and budget

Find the IAM role ARN corresponding to your approved source identity in the IAM console. An STS assumed-role session ARN is not the same as the underlying IAM role ARN.

```bash
export LAB_PRINCIPAL_ARN='arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_APPROVED_ROLE'
export ALERT_EMAIL='YOUR_EMAIL_ADDRESS'
python3 scripts/lab.py validate 01
python3 scripts/lab.py deploy 01 \
  --param "LabPrincipalArn=$LAB_PRINCIPAL_ARN" \
  --param "AlertEmail=$ALERT_EMAIL" \
  --param BudgetAmount=10
```

Review the change set, then repeat with `--execute`. The amount is a chosen monthly practice budget in USD, not an estimate of project cost. Change it to your approved limit. The template creates actual-spend notifications at 80% and 100%. Confirm the email destination and review the budget in the billing console.

The exercise role allows `s3:ListAllMyBuckets` and explicitly denies `ec2:DescribeInstances`. It intentionally cannot deploy projects. The source identity must also be permitted to assume that exact role. Use `policies/assume-exercise.template.json` with the returned role ARN if the administrator needs a narrowly scoped identity policy.

```bash
python3 scripts/lab.py output 01 ExerciseRoleArn
python3 scripts/permission_test.py
```

Expected: S3 listing allowed, EC2 describe denied. The test uses a short-lived role session in memory and does not print or save its credentials. An account-wide restriction may also block the allowed read; distinguish that from a successful exercise result.

## Step 3. Inspect CloudTrail

Open CloudTrail Event history in the relevant region. Find recent role/API activity, inspect event time, event name, identity/session, source, and any error code. Event delivery can be delayed. Event history and a configured trail are different: a trail supports ongoing delivery to storage; not every data-plane event is enabled by default.

For durable audit practice, update project 1 with `EnableTrail=true` only after checking existing account trails and delivery costs:

```bash
python3 scripts/lab.py deploy 01 \
  --param "LabPrincipalArn=$LAB_PRINCIPAL_ARN" \
  --param "AlertEmail=$ALERT_EMAIL" \
  --param BudgetAmount=10 --param EnableTrail=true
```

Review and execute when appropriate. The optional multi-region trail writes to a private versioned bucket and includes delivery-integrity validation. It does not automatically enable every S3 object or DynamoDB item data event. Avoid creating a duplicate trail merely because event history already works.

## Troubleshoot and verify

- `AssumeRole` denied: check both source identity permissions and target trust.
- S3 listing denied unexpectedly: check SCPs, session/boundary restrictions, and the role actually assumed.
- EC2 request fails for an unrelated reason: check credentials, region, and connectivity; only a permission denial satisfies the exercise.
- No event visible yet: check time window, region, event category, delivery delay, and the right session identity.
- No budget email: a configured budget has not necessarily crossed its threshold; inspect configuration and delivery route instead of spending money to force a test.

**Checkpoint:** Explain root, IAM user, role, trust policy, permission policy, boundary, MFA, temporary session, audit event, and budget notification.

**Cleanup:** Remove only the practice role and budget if no longer needed. Preserve the account’s MFA, federation, recovery controls, and required audit trail. If deleting the optional practice trail, stop its logging before emptying its stack-owned bucket. The final cleanup section includes the exact order.

# Project 02. Host a static website on AWS

## Architecture and concepts

```text
Browser --HTTPS--> CloudFront --signed origin request--> private S3 bucket
```

S3 stores objects identified by keys. CloudFront serves and caches content at edge locations. Origin Access Control signs CloudFront’s origin requests, while a bucket policy permits only the intended distribution to retrieve the website objects.

Use an S3 bucket REST origin, not an S3 website endpoint, for OAC. Keep Block Public Access enabled and use bucket-owner-enforced ownership. The [CloudFront private-origin guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html) explains these requirements.

## Step 1. Inspect and validate the website

The `site/` directory includes `index.html`, `about.html`, and `style.css`. Its links are relative and can be checked without AWS:

```bash
python3 scripts/check_site.py
python3 scripts/lab.py validate 02
python3 scripts/lab.py deploy 02
```

Review the private bucket, OAC, scoped bucket policy, cache policy, and distribution; then deploy:

```bash
python3 scripts/lab.py deploy 02 --execute
export SITE_BUCKET=$(python3 scripts/lab.py output 02 BucketName)
export DISTRIBUTION_ID=$(python3 scripts/lab.py output 02 DistributionId)
export SITE_URL=$(python3 scripts/lab.py output 02 SiteUrl)
aws s3 sync site/ "s3://$SITE_BUCKET/" --cache-control 'public,max-age=60'
```

The objects are publicly viewable through CloudFront, but the origin bucket remains private. The template uses a limited CloudFront price class; review edge coverage and pricing before selecting a different class for a worldwide production audience. The `public` cache directive describes caching eligibility; it does not change S3 object permissions.

## Step 2. Test delivery and origin privacy

```bash
curl --fail --silent --show-error "$SITE_URL/"
curl -I "$SITE_URL/about.html"
curl -I "$SITE_URL/style.css"
curl -I "https://$SITE_BUCKET.s3.$AWS_REGION.amazonaws.com/index.html"
```

Expect the Veriqta website through CloudFront and denied anonymous direct S3 access. Your signed `aws s3 cp` command may work because your authenticated identity is authorized; that does not prove anonymous access is enabled.

A successful root page is not enough: verify the second page and stylesheet, check browser network requests, and confirm the bucket’s public-access settings and distribution-scoped policy.

## Step 3. Update and invalidate selected paths

Edit website text, run the local check again, and upload the intended files. Refresh cached objects when needed:

```bash
aws s3 sync site/ "s3://$SITE_BUCKET/" --cache-control 'public,max-age=60'
VERIQTA_INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths '/' '/index.html' '/about.html' '/style.css' \
  --query 'Invalidation.Id' --output text)
aws cloudfront wait invalidation-completed \
  --distribution-id "$DISTRIBUTION_ID" --id "$VERIQTA_INVALIDATION_ID"
```

Invalidation affects edge caches; browsers can still cache according to response headers. Versioned asset filenames are useful for larger sites. Avoid repeated broad invalidations when selected paths or versioned assets suffice.

## Troubleshoot a 403, missing file, or stale page

| Symptom | Checks |
| --- | --- |
| CloudFront 403 | OAC attached, signing enabled, correct bucket origin and distribution ARN, object key exists |
| Anonymous S3 denied | Expected for the private origin |
| Missing page | Exact key, filename case, upload directory, URL path |
| Root fails but `/index.html` works | Default root object configuration |
| Old content | Object version uploaded, cache headers, invalidation status, browser cache |

A missing object can appear as 403 when S3 does not allow the caller to list the bucket; do not assume every missing-file response must be 404. Opening the bucket publicly is not the fix for a broken OAC policy. Block Public Access being enabled is intentional.

**Checkpoint:** Explain why a public website can use a private bucket and why an authorized CLI read differs from an anonymous browser read.

**Cleanup:** Keep this project for project 9, or stop all deployers, empty its object versions/delete markers with the helper, and delete stack 02. Distribution removal can take time. Do not delete a bucket that belongs to another project.

# Project 03. Deploy a Linux web server

## What you will build

A small Amazon Linux 2023 instance runs NGINX in a dedicated public subnet. Session Manager provides administrative access without opening SSH. HTTP ingress is limited to the public client CIDR you choose.

```text
Your client --HTTP:80--> security group --> NGINX on EC2
Administrator --Session Manager service--> SSM Agent using instance role
```

A public subnet needs an internet-gateway route; the instance also needs an appropriate address and security rules. A public IP alone does not establish a working route or listener.

## Step 1. Select access and deploy

Find your client’s actual public IPv4 address. Running the following from your own terminal can retrieve it; inspect the result before using it:

```bash
export CLIENT_CIDR="$(curl --fail --silent --show-error https://checkip.amazonaws.com)/32"
printf '%s\n' "$CLIENT_CIDR"
python3 scripts/lab.py validate 03
python3 scripts/lab.py deploy 03 --param "ClientCidr=$CLIENT_CIDR"
```

Review and deploy:

```bash
python3 scripts/lab.py deploy 03 --param "ClientCidr=$CLIENT_CIDR" --execute
export WEB_INSTANCE_ID=$(python3 scripts/lab.py output 03 InstanceId)
export WEB_PUBLIC_IP=$(python3 scripts/lab.py output 03 PublicIp)
```

The template resolves the regional Amazon Linux x86 AMI through a public Systems Manager parameter. Its instance type defaults to `t3.micro`; inspect availability, account restrictions, and pricing first. IMDSv2 is required, the root EBS volume is encrypted, and termination removes that volume. A user-data script installs NGINX, writes a Veriqta page, and enables the service.

CloudFormation creating the instance does not prove its user-data installation has completed. Wait for instance checks, then inspect the service if HTTP is not ready.

## Step 2. Connect through Session Manager

In EC2, select the instance, choose Connect, and use Session Manager after the node becomes managed. The attached instance role includes `AmazonSSMManagedInstanceCore`; your operator also needs session permissions.

Resolving the public AMI parameter also requires the deployer’s appropriate Systems Manager parameter-read permission.

The SSM Agent initiates HTTPS connections. It needs working DNS and outbound access to its service endpoints through internet/NAT connectivity or configured private endpoints; an IAM role alone is insufficient. See [Systems Manager endpoint requirements](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html).

Run these **inside the EC2 session**:

```bash
sudo systemctl status nginx --no-pager
sudo nginx -t
curl -i http://127.0.0.1/
sudo journalctl -u nginx -n 30 --no-pager
sudo tail -n 30 /var/log/cloud-init-output.log
sudo ss -ltnp
```

The user-data installation uses:

```bash
sudo dnf install -y nginx
sudo systemctl enable --now nginx
```

`dnf update` upgrades installed packages; it is separate from installing NGINX. Plan host updates deliberately rather than hiding a broad upgrade inside every troubleshooting step.

## Step 3. Test from your client

Back in the **local project terminal**:

```bash
curl -i --connect-timeout 5 --max-time 10 "http://$WEB_PUBLIC_IP/"
```

Expect HTTP 200 and `Hello from Veriqta on EC2`. This is an HTTP learning endpoint, not a production HTTPS deployment. A public production service generally needs the appropriate load-balancer/TLS architecture and ingress policy.

## Optional SSH fallback

Session Manager is the default path and needs no inbound SSH rule. If you intentionally practice SSH, create a dedicated EC2 key pair in the selected region using **EC2 → Key pairs → Create key pair**, choose a compatible key format such as PEM, and store the downloaded private key outside the project. Restrict its local permissions to the owner.

Update only this lab stack with the actual key-pair name and your narrow client CIDR:

```bash
python3 scripts/lab.py deploy 03 --param "ClientCidr=$CLIENT_CIDR" \
  --param EnableSsh=true --param KeyName=YOUR_EXISTING_REGIONAL_KEY_NAME
```

Review and repeat with `--execute`. Adding/changing a key pair can replace this disposable instance, so inspect the change set and retrieve the current address before connecting:

```bash
export WEB_PUBLIC_IP=$(python3 scripts/lab.py output 03 PublicIp)
chmod 600 /ABSOLUTE/PRIVATE/PATH/veriqta-project03.pem
ssh -i /ABSOLUTE/PRIVATE/PATH/veriqta-project03.pem "ec2-user@$WEB_PUBLIC_IP"
```

Replace the key path and regional key-pair name with your own. Never open SSH to `0.0.0.0/0`; the optional template rule rejects that broad source. If your internet address changes, update the intended client CIDR rather than broadening it. Disable SSH again with `EnableSsh=false` when finished. The independently created key pair/private key is not owned by CloudFormation; remove it when no longer needed after confirming it is dedicated to this exercise.

## Diagnose a failed web server

- Local EC2 `curl` fails: inspect NGINX process, configuration, listener, files, and installation output.
- Local EC2 `curl` succeeds but your client times out: inspect client CIDR, security group, public IP, subnet route, gateway attachment, and any custom network ACL.
- NGINX 403: inspect document root, index configuration, and file permissions; it is not automatically an S3 policy problem.
- NGINX 502: inspect the configured upstream if you added reverse proxying. The static NGINX configuration in this project has no application upstream.
- Session Manager unavailable: check node state, agent, role, operator session permission, DNS, and outbound HTTPS.

For a controlled exercise, stop NGINX in the instance session, observe the failed request, and restore it with `sudo systemctl start nginx`. Verify the external response afterward. Do not widen unrelated rules to bypass an application failure.

**Cleanup:** Delete stack 03 after the exercise. Verify the instance terminated, its lab EBS volume was removed, and no manually allocated addresses or extra resources remain. Stopping a VM is not equivalent to removing all billable storage and address resources.

# Project 04. Build your first VPC network

## Plan the topology

A VPC is a regional network. A subnet belongs to one Availability Zone. CIDR blocks must fit within the VPC and avoid overlap with other subnets and any networks you intend to connect.

| Resource | CIDR | Placement |
| --- | --- | --- |
| VPC | `10.0.0.0/16` | Selected region |
| Public subnet 1 | `10.0.1.0/24` | First available AZ |
| Public subnet 2 | `10.0.2.0/24` | Second available AZ |
| Private subnet 1 | `10.0.3.0/24` | First available AZ |
| Private subnet 2 | `10.0.4.0/24` | Second available AZ |

A `/16` contains 65,536 IPv4 addresses mathematically. AWS reserves addresses within each subnet, so usable host capacity is smaller than the raw subnet size.

```text
VPC
├── Public AZ 1 ─┐
├── Public AZ 2 ─┴─ public route table ── Internet Gateway
├── Private AZ 1 ┐
└── Private AZ 2 ┴─ private route table ── local routes only by default
```

Private subnets are suitable for internal application servers and database placement, such as RDS database subnets. A database subnet group, its security groups, availability configuration, and actual database are additional resources; creating subnets alone does not create a database.

The internet gateway attaches to the VPC, not an individual subnet. Public subnets have a route to it; private subnets do not have that direct route. A private IPv4 instance can reach selected AWS services through VPC endpoints or general outbound internet through an appropriate NAT path.

## Step 1. Create the network without compute

```bash
python3 scripts/lab.py validate 04
python3 scripts/lab.py deploy 04
python3 scripts/lab.py deploy 04 --execute
export LAB_VPC_ID=$(python3 scripts/lab.py output 04 VpcId)
export LAB_PUBLIC_SUBNET=$(python3 scripts/lab.py output 04 PublicSubnet1)
export LAB_PRIVATE_SUBNET=$(python3 scripts/lab.py output 04 PrivateSubnet1)
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$LAB_VPC_ID"
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$LAB_VPC_ID"
```

Verify both public associations, both private associations, the public default route, and the absence of a private internet default route. Default/local VPC routes support internal routing; security groups and network ACLs still govern permitted traffic.

## Step 2. Add managed test nodes and private SSM connectivity

Private Session Manager access needs service connectivity. This optional update creates public/private test instances and private Systems Manager endpoints; interface endpoints can incur charges in each enabled zone.

```bash
python3 scripts/lab.py deploy 04 \
  --param CreateTestNodes=true --param EnablePrivateSsm=true
python3 scripts/lab.py deploy 04 \
  --param CreateTestNodes=true --param EnablePrivateSsm=true --execute
export PUBLIC_TEST_ID=$(python3 scripts/lab.py output 04 PublicTestId)
export PRIVATE_TEST_ID=$(python3 scripts/lab.py output 04 PrivateTestId)
```

The template creates `ssm` and `ssmmessages` interface endpoints with private DNS and HTTPS ingress from the test-node security group, plus an S3 gateway endpoint on the private route table. It uses current Amazon Linux/SSM behavior; check additional endpoint requirements for your selected agent, region, and optional features.

Connect to both test nodes with Session Manager. Confirm the private node has no public address. Run the following **inside each node’s session**:

```bash
ip route
getent hosts ssm.us-east-1.amazonaws.com
curl -I --connect-timeout 3 --max-time 10 https://aws.amazon.com/
```

Replace the endpoint region in the DNS check if you selected another region. The public node should have its internet path. With no NAT, the private node’s general internet request is expected to fail, even though its approved SSM private connection works. DNS resolution alone does not prove the TCP/TLS request path works. A failed ping also does not prove every application protocol is blocked.

## Step 3. Compare outbound options

| Option | Provides | Operational considerations |
| --- | --- | --- |
| NAT gateway | Outbound IPv4 internet connectivity for private workloads | Service/data/public-address charges; zone design matters |
| NAT instance | Self-managed network translation | Patching, routing, forwarding, source/destination checks, capacity and failover are your responsibility |
| Gateway endpoint | Private route to supported services such as S3/DynamoDB | Service-specific connectivity, endpoint policies and route associations |
| Interface endpoint | Private service addresses through PrivateLink | DNS, security groups, per-zone/service availability and charges |

The template can add a **single-AZ learning NAT gateway**:

```bash
python3 scripts/lab.py deploy 04 \
  --param CreateTestNodes=true --param EnablePrivateSsm=true \
  --param EnableNatGateway=true
```

Review the additional address, NAT gateway, and private default route before executing. Repeat with `--execute` only when you need that experiment. Test the private internet request again. A single NAT gateway is not a multi-zone resilient egress design; cross-zone routing and failure behavior require deliberate planning.

Remove the learning NAT promptly when finished by updating with `EnableNatGateway=false`. Keep other enabled parameters explicit so an update does not unintentionally change the rest of the exercise.

## Diagnose connectivity failures

Check the route table actually associated with the subnet, destination route and target state, public-address assignment, gateway attachment, security-group ingress/egress, network ACL return traffic, DNS, and the application listener. Security groups are stateful; network ACLs are stateless and can require return/ephemeral-port rules when customized.

A private subnet can be intentionally unable to reach the general internet. Do not “fix” that by directly attaching an internet-gateway route while still claiming the subnet is private. Check whether the task needs a specific endpoint, a NAT path, or no external access at all.

**Checkpoint:** Explain why the private node can be managed through SSM while its general internet curl fails.

**Cleanup:** Keep the VPC and public subnet for project 8 if needed. To reduce interim costs, remove optional nodes/endpoints/NAT through a reviewed update, while leaving the base network. Delete project 8 before deleting this network stack, and verify manually attached interfaces/resources are not blocking deletion.

# Project 05. Build a serverless API

## Architecture

```text
Client --HTTPS GET /--> API Gateway HTTP API --> Lambda Python function
                                    ↓                    ↓
                              access log            execution log
```

API Gateway supplies the HTTP front door and route. Lambda runs the function under an execution role. The function returns a proxy response whose `body` is a JSON string. API Gateway’s invocation permission and the Lambda role’s logging permissions serve different purposes.

This learning endpoint is public and returns a fixed non-sensitive response. It has no user authentication or database mutations. Add appropriate authentication and authorization before extending it to private data or privileged operations.

## Step 1. Read and test the function

Read `code/lambda_function.py`. It returns a message, method, actual UTC timestamp, and Lambda request ID. The request ID is an identifier, not the time of execution.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/lab.py validate 05
python3 scripts/lab.py deploy 05
python3 scripts/lab.py deploy 05 --execute
export API_URL=$(python3 scripts/lab.py output 05 ApiUrl)
export API_FUNCTION=$(python3 scripts/lab.py output 05 FunctionName)
export API_FUNCTION_LOG=$(python3 scripts/lab.py output 05 FunctionLogGroup)
export API_ACCESS_LOG=$(python3 scripts/lab.py output 05 ApiLogGroup)
```

The template uses a Python 3.12 inline Lambda package, so CloudFormation’s generated module is `index` and the handler is `index.lambda_handler`. A manually uploaded ZIP using `lambda_function.py` would instead need the corresponding `lambda_function.lambda_handler` setting.

The HTTP API defines `GET /`, a `$default` auto-deployed stage, a small route throttle, and separate access/execution log groups with seven-day retention. No arbitrary method or catch-all write route is added.

## Step 2. Verify responses and route behavior

```bash
curl -i "$API_URL/"
curl -i "$API_URL/missing"
curl -i -X POST "$API_URL/"
aws logs tail "$API_FUNCTION_LOG" --since 10m
aws logs tail "$API_ACCESS_LOG" --since 10m
```

Expect a 200 JSON response for `GET /`. Missing routes/methods should not call a route you never configured; a route-not-found response is different from a Lambda application failure.

The execution log includes a structured completion with request ID and status. It deliberately omits credentials and request bodies. The API access log can expose integration errors needed to diagnose invocation problems.

## Step 3. Debug a failing API

| Symptom | Evidence to inspect |
| --- | --- |
| 400 | Request format, validation, required headers/parameters |
| 401/403 | Actual configured authentication/authorization layer and resource policy |
| 404 | Exact route, method, stage, custom-domain mapping |
| 429 | API throttling and Lambda/account concurrency |
| 500/502 | Integration permission, handler exception, malformed proxy response, access-log integration error |
| 504 | Integration timeout and function duration |
| Browser-only CORS failure | Browser origin/method/headers and API CORS configuration |

A missing API Gateway permission to invoke Lambda commonly surfaces as an integration/internal error, not necessarily as an end-user 403. Use [HTTP API Lambda integration diagnostics](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-troubleshooting-lambda.html) and the actual log evidence.

The demonstration function can intentionally throw when its protected `LAB_FAIL` environment setting is true. Use that controlled failure in project 10 rather than accepting a public request parameter that any caller could use to crash it.

Browser CORS restrictions do not apply to curl in the same way, and CORS is not authentication. If you create a separate browser client, configure its exact allowed origins and request needs rather than enabling every origin as a substitute for authorization.

**Checkpoint:** Distinguish a route failure, invocation-permission failure, function exception, returned HTTP error, and browser CORS failure.

**Cleanup:** Keep stack 05 for project 10 or delete it and its owned log groups after saving any required evidence.

# Project 06. Create a cloud database

## Table design

DynamoDB stores items with typed attributes. This project uses a simple primary key consisting of the string partition key `taskId`. A table with a composite primary key identifies items using the partition **and** sort key together; a partition key alone is not universally unique in every table design.

| Attribute | Type | Purpose |
| --- | --- | --- |
| `taskId` | String, partition key | Unique task identity in this table |
| `title` | String | Task description |
| `status` | String | `todo`, `in-progress`, or `done` |
| `createdAt` | String | UTC creation timestamp |

Choose access patterns before adding indexes. `GetItem` is the simplest known-key read. `Query` uses key conditions; `Scan` evaluates table/index items and filters afterward. Filters do not turn a broad scan into a cheap keyed lookup.

## Step 1. Create the table and prepare a scoped policy

```bash
python3 scripts/lab.py validate 06
python3 scripts/lab.py deploy 06
python3 scripts/lab.py deploy 06 --execute
export TASK_TABLE=$(python3 scripts/lab.py output 06 TableName)
export TASK_TABLE_ARN=$(python3 scripts/lab.py output 06 TableArn)
python3 scripts/render_task_policy.py "$TASK_TABLE_ARN" > build/task-policy.json
cat build/task-policy.json
```

The table uses on-demand billing and an automatically generated name. Have the administrator attach the rendered policy to a separate intended data-access role if practicing least-privilege access. It grants the table operations used here on this exact table; it does not grant full DynamoDB access across the account.

## Step 2. Create two tasks without overwriting existing items

```bash
aws dynamodb put-item --table-name "$TASK_TABLE" \
  --item file://code/task-one.json \
  --condition-expression 'attribute_not_exists(taskId)'
aws dynamodb put-item --table-name "$TASK_TABLE" \
  --item file://code/task-two.json \
  --condition-expression 'attribute_not_exists(taskId)'
```

`S` in the low-level CLI JSON denotes a string attribute. Repeating a conditional create for an existing key should fail with `ConditionalCheckFailedException`; that protects against accidental overwrite. An unconditional `PutItem` can replace an existing item with the same key.

## Step 3. Read, query, and inspect a missing key

```bash
aws dynamodb get-item --table-name "$TASK_TABLE" \
  --key '{"taskId":{"S":"1"}}' --consistent-read
aws dynamodb get-item --table-name "$TASK_TABLE" \
  --key '{"taskId":{"S":"missing"}}' --consistent-read
aws dynamodb query --table-name "$TASK_TABLE" \
  --key-condition-expression 'taskId = :id' \
  --expression-attribute-values '{":id":{"S":"1"}}' --consistent-read
aws dynamodb scan --table-name "$TASK_TABLE" --max-items 20
```

A missing `GetItem` normally has no `Item` member, rather than returning a service error or an explicit `"Item": null`. Strongly consistent reads help verify a just-completed write on this table. Eventual-consistency behavior and index support differ across read paths.

The scan is a small-table inspection exercise and has a client item limit. Follow pagination when appropriate; do not treat one limited response as a full export or consistent backup.

## Step 4. Update one attribute and delete a task

```bash
aws dynamodb update-item --table-name "$TASK_TABLE" \
  --key '{"taskId":{"S":"1"}}' \
  --update-expression 'SET #s = :value' \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{":value":{"S":"done"}}' \
  --condition-expression 'attribute_exists(taskId)' \
  --return-values ALL_NEW
aws dynamodb delete-item --table-name "$TASK_TABLE" \
  --key '{"taskId":{"S":"2"}}' \
  --condition-expression 'attribute_exists(taskId)'
```

The existence condition prevents `UpdateItem` from accidentally creating a partial new item. Expression aliases also handle reserved attribute names. Re-read task 1 and verify its title remains while status changes.

## Diagnose missing data and denied operations

Check account, region, table name, key spelling and type, whether the write succeeded, and consistency expectations. For denials, identify the exact operation and table/index ARN. A missing key is not an authorization failure, and a conditional conflict is not an unavailable database.

Use the console’s item explorer to compare the same table and key. For important data, configure the appropriate backup/PITR/export strategy and test recovery before deletion; a console screenshot is not a backup.

**Cleanup:** Save any needed practice evidence, then delete stack 06. Table deletion removes its items. The learning table is independent of the fixed-response API and does not need to remain for later projects.

# Project 07. Automate infrastructure deployment

## What infrastructure as code adds

CloudFormation describes resources, relationships, parameters, outputs, and lifecycle behavior in YAML or JSON. A stack groups that deployment’s resources. Version-controlled templates make changes reviewable, but account permissions, quotas, existing names, and service behavior still affect execution.

This project creates an empty private S3 bucket with Veriqta/Practice tags. It has no globally hardcoded bucket name, avoiding unnecessary naming collisions. The equivalent JSON and YAML templates are both included.

## Step 1. Read and validate the YAML

```bash
cat infra/07-infrastructure.yaml
aws cloudformation validate-template --template-body file://infra/07-infrastructure.yaml
python3 scripts/lab.py validate 07
```

The YAML uses spaces for nesting and explicit resource properties. CloudFormation intrinsics such as `Ref`, `Fn::GetAtt`, and `Fn::Sub` are evaluated by CloudFormation; generic YAML parsing alone cannot validate their AWS semantics.

## Step 2. Review and deploy

```bash
python3 scripts/lab.py deploy 07
python3 scripts/lab.py deploy 07 --execute
export IAC_BUCKET=$(python3 scripts/lab.py output 07 BucketName)
aws cloudformation describe-stack-resources --stack-name veriqta-project-07
aws cloudformation describe-stack-events --stack-name veriqta-project-07
aws s3api get-bucket-tagging --bucket "$IAC_BUCKET"
```

Expected: bucket resource `CREATE_COMPLETE`, stack complete, and the intended tags. The helper selects the equivalent JSON template; the YAML can also be deployed directly using the same resource definition.

This stack creates no IAM resource, so it does not require a named-IAM capability. The helper uses a common `CAPABILITY_IAM` acknowledgement because several other project templates create generated-name roles; that flag does not supply permissions or turn this bucket into an IAM resource.

## Step 3. Understand updates and retention

Review a change set before changing properties. It can identify additions, removals, modifications, and replacements. Replacement can create a new resource and remove an old one; a familiar logical ID does not guarantee the physical resource stays the same.

- `DeletionPolicy` controls what happens to a resource when removed/deleted through the stack lifecycle.
- `UpdateReplacePolicy` concerns the old physical resource during replacement.
- `UpdatePolicy` configures supported update behaviors for specific resource types; it is not a universal retention switch.

A retained bucket or snapshot remains outside the deleted stack’s managed lifecycle and may remain billable. Record its owner and later cleanup explicitly. This simple empty-bucket template uses normal deletion behavior for the practice exercise.

## Diagnose deployment and rollback failures

Find the failed logical resource and read `ResourceStatusReason`; a stack-level rollback message often only summarizes the underlying failure. Check permissions, property values, name conflicts, service limits, region availability, and resource dependencies.

`validate-template` passing does not prove a resource can be created. `ROLLBACK_COMPLETE` after an unsuccessful initial create often requires deleting and recreating that failed stack. `UPDATE_ROLLBACK_FAILED` needs investigation and a supported recovery procedure; do not skip resources blindly just to obtain a green status.

**Controlled practice:** Break a copy of the template’s JSON/YAML syntax locally and observe validation failure, then restore it. Do not break an unrelated live stack to generate a screenshot.

**Cleanup:** The bucket is empty unless you uploaded files. Preview stack deletion, empty only its owned bucket if necessary, delete stack 07, and verify completion and any intentionally retained resources.

# Project 08. Deploy a containerized application

## Architecture and identities

```text
Local build → private ECR repository → Fargate task in the project-4 VPC
                                            ↓
                                 CloudWatch container logs
Client --HTTP:5000 from selected CIDR--> task network interface
```

An image packages application dependencies and startup instructions. ECS manages task definitions and tasks; Fargate provides their compute without you managing EC2 container hosts. The task definition describes CPU, memory, image, ports, logs, roles, and health check.

The execution role is used by the ECS/Fargate agent to pull the selected image and deliver logs. The task role grants application AWS access. This demonstration application needs none, so its task role has no application permissions. See the [ECS execution-role guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html).

## Step 1. Build and test locally

The Flask routes use a small response module; Gunicorn serves them inside a Python 3.12 container under a non-root UID.

```bash
docker version
docker build --platform linux/amd64 -t veriqta-app:v1 container
docker run -d --name veriqta-local -p 127.0.0.1:5000:5000 veriqta-app:v1
curl --fail --silent --show-error http://127.0.0.1:5000/
curl --fail --silent --show-error http://127.0.0.1:5000/health
docker logs veriqta-local
docker rm -f veriqta-local
```

Expected root response includes `Hello from Veriqta on AWS`; `/health` returns `status: ok`. The build targets x86-64 to match the Fargate task. On an ARM development machine, the builder may use emulation; do not push an incompatible architecture and expect it to run on an x86 task.

Resolve/review dependency versions for reproducible team releases, and use reviewed image digests/action commits when adopting an immutable release policy. A version range or mutable base-image tag is not a full lock.

## Step 2. Create ECR and push an immutable release tag

```bash
python3 scripts/lab.py deploy 08-registry
python3 scripts/lab.py deploy 08-registry --execute
export ECR_REPOSITORY=$(python3 scripts/lab.py output 08-registry RepositoryName)
export ECR_URI=$(python3 scripts/lab.py output 08-registry RepositoryUri)
export ECR_ARN=$(python3 scripts/lab.py output 08-registry RepositoryArn)
export ECR_HOST="${ECR_URI%%/*}"
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_HOST"
docker tag veriqta-app:v1 "$ECR_URI:v1"
docker push "$ECR_URI:v1"
aws ecr describe-images --repository-name "$ECR_REPOSITORY" --image-ids imageTag=v1
```

The repository uses immutable tags and scan-on-push configuration. Rebuilding and pushing a different image to `v1` should not silently overwrite that release. Use a new tag for a new build. Scan coverage/findings depend on the registry configuration; review results rather than treating scanning as proof an image is safe.

## Step 3. Deploy the Fargate service

Use the VPC and public subnet created in project 4. Optional test EC2 instances, private endpoints, and NAT are not required for this public-subnet Fargate exercise.

```bash
export LAB_VPC_ID=$(python3 scripts/lab.py output 04 VpcId)
export LAB_PUBLIC_SUBNET=$(python3 scripts/lab.py output 04 PublicSubnet1)
python3 scripts/lab.py deploy 08 \
  --param "VpcId=$LAB_VPC_ID" --param "SubnetId=$LAB_PUBLIC_SUBNET" \
  --param "ClientCidr=$CLIENT_CIDR" --param "ImageUri=$ECR_URI:v1" \
  --param "RepositoryArn=$ECR_ARN"
```

Review, then repeat with `--execute`. If you opened a new terminal, restore the exported values from outputs, including your intended client CIDR.

The task has 0.25 vCPU, 512 MiB memory, a container port of 5000, an internal health check, and a public address for this limited-access test. Its security group allows port 5000 only from your chosen client range. The service maintains one task and uses a deployment circuit breaker.

The subnet’s internet route, task public address, DNS, and outbound permissions allow ECR/image-layer and CloudWatch access. In a private-subnet deployment, supply NAT or the necessary ECR/logs interface endpoints and S3 layer-access path; an execution role alone cannot create network reachability.

## Step 4. Verify the running application

```bash
export ECS_CLUSTER=$(python3 scripts/lab.py output 08 ClusterName)
export ECS_SERVICE=$(python3 scripts/lab.py output 08 ServiceName)
export ECS_LOG_GROUP=$(python3 scripts/lab.py output 08 LogGroup)
aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE"
export TASK_PUBLIC_IP=$(python3 scripts/lab.py task-ip 08)
curl -i --connect-timeout 5 --max-time 10 "http://$TASK_PUBLIC_IP:5000/"
aws logs tail "$ECS_LOG_GROUP" --since 10m
```

Verify task state and health plus the actual HTTP result. A replacement task may have a different public address. A stable public service generally needs a load balancer, TLS, appropriate ingress, and a multi-zone deployment; this exercise’s direct IP is temporary.

## Diagnose a container that will not start

Inspect service events and stopped tasks, not only currently running tasks:

```bash
aws ecs list-tasks --cluster "$ECS_CLUSTER" --desired-status STOPPED
aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
  --query 'services[0].events[0:10]'
```

Use a returned task ARN with `aws ecs describe-tasks` to inspect `stopCode`, `stoppedReason`, and container exit codes/reasons. Then inspect the exact container log stream.

| Symptom | Likely investigation path |
| --- | --- |
| `CannotPullContainerError` | Image URI/tag/digest, ECR permissions, network/DNS, architecture |
| `ResourceInitializationError` | Registry/log/secrets connectivity or permissions |
| Essential container exited | Startup command, missing file, import/configuration, process exit |
| Task runs but request times out | Current task IP, client CIDR, subnet route, port binding/mapping |
| Health check fails | Exact URL/port, startup delay, dependency contract, logs |

Do not attach a broad role when the evidence points to DNS or a missing image tag. Change the controlled configuration, deploy a new task-definition revision through the stack, and verify a fresh task and real response.

**Cleanup:** Delete service stack 08 first; otherwise it will replace manually stopped tasks. Verify tasks are gone, then preview/delete the registry’s images and delete `08-registry`. Delete the project-4 network only after its dependent tasks/interfaces are removed.

# Project 09. Build an automated deployment pipeline

## What you will build

```text
Push reviewed main-branch change → local file/link checks → GitHub OIDC session
    → sync only site/ to project-2 bucket → selected cache invalidation → HTTPS verification
```

GitHub OIDC obtains short-lived AWS credentials through a trusted role. The role trust checks audience and the exact repository/main-branch subject. Its permission policy limits object operations to the website bucket and cache operations to the selected distribution.

See [GitHub’s AWS OIDC setup](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws). Authentication through OIDC does not replace scoped AWS permissions or repository protection.

## Step 1. Create your repository

Use a repository you own and place the project’s contents at its root so `.github/workflows/deploy.yml`, `site/`, and `scripts/check_site.py` are in the expected paths. Keep generated `build/`, credentials, and private evidence out of commits.

```bash
python3 scripts/check_site.py
git init -b main
git status
```

Review files before adding/committing. Configure your remote using your repository’s actual URL and push through your normal Git authentication. Do not use the Veriqta brand name as an assumed existing repository/account you do not control.

## Step 2. Establish the scoped AWS role

Check whether the account already has GitHub’s OIDC provider:

```bash
aws iam list-open-id-connect-providers
```

If it exists, use its actual ARN. A provider is shared account infrastructure; do not create a duplicate or delete an existing shared provider during cleanup.

```bash
export GITHUB_REPOSITORY='YOUR_OWNER/YOUR_REPOSITORY'
export EXISTING_OIDC_ARN=''
export SITE_BUCKET=$(python3 scripts/lab.py output 02 BucketName)
export DISTRIBUTION_ID=$(python3 scripts/lab.py output 02 DistributionId)
export SITE_URL=$(python3 scripts/lab.py output 02 SiteUrl)
python3 scripts/lab.py deploy 09 \
  --param "GitHubRepository=$GITHUB_REPOSITORY" \
  --param "SiteBucketName=$SITE_BUCKET" --param "DistributionId=$DISTRIBUTION_ID" \
  --param "ExistingProviderArn=$EXISTING_OIDC_ARN"
```

Leave the provider ARN empty only when no matching provider exists and the administrator intends this stack to create it. Review and repeat with `--execute`.

The trust subject is `repo:OWNER/REPOSITORY:ref:refs/heads/main`. A GitHub environment changes OIDC subject claims; if you add environment-based approvals, update the trust accordingly rather than widening it to every repository/branch.

## Step 3. Configure GitHub variables and run the workflow

Set repository Actions variables using the actual outputs:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | Selected region |
| `AWS_ROLE_ARN` | `lab.py output 09 RoleArn` |
| `SITE_BUCKET` | Project-2 bucket |
| `DISTRIBUTION_ID` | Project-2 distribution |
| `SITE_URL` | Project-2 HTTPS URL |

These identifiers are configuration, not long-lived AWS access keys. Do not add `AWS_ACCESS_KEY_ID` or secret keys to make OIDC work.

The supplied workflow uses the GitHub-hosted Ubuntu 24.04 image and checks the available AWS CLI before deployment. It runs on main-branch website/workflow changes or a manual dispatch on main. It requests `id-token: write`, validates local files before obtaining AWS credentials, and syncs **only `site/`**, with `--delete` scoped to this dedicated website bucket. It does not upload the entire repository or accidentally publish source/configuration files.

Make a small website change, push it to main after review, inspect the Actions run, and verify the delivered pages. The smoke checks match the sample headings; update the contract deliberately if you change those headings. Re-run local checks first:

```bash
python3 scripts/check_site.py
```

The workflow uses selected action versions documented by their maintainers. For a reviewed production workflow, pin full action commit IDs and update them through a controlled process. See [the AWS credentials action](https://github.com/aws-actions/configure-aws-credentials) for its current options and supported runtime requirements.

## Recover from a failed deployment

1. Open the failed workflow and locate the first meaningful failure.
2. If local checks failed, correct the missing file/link; no upload should have run.
3. If role assumption failed, inspect provider, role ARN, audience, and repository/branch subject.
4. If S3 sync failed, inspect bucket identity/region and object/list/delete permissions.
5. If invalidation failed, inspect distribution identity and exact CloudFront permissions.
6. If delivery verification failed, compare deployed object content, cache state, and intended page contract.

S3 sync is not an atomic multi-file deployment. A network failure can publish part of a release before the workflow fails. For larger applications use versioned assets or a release-prefix/traffic-switch design.

To recover a small practice site, create a new main-branch revert of the bad change, review it, and redeploy:

```bash
git log --oneline -n 10
git revert YOUR_BAD_COMMIT_ID
python3 scripts/check_site.py
git push origin main
```

Replace the placeholder with the identified commit. Handle merge/conflict cases deliberately. Checking out an old detached commit and pushing an unchanged branch does not roll a deployment back. Re-running an old successful workflow can also republish obsolete content, so serialize deployments and record the intended release.

After recovery, verify root page, about page, stylesheet, HTTP status, and expected content. CloudFront headers such as `x-cache` can help interpret cache behavior; they do not independently prove the correct release is served.

**Cleanup:** Disable the deployment workflow before dismantling its target. Delete project 09’s role stack, preserving a shared provider when it was reused. Delete the project-2 website only after no workflow is still uploading to it. Retain repository history as appropriate.

# Project 10. Monitor and investigate a cloud incident

## Architecture and metric meaning

```text
Project-5 Lambda failure → CloudWatch Errors alarm → SNS topic → confirmed email
             ↓
        request evidence and execution logs → diagnosis → correction → user-path verification
```

Useful Lambda metrics include invocation count, function errors, duration, throttles, and concurrent executions. Unhandled exceptions/timeouts can increment `Errors`; a function that successfully returns an HTTP 500 payload is not necessarily a Lambda invocation error. Monitor HTTP outcomes and business checks in addition to runtime metrics. See [Lambda metric definitions](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html).

## Step 1. Verify the API baseline

```bash
export API_FUNCTION=$(python3 scripts/lab.py output 05 FunctionName)
export API_URL=$(python3 scripts/lab.py output 05 ApiUrl)
export API_FUNCTION_LOG=$(python3 scripts/lab.py output 05 FunctionLogGroup)
curl --fail --silent --show-error "$API_URL/"
```

Record a successful response and request ID before creating a failure. This confirms you are monitoring the intended function/account/region.

## Step 2. Create the alarm and notification path

```bash
export ALERT_EMAIL='YOUR_EMAIL_ADDRESS'
python3 scripts/lab.py deploy 10 \
  --param "FunctionName=$API_FUNCTION" --param "AlertEmail=$ALERT_EMAIL"
python3 scripts/lab.py deploy 10 \
  --param "FunctionName=$API_FUNCTION" --param "AlertEmail=$ALERT_EMAIL" --execute
export ERROR_ALARM=$(python3 scripts/lab.py output 10 AlarmName)
export ALERT_TOPIC=$(python3 scripts/lab.py output 10 TopicArn)
aws sns list-subscriptions-by-topic --topic-arn "$ALERT_TOPIC"
```

Confirm the email subscription using the message from SNS. A `PendingConfirmation` subscription cannot be treated as a tested delivery path. The alarm watches this function’s `Errors`, Sum, a 60-second period, and at least one error in one evaluation period. Both alarm and OK transitions route to the topic. The topic policy permits CloudWatch publication from this alarm and account.

The one-error threshold is appropriate for a deliberate practice test; production alerts should reflect user impact, volume, acceptable failure rates, duration, and operator response needs. Missing metric data is treated as non-breaching here, which is not a detector for a function that never runs.

## Step 3. Trigger a controlled function failure

```bash
python3 scripts/set_failure.py --enable
curl -i "$API_URL/"
aws lambda invoke --function-name "$API_FUNCTION" \
  --cli-binary-format raw-in-base64-out \
  --payload file://code/api-event.json build/failed-invocation.json
cat build/failed-invocation.json
```

The helper changes only this handbook’s project-5 function, waits for the configuration update, and does not accept a public request flag. Expect an API 5xx and a failed Lambda invocation. A direct invoke can have an HTTP/API-level status of 200 while its metadata includes `FunctionError`; inspect that field and the response payload instead of relying solely on the CLI process exit status.

Do not repeatedly hammer the public endpoint. A small number of controlled invocations is sufficient for this exercise.

## Step 4. Observe and investigate

```bash
aws cloudwatch describe-alarms --alarm-names "$ERROR_ALARM"
aws cloudwatch describe-alarm-history --alarm-name "$ERROR_ALARM" --max-records 10
aws logs tail "$API_FUNCTION_LOG" --since 10m
```

Allow for metric evaluation and notification delay. Confirm the alarm actually transitions to ALARM and the selected recipient receives the notification. A configured topic, a pending subscription, or a screenshot of an alarm definition is not proof of delivery.

Match the controlled-failure event/request ID and RuntimeError to the test window. The initiating change was the deliberately enabled environment flag; the API 5xx and error alarm are downstream observations. In an unfamiliar incident, use code/configuration history, request logs, service state, and metrics to test competing explanations.

Metrics help identify scope and timing, logs explain recorded events, and traces can connect distributed operations when configured. Monitoring does not automatically prove correct business output or repair the system.

## Step 5. Restore and verify

```bash
python3 scripts/set_failure.py --disable
curl --fail --silent --show-error "$API_URL/"
aws lambda invoke --function-name "$API_FUNCTION" \
  --cli-binary-format raw-in-base64-out \
  --payload file://code/api-event.json build/recovered-invocation.json
cat build/recovered-invocation.json
aws cloudwatch describe-alarms --alarm-names "$ERROR_ALARM"
```

Verify repeated successful user-path responses and the absence of a new function error for the recovered calls. The alarm should return to OK after its configured evaluation; with missing data treated as non-breaching it can also return to OK when no calls arrive, so an OK state alone is insufficient recovery evidence.

Changing an environment variable manually is drift relative to the template while the exercise is active. Restoring `LAB_FAIL=false` returns the intended value. If you change the function/template permanently, reconcile the declared infrastructure as part of the change.

Complete [the incident worksheet](exercises/incident-report.md): impact, timeline, evidence, initiating change, correction, recovery verification, and a prevention action with an owner and check.

**Cleanup:** Delete monitoring stack 10 before API stack 05. The monitoring stack owns its alarm/topic/subscription; the API stack owns its API, function, roles, and log groups. Save needed investigation evidence privately before removing logs.

# Final cleanup plan

## Stop writers before deleting storage

Disable project-9 deployment automation and stop optional trail logging before emptying their buckets. The bucket helper resolves a logical resource from the selected stack and previews exactly that owned bucket. It handles object versions, delete markers, and unfinished multipart uploads rather than only deleting visible current objects.

For the website:

```bash
python3 scripts/lab.py empty-bucket 02 SiteBucket
python3 scripts/lab.py empty-bucket 02 SiteBucket --execute
```

For the optional practice CloudTrail bucket, only if you enabled it and it is not an audit resource you must retain:

```bash
aws cloudtrail stop-logging --name veriqta-project-01-trail
python3 scripts/lab.py empty-bucket 01 TrailBucket
python3 scripts/lab.py empty-bucket 01 TrailBucket --execute
```

An emptying operation is irreversible for the selected object versions. Preserve required data, stop concurrent writes, and review the preview before execution. Deleting a versioned object’s current view alone does not remove old versions or their storage usage.

## Delete consumers before dependencies

Preview a selected stack deletion without `--execute`; execute only that project when ready. For a complete run, the useful order is:

```bash
python3 scripts/lab.py delete 10 --execute
python3 scripts/lab.py delete 09 --execute
python3 scripts/lab.py delete 08 --execute
python3 scripts/lab.py empty-registry 08-registry
python3 scripts/lab.py empty-registry 08-registry --execute
python3 scripts/lab.py delete 08-registry --execute
python3 scripts/lab.py delete 04 --execute
python3 scripts/lab.py delete 03 --execute
python3 scripts/lab.py delete 06 --execute
python3 scripts/lab.py delete 07 --execute
python3 scripts/lab.py delete 05 --execute
python3 scripts/lab.py delete 02 --execute
```

Run commands only for stacks you actually created. Empty project-7 or other owned buckets first if you added objects. Review failed-delete events instead of repeatedly retrying without checking dependencies.

Delete project 01 only if its budget, practice role, and optional audit resources are no longer required. Keep account protections and shared federation/audit controls. Reused OIDC providers are outside project 09’s ownership; a provider created by that stack will be removed with it only when no other identity depends on it.

Finally inspect EC2 instances/volumes/addresses, NAT gateways, endpoints/interfaces, ECS tasks/services, ECR images, S3 versions, DynamoDB tables/backups, Lambda/APIs/logs, alarms/topics, and retained CloudFormation resources. Check all used regions and global services such as CloudFront/IAM. Billing views can lag; a deleted stack does not prove there are no manual or retained resources.

# Review questions and answers

1. **Why use a role instead of copying keys into an application?** The workload receives scoped temporary credentials through its supported identity path without embedding durable keys in source or images.
2. **Does MFA make an administrator policy least-privilege?** No. Authentication protection and action/resource authorization solve different problems.
3. **Can a budget guarantee spending stops at its amount?** No. Notifications and billing data have delays and do not form a universal immediate hard cap.
4. **Why is anonymous S3 access denied while the website works?** CloudFront’s signed origin request is permitted by the bucket policy; anonymous direct access is not.
5. **Does every missing S3 object produce 404?** No. Listing permissions and the request path can influence whether a missing key appears as access denied.
6. **Does a public subnet give every instance internet access?** No. Addressing, routes, security rules, and the application path must also be correct.
7. **Why can a private instance use SSM but not a general website?** Its service endpoints may provide specific private connectivity without a NAT/general internet route.
8. **Does a 500 response always increment Lambda Errors?** No. A successfully returned HTTP error payload differs from an unhandled function/runtime failure.
9. **Why condition an UpdateItem on key existence?** Otherwise it can create a new partial item when the key is absent.
10. **Why is a Scan filter not equivalent to Query?** A filter operates after items are evaluated; it does not provide the same keyed access pattern.
11. **Does template validation prove deployment will succeed?** No. Permissions, quotas, regional support, runtime behavior, and dependencies remain.
12. **What is the ECS execution role versus task role?** The agent uses the execution role for image/log operations; application AWS calls use the task role.
13. **Does a running ECS task prove correct user output?** No. Verify its health and actual endpoint contract as well as process state.
14. **Why restrict the OIDC subject?** It limits which repository/branch or environment can obtain the deployment role session.
15. **Why sync `site/` rather than the repository root?** Only public website assets belong in the bucket; source, infrastructure, and private files should not be published accidentally.
16. **Is S3 sync atomic across a release?** No. Partial publication is possible; larger systems need an appropriate release strategy.
17. **Does an OK alarm prove recovery?** No. Missing data or unrelated traffic can affect alarm state; verify intended user operations and matching evidence.
18. **Why delete consumers first?** Running tasks/services or active writers can keep dependencies in use, recreate work, or refill storage during deletion.

# Project completion checklist

For each project record:

- Intended account, region, owner, and approved execution identity.
- Architecture, resource IDs/outputs, and selected deployment change.
- Successful user-path result and evidence of the expected permissions.
- One controlled failure, supported diagnosis, and verified correction.
- Observed limitations, retained data, and recovery considerations.
- Cleanup result, remaining dependencies, and any intentionally retained resources.

A project is complete when you can explain its behavior, reproduce its result, diagnose a failure using evidence, and account for the resources left behind.

# Complete code and configuration

Paths are relative to the project directory. The same files are included in their corresponding folders for the follow-along exercises. Templates create real resources only when executed with an authorized AWS identity; replace account-specific placeholders before using them.

## File: `.github/workflows/deploy.yml`

```yaml
name: Veriqta website deployment
on:
  push:
    branches: [main]
    paths: ['site/**', 'scripts/check_site.py', '.github/workflows/deploy.yml']
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: veriqta-website
  cancel-in-progress: false
jobs:
  deploy:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    permissions:
      contents: read
      id-token: write
    env:
      AWS_REGION: ${{ vars.AWS_REGION }}
      SITE_BUCKET: ${{ vars.SITE_BUCKET }}
      DISTRIBUTION_ID: ${{ vars.DISTRIBUTION_ID }}
      SITE_URL: ${{ vars.SITE_URL }}
    steps:
      - uses: actions/checkout@v5
        with:
          persist-credentials: false
      - name: Check website and required configuration
        run: |
          set -euo pipefail
          python3 scripts/check_site.py
          aws --version
          test -n "$AWS_REGION"
          test -n "$SITE_BUCKET"
          test -n "$DISTRIBUTION_ID"
          test -n "$SITE_URL"
      - name: Obtain temporary AWS credentials
        uses: aws-actions/configure-aws-credentials@v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
          role-session-name: veriqta-website
      - name: Upload only the website directory
        run: |
          set -euo pipefail
          aws s3 sync site/ "s3://$SITE_BUCKET/" --delete --cache-control 'public,max-age=60'
      - name: Refresh the small website cache
        run: |
          set -euo pipefail
          INVALIDATION_ID=$(aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths '/' '/index.html' '/about.html' '/style.css' --query 'Invalidation.Id' --output text)
          aws cloudfront wait invalidation-completed --distribution-id "$DISTRIBUTION_ID" --id "$INVALIDATION_ID"
      - name: Verify delivered pages
        run: |
          set -euo pipefail
          curl --fail --silent --show-error --max-time 20 "$SITE_URL/" | grep -F 'Welcome to Veriqta on AWS'
          curl --fail --silent --show-error --max-time 20 "$SITE_URL/about.html" | grep -F 'A private origin, a public website'
```

## File: `.gitignore`

```text
build/
.venv/
__pycache__/
*.pyc
.env
*.pem
.DS_Store
```

## File: `code/api-event.json`

```json
{
  "version": "2.0",
  "rawPath": "/",
  "requestContext": {
    "http": {"method": "GET", "path": "/"}
  }
}
```

## File: `code/lambda_function.py`

```python
"""Veriqta HTTP API example. No credentials or request bodies are logged."""
from datetime import datetime,timezone
import json
import os

def lambda_handler(event,context):
    request_id=getattr(context,'aws_request_id','local-test')
    if os.getenv('LAB_FAIL','false').lower()=='true':
        print(json.dumps({'event':'controlled_failure','request_id':request_id}))
        raise RuntimeError('Veriqta controlled monitoring exercise')
    method=event.get('requestContext',{}).get('http',{}).get('method','GET')
    body={'message':'Hello from Veriqta API','method':method,'request_id':request_id,
          'timestamp':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
    print(json.dumps({'event':'request_completed','request_id':request_id,'method':method,'status':200}))
    return {'statusCode':200,'headers':{'Content-Type':'application/json'},'body':json.dumps(body)}
```

## File: `code/task-one.json`

```json
{
  "taskId": {"S": "1"},
  "title": {"S": "Learn AWS with Veriqta"},
  "status": {"S": "todo"},
  "createdAt": {"S": "2026-01-15T10:00:00Z"}
}
```

## File: `code/task-two.json`

```json
{
  "taskId": {"S": "2"},
  "title": {"S": "Build a Veriqta project"},
  "status": {"S": "in-progress"},
  "createdAt": {"S": "2026-01-15T11:00:00Z"}
}
```

## File: `container/.dockerignore`

```text
__pycache__
.venv
*.pyc
.env
.git
```

## File: `container/Dockerfile`

```text
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py app_core.py ./
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 5000
CMD ["gunicorn","--bind","0.0.0.0:5000","--workers","2","--timeout","10","--access-logfile","-","--error-logfile","-","app:app"]
```

## File: `container/app.py`

```python
from flask import Flask,jsonify
from app_core import response
app=Flask(__name__)
@app.route('/',defaults={'path':''})
@app.route('/<path:path>')
def route(path):
    body,status=response('/'+path)
    return jsonify(body),status
```

## File: `container/app_core.py`

```python
"""Response contracts shared by the container routes and offline tests."""
def response(path):
    if path=='/':return {'message':'Hello from Veriqta on AWS','status':'success'},200
    if path=='/health':return {'status':'ok'},200
    return {'error':'not_found'},404
```

## File: `container/requirements.txt`

```text
Flask>=3.1,<4
gunicorn>=23,<24
```

## File: `exercises/incident-report.md`

```markdown
# Cloud incident report

- Project, account, region, stack and affected resource:
- User-visible symptom and impact:
- Detection time, first observed failure, recovery time (UTC):
- Timeline: timestamp, event/action, evidence, interpretation:
- Root cause and contributing conditions:
- Targeted correction and deployment identity:
- Verification from the user path:
- Alarm state, notification receipt, and recovery evidence:
- Remaining unknowns:
- Prevention action, owner, due date and validation:
- Cleanup and retained-resource review:
```

## File: `exercises/resource-register.md`

```markdown
# AWS project resource register

| Project | Account | Region | Stack | Resource/output | Created UTC | Owner | Needed until | Cleanup result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |

Record current pricing/eligibility before deployment, identity used, required permissions, dependent stacks, retained objects/versions, snapshots, interfaces, public addresses, logs, and any intentionally retained audit resources. A successful stack deletion is one part of cleanup verification.
```

## File: `infra/01-security.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: account permission exercise, monthly budget and optional audit trail",
  "Parameters": {
    "LabPrincipalArn": {
      "Type": "String",
      "Description": "IAM role or user ARN allowed to assume the exercise role"
    },
    "AlertEmail": {
      "Type": "String"
    },
    "BudgetAmount": {
      "Type": "Number",
      "Default": 10,
      "MinValue": 1
    },
    "EnableTrail": {
      "Type": "String",
      "AllowedValues": [
        "true",
        "false"
      ],
      "Default": "false"
    }
  },
  "Conditions": {
    "CreateTrail": {
      "Fn::Equals": [
        {
          "Ref": "EnableTrail"
        },
        "true"
      ]
    }
  },
  "Resources": {
    "ExerciseRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "AWS": {
                  "Ref": "LabPrincipalArn"
                }
              },
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "VeriqtaPermissionExercise",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": "s3:ListAllMyBuckets",
                  "Resource": "*"
                },
                {
                  "Effect": "Deny",
                  "Action": "ec2:DescribeInstances",
                  "Resource": "*"
                }
              ]
            }
          }
        ]
      }
    },
    "Budget": {
      "Type": "AWS::Budgets::Budget",
      "Properties": {
        "Budget": {
          "BudgetName": {
            "Fn::Sub": "${AWS::StackName}-monthly"
          },
          "BudgetType": "COST",
          "TimeUnit": "MONTHLY",
          "BudgetLimit": {
            "Amount": {
              "Ref": "BudgetAmount"
            },
            "Unit": "USD"
          }
        },
        "NotificationsWithSubscribers": [
          {
            "Notification": {
              "NotificationType": "ACTUAL",
              "ComparisonOperator": "GREATER_THAN",
              "Threshold": 80,
              "ThresholdType": "PERCENTAGE"
            },
            "Subscribers": [
              {
                "SubscriptionType": "EMAIL",
                "Address": {
                  "Ref": "AlertEmail"
                }
              }
            ]
          },
          {
            "Notification": {
              "NotificationType": "ACTUAL",
              "ComparisonOperator": "GREATER_THAN",
              "Threshold": 100,
              "ThresholdType": "PERCENTAGE"
            },
            "Subscribers": [
              {
                "SubscriptionType": "EMAIL",
                "Address": {
                  "Ref": "AlertEmail"
                }
              }
            ]
          }
        ]
      }
    },
    "TrailBucket": {
      "Type": "AWS::S3::Bucket",
      "Properties": {
        "PublicAccessBlockConfiguration": {
          "BlockPublicAcls": true,
          "BlockPublicPolicy": true,
          "IgnorePublicAcls": true,
          "RestrictPublicBuckets": true
        },
        "OwnershipControls": {
          "Rules": [
            {
              "ObjectOwnership": "BucketOwnerEnforced"
            }
          ]
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
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ],
        "VersioningConfiguration": {
          "Status": "Enabled"
        }
      },
      "Condition": "CreateTrail"
    },
    "TrailBucketPolicy": {
      "Type": "AWS::S3::BucketPolicy",
      "Properties": {
        "Bucket": {
          "Ref": "TrailBucket"
        },
        "PolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "cloudtrail.amazonaws.com"
              },
              "Action": "s3:GetBucketAcl",
              "Resource": {
                "Fn::GetAtt": [
                  "TrailBucket",
                  "Arn"
                ]
              },
              "Condition": {
                "StringEquals": {
                  "aws:SourceArn": {
                    "Fn::Sub": "arn:${AWS::Partition}:cloudtrail:${AWS::Region}:${AWS::AccountId}:trail/${AWS::StackName}-trail"
                  }
                }
              }
            },
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "cloudtrail.amazonaws.com"
              },
              "Action": "s3:PutObject",
              "Resource": {
                "Fn::Sub": "${TrailBucket.Arn}/AWSLogs/${AWS::AccountId}/*"
              },
              "Condition": {
                "StringEquals": {
                  "s3:x-amz-acl": "bucket-owner-full-control",
                  "aws:SourceArn": {
                    "Fn::Sub": "arn:${AWS::Partition}:cloudtrail:${AWS::Region}:${AWS::AccountId}:trail/${AWS::StackName}-trail"
                  }
                }
              }
            }
          ]
        }
      },
      "Condition": "CreateTrail"
    },
    "Trail": {
      "Type": "AWS::CloudTrail::Trail",
      "Properties": {
        "TrailName": {
          "Fn::Sub": "${AWS::StackName}-trail"
        },
        "S3BucketName": {
          "Ref": "TrailBucket"
        },
        "IsLogging": true,
        "IsMultiRegionTrail": true,
        "IncludeGlobalServiceEvents": true,
        "EnableLogFileValidation": true
      },
      "Condition": "CreateTrail",
      "DependsOn": "TrailBucketPolicy"
    }
  },
  "Outputs": {
    "ExerciseRoleArn": {
      "Value": {
        "Fn::GetAtt": [
          "ExerciseRole",
          "Arn"
        ]
      }
    },
    "TrailBucketName": {
      "Value": {
        "Fn::If": [
          "CreateTrail",
          {
            "Ref": "TrailBucket"
          },
          "not-created"
        ]
      }
    }
  }
}
```

## File: `infra/02-website.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: private S3 website delivered by CloudFront OAC",
  "Resources": {
    "SiteBucket": {
      "Type": "AWS::S3::Bucket",
      "Properties": {
        "PublicAccessBlockConfiguration": {
          "BlockPublicAcls": true,
          "BlockPublicPolicy": true,
          "IgnorePublicAcls": true,
          "RestrictPublicBuckets": true
        },
        "OwnershipControls": {
          "Rules": [
            {
              "ObjectOwnership": "BucketOwnerEnforced"
            }
          ]
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
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ],
        "VersioningConfiguration": {
          "Status": "Enabled"
        }
      }
    },
    "Oac": {
      "Type": "AWS::CloudFront::OriginAccessControl",
      "Properties": {
        "OriginAccessControlConfig": {
          "Name": {
            "Fn::Sub": "${AWS::StackName}-oac"
          },
          "OriginAccessControlOriginType": "s3",
          "SigningBehavior": "always",
          "SigningProtocol": "sigv4"
        }
      }
    },
    "CachePolicy": {
      "Type": "AWS::CloudFront::CachePolicy",
      "Properties": {
        "CachePolicyConfig": {
          "Name": {
            "Fn::Sub": "${AWS::StackName}-cache"
          },
          "MinTTL": 0,
          "DefaultTTL": 60,
          "MaxTTL": 300,
          "ParametersInCacheKeyAndForwardedToOrigin": {
            "CookiesConfig": {
              "CookieBehavior": "none"
            },
            "HeadersConfig": {
              "HeaderBehavior": "none"
            },
            "QueryStringsConfig": {
              "QueryStringBehavior": "none"
            },
            "EnableAcceptEncodingGzip": true,
            "EnableAcceptEncodingBrotli": true
          }
        }
      }
    },
    "Distribution": {
      "Type": "AWS::CloudFront::Distribution",
      "Properties": {
        "DistributionConfig": {
          "Enabled": true,
          "DefaultRootObject": "index.html",
          "HttpVersion": "http2",
          "PriceClass": "PriceClass_100",
          "Origins": [
            {
              "Id": "private-s3",
              "DomainName": {
                "Fn::GetAtt": [
                  "SiteBucket",
                  "RegionalDomainName"
                ]
              },
              "OriginAccessControlId": {
                "Fn::GetAtt": [
                  "Oac",
                  "Id"
                ]
              },
              "S3OriginConfig": {
                "OriginAccessIdentity": ""
              }
            }
          ],
          "DefaultCacheBehavior": {
            "TargetOriginId": "private-s3",
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": [
              "GET",
              "HEAD"
            ],
            "CachedMethods": [
              "GET",
              "HEAD"
            ],
            "Compress": true,
            "CachePolicyId": {
              "Ref": "CachePolicy"
            }
          },
          "ViewerCertificate": {
            "CloudFrontDefaultCertificate": true
          }
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "SitePolicy": {
      "Type": "AWS::S3::BucketPolicy",
      "Properties": {
        "Bucket": {
          "Ref": "SiteBucket"
        },
        "PolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "cloudfront.amazonaws.com"
              },
              "Action": "s3:GetObject",
              "Resource": {
                "Fn::Sub": "${SiteBucket.Arn}/*"
              },
              "Condition": {
                "StringEquals": {
                  "AWS:SourceArn": {
                    "Fn::Sub": "arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}"
                  }
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
        "Ref": "SiteBucket"
      }
    },
    "DistributionId": {
      "Value": {
        "Ref": "Distribution"
      }
    },
    "SiteUrl": {
      "Value": {
        "Fn::Sub": "https://${Distribution.DomainName}"
      }
    }
  }
}
```

## File: `infra/03-ec2.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: Amazon Linux web server with Session Manager access",
  "Parameters": {
    "ClientCidr": {
      "Type": "String",
      "Description": "Your public IPv4 address with /32"
    },
    "AmiId": {
      "Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
      "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    },
    "InstanceType": {
      "Type": "String",
      "AllowedValues": [
        "t3.micro",
        "t3.small",
        "t3a.micro",
        "t3a.small"
      ],
      "Default": "t3.micro"
    },
    "EnableSsh": {
      "Type": "String",
      "Default": "false",
      "AllowedValues": [
        "true",
        "false"
      ]
    },
    "KeyName": {
      "Type": "String",
      "Default": "",
      "Description": "Existing regional key-pair name, required only for the optional SSH exercise"
    }
  },
  "Resources": {
    "Vpc": {
      "Type": "AWS::EC2::VPC",
      "Properties": {
        "CidrBlock": "10.0.0.0/16",
        "EnableDnsSupport": true,
        "EnableDnsHostnames": true,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Gateway": {
      "Type": "AWS::EC2::InternetGateway",
      "Properties": {
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Attachment": {
      "Type": "AWS::EC2::VPCGatewayAttachment",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "InternetGatewayId": {
          "Ref": "Gateway"
        }
      }
    },
    "PublicRoutes": {
      "Type": "AWS::EC2::RouteTable",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "InternetRoute": {
      "Type": "AWS::EC2::Route",
      "Properties": {
        "RouteTableId": {
          "Ref": "PublicRoutes"
        },
        "DestinationCidrBlock": "0.0.0.0/0",
        "GatewayId": {
          "Ref": "Gateway"
        }
      },
      "DependsOn": "Attachment"
    },
    "Public1": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "CidrBlock": "10.0.1.0/24",
        "AvailabilityZone": {
          "Fn::Select": [
            0,
            {
              "Fn::GetAZs": ""
            }
          ]
        },
        "MapPublicIpOnLaunch": true,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "PublicAssociation1": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {
          "Ref": "Public1"
        },
        "RouteTableId": {
          "Ref": "PublicRoutes"
        }
      }
    },
    "InstanceRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "ec2.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "ManagedPolicyArns": [
          {
            "Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
          }
        ]
      }
    },
    "InstanceProfile": {
      "Type": "AWS::IAM::InstanceProfile",
      "Properties": {
        "Roles": [
          {
            "Ref": "InstanceRole"
          }
        ]
      }
    },
    "WebSecurity": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "GroupDescription": "Veriqta HTTP from selected client CIDR; no SSH ingress",
        "VpcId": {
          "Ref": "Vpc"
        },
        "SecurityGroupIngress": [
          {
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "CidrIp": {
              "Ref": "ClientCidr"
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "WebInstance": {
      "Type": "AWS::EC2::Instance",
      "Properties": {
        "ImageId": {
          "Ref": "AmiId"
        },
        "InstanceType": {
          "Ref": "InstanceType"
        },
        "IamInstanceProfile": {
          "Ref": "InstanceProfile"
        },
        "SubnetId": {
          "Ref": "Public1"
        },
        "SecurityGroupIds": [
          {
            "Ref": "WebSecurity"
          }
        ],
        "MetadataOptions": {
          "HttpTokens": "required"
        },
        "BlockDeviceMappings": [
          {
            "DeviceName": "/dev/xvda",
            "Ebs": {
              "VolumeSize": 8,
              "VolumeType": "gp3",
              "Encrypted": true,
              "DeleteOnTermination": true
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ],
        "UserData": {
          "Fn::Base64": "#!/bin/bash\nset -euxo pipefail\ndnf install -y nginx\nprintf '<h1>Hello from Veriqta on EC2</h1>\\n' > /usr/share/nginx/html/index.html\nsystemctl enable --now nginx\n"
        },
        "KeyName": {
          "Fn::If": [
            "SshEnabled",
            {
              "Ref": "KeyName"
            },
            {
              "Ref": "AWS::NoValue"
            }
          ]
        }
      },
      "DependsOn": "InternetRoute"
    },
    "SshIngress": {
      "Type": "AWS::EC2::SecurityGroupIngress",
      "Condition": "SshEnabled",
      "Properties": {
        "GroupId": {
          "Ref": "WebSecurity"
        },
        "IpProtocol": "tcp",
        "FromPort": 22,
        "ToPort": 22,
        "CidrIp": {
          "Ref": "ClientCidr"
        }
      }
    }
  },
  "Outputs": {
    "InstanceId": {
      "Value": {
        "Ref": "WebInstance"
      }
    },
    "PublicIp": {
      "Value": {
        "Fn::GetAtt": [
          "WebInstance",
          "PublicIp"
        ]
      }
    },
    "SecurityGroupId": {
      "Value": {
        "Ref": "WebSecurity"
      }
    }
  },
  "Conditions": {
    "SshEnabled": {
      "Fn::Equals": [
        {
          "Ref": "EnableSsh"
        },
        "true"
      ]
    }
  },
  "Rules": {
    "SshKeyRequired": {
      "RuleCondition": {
        "Fn::Equals": [
          {
            "Ref": "EnableSsh"
          },
          "true"
        ]
      },
      "Assertions": [
        {
          "Assert": {
            "Fn::Not": [
              {
                "Fn::Equals": [
                  {
                    "Ref": "KeyName"
                  },
                  ""
                ]
              }
            ]
          },
          "AssertDescription": "Provide an existing regional key pair when enabling SSH"
        },
        {
          "Assert": {
            "Fn::Not": [
              {
                "Fn::Equals": [
                  {
                    "Ref": "ClientCidr"
                  },
                  "0.0.0.0/0"
                ]
              }
            ]
          },
          "AssertDescription": "Do not enable this SSH exercise from all IPv4 addresses"
        }
      ]
    }
  }
}
```

## File: `infra/04-network.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: two-AZ public/private VPC with optional connectivity exercises",
  "Parameters": {
    "AmiId": {
      "Type": "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
      "Default": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
    },
    "InstanceType": {
      "Type": "String",
      "AllowedValues": [
        "t3.micro",
        "t3.small",
        "t3a.micro",
        "t3a.small"
      ],
      "Default": "t3.micro"
    },
    "CreateTestNodes": {
      "Type": "String",
      "AllowedValues": [
        "true",
        "false"
      ],
      "Default": "false"
    },
    "EnablePrivateSsm": {
      "Type": "String",
      "AllowedValues": [
        "true",
        "false"
      ],
      "Default": "false"
    },
    "EnableNatGateway": {
      "Type": "String",
      "AllowedValues": [
        "true",
        "false"
      ],
      "Default": "false"
    }
  },
  "Conditions": {
    "CreateNodes": {
      "Fn::Equals": [
        {
          "Ref": "CreateTestNodes"
        },
        "true"
      ]
    },
    "CreateEndpoints": {
      "Fn::Equals": [
        {
          "Ref": "EnablePrivateSsm"
        },
        "true"
      ]
    },
    "CreateNat": {
      "Fn::Equals": [
        {
          "Ref": "EnableNatGateway"
        },
        "true"
      ]
    }
  },
  "Resources": {
    "Vpc": {
      "Type": "AWS::EC2::VPC",
      "Properties": {
        "CidrBlock": "10.0.0.0/16",
        "EnableDnsSupport": true,
        "EnableDnsHostnames": true,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Gateway": {
      "Type": "AWS::EC2::InternetGateway",
      "Properties": {
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Attachment": {
      "Type": "AWS::EC2::VPCGatewayAttachment",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "InternetGatewayId": {
          "Ref": "Gateway"
        }
      }
    },
    "PublicRoutes": {
      "Type": "AWS::EC2::RouteTable",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "InternetRoute": {
      "Type": "AWS::EC2::Route",
      "Properties": {
        "RouteTableId": {
          "Ref": "PublicRoutes"
        },
        "DestinationCidrBlock": "0.0.0.0/0",
        "GatewayId": {
          "Ref": "Gateway"
        }
      },
      "DependsOn": "Attachment"
    },
    "Public1": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "CidrBlock": "10.0.1.0/24",
        "AvailabilityZone": {
          "Fn::Select": [
            0,
            {
              "Fn::GetAZs": ""
            }
          ]
        },
        "MapPublicIpOnLaunch": true,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "PublicAssociation1": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {
          "Ref": "Public1"
        },
        "RouteTableId": {
          "Ref": "PublicRoutes"
        }
      }
    },
    "Public2": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "CidrBlock": "10.0.2.0/24",
        "AvailabilityZone": {
          "Fn::Select": [
            1,
            {
              "Fn::GetAZs": ""
            }
          ]
        },
        "MapPublicIpOnLaunch": true,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "PublicAssociation2": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {
          "Ref": "Public2"
        },
        "RouteTableId": {
          "Ref": "PublicRoutes"
        }
      }
    },
    "PrivateRoutes": {
      "Type": "AWS::EC2::RouteTable",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Private1": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "CidrBlock": "10.0.3.0/24",
        "AvailabilityZone": {
          "Fn::Select": [
            0,
            {
              "Fn::GetAZs": ""
            }
          ]
        },
        "MapPublicIpOnLaunch": false,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "PrivateAssociation1": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {
          "Ref": "Private1"
        },
        "RouteTableId": {
          "Ref": "PrivateRoutes"
        }
      }
    },
    "Private2": {
      "Type": "AWS::EC2::Subnet",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "CidrBlock": "10.0.4.0/24",
        "AvailabilityZone": {
          "Fn::Select": [
            1,
            {
              "Fn::GetAZs": ""
            }
          ]
        },
        "MapPublicIpOnLaunch": false,
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "PrivateAssociation2": {
      "Type": "AWS::EC2::SubnetRouteTableAssociation",
      "Properties": {
        "SubnetId": {
          "Ref": "Private2"
        },
        "RouteTableId": {
          "Ref": "PrivateRoutes"
        }
      }
    },
    "InstanceRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "ec2.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "ManagedPolicyArns": [
          {
            "Fn::Sub": "arn:${AWS::Partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
          }
        ]
      },
      "Condition": "CreateNodes"
    },
    "InstanceProfile": {
      "Type": "AWS::IAM::InstanceProfile",
      "Properties": {
        "Roles": [
          {
            "Ref": "InstanceRole"
          }
        ]
      },
      "Condition": "CreateNodes"
    },
    "NodeSecurity": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "GroupDescription": "Veriqta test nodes; no inbound ports",
        "VpcId": {
          "Ref": "Vpc"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "EndpointSecurity": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "GroupDescription": "HTTPS from test nodes only",
        "VpcId": {
          "Ref": "Vpc"
        },
        "SecurityGroupIngress": [
          {
            "IpProtocol": "tcp",
            "FromPort": 443,
            "ToPort": 443,
            "SourceSecurityGroupId": {
              "Ref": "NodeSecurity"
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "Condition": "CreateEndpoints"
    },
    "S3Endpoint": {
      "Type": "AWS::EC2::VPCEndpoint",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "ServiceName": {
          "Fn::Sub": "com.amazonaws.${AWS::Region}.s3"
        },
        "VpcEndpointType": "Gateway",
        "RouteTableIds": [
          {
            "Ref": "PrivateRoutes"
          }
        ]
      },
      "Condition": "CreateEndpoints"
    },
    "NatAddress": {
      "Type": "AWS::EC2::EIP",
      "Properties": {
        "Domain": "vpc",
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "Condition": "CreateNat"
    },
    "NatGateway": {
      "Type": "AWS::EC2::NatGateway",
      "Properties": {
        "AllocationId": {
          "Fn::GetAtt": [
            "NatAddress",
            "AllocationId"
          ]
        },
        "SubnetId": {
          "Ref": "Public1"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "Condition": "CreateNat",
      "DependsOn": "Attachment"
    },
    "NatRoute": {
      "Type": "AWS::EC2::Route",
      "Properties": {
        "RouteTableId": {
          "Ref": "PrivateRoutes"
        },
        "DestinationCidrBlock": "0.0.0.0/0",
        "NatGatewayId": {
          "Ref": "NatGateway"
        }
      },
      "Condition": "CreateNat"
    },
    "EndpointSsm": {
      "Type": "AWS::EC2::VPCEndpoint",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "ServiceName": {
          "Fn::Sub": "com.amazonaws.${AWS::Region}.ssm"
        },
        "VpcEndpointType": "Interface",
        "PrivateDnsEnabled": true,
        "SubnetIds": [
          {
            "Ref": "Private1"
          },
          {
            "Ref": "Private2"
          }
        ],
        "SecurityGroupIds": [
          {
            "Ref": "EndpointSecurity"
          }
        ]
      },
      "Condition": "CreateEndpoints"
    },
    "EndpointSsmmessages": {
      "Type": "AWS::EC2::VPCEndpoint",
      "Properties": {
        "VpcId": {
          "Ref": "Vpc"
        },
        "ServiceName": {
          "Fn::Sub": "com.amazonaws.${AWS::Region}.ssmmessages"
        },
        "VpcEndpointType": "Interface",
        "PrivateDnsEnabled": true,
        "SubnetIds": [
          {
            "Ref": "Private1"
          },
          {
            "Ref": "Private2"
          }
        ],
        "SecurityGroupIds": [
          {
            "Ref": "EndpointSecurity"
          }
        ]
      },
      "Condition": "CreateEndpoints"
    },
    "PublicTest": {
      "Type": "AWS::EC2::Instance",
      "Properties": {
        "ImageId": {
          "Ref": "AmiId"
        },
        "InstanceType": {
          "Ref": "InstanceType"
        },
        "IamInstanceProfile": {
          "Ref": "InstanceProfile"
        },
        "SubnetId": {
          "Ref": "Public1"
        },
        "SecurityGroupIds": [
          {
            "Ref": "NodeSecurity"
          }
        ],
        "MetadataOptions": {
          "HttpTokens": "required"
        },
        "BlockDeviceMappings": [
          {
            "DeviceName": "/dev/xvda",
            "Ebs": {
              "VolumeSize": 8,
              "VolumeType": "gp3",
              "Encrypted": true,
              "DeleteOnTermination": true
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "DependsOn": "InternetRoute",
      "Condition": "CreateNodes"
    },
    "PrivateTest": {
      "Type": "AWS::EC2::Instance",
      "Properties": {
        "ImageId": {
          "Ref": "AmiId"
        },
        "InstanceType": {
          "Ref": "InstanceType"
        },
        "IamInstanceProfile": {
          "Ref": "InstanceProfile"
        },
        "SubnetId": {
          "Ref": "Private1"
        },
        "SecurityGroupIds": [
          {
            "Ref": "NodeSecurity"
          }
        ],
        "MetadataOptions": {
          "HttpTokens": "required"
        },
        "BlockDeviceMappings": [
          {
            "DeviceName": "/dev/xvda",
            "Ebs": {
              "VolumeSize": 8,
              "VolumeType": "gp3",
              "Encrypted": true,
              "DeleteOnTermination": true
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "Condition": "CreateNodes"
    }
  },
  "Outputs": {
    "VpcId": {
      "Value": {
        "Ref": "Vpc"
      }
    },
    "PublicSubnet1": {
      "Value": {
        "Ref": "Public1"
      }
    },
    "PublicSubnet2": {
      "Value": {
        "Ref": "Public2"
      }
    },
    "PrivateSubnet1": {
      "Value": {
        "Ref": "Private1"
      }
    },
    "PrivateSubnet2": {
      "Value": {
        "Ref": "Private2"
      }
    },
    "PublicRouteTable": {
      "Value": {
        "Ref": "PublicRoutes"
      }
    },
    "PrivateRouteTable": {
      "Value": {
        "Ref": "PrivateRoutes"
      }
    },
    "PublicTestId": {
      "Value": {
        "Fn::If": [
          "CreateNodes",
          {
            "Ref": "PublicTest"
          },
          "not-created"
        ]
      }
    },
    "PrivateTestId": {
      "Value": {
        "Fn::If": [
          "CreateNodes",
          {
            "Ref": "PrivateTest"
          },
          "not-created"
        ]
      }
    }
  }
}
```

## File: `infra/05-api.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: HTTP API, Lambda and short-retention execution logs",
  "Resources": {
    "FunctionLog": {
      "Type": "AWS::Logs::LogGroup",
      "Properties": {
        "LogGroupName": {
          "Fn::Sub": "/aws/lambda/${AWS::StackName}-api"
        },
        "RetentionInDays": 7
      }
    },
    "ApiLog": {
      "Type": "AWS::Logs::LogGroup",
      "Properties": {
        "RetentionInDays": 7
      }
    },
    "FunctionRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "VeriqtaFunctionLogs",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                  ],
                  "Resource": {
                    "Fn::GetAtt": [
                      "FunctionLog",
                      "Arn"
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    },
    "Function": {
      "Type": "AWS::Lambda::Function",
      "Properties": {
        "FunctionName": {
          "Fn::Sub": "${AWS::StackName}-api"
        },
        "Runtime": "python3.12",
        "Handler": "index.lambda_handler",
        "Role": {
          "Fn::GetAtt": [
            "FunctionRole",
            "Arn"
          ]
        },
        "Timeout": 5,
        "MemorySize": 128,
        "Environment": {
          "Variables": {
            "LAB_FAIL": "false"
          }
        },
        "Code": {
          "ZipFile": "\"\"\"Veriqta HTTP API example. No credentials or request bodies are logged.\"\"\"\nfrom datetime import datetime,timezone\nimport json\nimport os\n\ndef lambda_handler(event,context):\n    request_id=getattr(context,'aws_request_id','local-test')\n    if os.getenv('LAB_FAIL','false').lower()=='true':\n        print(json.dumps({'event':'controlled_failure','request_id':request_id}))\n        raise RuntimeError('Veriqta controlled monitoring exercise')\n    method=event.get('requestContext',{}).get('http',{}).get('method','GET')\n    body={'message':'Hello from Veriqta API','method':method,'request_id':request_id,\n          'timestamp':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}\n    print(json.dumps({'event':'request_completed','request_id':request_id,'method':method,'status':200}))\n    return {'statusCode':200,'headers':{'Content-Type':'application/json'},'body':json.dumps(body)}\n"
        }
      },
      "DependsOn": "FunctionLog"
    },
    "Api": {
      "Type": "AWS::ApiGatewayV2::Api",
      "Properties": {
        "Name": {
          "Fn::Sub": "${AWS::StackName}-http"
        },
        "ProtocolType": "HTTP"
      }
    },
    "Integration": {
      "Type": "AWS::ApiGatewayV2::Integration",
      "Properties": {
        "ApiId": {
          "Ref": "Api"
        },
        "IntegrationType": "AWS_PROXY",
        "IntegrationUri": {
          "Fn::GetAtt": [
            "Function",
            "Arn"
          ]
        },
        "PayloadFormatVersion": "2.0",
        "TimeoutInMillis": 6000
      }
    },
    "Route": {
      "Type": "AWS::ApiGatewayV2::Route",
      "Properties": {
        "ApiId": {
          "Ref": "Api"
        },
        "RouteKey": "GET /",
        "Target": {
          "Fn::Join": [
            "/",
            [
              "integrations",
              {
                "Ref": "Integration"
              }
            ]
          ]
        }
      }
    },
    "Stage": {
      "Type": "AWS::ApiGatewayV2::Stage",
      "Properties": {
        "ApiId": {
          "Ref": "Api"
        },
        "StageName": "$default",
        "AutoDeploy": true,
        "DefaultRouteSettings": {
          "ThrottlingBurstLimit": 5,
          "ThrottlingRateLimit": 1
        },
        "AccessLogSettings": {
          "DestinationArn": {
            "Fn::GetAtt": [
              "ApiLog",
              "Arn"
            ]
          },
          "Format": "{\"requestId\":\"$context.requestId\",\"status\":\"$context.status\",\"integrationError\":\"$context.integrationErrorMessage\"}"
        }
      }
    },
    "InvokePermission": {
      "Type": "AWS::Lambda::Permission",
      "Properties": {
        "Action": "lambda:InvokeFunction",
        "FunctionName": {
          "Ref": "Function"
        },
        "Principal": "apigateway.amazonaws.com",
        "SourceArn": {
          "Fn::Sub": "arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/*/GET/"
        }
      }
    }
  },
  "Outputs": {
    "FunctionName": {
      "Value": {
        "Ref": "Function"
      }
    },
    "ApiUrl": {
      "Value": {
        "Fn::GetAtt": [
          "Api",
          "ApiEndpoint"
        ]
      }
    },
    "ApiId": {
      "Value": {
        "Ref": "Api"
      }
    },
    "FunctionLogGroup": {
      "Value": {
        "Ref": "FunctionLog"
      }
    },
    "ApiLogGroup": {
      "Value": {
        "Ref": "ApiLog"
      }
    }
  }
}
```

## File: `infra/06-database.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: on-demand task tracking table",
  "Resources": {
    "Tasks": {
      "Type": "AWS::DynamoDB::Table",
      "Properties": {
        "AttributeDefinitions": [
          {
            "AttributeName": "taskId",
            "AttributeType": "S"
          }
        ],
        "KeySchema": [
          {
            "AttributeName": "taskId",
            "KeyType": "HASH"
          }
        ],
        "BillingMode": "PAY_PER_REQUEST",
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    }
  },
  "Outputs": {
    "TableName": {
      "Value": {
        "Ref": "Tasks"
      }
    },
    "TableArn": {
      "Value": {
        "Fn::GetAtt": [
          "Tasks",
          "Arn"
        ]
      }
    }
  }
}
```

## File: `infra/07-infrastructure.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: tagged private bucket infrastructure exercise",
  "Resources": {
    "Bucket": {
      "Type": "AWS::S3::Bucket",
      "Properties": {
        "PublicAccessBlockConfiguration": {
          "BlockPublicAcls": true,
          "BlockPublicPolicy": true,
          "IgnorePublicAcls": true,
          "RestrictPublicBuckets": true
        },
        "OwnershipControls": {
          "Rules": [
            {
              "ObjectOwnership": "BucketOwnerEnforced"
            }
          ]
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
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    }
  },
  "Outputs": {
    "BucketName": {
      "Value": {
        "Ref": "Bucket"
      }
    }
  }
}
```

## File: `infra/07-infrastructure.yaml`

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Veriqta: tagged private bucket infrastructure exercise'
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      OwnershipControls:
        Rules:
          - ObjectOwnership: BucketOwnerEnforced
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      Tags:
        - {Key: Project, Value: Veriqta}
        - {Key: Environment, Value: Practice}
Outputs:
  BucketName:
    Value:
      Ref: Bucket
```

## File: `infra/08-container.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: Fargate service with restricted direct test access",
  "Parameters": {
    "VpcId": {
      "Type": "AWS::EC2::VPC::Id"
    },
    "SubnetId": {
      "Type": "AWS::EC2::Subnet::Id"
    },
    "ClientCidr": {
      "Type": "String"
    },
    "ImageUri": {
      "Type": "String"
    },
    "RepositoryArn": {
      "Type": "String"
    }
  },
  "Resources": {
    "Cluster": {
      "Type": "AWS::ECS::Cluster",
      "Properties": {
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "LogGroup": {
      "Type": "AWS::Logs::LogGroup",
      "Properties": {
        "RetentionInDays": 7
      }
    },
    "ExecutionRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "VeriqtaImageAndLogs",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": "ecr:GetAuthorizationToken",
                  "Resource": "*"
                },
                {
                  "Effect": "Allow",
                  "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                  ],
                  "Resource": {
                    "Ref": "RepositoryArn"
                  }
                },
                {
                  "Effect": "Allow",
                  "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                  ],
                  "Resource": {
                    "Fn::GetAtt": [
                      "LogGroup",
                      "Arn"
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    },
    "TaskRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }
      }
    },
    "Security": {
      "Type": "AWS::EC2::SecurityGroup",
      "Properties": {
        "VpcId": {
          "Ref": "VpcId"
        },
        "GroupDescription": "Veriqta container access from selected client",
        "SecurityGroupIngress": [
          {
            "IpProtocol": "tcp",
            "FromPort": 5000,
            "ToPort": 5000,
            "CidrIp": {
              "Ref": "ClientCidr"
            }
          }
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "TaskDefinition": {
      "Type": "AWS::ECS::TaskDefinition",
      "Properties": {
        "NetworkMode": "awsvpc",
        "RequiresCompatibilities": [
          "FARGATE"
        ],
        "Cpu": "256",
        "Memory": "512",
        "RuntimePlatform": {
          "CpuArchitecture": "X86_64",
          "OperatingSystemFamily": "LINUX"
        },
        "ExecutionRoleArn": {
          "Fn::GetAtt": [
            "ExecutionRole",
            "Arn"
          ]
        },
        "TaskRoleArn": {
          "Fn::GetAtt": [
            "TaskRole",
            "Arn"
          ]
        },
        "ContainerDefinitions": [
          {
            "Name": "veriqta-app",
            "Image": {
              "Ref": "ImageUri"
            },
            "Essential": true,
            "PortMappings": [
              {
                "ContainerPort": 5000,
                "Protocol": "tcp"
              }
            ],
            "HealthCheck": {
              "Command": [
                "CMD-SHELL",
                "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)\""
              ],
              "Interval": 15,
              "Timeout": 5,
              "Retries": 3,
              "StartPeriod": 20
            },
            "LogConfiguration": {
              "LogDriver": "awslogs",
              "Options": {
                "awslogs-group": {
                  "Ref": "LogGroup"
                },
                "awslogs-region": {
                  "Ref": "AWS::Region"
                },
                "awslogs-stream-prefix": "veriqta"
              }
            }
          }
        ]
      }
    },
    "Service": {
      "Type": "AWS::ECS::Service",
      "Properties": {
        "Cluster": {
          "Ref": "Cluster"
        },
        "TaskDefinition": {
          "Ref": "TaskDefinition"
        },
        "DesiredCount": 1,
        "LaunchType": "FARGATE",
        "DeploymentConfiguration": {
          "MinimumHealthyPercent": 0,
          "MaximumPercent": 200,
          "DeploymentCircuitBreaker": {
            "Enable": true,
            "Rollback": true
          }
        },
        "NetworkConfiguration": {
          "AwsvpcConfiguration": {
            "Subnets": [
              {
                "Ref": "SubnetId"
              }
            ],
            "SecurityGroups": [
              {
                "Ref": "Security"
              }
            ],
            "AssignPublicIp": "ENABLED"
          }
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    }
  },
  "Outputs": {
    "ClusterName": {
      "Value": {
        "Ref": "Cluster"
      }
    },
    "ServiceName": {
      "Value": {
        "Fn::GetAtt": [
          "Service",
          "Name"
        ]
      }
    },
    "LogGroup": {
      "Value": {
        "Ref": "LogGroup"
      }
    },
    "TaskDefinitionArn": {
      "Value": {
        "Ref": "TaskDefinition"
      }
    }
  }
}
```

## File: `infra/08-registry.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: private image registry",
  "Resources": {
    "Repository": {
      "Type": "AWS::ECR::Repository",
      "Properties": {
        "ImageTagMutability": "IMMUTABLE",
        "ImageScanningConfiguration": {
          "ScanOnPush": true
        },
        "EncryptionConfiguration": {
          "EncryptionType": "AES256"
        },
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    }
  },
  "Outputs": {
    "RepositoryName": {
      "Value": {
        "Ref": "Repository"
      }
    },
    "RepositoryUri": {
      "Value": {
        "Fn::GetAtt": [
          "Repository",
          "RepositoryUri"
        ]
      }
    },
    "RepositoryArn": {
      "Value": {
        "Fn::GetAtt": [
          "Repository",
          "Arn"
        ]
      }
    }
  }
}
```

## File: `infra/09-pipeline.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: repository/branch scoped GitHub OIDC deployment identity",
  "Parameters": {
    "GitHubRepository": {
      "Type": "String",
      "AllowedPattern": "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    },
    "SiteBucketName": {
      "Type": "String"
    },
    "DistributionId": {
      "Type": "String"
    },
    "ExistingProviderArn": {
      "Type": "String",
      "Default": ""
    }
  },
  "Conditions": {
    "CreateProvider": {
      "Fn::Equals": [
        {
          "Ref": "ExistingProviderArn"
        },
        ""
      ]
    }
  },
  "Resources": {
    "Provider": {
      "Type": "AWS::IAM::OIDCProvider",
      "Properties": {
        "Url": "https://token.actions.githubusercontent.com",
        "ClientIdList": [
          "sts.amazonaws.com"
        ],
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      },
      "Condition": "CreateProvider"
    },
    "DeployRole": {
      "Type": "AWS::IAM::Role",
      "Properties": {
        "AssumeRolePolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Federated": {
                  "Fn::If": [
                    "CreateProvider",
                    {
                      "Ref": "Provider"
                    },
                    {
                      "Ref": "ExistingProviderArn"
                    }
                  ]
                }
              },
              "Action": "sts:AssumeRoleWithWebIdentity",
              "Condition": {
                "StringEquals": {
                  "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                  "token.actions.githubusercontent.com:sub": {
                    "Fn::Sub": "repo:${GitHubRepository}:ref:refs/heads/main"
                  }
                }
              }
            }
          ]
        },
        "Policies": [
          {
            "PolicyName": "VeriqtaWebsiteDeployment",
            "PolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [
                {
                  "Effect": "Allow",
                  "Action": "s3:ListBucket",
                  "Resource": {
                    "Fn::Sub": "arn:${AWS::Partition}:s3:::${SiteBucketName}"
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
                    "Fn::Sub": "arn:${AWS::Partition}:s3:::${SiteBucketName}/*"
                  }
                },
                {
                  "Effect": "Allow",
                  "Action": [
                    "cloudfront:CreateInvalidation",
                    "cloudfront:GetInvalidation",
                    "cloudfront:GetDistribution"
                  ],
                  "Resource": {
                    "Fn::Sub": "arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${DistributionId}"
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
          "DeployRole",
          "Arn"
        ]
      }
    }
  }
}
```

## File: `infra/10-monitoring.json`

```json
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Description": "Veriqta: Lambda error alarm and confirmed-email notification path",
  "Parameters": {
    "FunctionName": {
      "Type": "String"
    },
    "AlertEmail": {
      "Type": "String"
    }
  },
  "Resources": {
    "Topic": {
      "Type": "AWS::SNS::Topic",
      "Properties": {
        "Tags": [
          {
            "Key": "Project",
            "Value": "Veriqta"
          },
          {
            "Key": "Environment",
            "Value": "Practice"
          }
        ]
      }
    },
    "Subscription": {
      "Type": "AWS::SNS::Subscription",
      "Properties": {
        "Protocol": "email",
        "Endpoint": {
          "Ref": "AlertEmail"
        },
        "TopicArn": {
          "Ref": "Topic"
        }
      }
    },
    "Errors": {
      "Type": "AWS::CloudWatch::Alarm",
      "Properties": {
        "AlarmDescription": "Veriqta: one or more Lambda invocation errors in a minute",
        "Namespace": "AWS/Lambda",
        "MetricName": "Errors",
        "Dimensions": [
          {
            "Name": "FunctionName",
            "Value": {
              "Ref": "FunctionName"
            }
          }
        ],
        "Statistic": "Sum",
        "Period": 60,
        "EvaluationPeriods": 1,
        "DatapointsToAlarm": 1,
        "Threshold": 1,
        "ComparisonOperator": "GreaterThanOrEqualToThreshold",
        "TreatMissingData": "notBreaching",
        "AlarmActions": [
          {
            "Ref": "Topic"
          }
        ],
        "OKActions": [
          {
            "Ref": "Topic"
          }
        ]
      }
    },
    "TopicPolicy": {
      "Type": "AWS::SNS::TopicPolicy",
      "Properties": {
        "Topics": [
          {
            "Ref": "Topic"
          }
        ],
        "PolicyDocument": {
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "Service": "cloudwatch.amazonaws.com"
              },
              "Action": "sns:Publish",
              "Resource": {
                "Ref": "Topic"
              },
              "Condition": {
                "StringEquals": {
                  "aws:SourceAccount": {
                    "Ref": "AWS::AccountId"
                  }
                },
                "ArnEquals": {
                  "aws:SourceArn": {
                    "Fn::GetAtt": [
                      "Errors",
                      "Arn"
                    ]
                  }
                }
              }
            }
          ]
        }
      }
    }
  },
  "Outputs": {
    "AlarmName": {
      "Value": {
        "Ref": "Errors"
      }
    },
    "TopicArn": {
      "Value": {
        "Ref": "Topic"
      }
    }
  }
}
```

## File: `policies/assume-exercise.template.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "REPLACE_WITH_EXERCISE_ROLE_ARN"
    }
  ]
}
```

## File: `scripts/check_site.py`

```python
"""Check required pages and local href/src targets without network access."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[1]/'site'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=[]
    def handle_starttag(self,tag,attrs):
        self.targets += [value for key,value in attrs if key in {'href','src'} and value]
def validate(root=ROOT):
    root=Path(root).resolve();errors=[]
    for name in ['index.html','about.html','style.css']:
        if not (root/name).is_file():errors.append('Missing required file: '+name)
    for page in root.rglob('*.html'):
        parser=Links();parser.feed(page.read_text())
        for target in parser.targets:
            url=urlsplit(target)
            if url.scheme or url.netloc or not url.path:continue
            dest=(root/unquote(url.path.lstrip('/')) if url.path.startswith('/') else page.parent/unquote(url.path)).resolve()
            if root not in dest.parents or not dest.is_file():errors.append(f'{page.name}: invalid local target {target}')
    return errors
if __name__=='__main__':
    errors=validate()
    if errors:raise SystemExit('\n'.join(errors))
    print('Veriqta website file/link checks passed')
```

## File: `scripts/lab.py`

```python
"""Account-checked helpers for the Veriqta AWS projects. AWS CLI v2 required."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
TEMPLATES={'01':'01-security.json','02':'02-website.json','03':'03-ec2.json','04':'04-network.json','05':'05-api.json','06':'06-database.json','07':'07-infrastructure.json','08-registry':'08-registry.json','08':'08-container.json','09':'09-pipeline.json','10':'10-monitoring.json'}

def aws(args,parsed=True):
    region=os.environ.get('AWS_REGION')
    if not region:raise ValueError('Export AWS_REGION first')
    env=dict(os.environ,AWS_PAGER='',AWS_CLI_AUTO_PROMPT='off')
    result=subprocess.run(['aws',*args,'--region',region,'--output','json'],capture_output=True,text=True,env=env)
    if result.returncode:
        # Preserve AWS diagnostics for this administrative CLI; never print credentials.
        raise RuntimeError(result.stderr.strip() or 'AWS CLI request failed')
    return json.loads(result.stdout) if parsed and result.stdout.strip() else result.stdout

def check_identity():
    expected=os.environ.get('AWS_ACCOUNT_ID','')
    if not re.fullmatch(r'\d{12}',expected):raise ValueError('Export the intended 12-digit AWS_ACCOUNT_ID')
    identity=aws(['sts','get-caller-identity'])
    if identity['Account']!=expected:raise ValueError('Current credentials do not match AWS_ACCOUNT_ID')
    if identity['Arn'].endswith(':root'):raise ValueError('Use an approved non-root execution identity')
    return identity

def stack_name(project):
    if project not in TEMPLATES:raise ValueError('Unknown project')
    return 'veriqta-project-'+project

def parameters(values):
    result=[];seen=set()
    for value in values:
        key,separator,text=value.partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',key):raise ValueError('Parameters must use Name=Value')
        if key in seen:raise ValueError('Duplicate parameter: '+key)
        seen.add(key);result.append({'ParameterKey':key,'ParameterValue':text})
    return result

def output(project,key):
    data=aws(['cloudformation','describe-stacks','--stack-name',stack_name(project)])
    outputs={r['OutputKey']:r['OutputValue'] for r in data['Stacks'][0].get('Outputs',[])}
    if key not in outputs:raise ValueError('No such output: '+key)
    return outputs[key]

def physical(project,logical):
    data=aws(['cloudformation','describe-stack-resource','--stack-name',stack_name(project),'--logical-resource-id',logical])
    return data['StackResourceDetail']['PhysicalResourceId']

def empty_bucket(project,logical,execute=False):
    # Derive the bucket from the exact selected stack resource, not a caller-supplied bucket.
    name=physical(project,logical)
    resources=aws(['cloudformation','list-stack-resources','--stack-name',stack_name(project)])['StackResourceSummaries']
    match=[r for r in resources if r['LogicalResourceId']==logical and r['ResourceType']=='AWS::S3::Bucket']
    if len(match)!=1 or match[0]['PhysicalResourceId']!=name:raise ValueError('Selected resource is not a stack-owned bucket')
    versions=aws(['s3api','list-object-versions','--bucket',name])
    items=[{'Key':x['Key'],'VersionId':x['VersionId']} for kind in ['Versions','DeleteMarkers'] for x in versions.get(kind,[])]
    objects=aws(['s3api','list-objects-v2','--bucket',name]).get('Contents',[])
    uploads=aws(['s3api','list-multipart-uploads','--bucket',name]).get('Uploads',[])
    print(json.dumps({'bucket':name,'versions_and_markers':len(items),'visible_objects':len(objects),'multipart_uploads':len(uploads),'execute':execute}))
    if not execute:return
    for i in range(0,len(items),1000):
        result=aws(['s3api','delete-objects','--bucket',name,'--delete',json.dumps({'Objects':items[i:i+1000],'Quiet':True})])
        if result.get('Errors'):raise RuntimeError('Some object versions could not be deleted')
    # Handle unversioned objects or any objects whose versions were not listed.
    remaining=aws(['s3api','list-objects-v2','--bucket',name]).get('Contents',[])
    for i in range(0,len(remaining),1000):
        result=aws(['s3api','delete-objects','--bucket',name,'--delete',json.dumps({'Objects':[{'Key':x['Key']} for x in remaining[i:i+1000]],'Quiet':True})])
        if result.get('Errors'):raise RuntimeError('Some objects could not be deleted')
    for upload in uploads:aws(['s3api','abort-multipart-upload','--bucket',name,'--key',upload['Key'],'--upload-id',upload['UploadId']])
    # Versioned buckets can gain delete markers during deletion. Repeat only when needed.
    leftovers=aws(['s3api','list-object-versions','--bucket',name])
    if leftovers.get('Versions') or leftovers.get('DeleteMarkers') or aws(['s3api','list-objects-v2','--bucket',name]).get('Contents'):
        raise RuntimeError('Bucket changed during cleanup; stop writers and repeat the preview')

def task_ip(project):
    cluster=output(project,'ClusterName');service=output(project,'ServiceName')
    arns=aws(['ecs','list-tasks','--cluster',cluster,'--service-name',service])['taskArns']
    if not arns:raise ValueError('No service task is running; inspect ECS service events')
    tasks=aws(['ecs','describe-tasks','--cluster',cluster,'--tasks',*arns])['tasks']
    for task in tasks:
        if task.get('lastStatus')!='RUNNING':continue
        for attachment in task.get('attachments',[]):
            fields={d['name']:d['value'] for d in attachment.get('details',[])}
            if 'networkInterfaceId' in fields:
                eni=aws(['ec2','describe-network-interfaces','--network-interface-ids',fields['networkInterfaceId']])['NetworkInterfaces'][0]
                ip=eni.get('Association',{}).get('PublicIp')
                if ip:print(ip);return
    raise ValueError('No public address is ready')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['identity','validate','deploy','output','delete','empty-bucket','empty-registry','task-ip'])
    p.add_argument('project',nargs='?',choices=list(TEMPLATES));p.add_argument('key',nargs='?')
    p.add_argument('--param',action='append',default=[]);p.add_argument('--execute',action='store_true');a=p.parse_args()
    identity=check_identity()
    if a.action=='identity':print(json.dumps(identity,indent=2));return
    if not a.project:p.error('Choose a project')
    name=stack_name(a.project);file=ROOT/'infra'/TEMPLATES[a.project]
    if a.action=='validate':print(json.dumps(aws(['cloudformation','validate-template','--template-body','file://'+str(file)]),indent=2))
    elif a.action=='output':
        if not a.key:p.error('Provide an output key')
        print(output(a.project,a.key))
    elif a.action=='deploy':
        supplied=parameters(a.param)
        args=['cloudformation','deploy','--stack-name',name,'--template-file',str(file),'--capabilities','CAPABILITY_IAM','--tags','Project=Veriqta','Environment=Practice','--no-fail-on-empty-changeset']
        if supplied:args+=['--parameter-overrides',*[r['ParameterKey']+'='+r['ParameterValue'] for r in supplied]]
        if not a.execute:args+=['--no-execute-changeset']
        print(aws(args,parsed=False))
    elif a.action=='delete':
        if not a.execute:print('Preview: delete stack',name);return
        aws(['cloudformation','delete-stack','--stack-name',name]);aws(['cloudformation','wait','stack-delete-complete','--stack-name',name],parsed=False);print('Deleted',name)
    elif a.action=='empty-bucket':
        if not a.key:p.error('Provide the bucket logical resource ID')
        empty_bucket(a.project,a.key,a.execute)
    elif a.action=='empty-registry':
        if a.project!='08-registry':p.error('Select 08-registry')
        repository=output(a.project,'RepositoryName');images=aws(['ecr','list-images','--repository-name',repository]).get('imageIds',[])
        print(json.dumps({'repository':repository,'images':len(images),'execute':a.execute}))
        if a.execute:
            # Delete by unique digest so multiple tags cannot cause partial duplicate deletions.
            ids=[{'imageDigest':d} for d in sorted({r['imageDigest'] for r in images})]
            for i in range(0,len(ids),100):
                result=aws(['ecr','batch-delete-image','--repository-name',repository,'--image-ids',json.dumps(ids[i:i+100])])
                if result.get('failures'):raise RuntimeError('Some images could not be deleted')
    elif a.action=='task-ip':task_ip(a.project)
if __name__=='__main__':
    try:main()
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
```

## File: `scripts/permission_test.py`

```python
"""Exercise one short-lived role session without printing or writing its credentials."""
import json
import os
import subprocess
import sys
import lab

def main():
    lab.check_identity();role=lab.output('01','ExerciseRoleArn')
    session=lab.aws(['sts','assume-role','--role-arn',role,'--role-session-name','veriqta-permission-test','--duration-seconds','900'])['Credentials']
    env=dict(os.environ,AWS_ACCESS_KEY_ID=session['AccessKeyId'],AWS_SECRET_ACCESS_KEY=session['SecretAccessKey'],AWS_SESSION_TOKEN=session['SessionToken'],AWS_PAGER='')
    env.pop('AWS_PROFILE',None);env.pop('AWS_DEFAULT_PROFILE',None)
    def call(args):return subprocess.run(['aws',*args,'--region',os.environ['AWS_REGION'],'--output','json'],env=env,capture_output=True,text=True)
    allowed=call(['s3api','list-buckets']);denied=call(['ec2','describe-instances'])
    print(json.dumps({'s3_list_buckets_allowed':allowed.returncode==0,'ec2_describe_instances_denied':denied.returncode!=0 and ('UnauthorizedOperation' in denied.stderr or 'AccessDenied' in denied.stderr)},indent=2))
    if allowed.returncode or denied.returncode==0:raise RuntimeError('Permission exercise did not produce the expected allow/deny results')
    if not any(code in denied.stderr for code in ['UnauthorizedOperation','AccessDenied']):raise RuntimeError('EC2 request failed for a reason other than expected denial')
if __name__=='__main__':
    try:main()
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
```

## File: `scripts/render_task_policy.py`

```python
"""Render a table-scoped practice policy. Does not attach it to an identity."""
import argparse
import json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('table_arn');a=p.parse_args()
if ':dynamodb:' not in a.table_arn or ':table/' not in a.table_arn:p.error('Provide the exact DynamoDB table ARN')
print(json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':['dynamodb:DescribeTable','dynamodb:PutItem','dynamodb:GetItem','dynamodb:UpdateItem','dynamodb:DeleteItem','dynamodb:Query','dynamodb:Scan'],'Resource':a.table_arn}]},indent=2))
```

## File: `scripts/set_failure.py`

```python
"""Toggle the controlled failure flag on this handbook's project-05 function only."""
import argparse
import lab
p=argparse.ArgumentParser(description=__doc__)
g=p.add_mutually_exclusive_group(required=True);g.add_argument('--enable',action='store_true');g.add_argument('--disable',action='store_true');a=p.parse_args()
lab.check_identity();name=lab.output('05','FunctionName')
config=lab.aws(['lambda','get-function-configuration','--function-name',name])
variables=config.get('Environment',{}).get('Variables',{})
if set(variables)-{'LAB_FAIL'}:raise SystemExit('Unexpected environment variables; inspect the lab function before changing it')
value='true' if a.enable else 'false'
import json
lab.aws(['lambda','update-function-configuration','--function-name',name,'--environment',json.dumps({'Variables':{'LAB_FAIL':value}})])
lab.aws(['lambda','wait','function-updated','--function-name',name],parsed=False)
print('Veriqta project-05 controlled failure:',value)
```

## File: `site/about.html`

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>About Veriqta on AWS</title><link rel="stylesheet" href="style.css"></head><body><main><p class="brand">VERIQTA</p><h1>A private origin, a public website</h1><p>CloudFront serves HTTPS requests while Origin Access Control signs its requests to S3.</p><p><a href="index.html">Home</a></p></main></body></html>
```

## File: `site/index.html`

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Veriqta on AWS</title><link rel="stylesheet" href="style.css"></head>
<body><main><p class="brand">VERIQTA</p><h1>Welcome to Veriqta on AWS</h1><p>A static website delivered through CloudFront from a private S3 origin.</p><p><a href="about.html">About this project</a></p></main></body>
</html>
```

## File: `site/style.css`

```css
:root{font-family:system-ui,sans-serif;color:#123e35;background:#faf8f3}body{margin:0}main{max-width:760px;margin:12vh auto;padding:40px}h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.1}.brand{letter-spacing:.3em;font-weight:700}p{line-height:1.7}a{color:#086a51}
```

## File: `tests/test_projects.py`

```python
"""Offline checks for application behavior, administrative helpers and template controls."""
import contextlib
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'container'),str(ROOT/'scripts')]
import lambda_function
from app_core import response
import check_site
import lab

class LambdaTests(unittest.TestCase):
    def setUp(self):self.context=type('Context',(),{'aws_request_id':'veriqta-request-1'})()
    def call(self,event=None):
        with contextlib.redirect_stdout(io.StringIO()):return lambda_function.lambda_handler(event or {},self.context)
    def test_success_contract(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):result=self.call({'requestContext':{'http':{'method':'GET'}}})
        self.assertEqual(result['statusCode'],200)
        self.assertEqual(result['headers']['Content-Type'],'application/json')
        self.assertEqual(json.loads(result['body'])['message'],'Hello from Veriqta API')
    def test_request_id(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):self.assertEqual(json.loads(self.call()['body'])['request_id'],'veriqta-request-1')
    def test_actual_timestamp(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):value=json.loads(self.call()['body'])['timestamp']
        self.assertIsNotNone(datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo)
    def test_controlled_failure_is_exception(self):
        with patch.dict(os.environ,{'LAB_FAIL':'true'}):
            with self.assertRaisesRegex(RuntimeError,'controlled'):self.call()
    def test_public_event_cannot_enable_failure(self):
        with patch.dict(os.environ,{'LAB_FAIL':'false'}):self.assertEqual(self.call({'LAB_FAIL':'true'})['statusCode'],200)
    def test_log_excludes_body(self):
        stream=io.StringIO()
        with patch.dict(os.environ,{'LAB_FAIL':'false'}),contextlib.redirect_stdout(stream):lambda_function.lambda_handler({'body':'private-body'},self.context)
        row=json.loads(stream.getvalue());self.assertEqual(row['request_id'],'veriqta-request-1');self.assertNotIn('private-body',stream.getvalue())

class ContainerTests(unittest.TestCase):
    def test_root(self):self.assertEqual(response('/'),({'message':'Hello from Veriqta on AWS','status':'success'},200))
    def test_health(self):self.assertEqual(response('/health'),({'status':'ok'},200))
    def test_missing(self):self.assertEqual(response('/missing')[1],404)

class SiteTests(unittest.TestCase):
    def test_site_complete(self):self.assertEqual(check_site.validate(),[])
    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertTrue(check_site.validate(Path(tmp)))
    def test_broken_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ['index.html','about.html','style.css']:(p/name).write_text('')
            (p/'index.html').write_text('<img src="missing.png">')
            self.assertTrue(check_site.validate(p))
    def test_escape_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name in ['index.html','about.html','style.css']:(p/name).write_text('')
            (p/'index.html').write_text('<a href="../secret.txt">bad</a>');self.assertTrue(check_site.validate(p))

class HelperTests(unittest.TestCase):
    def test_account_mismatch(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':'111111111111'}),patch.object(lab,'aws',return_value={'Account':'222222222222','Arn':'arn:aws:iam::222222222222:role/test'}):
            with self.assertRaisesRegex(ValueError,'match'):lab.check_identity()
    def test_root_rejected(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':'111111111111'}),patch.object(lab,'aws',return_value={'Account':'111111111111','Arn':'arn:aws:iam::111111111111:root'}):
            with self.assertRaisesRegex(ValueError,'non-root'):lab.check_identity()
    def test_account_required(self):
        with patch.dict(os.environ,{'AWS_ACCOUNT_ID':''}):
            with self.assertRaises(ValueError):lab.check_identity()
    def test_parameter_values_not_shell_parsed(self):
        value='name with spaces; $(false)'
        self.assertEqual(lab.parameters(['Name='+value]),[{'ParameterKey':'Name','ParameterValue':value}])
    def test_duplicate_parameter_rejected(self):
        with self.assertRaises(ValueError):lab.parameters(['Name=a','Name=b'])
    def test_unknown_project(self):
        with self.assertRaises(ValueError):lab.stack_name('../other')
    def test_deployment_defaults_to_review(self):
        calls=[]
        def fake(args,parsed=True):calls.append(args);return ''
        with patch.object(lab,'check_identity',return_value={}),patch.object(lab,'aws',side_effect=fake),patch.object(sys,'argv',['lab.py','deploy','07']),contextlib.redirect_stdout(io.StringIO()):lab.main()
        self.assertIn('--no-execute-changeset',calls[0])
    def test_execute_is_explicit(self):
        calls=[]
        def fake(args,parsed=True):calls.append(args);return ''
        with patch.object(lab,'check_identity',return_value={}),patch.object(lab,'aws',side_effect=fake),patch.object(sys,'argv',['lab.py','deploy','07','--execute']),contextlib.redirect_stdout(io.StringIO()):lab.main()
        self.assertNotIn('--no-execute-changeset',calls[0])
    def test_bucket_preview_does_not_mutate(self):
        calls=[]
        def fake(args,parsed=True):
            calls.append(args)
            if args[0]=='cloudformation':return {'StackResourceSummaries':[{'LogicalResourceId':'SiteBucket','PhysicalResourceId':'veriqta-test','ResourceType':'AWS::S3::Bucket'}]}
            if args[1]=='list-object-versions':return {'Versions':[{'Key':'index.html','VersionId':'1'}]}
            return {}
        with patch.object(lab,'physical',return_value='veriqta-test'),patch.object(lab,'aws',side_effect=fake),contextlib.redirect_stdout(io.StringIO()):lab.empty_bucket('02','SiteBucket')
        self.assertFalse(any(a[1] in {'delete-objects','abort-multipart-upload'} for a in calls))
    def test_bucket_must_be_stack_owned(self):
        with patch.object(lab,'physical',return_value='not-owned'),patch.object(lab,'aws',return_value={'StackResourceSummaries':[]}):
            with self.assertRaises(ValueError):lab.empty_bucket('02','SiteBucket',True)

class TemplateTests(unittest.TestCase):
    def load(self,prefix):return json.loads(next((ROOT/'infra').glob(prefix+'*.json')).read_text())
    def test_all_projects_have_templates(self):
        self.assertEqual(len(list((ROOT/'infra').glob('*.json'))),11)
        for number in range(1,11):self.assertTrue(list((ROOT/'infra').glob(f'{number:02}-*.json')))
    def test_references_and_dependencies(self):
        import re
        for path in (ROOT/'infra').glob('*.json'):
            t=json.loads(path.read_text());names=set(t['Resources'])|set(t.get('Parameters',{}))
            def walk(x):
                if isinstance(x,dict):
                    if 'Ref' in x:self.assertTrue(x['Ref'] in names or x['Ref'].startswith('AWS::'),(path,x))
                    if 'Fn::GetAtt' in x:self.assertIn(x['Fn::GetAtt'][0],t['Resources'])
                    if 'Fn::If' in x:self.assertIn(x['Fn::If'][0],t.get('Conditions',{}))
                    if 'Fn::Sub' in x and isinstance(x['Fn::Sub'],str):
                        for target in re.findall(r'\$\{([^}]+)\}',x['Fn::Sub']):self.assertTrue(target.split('.')[0] in names or target.startswith(('AWS::','!')),(path,target))
                    for value in x.values():walk(value)
                elif isinstance(x,list):
                    for value in x:walk(value)
            walk(t)
            for resource in t['Resources'].values():
                dependencies=resource.get('DependsOn',[])
                for name in ([dependencies] if isinstance(dependencies,str) else dependencies):self.assertIn(name,t['Resources'])
    def test_private_bucket_controls(self):
        for path in (ROOT/'infra').glob('*.json'):
            for resource in json.loads(path.read_text())['Resources'].values():
                if resource['Type']=='AWS::S3::Bucket':self.assertTrue(all(resource['Properties']['PublicAccessBlockConfiguration'].values()))
    def test_oac_distribution_scoped(self):
        t=self.load('02-');statement=t['Resources']['SitePolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(statement['Principal'],{'Service':'cloudfront.amazonaws.com'})
        self.assertIn('AWS:SourceArn',statement['Condition']['StringEquals'])
        self.assertEqual(t['Resources']['Oac']['Properties']['OriginAccessControlConfig']['SigningBehavior'],'always')
    def test_no_ssh_ingress(self):
        t=self.load('03-');rules=t['Resources']['WebSecurity']['Properties']['SecurityGroupIngress']
        self.assertEqual([r['FromPort'] for r in rules],[80])
        self.assertEqual(t['Resources']['WebInstance']['Properties']['MetadataOptions']['HttpTokens'],'required')
    def test_private_subnets_not_public(self):
        t=self.load('04-')
        for name in ['Private1','Private2']:self.assertFalse(t['Resources'][name]['Properties']['MapPublicIpOnLaunch'])
        self.assertEqual(t['Parameters']['EnableNatGateway']['Default'],'false')
        self.assertEqual(t['Resources']['NatGateway']['Condition'],'CreateNat')
    def test_api_inline_code_matches_source(self):
        t=self.load('05-');f=t['Resources']['Function']['Properties']
        self.assertEqual(f['Code']['ZipFile'],(ROOT/'code/lambda_function.py').read_text())
        self.assertEqual(f['Handler'],'index.lambda_handler')
    def test_database_key_contract(self):
        t=self.load('06-');p=t['Resources']['Tasks']['Properties']
        self.assertEqual(p['BillingMode'],'PAY_PER_REQUEST');self.assertEqual(p['KeySchema'],[{'AttributeName':'taskId','KeyType':'HASH'}])
        for path in (ROOT/'code').glob('task-*.json'):self.assertIn('S',json.loads(path.read_text())['taskId'])
    def test_execution_and_task_roles_separate(self):
        t=json.loads((ROOT/'infra/08-container.json').read_text())
        self.assertNotIn('Policies',t['Resources']['TaskRole']['Properties'])
        p=t['Resources']['TaskDefinition']['Properties'];self.assertNotEqual(p['ExecutionRoleArn'],p['TaskRoleArn'])
        self.assertEqual(p['RuntimePlatform']['CpuArchitecture'],'X86_64')
    def test_oidc_claims_scoped(self):
        t=self.load('09-');trust=t['Resources']['DeployRole']['Properties']['AssumeRolePolicyDocument']['Statement'][0]
        values=trust['Condition']['StringEquals'];self.assertEqual(values['token.actions.githubusercontent.com:aud'],'sts.amazonaws.com')
        self.assertIn('refs/heads/main',json.dumps(values['token.actions.githubusercontent.com:sub']))
    def test_optional_ssh_is_disabled_and_guarded(self):
        t=self.load('03-')
        self.assertEqual(t['Parameters']['EnableSsh']['Default'],'false')
        self.assertEqual(t['Resources']['SshIngress']['Condition'],'SshEnabled')
        self.assertIn('0.0.0.0/0',json.dumps(t['Rules']['SshKeyRequired']))
    def test_alarm_topic_allows_only_scoped_service(self):
        t=self.load('10-');s=t['Resources']['TopicPolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(s['Principal'],{'Service':'cloudwatch.amazonaws.com'})
        self.assertEqual(s['Action'],'sns:Publish')
        self.assertEqual(s['Condition']['ArnEquals']['aws:SourceArn'],{'Fn::GetAtt':['Errors','Arn']})
    def test_alarm_targets_errors(self):
        t=self.load('10-');p=t['Resources']['Errors']['Properties']
        self.assertEqual((p['MetricName'],p['Statistic'],p['Period']),('Errors','Sum',60))
        self.assertEqual(p['TreatMissingData'],'notBreaching')
if __name__=='__main__':unittest.main()
```
