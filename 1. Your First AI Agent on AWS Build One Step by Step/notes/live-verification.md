# Live verification worksheet

Date / tester / account ID / region / stack:
Model ID or inference profile / exact allowed ARNs / resolved SDK version:

For every check record: command or prompt; expected behavior; actual tool/arguments; observed result; latency/usage; evidence/request ID; pass/fail; cleanup.

1. STS identifies intended non-root identity.
2. First Converse request succeeds with verified model and usage.
3. Independent EC2/S3/CloudWatch reads match account/region console.
4. Natural-language requests choose correct tools; no fabricated facts.
5. Empty data, truncation and denied reads are represented honestly.
6. Disallowed write/region/object-prefix requests are rejected without mutation.
7. CloudFormation succeeds; runtime role has no infrastructure-write tools/permissions.
8. Synthetic Lambda test succeeds (privileged test only, not JWT evidence).
9. Signed-out API denied; signed-in browser flow succeeds with required scope.
10. Invalid body rejected; CORS preflight configured for exact origin.
11. Same session remembers; new session/other user does not share history.
12. Concurrent session write returns conflict rather than silent overwrite.
13. Controlled application failure creates logs/metric/alarm/confirmed SNS notification.
14. Working model/config restored; normal operation recovered.
15. Training objects/stack/artifact bucket cleaned up and residual resources reviewed.

Never attach bearer tokens, passwords, secret keys or sensitive prompts as evidence. A result not run must be marked NOT RUN rather than PASS.
