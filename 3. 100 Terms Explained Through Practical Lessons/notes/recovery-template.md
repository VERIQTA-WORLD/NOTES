# Recovery runbook

Service, owner, escalation path and last-tested date:
Trigger and impact/severity criteria:
Scope and environment identifiers:
RTO / RPO and measurement convention:
Required permissions, tools and access recovery:
Source image/digest, infrastructure code and protected state location:
Secret/key recovery location (references only, never secret values):
Backup location, encryption/access, retention, latest usable timestamp:
Dependencies and restoration order:

1. Confirm scope, environment and incident ownership.
2. Capture evidence; identify last known-good artifact/configuration.
3. Select mitigation: rollback, forward repair, scaling or isolated restore, with decision criteria.
4. Restore infrastructure/dependencies in documented order.
5. Restore data into an isolated destination; verify integrity and consistency.
6. Validate read/write application behavior and compatibility.
7. Switch traffic using reviewed criteria; observe propagation and connection draining.
8. Confirm user-facing behavior, monitoring and actual recovered data age.
9. Record recovery duration, data-loss age and whether RTO/RPO were met.
10. Plan failback, reconcile infrastructure source and close follow-up actions.

For each step add exact environment-specific commands, expected observations, stop conditions and rollback/escalation choices. Test the runbook before relying on it. This template is not a claim that regional recovery has been validated.
