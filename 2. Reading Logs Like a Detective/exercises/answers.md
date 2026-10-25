## Worked answers

### Foundations and timeline

The server starts first at 10:15:20 UTC. The database connection succeeds at 10:16:05, is lost at 10:17:12, and is retried at 10:17:30. The next recorded successful connection is 10:18:05. The loss-to-success interval is 53 seconds. These events suggest recovery behavior but do not establish the exact scope of user impact.

For the eight-event timeline, the first recorded failure is the database-client connection refusal at 14:21:15. The warning at 14:21:18, timeout at 14:21:20, order failure at 14:21:25, and retry exhaustion at 14:21:30 follow it. The database’s own failure reason is not supplied in that exercise, so the complete initiating cause remains unknown.

### Live exercises

- `/error` intentionally produces an exception and HTTP 500; `/slow` produces a warning but returns 200.
- A bad systemd script path prevents Python from opening the configured application. Removing the exercise override restores the original command.
- Stopping the standalone upstream produces a proxy 502; the short read timeout on `/timeout` produces a 504 while the application is running.
- The Docker configuration-failure container exits because the required database configuration is absent. Restarting it without changing configuration repeats the failure.
- Kubernetes `--previous` retrieves a prior terminated container instance in the same Pod. A deployment update replaces Pods and can remove access to their local history.
- The access dataset has four 5xx responses among twelve requests. The before/after comparison changes from 2% to 5%, despite fewer total failures.

### Capstone timeline

| UTC time | Evidence | Interpretation |
| --- | --- | --- |
| 09:55:00 | `changes.jsonl` | Debug export job enabled without retention or size cap |
| 10:04:58 | `database.jsonl` | Database write fails with `ENOSPC` |
| 10:04:59 | `database.jsonl` | Database shuts down after the write failure |
| 10:05:00 | `storage-before.txt` | Database volume full; debug exports occupy 8 GB of 10 GB |
| 10:05:02 | `app.jsonl` | Database connection refused |
| 10:05:03 | `app.jsonl` | Application exits after failed startup check |
| 10:05:05 | `kubernetes.jsonl` | Restart backoff follows application failure |
| 10:05:06 | `proxy.jsonl`, `proxy-error.log` | Proxy cannot connect; request returns 502 |
| 10:06:05 | `recovery.jsonl`, `storage-after.txt` | Export job disabled; approved disposable exports moved; volume at 20% |
| 10:06:08 | `database.jsonl` | Database ready |
| 10:06:10 | `app.jsonl` | Application reconnects |
| 10:06:12 | `proxy.jsonl` | Database-backed request returns 200 |
| 10:06:20 | `recovery.jsonl` | Repeated checks succeed and storage is stable |

The evidence supports this chain:

```text
Unbounded debug exports on database storage
    → full volume
    → database write failure and shutdown
    → application cannot pass its database startup check
    → repeated container restarts
    → proxy has no healthy upstream
    → user receives 502
```

The uncapped export job is the initiating configuration change. Sharing the database volume with disposable exports and lacking effective retention/capacity controls are contributing conditions. The earliest relevant failure is the database write error at 10:04:58; the proxy 502 is a downstream symptom.

The analytics Pod’s earlier out-of-memory event concerns a different workload at 09:40. The cache miss at 10:04:20 explicitly describes expected fallback behavior. Neither explains the subsequent database storage exhaustion as well as the matched storage and database evidence.

A defensible mitigation stops the producer, identifies approved disposable output, moves it to suitable separate storage, and preserves database/WAL files. After restoring capacity, verify database readiness and integrity checks appropriate to the incident, application startup, database-backed user operations, stable restart counts, and continued capacity headroom.

Do not delete `pg_wal`, database relation files, or an entire volume to free space. Prevention should separate export storage, enforce size/age limits, alert on both disk bytes and inodes, track capacity growth, and test dependency recovery. Each action needs an owner and a completion check.

The captured evidence establishes a failed request at 10:05:06 and a successful one at 10:06:12. It does not establish every affected user, exact global outage duration, or lost transaction count. Those require fuller request metrics, business records, and integrity checks.

