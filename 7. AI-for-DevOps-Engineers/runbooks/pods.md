# Veriqta Pod startup and readiness

CrashLoopBackOff is restart backoff. Inspect previous logs, termination reason, exit status and relevant events. A missing APP_CONFIG causes this lab process to exit with a missing_app_config event.

ImagePullBackOff concerns image retrieval, not an application stack trace. Confirm repository, tag/digest, registry access and node architecture. Pending can mean unscheduled or still preparing; inspect conditions and events.

Running does not mean Ready. Liveness checks process health. Readiness must reflect the intended traffic contract. The introductory lab's shallow readiness does not test the DB unless READINESS_CHECK_DB=true is set.
