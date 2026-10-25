# The Cron Job Cookbook

## 30 Recipes You’ll Actually Use

**VERIQTA**

Turn repeated operational work into scheduled tasks you can understand, verify, and recover. These lessons cover Linux cron, file maintenance, backups, health checks, reports, concurrency, retries, containers, cloud reporting, Kubernetes CronJobs, logging, alerts, security, and troubleshooting.

Every recipe includes a purpose, a complete implementation, a manual exercise, a schedule, and a result to check. The final project combines the pieces into a maintenance workflow with verified backups and separate missed-run monitoring.

## Contents

1. [Cron is your Linux automation clock](#01-cron-is-your-linux-automation-clock)
2. [Read a schedule without guessing](#02-read-a-schedule-without-guessing)
3. [Your first cron jobs](#03-your-first-cron-jobs)
4. [Cron environments and configuration](#04-cron-environments-and-configuration)
5. [Disk monitoring and temporary files](#05-disk-monitoring-and-temporary-files)
6. [Log rotation and archiving](#06-log-rotation-and-archiving)
7. [Configuration backups and restore verification](#07-configuration-backups-and-restore-verification)
8. [Database backups and retention](#08-database-backups-and-retention)
9. [HTTP health checks and notifications](#09-http-health-checks-and-notifications)
10. [Scheduled application work](#10-scheduled-application-work)
11. [Locks and runtime limits](#11-locks-and-runtime-limits)
12. [Retries and failed-run evidence](#12-retries-and-failed-run-evidence)
13. [Docker maintenance reports](#13-docker-maintenance-reports)
14. [AWS inventory and cost reports](#14-aws-inventory-and-cost-reports)
15. [Kubernetes CronJobs](#15-kubernetes-cronjobs)
16. [Execution logs and exit status](#16-execution-logs-and-exit-status)
17. [Failure and missed-run alerts](#17-failure-and-missed-run-alerts)
18. [Security and job audits](#18-security-and-job-audits)
19. [Troubleshooting playbook](#19-troubleshooting-playbook)
20. [Complete maintenance project](#20-complete-maintenance-project)

The [recipe index](#recipe-index), [worked answers](#worked-answers), [cleanup instructions](#cleanup), and [complete code](#complete-code-and-configuration) support the exercises.

# 01. Cron is your Linux automation clock

Cron is a background scheduling service. A crontab describes when to launch a command and which command to run. The daemon checks schedules and starts matching jobs without requiring an interactive login.

```text
Schedule matches → command starts as its owner → work runs → result is checked → evidence is recorded
```

Typical uses include configuration backups, report generation, expired-file cleanup, inventory collection, and health checks. Cron schedules a launch; your program must define success, handle failures, prevent unsafe overlap, and produce evidence. A schedule alone does not guarantee a backup exists or an application works.

Cron must be installed and running. A powered-off server cannot run its jobs. Traditional cron does not generally replay every scheduled execution missed during downtime. For recurring work that must catch up after downtime, consider anacron or a systemd timer; neither replaces application-level idempotency and verification.

## Set up the practice environment

Use a Linux practice machine for cron, GNU `timeout`, util-linux `flock`, and logrotate. Windows readers can use an Ubuntu virtual machine or WSL2 with the needed services enabled. macOS can run most Python/file exercises, but its native scheduling and command options differ; a Linux VM provides a consistent environment for the scheduler lessons.

The local Python tasks use only the standard library. Python 3.10 or newer is suitable. PostgreSQL, Docker, AWS, and Kubernetes recipes introduce their own prerequisites.

On Ubuntu or Debian, install the tools needed for the first lessons:

```bash
sudo apt update
sudo apt install cron python3 curl util-linux coreutils logrotate
sudo systemctl enable --now cron
systemctl status cron --no-pager
```

On systems using Cronie, the service is commonly named `crond`; use that distribution’s package manager and service name. In minimal containers or WSL installations without systemd, `systemctl` may be unavailable. Confirm the actual init/service setup instead of treating that error as a broken job.

Open a terminal in the `Veriqta-Cron-Job-Cookbook` project directory. Unless stated otherwise, commands run from this directory:

```bash
python3 --version
python3 code/cookbook.py init
python3 -m unittest discover -s tests -v
```

Initialization creates a private `runtime/` directory, a non-secret `config/settings.json`, and small practice inputs. It preserves existing configuration and inputs when repeated. It does not install a schedule or contact an external service.

```text
Cron-Job-Cookbook.md       Lessons and complete source listings
bin/                       Shell entry points
code/                      Tasks, runner, local health endpoint, configuration renderers
config/                    Example settings and AWS policy
kubernetes/                CronJob manifest
exercises/                 Job register and incident worksheet
runtime/                   Practice data, created by init
```

Keep the project at a stable absolute path after scheduling it. Moving or renaming it changes the paths cron needs. Paths in generated schedules are derived from its actual location.

# 02. Read a schedule without guessing

A user crontab entry has five scheduling fields followed by a command:

```text
minute  hour  day-of-month  month  day-of-week  command
0–59    0–23  1–31          1–12   0–7
```

On common Linux cron implementations, Sunday is 0 or 7; Monday is 1. Ranges, names, and extensions can vary across implementations, so check `man 5 crontab` on the target host.

| Symbol | Meaning | Example |
| --- | --- | --- |
| `*` | Every value in that field | `*` in minutes matches each minute |
| `,` | List of values | `0,15,30,45` |
| `-` | Inclusive range | `1-5` for Monday through Friday |
| `/` | Step within a field or range | `*/5` in minutes means 0,5,10…55 |

| Expression | Meaning |
| --- | --- |
| `* * * * *` | Every minute |
| `0 * * * *` | Hourly, at minute 0 |
| `0 0 * * *` | Daily at midnight |
| `5 0 * * 1` | Mondays at 00:05 |
| `0 0 1 * *` | First day of each month at midnight |
| `0 18 * * 1-5` | Weekdays at 18:00 |
| `*/15 * * * *` | At minutes 0,15,30,45 of each hour |
| `0 */2 * * *` | Even-numbered hours, at minute 0 |
| `0 2 * * 0` | Sundays at 02:00 |

`0 2 */7 * *` is a step through the day-of-month field: days 1,8,15,22,29 when those dates exist. It is not a continuous seven-day interval, and the month boundary breaks the spacing. Use a weekday for a weekly job; use an elapsed-time scheduler or stored last-run time for a true interval.

When both day-of-month and day-of-week are restricted, common Vixie-derived cron implementations match either day field. Thus `0 0 1 * 1` means the first of the month **or** Monday, with a single execution when both match. To require the first Monday, use a Monday schedule and a date check inside the script.

## User crontab versus system crontab

User crontab, edited with `crontab -e`:

```cron
0 2 * * * /opt/veriqta/bin/maintenance.sh
```

A file under `/etc/cron.d/` or `/etc/crontab` includes an execution user:

```cron
0 2 * * * veriqta /opt/veriqta/bin/maintenance.sh
```

Do not put the username into a user-crontab entry. It would become part of the command. Do not omit the username from a system-crontab entry. Periodic directories such as `/etc/cron.daily/` generally contain executable scripts invoked by `run-parts`, whose filename rules differ from crontab syntax.

Other common aliases include `@hourly`, `@daily`, `@weekly`, `@monthly`, and `@reboot`. `@reboot` is a cron startup trigger on supporting implementations, not a guarantee that networking or a database is ready.

## Percent signs, comments, and timezones

A literal `%` in a Linux crontab command needs special care: cron can interpret it before the shell sees the line, even inside quotes. Put formatting expressions inside scripts. For an inline date expression, escape its percent signs:

```cron
* * * * * /bin/date +\%Y-\%m-\%d >> /home/veriqta/cron-date.log 2>&1
```

The sample `/home/veriqta` path is illustrative; the renderer in this project generates your actual paths. Keep each cron entry on one physical line, end the file with a newline, and place comments on their own lines. See the [Cronie crontab specification](https://raw.githubusercontent.com/cronie-crond/cronie/master/man/crontab.5).

Decide which timezone defines the schedule. The daemon’s timezone and a process’s `TZ` setting are not always the same thing. Cronie supports `CRON_TZ`, but it is not portable to every cron implementation. Setting `TZ=UTC` for a command does not reliably change when all cron daemons launch it. Confirm local manual pages and the host timezone. Daylight-saving transitions can skip or repeat wall-clock times, with handling dependent on the daemon.

```bash
date
date -u
timedatectl
```

Record the schedule timezone in the job register. Use UTC for application execution logs so records can be compared globally.

# 03. Your first cron jobs

## Recipe 01. Write a timestamp every minute

**Purpose:** Prove the scheduler can launch a command and produce an observable result.

The `tick` task writes the current UTC time and a Veriqta message. Test it and then run it through the execution wrapper:

```bash
python3 code/cookbook.py tick
python3 code/run_job.py tick -- tick
cat runtime/logs/tick.log
cat runtime/logs/tick.jsonl
```

The raw log contains the task’s output. The JSONL log records start, end, run ID, duration, and exit status. A success record is created only after the child exits with status 0.

Generate the first two schedules:

```bash
python3 code/render_crontab.py --profile first > runtime/first.crontab
cat runtime/first.crontab
crontab -l
crontab -e
```

If `crontab -l` reports that no crontab exists, create one with the editor. Other errors, such as permission failures, need investigation. Paste the generated block into the editor while preserving unrelated entries. Save and exit, then list the installed crontab again. Do not run `crontab runtime/first.crontab` casually: that replaces the entire current user crontab.

Wait across two or three minute boundaries:

```bash
tail -n 10 runtime/logs/tick.log
tail -n 6 runtime/logs/tick.jsonl
```

Expect new timestamps approximately once per minute while the daemon is running. Investigate a missing output rather than assuming the cron editor accepted a working command.

## Recipe 02. Run a health-check script every five minutes

**Purpose:** Check an actual condition rather than printing “Service OK” unconditionally.

The first health exercise verifies that a required practice input exists and is nonempty. HTTP application health is introduced in recipe 13.

```bash
python3 code/run_job.py heartbeat -- heartbeat
cat runtime/logs/heartbeat.log
```

The `first` schedule already includes `*/5 * * * *` for this task. It runs on wall-clock minute multiples of five, not five minutes after installation.

Make the condition fail, then restore it:

```bash
mv runtime/heartbeat-input.txt runtime/heartbeat-input.saved
python3 code/run_job.py heartbeat -- heartbeat
mv runtime/heartbeat-input.saved runtime/heartbeat-input.txt
python3 code/run_job.py heartbeat -- heartbeat
```

Expect a nonzero result during the missing-input test and a successful result after restoration. A failed run does not refresh its last-success timestamp.

**Checkpoint:** Explain the difference between seeing a scheduler launch record, seeing an exit status of 0, and verifying the intended output.

# 04. Cron environments and configuration

Cron commonly runs with fewer variables than an interactive terminal. It does not automatically load your `.bashrc`, activate a virtual environment, inherit terminal aliases, or start in your project directory.

Set a deliberate `PATH` and interpreter, use absolute paths, and resolve data paths from the script location. The generated schedules use the absolute Python interpreter that ran the renderer. Activate a virtual environment first if that interpreter should run the job.

```bash
command -v python3
printf '%s\n' "$PATH"
python3 code/render_crontab.py --profile first
```

You can reproduce a limited environment manually, substituting the absolute paths printed by your terminal:

```bash
env -i HOME="$HOME" PATH=/usr/bin:/bin /usr/bin/python3 "$PWD/code/cookbook.py" config
```

This tests that interpreter and task under a minimal environment. It does not perfectly reproduce every cron daemon, permission, locale, or security policy. Inspect only needed environment fields; dumping every environment variable can expose credentials.

## Recipe 03. Run a Python script safely

**Implementation:** `code/cookbook.py python` writes a UTC timestamp without requiring external packages. `run_job.py` runs it with a bounded timeout and logs its result.

```bash
python3 code/run_job.py python-demo -- python
python3 code/render_crontab.py --profile recipe03 > runtime/recipe03.crontab
cat runtime/recipe03.crontab
```

The default schedule is every five minutes. Use `crontab -e` to add the selected block after a manual success. Cron’s command shell may be `/bin/sh`; invoking Python explicitly avoids relying on a shell alias or executable bit for the `.py` file.

For a Python project with dependencies, create a virtual environment, install reviewed requirements, and generate the schedule using that environment’s Python. The shell entry point `bin/run-job.sh` defaults to `/usr/bin/python3`; set `VERIQTA_PYTHON` when using a different interpreter.

## Recipe 04. Load a configuration file

**Implementation:** Tasks read `config/settings.json` using a JSON parser. Configuration is data and is not executed as shell code.

```bash
cat config/settings.example.json
python3 code/cookbook.py config
python3 code/render_crontab.py --profile recipe04
```

Expected output includes `app_name: veriqta` and `environment: practice`. The default schedule is hourly. Edit `config/settings.json` to change non-secret task settings; keep the example unchanged as a reusable starting point.

Shell scripts can load a trusted file with `source` or `.`, but that file can execute commands. A file that looks like `KEY=value` is not inherently safe to source. Protect its ownership and write permissions. Shell variables become child-process environment variables only when exported or passed explicitly.

The runner changes to the project directory before launching a task. The tasks also construct file paths from their own location, so they work when called from another working directory.

# 05. Disk monitoring and temporary files

A full filesystem can stop writes, break databases, and prevent logging. Check the filesystem that contains the data, not just `/` by habit. Byte usage and inode exhaustion are separate failure modes.

```bash
df -h .
df -i .
```

## Recipe 05. Monitor disk usage and alert

**Implementation:** `disk` uses Python’s disk-usage API on `runtime/` and compares usage with `disk_threshold_percent`.

```bash
python3 code/run_job.py disk -- disk
python3 code/render_crontab.py --profile recipe05
```

The schedule checks every ten minutes. Output includes the checked path, free bytes, used percentage, and threshold. Crossing the threshold returns nonzero, producing failure evidence and a local alert message.

To test the failure path without filling a disk, temporarily set the threshold below the current usage in `config/settings.json`. Run the check, inspect its alert, and restore the intended value. A threshold should leave enough capacity and response time for the workload; an arbitrary percentage is not a universal operational standard.

## Recipe 06. Remove expired temporary files

**Implementation:** `clean-temp` considers only regular `*.log` files directly inside `runtime/tmp/`. It skips symlinks and previews candidates unless `--apply` is supplied.

Create an old practice file:

```bash
python3 - <<'PY'
from pathlib import Path
import os,time
p=Path('runtime/tmp/expired.log')
p.write_text('Veriqta disposable practice output\n')
old=time.time()-9*86400
os.utime(p,(old,old))
PY
python3 code/cookbook.py clean-temp --days 7
python3 code/cookbook.py clean-temp --days 7 --apply
```

Expect `WOULD_DELETE` first, then `DELETE`. Confirm the selected file is gone and recent files remain. The generated daily 02:00 schedule remains a preview; add `--apply` to its task arguments only after reviewing the directory and retention policy.

```bash
python3 code/render_crontab.py --profile recipe06
```

For a known Linux directory, `find -type f -name '*.log' -mtime +7 -print` previews candidates; `-delete` performs deletion. GNU `find -mtime` uses completed 24-hour periods: `+7` matches at least eight completed periods, which differs from the Python task’s exact “older than seven days” cutoff. File age alone does not prove a file is unused. Limit cleanup to completed disposable output and coordinate with its producer.

# 06. Log rotation and archiving

Deleting an active log does not necessarily free its storage: a process may retain an open descriptor. Renaming a log also does not force a long-running writer to reopen it.

```text
Current log → rotate name → writer opens a new log → compress completed history → expire by retention policy
```

## Recipe 07. Rotate application logs using logrotate

**Implementation:** `render_logrotate.py` generates a standalone configuration for the project’s short-lived task logs. It keeps seven rotations, compresses old files after a delay, skips missing/empty files, and creates new files with mode 0600.

```bash
python3 code/render_logrotate.py > runtime/logrotate.conf
logrotate --debug --state "$PWD/runtime/state/logrotate.state" "$PWD/runtime/logrotate.conf"
logrotate --force --state "$PWD/runtime/state/logrotate.state" "$PWD/runtime/logrotate.conf"
ls -lh runtime/logs
python3 code/render_crontab.py --profile recipe07
```

Run debug first. Force rotation only in this practice project. The task `rotate` runs the same standalone configuration; do not also install it under `/etc/logrotate.d/` and schedule a second competing rotation.

The `daily` directive is evaluated when logrotate runs; it does not schedule the tool by itself. The task runner opens and closes its log for each execution. Rotate between runs; long-running writers need a documented reopen signal or reload hook. `postrotate` and `sharedscripts` can implement that hook when the application supports it. A generic `systemctl reload` is not valid for every service. `copytruncate` has a possible copy/truncate race and data-loss window. See the [logrotate manual](https://github.com/logrotate/logrotate/blob/main/logrotate.8.in).

## Recipe 08. Compress and archive completed logs

**Implementation:** `archive-logs` reads only `runtime/completed-logs/`, compresses old `*.log.*` files, checks the decompressed content, and then removes the completed original. Already compressed files and symlinks are skipped; a conflicting archive name stops the task.

```bash
python3 - <<'PY'
from pathlib import Path
import os,time
p=Path('runtime/completed-logs/veriqta.log.1')
p.write_text('Veriqta completed log\n')
old=time.time()-31*86400
os.utime(p,(old,old))
PY
python3 code/cookbook.py archive-logs --days 30
ls -lh runtime/archive
python3 code/render_crontab.py --profile recipe08
```

The default schedule is 00:30 daily. Use this directory only for closed logs that the producer will not modify. Compression saves space; moving a file on the same filesystem does not free capacity. A separate archive filesystem needs its own retention, access controls, capacity checks, and restore tests.

# 07. Configuration backups and restore verification

A backup is useful when it can restore required data at an acceptable age. A nonempty file or successful archive command is only the beginning of verification.

```text
Select stable input → create temporary archive → publish complete archive → verify digest → restore in isolation → compare restored content
```

## Recipe 09. Create a timestamped backup

**Implementation:** `backup` archives regular files under `runtime/app-config/` into `runtime/backups/`, with a UTC timestamp and random suffix. It writes to a temporary name and publishes the completed file only after archive creation succeeds.

```bash
python3 code/run_job.py config-backup -- backup
ls -lh runtime/backups
python3 code/render_crontab.py --profile recipe09
```

The default schedule is daily at 02:00. Expect a `veriqta-config-…tar.gz` archive and its JSON metadata. Metadata records file digests and verification state. These are practice backup records created when the recipe runs.

For a stable Linux configuration directory, an equivalent archive command is `tar -czf backup.tar.gz -C /etc/veriqta .`. `-c` creates, `-z` compresses with gzip, and `-f` selects the archive file. `-v` lists processed entries; `-p` is relevant to permission restoration and does not make an application-consistent backup by itself. Relative archive member paths make an isolated restore easier to control.

The isolated restore check validates file contents. A full configuration recovery also needs the required ownership, permissions, ACLs, extended attributes, and service configuration verified.

The practice source is small and should not change during backup. Live data requires a snapshot or application-aware backup method. The scripts reject symlinks rather than silently archiving an unexpected target. Keep backups private, protect encryption keys, and maintain an independent protected copy when the recovery plan requires survival of host loss.

## Recipe 10. Verify backup integrity and test extraction

**Implementation:** `verify` selects the newest configuration archive by default, checks it against its recorded digest, extracts only expected regular files into a temporary restore directory, and compares every restored file with the recorded contents.

```bash
python3 code/cookbook.py verify
python3 code/render_crontab.py --profile recipe10
```

Expected output: `VERIFIED` with the archive name. The verification schedule is 02:15 daily; backup creation already performs verification, so this is an additional repeat check rather than a prerequisite hidden in another job.

A digest detects changes relative to trusted metadata. It does not prove authenticity if an attacker can change both archive and metadata, and it does not prove the selected input was complete. The restore comparison checks this practice archive’s content; a real application needs its own restore validation.

You can inspect an archive without extracting it:

```bash
python3 - <<'PY'
from pathlib import Path
import tarfile
p=max(Path('runtime/backups').glob('veriqta-config-*.tar.gz'),key=lambda x:x.stat().st_mtime)
with tarfile.open(p) as archive:
    for name in archive.getnames():
        print(name)
PY
```

Keep integrity verification in the backup workflow.

# 08. Database backups and retention

Database backups need a consistent database-aware export, protected credentials, compatible tools, and a restore test. `pg_dump` exports one PostgreSQL database consistently while it is in use; cluster-wide roles, tablespaces, and point-in-time recovery require additional methods. See the [PostgreSQL pg_dump reference](https://www.postgresql.org/docs/current/app-pgdump.html).

## Recipe 11. Back up PostgreSQL with pg_dump

**Implementation:** `pg-backup` creates a custom-format dump, checks that its catalog can be read with `pg_restore --list`, and records its digest. It does not mark the dump restore-verified until the separate restore exercise succeeds.

### Create an isolated practice database

On a disposable Ubuntu machine with a local PostgreSQL installation:

```bash
sudo apt install postgresql postgresql-client
sudo systemctl start postgresql
sudo -u postgres createdb veriqta_lab
sudo -u postgres psql --set ON_ERROR_STOP=on --dbname postgres <<'SQL'
CREATE ROLE veriqta_backup LOGIN;
CREATE ROLE veriqta_restore LOGIN CREATEDB;
GRANT CONNECT ON DATABASE veriqta_lab TO veriqta_backup;
SQL
sudo -u postgres psql --set ON_ERROR_STOP=on --dbname veriqta_lab <<'SQL'
CREATE TABLE public.veriqta_events (id integer PRIMARY KEY, message text NOT NULL);
INSERT INTO public.veriqta_events VALUES (1, 'Veriqta first event'), (2, 'Veriqta second event');
GRANT USAGE ON SCHEMA public TO veriqta_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO veriqta_backup;
SQL
sudo -u postgres psql --dbname postgres --command '\password veriqta_backup'
sudo -u postgres psql --dbname postgres --command '\password veriqta_restore'
```

Choose separate practice passwords at the prompts. These are first-run setup commands; inspect existing roles/databases instead of repeating `CREATE` blindly. The backup role can read this database’s current tables. New tables, sequences, row-level security, and other ownership models require deliberate grants and testing. The restore role’s database-creation permission belongs on the isolated restore server.

Use client binaries compatible with the server. If multiple PostgreSQL versions are installed, select the intended `pg_dump`, `pg_restore`, `psql`, `createdb`, and `dropdb` paths; do not assume a randomly selected client can dump every server version.

### Configure a password file

```bash
umask 077
touch "$HOME/.veriqta-cron.pgpass"
chmod 600 "$HOME/.veriqta-cron.pgpass"
nano "$HOME/.veriqta-cron.pgpass"
```

Add these entries with the actual passwords chosen above:

```text
127.0.0.1:5432:veriqta_lab:veriqta_backup:YOUR_BACKUP_PASSWORD
127.0.0.1:5432:*:veriqta_restore:YOUR_RESTORE_PASSWORD
```

The password file must be private to the execution user. Escape colons and backslashes in values according to the [PostgreSQL password-file format](https://www.postgresql.org/docs/current/libpq-pgpass.html). Keep this file outside the public project and version control.

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGDATABASE=veriqta_lab
export PGUSER=veriqta_backup
export PGPASSFILE="$HOME/.veriqta-cron.pgpass"
python3 code/run_job.py pg-backup --timeout 180 -- pg-backup
ls -lh runtime/backups
```

Expect a nonempty `.dump` and JSON metadata with `restore_verified: false`. A readable catalog is not a tested restore.

### Restore and verify the demonstration data

```bash
VERIQTA_DUMP=$(python3 - <<'PY'
from pathlib import Path
p=max(Path('runtime/backups').glob('veriqta-postgres-*.dump'),key=lambda x:x.stat().st_mtime)
print(p.resolve())
PY
)
PGUSER=veriqta_restore python3 code/cookbook.py pg-restore-test --archive "$VERIQTA_DUMP"
```

The test creates a uniquely named database, restores with error checking, verifies two rows in `public.veriqta_events`, and drops that temporary database. Run it only against the isolated test server. A different real dataset needs its own consistency and application checks; the demonstration row count is not a general restore standard.

```bash
python3 code/render_crontab.py --profile recipe11
```

The default schedule is daily at 02:00. Your terminal’s exported variables are not automatically available to cron. Add the required `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and absolute `PGPASSFILE` path as non-secret crontab environment settings, or use a protected wrapper owned by the execution identity. Never put a password into the cron command or command-line arguments.

## Recipe 12. Apply retention rules to verified backups

**Implementation:** `retention` checks archive metadata and current content, considers only restore-verified backups, retains at least `retain_at_least` copies per backup type, and requires a recent verified copy before removing older history.

```bash
python3 code/cookbook.py retention
python3 code/cookbook.py retention --apply
python3 code/render_crontab.py --profile recipe12
```

The schedule is daily at 03:30 and remains a preview. With fresh practice backups, it may select nothing. To practice expiry safely, use temporary copies and old modification times as demonstrated in the included tests; do not age real backups merely to force deletion.

Both age and recovery requirements matter. Do not remove the only known-good backup because it is old. Coordinate archive/metadata deletion and protect against concurrent backup/retention operations. For a production workflow, use a shared lock or storage-side lifecycle policy with equivalent retention guarantees and a durable catalog.

Custom-format PostgreSQL dumps already support compression. Adding an outer gzip layer changes the file handling and offers limited benefit; avoid treating an extra compressed file as automatically restorable. Store independent protected copies and test the full recovery path.

# 09. HTTP health checks and notifications

An open TCP port proves only that a connection can be accepted. An application can still return an error or fail a dependency. Define an HTTP status/body contract that represents the capability you need.

## Recipe 13. Check an HTTP health endpoint

Start the local endpoint in terminal A:

```bash
python3 code/demo_server.py
```

From terminal B in the project directory:

```bash
curl -i --connect-timeout 2 --max-time 5 http://127.0.0.1:8050/health
python3 code/run_job.py health -- health
python3 code/render_crontab.py --profile recipe13
```

Expected response: HTTP 200 and JSON containing `"status": "ok"`. The task requires both. Set `health_url` in the private settings file when checking another authorized endpoint.

| curl option | Purpose |
| --- | --- |
| `-sS` | Suppress progress while keeping error messages |
| `-o /dev/null` | Discard the body |
| `-w '%{http_code}'` | Print the final HTTP status |
| `--connect-timeout` | Bound connection establishment |
| `--max-time` | Bound the whole curl operation |
| `-f` | Return failure for HTTP error statuses |
| `-I` | Send HEAD instead of GET |
| `-L` | Follow redirects |

Printing a status with `-w` does not make a 500 response fail by itself. Check the status or use an appropriate failure option. A response code `000` indicates no usable HTTP response, not a real HTTP status. Curl exit 7 commonly means connection failure; 28 means its timeout expired. A redirect can lead to a login page instead of a healthy application, so validate the final response. The local server implements GET; HEAD is not an equivalent test here.

## Recipe 14. Record failures and notify an operator

Cause the local endpoint to return 503:

```bash
touch runtime/unhealthy
python3 code/run_job.py health -- health
cat runtime/logs/health.log
cat runtime/logs/health.jsonl
ls -lh runtime/outbox
rm runtime/unhealthy
python3 code/run_job.py health -- health
```

Expect a failed health contract, an end event with a nonzero exit code, and a saved `.eml` alert. Restoring the endpoint should produce a successful run. The default schedule checks every five minutes:

```bash
python3 code/render_crontab.py --profile recipe14
```

The notification is saved locally until you explicitly enable delivery. Configure and test the mail path in chapter 17. Merely having an outbox file does not mean an operator received a message.

# 10. Scheduled application work

Use the application’s identity, correct working directory, and validated inputs. Build a complete output under a temporary name before publishing it to consumers. If downstream processing repeats a report, use a stable business identifier or an idempotent import strategy to avoid duplicate records.

## Recipe 15. Execute a scheduled application report

**Implementation:** `report` reads the practice sales CSV, validates nonnegative quantities/prices, calculates totals with decimal arithmetic, and publishes a timestamped CSV in `runtime/reports/`.

```bash
cat runtime/sales.csv
python3 code/run_job.py report -- report
ls -lh runtime/reports
python3 code/render_crontab.py --profile recipe15
```

The schedule is daily at 01:00. Expect a report with these totals:

```csv
product,revenue
Notebook,10.00
Pen,4.50
```

The report is new output for each execution. Real reporting needs an explicit period and duplicate-delivery policy. A zero-row input is treated as a failure here so an empty file cannot masquerade as a valid completed report.

## Recipe 16. Clean up expired application files

**Implementation:** `clean-exports` previews or removes old regular CSV files directly inside `runtime/exports/`.

```bash
python3 code/cookbook.py clean-exports --days 30
python3 code/cookbook.py clean-exports --days 30 --apply
python3 code/render_crontab.py --profile recipe16
```

The default schedule is 02:00 daily and performs a preview. Only completed disposable exports belong in this directory. Keep the producer’s active `.partial` files elsewhere, or ensure the matching rule excludes them.

On Linux, use `lsof` for targeted open-file investigation when available. File age and an empty `lsof` result are not a complete concurrency protocol; coordinate cleanup with the producer, use atomic publication, and enforce the required retention period.

# 11. Locks and runtime limits

If a five-minute job runs for eight minutes, the next scheduled launch can overlap it. Both may write the same destination, generate duplicate work, or exhaust resources. A lock prevents cooperating executions from entering the protected section together.

## Recipe 17. Use flock to prevent overlapping executions

The Python wrapper acquires an advisory `fcntl.flock` lock for each job name. A second invocation with the same name skips with exit 75 and logs `lock_held`. All executions that touch the same protected resource must use a compatible locking scheme.

To demonstrate overlap, start this in terminal A:

```bash
python3 code/run_job.py overlap-demo --timeout 20 -- slow --seconds 8
```

Immediately run this in terminal B:

```bash
python3 code/run_job.py overlap-demo -- tick
cat runtime/logs/overlap-demo.jsonl
```

Expect the second invocation to return 75. The existing lock file is not proof a process still holds the lock; the kernel tracks the active lock. Do not delete a lock file while another process may hold it, because a new file can create a different lock target.

For the GNU/Linux command-line form:

```bash
flock --nonblock --conflict-exit-code 75 "$PWD/runtime/locks/manual.lock" /bin/sleep 8
```

`-n` does not wait; `-w 30` waits up to 30 seconds; the default waits; `-x` is exclusive and `-s` is shared. See the [util-linux flock reference](https://man7.org/linux/man-pages/man1/flock.1.html).

These are local cooperating-process locks. They do not create a distributed lock across separate hosts, and network filesystem lock behavior must be checked. A skipped launch is not a successful execution; missed-success monitoring should still detect a job that never completes.

## Recipe 18. Apply a runtime limit

**Implementation:** The wrapper sets a child-process deadline. On expiry it sends termination to the process group, waits briefly, and escalates to kill if necessary. The task result becomes 124 and no success record is written.

```bash
python3 code/run_job.py timeout-demo --timeout 1 -- slow --seconds 5
printf 'Wrapper exit: %s\n' "$?"
cat runtime/logs/timeout-demo.jsonl
```

Expected wrapper exit: 124. Command-specific exit codes vary; interpret them with the program’s contract.

The supplied Linux shell entry point combines util-linux `flock`, GNU `timeout`, and the Python runner:

```bash
bash bin/locked-maintenance.sh
```

Run it with the local health server available. GNU `timeout --kill-after=5s 60s command` allows a termination grace period; kill escalation can produce a signal-related result. A timeout stops execution but cannot undo a partially applied operation. Use temporary output, transactions, or resumable/idempotent work where interruption is possible.

The recipe 17 and 18 schedules use the same maintenance task to demonstrate protection. Choose one intended schedule, not both duplicate launches:

```bash
python3 code/render_crontab.py --profile recipe17
python3 code/render_crontab.py --profile recipe18
```

# 12. Retries and failed-run evidence

A temporary connection problem may recover; an invalid password usually will not. Retry only an operation that is safe to repeat, and bound both attempts and total elapsed time.

| Failure class | Example | Usual response |
| --- | --- | --- |
| Transient | Connection timeout, 503, temporary throttling | Limited retry with delay |
| Configuration | Wrong URL, expired/invalid credentials, bad input | Correct configuration |
| Permission | 401/403, denied file read | Investigate identity and authorization |
| Application/data | Invalid record or logic error | Correct the task or input |

## Recipe 19. Retry a network operation

**Implementation:** `retry-health` retries selected transport and HTTP failures up to `retry_attempts`, with a bounded exponential delay. It does not retry a 403 or a 200 response with an invalid health body.

```bash
python3 code/run_job.py retry-health --timeout 30 -- retry-health
python3 code/render_crontab.py --profile recipe19
```

Default delays are 1 second, then 2 seconds, with no sleep after the final failed attempt. Configure up to five attempts, at most a ten-second base delay, and a request timeout no greater than ten seconds. The wrapper caps the entire run.

Fixed delays are simple; linear backoff grows proportionally; exponential backoff grows faster. Multiple clients should usually add jitter to avoid synchronized retries. A server’s `Retry-After` policy also matters. This small local health task demonstrates bounded exponential retries; a production integration needs the service’s specific retry policy.

Do not apply this retry loop to payments, message publication, or database writes without an idempotency design. An ambiguous timeout can occur after the remote side completed an operation.

## Recipe 20. Record failed runs

**Implementation:** The wrapper preserves the task’s nonzero exit result, records an end event, and creates a failure alert. Notification errors are logged without replacing the original task failure.

```bash
python3 code/run_job.py failure-demo -- fail
printf 'Task exit: %s\n' "$?"
cat runtime/logs/failure-demo.jsonl
ls -lh runtime/outbox
```

Expected exit: 7, the deliberate demonstration failure. The demonstration does not create a last-success record. The schedule generated for recipe 20 runs the real retry-health task rather than deliberately scheduling an endless stream of known failures:

```bash
python3 code/render_crontab.py --profile recipe20
```

Alert content includes a job name and result, not credentials or full command environments. For repeated failures, route and deduplicate alerts deliberately; a scheduler that sends an email every minute can quickly become noise.

# 13. Docker maintenance reports

Containers, images, writable layers, build caches, networks, and volumes serve different purposes. An unused resource may still be needed for rollback or recovery. Start with reports before designing any removal policy.

## Recipe 21. Record container health and status

**Implementation:** `docker-health` records container status and a one-shot resource-usage snapshot. Install Docker, start its daemon, and use an identity permitted to read it.

```bash
docker version
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}'
docker stats --no-stream
python3 code/run_job.py docker-health -- docker-health
python3 code/render_crontab.py --profile recipe21
```

The schedule is every fifteen minutes. The report is saved in `runtime/reports/`. For one known container, use `docker inspect --format '{{json .State}}' CONTAINER_NAME`, replacing the name with an actual container.

| State | Interpretation |
| --- | --- |
| Running | Main container process is active; an application check may still fail |
| Healthy | Its configured health check is passing |
| Unhealthy | Its configured health check is failing |
| Exited | Main process ended; inspect exit status and logs |
| Restarting | Runtime is repeatedly restarting the process |

A container without a configured health check cannot prove application health by reporting “running.” Docker socket access is powerful and can grant host-level control; do not add a general scheduler identity to the Docker group merely to make a command succeed without reviewing the trust boundary.

## Recipe 22. Report unused Docker resources

**Implementation:** `docker-storage` runs reporting commands only:

```bash
docker system df -v
docker image ls --filter dangling=true
docker container ls -a --filter status=exited
python3 code/run_job.py docker-storage -- docker-storage
python3 code/render_crontab.py --profile recipe22
```

The schedule is daily at 04:00. A report includes storage accounting, dangling images, and stopped containers. `docker system df` reports the daemon’s storage usage; see the [Docker command reference](https://docs.docker.com/reference/cli/docker/system/df/).

“Reclaimable” is a technical storage category, not approval to delete. Review ownership, rollback images, stopped jobs, and volume contents. Broad `docker system prune`, image removal, and volume pruning do not belong in an unattended beginner cleanup task. Container removal does not imply the application’s persistent data is disposable.

# 14. AWS inventory and cost reports

Use scheduled cloud reporting to collect information without granting infrastructure mutation. Establish an AWS execution identity, select the intended account and region, and verify the API permissions before scheduling.

Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). For manual practice, authenticate through the account’s approved short-lived access process. Interactive SSO sessions can expire; a scheduled job needs a supported unattended credential mechanism such as an EC2 instance role or another approved workload identity. Do not create permanent administrator keys to bypass expiry.

## Recipe 23. Schedule a resource inventory

**Implementation:** `aws-inventory` captures caller identity, regional EC2/RDS/Lambda inventory, and account-level S3 bucket listing as JSON. The AWS CLI handles its supported pagination; the task bounds each command and records a complete report only after the reads succeed.

```bash
aws sts get-caller-identity
python3 code/run_job.py aws-inventory --timeout 400 -- aws-inventory
python3 code/render_crontab.py --profile recipe23
```

The default schedule is daily at 02:00. Set `aws_region` in `config/settings.json`. Review [the included policy](config/inventory-policy.json): it names the read APIs used by these recipes instead of granting every `Describe*` or `List*` action. Separate the cost permission if the inventory identity should not see billing data. Scope roles and regions further where the account and action support it.

An empty regional inventory is a valid result. It does not prove the account has no resources elsewhere. Record account, region, capture time, and the services covered. API denial is a failed collection, not an empty account. Inventory reports can contain private resource names and configuration; store and share them accordingly.

## Recipe 24. Produce a daily cost report

**Implementation:** `aws-cost` requests yesterday’s UTC day, groups unblended cost by service, saves the raw response, and writes a genuine CSV using Python’s CSV writer.

```bash
python3 code/run_job.py aws-cost --timeout 90 -- aws-cost
ls -lh runtime/reports/veriqta-cost-*
python3 code/render_crontab.py --profile recipe24
```

The default schedule is 03:00 daily. Cost Explorer’s start date is inclusive and end date exclusive: yesterday-to-today covers yesterday, while yesterday-to-yesterday is an empty/invalid interval. Its standard CLI output formats do not include a generic `--output csv`; convert JSON deliberately. See [GetCostAndUsage](https://docs.aws.amazon.com/cli/latest/reference/ce/get-cost-and-usage.html).

The CSV columns are date, service, unblended cost, unit, and estimated status. Preserve amount precision and unit instead of assuming every amount is a finalized invoice or every usage value can be summed. Billing data can arrive late or be revised. Enable Cost Explorer and verify its permissions and current API charges before scheduling; a report is not an immediate budget enforcement mechanism.

# 15. Kubernetes CronJobs

A Kubernetes CronJob creates Jobs, and a Job manages task Pods. The scheduler/controller, Pod environment, service account, storage, and retry behavior all affect the result.

```text
CronJob schedule → Job → Pod task → output verification → Job status and logs
```

| Linux cron | Kubernetes CronJob |
| --- | --- |
| Runs a command on one host | Creates containerized Jobs in a cluster |
| Host files, PATH, and permissions | Image, volumes, service account, and Pod security |
| Application must implement overlap control | CronJob concurrency policy plus application safeguards |
| Cron/system logs and task output | Job/Pod status, events, and container logs |
| Host outage can miss launches | Controller availability and missed-schedule rules matter |

## Recipe 25. Create a Kubernetes CronJob

**Implementation:** `kubernetes/cronjob.yaml` creates a dedicated namespace and a task that archives a demonstration file, restores it, and compares the result. It runs as a non-root user with an explicit UTC timezone, a runtime deadline, bounded retries, and history limits.

Use an isolated local kind cluster:

```bash
kind create cluster --name veriqta-cron
kubectl --context kind-veriqta-cron apply -f kubernetes/cronjob.yaml
kubectl --context kind-veriqta-cron -n veriqta-cron get cronjobs
kubectl --context kind-veriqta-cron -n veriqta-cron create job --from=cronjob/veriqta-backup veriqta-backup-manual
kubectl --context kind-veriqta-cron -n veriqta-cron wait --for=condition=complete job/veriqta-backup-manual --timeout=120s
kubectl --context kind-veriqta-cron -n veriqta-cron logs job/veriqta-backup-manual
```

Expected message: `Veriqta backup round trip verified`. A failed `wait` needs status/events/log inspection; it is not a successful exercise merely because `apply` succeeded.

```bash
kubectl --context kind-veriqta-cron -n veriqta-cron get jobs --sort-by=.metadata.creationTimestamp
kubectl --context kind-veriqta-cron -n veriqta-cron get pods -l job-name=veriqta-backup-manual
kubectl --context kind-veriqta-cron -n veriqta-cron describe cronjob veriqta-backup
kubectl --context kind-veriqta-cron -n veriqta-cron describe job veriqta-backup-manual
```

The first task uses `emptyDir`: its archive disappears with the Pod. It demonstrates execution and a restore round trip, not durable backup storage.

### Keep an archive beyond the Pod

The separate `persistent-backup.yaml` includes a configuration source, persistent-volume claim, and a CronJob that writes uniquely named archives to that claim. Check your cluster’s default storage class first:

```bash
kubectl --context kind-veriqta-cron get storageclass
kubectl --context kind-veriqta-cron -n veriqta-cron patch cronjob veriqta-backup --type merge -p '{"spec":{"suspend":true}}'
kubectl --context kind-veriqta-cron apply -f kubernetes/persistent-backup.yaml
kubectl --context kind-veriqta-cron -n veriqta-cron get pvc
kubectl --context kind-veriqta-cron -n veriqta-cron create job --from=cronjob/veriqta-persistent-backup veriqta-persistent-manual
kubectl --context kind-veriqta-cron -n veriqta-cron wait --for=condition=complete job/veriqta-persistent-manual --timeout=180s
kubectl --context kind-veriqta-cron -n veriqta-cron logs job/veriqta-persistent-manual
```

A Pending claim may need a compatible storage class or a Pod to trigger binding. Inspect events and the provisioner. The storage driver must support the requested access mode and non-root group access. A PVC surviving Pod deletion is still not an independent off-cluster backup; deleting its claim or cluster can delete the data depending on storage policy.

### Understand the control fields

- `concurrencyPolicy: Forbid` avoids overlapping scheduled Jobs from this CronJob; it is not a global lock for manually created Jobs.
- `startingDeadlineSeconds` limits how late a missed scheduled launch may be created. It is different from the task runtime deadline.
- `activeDeadlineSeconds` limits Job duration; `backoffLimit` limits retries.
- History limits bound retained successful and failed Jobs, not backup retention.
- `timeZone` selects the schedule timezone on supporting Kubernetes versions.

Controllers can occasionally create duplicate or missed executions, so design tasks to be idempotent. Suspended schedules and controller downtime need an explicit catch-up policy. Consult the [Kubernetes CronJob documentation](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/) for the target version.

# 16. Execution logs and exit status

A scheduler launch record is not enough. Record when the task started, what it produced, whether it finished, and its actual exit result. Separate machine-readable event logs from arbitrary stdout/stderr.

## Recipe 26. Capture stdout, stderr, timestamps, and exit status

**Implementation:** `run_job.py` records a start event, sends child stdout/stderr to a protected raw log, waits for the result, records an end event, and returns the result to its caller.

```bash
python3 code/run_job.py logged-report -- report
cat runtime/logs/logged-report.log
cat runtime/logs/logged-report.jsonl
python3 code/render_crontab.py --profile recipe26
```

The default schedule is 01:00 daily. The raw log includes the report path; the execution event contains duration and exit status. If opening the scheduler’s output redirection fails, the wrapper never starts, so inspect the parent scheduler logs too.

| Redirection | Effect |
| --- | --- |
| `> file` | Replace stdout destination, truncating existing content |
| `>> file` | Append stdout |
| `2> file` | Replace stderr destination |
| `2>> file` | Append stderr |
| `>> file 2>&1` | Append stdout and send stderr to that destination |

Redirection order matters: `2>&1 > file` does not have the same effect as `> file 2>&1`. Capture `$?` immediately after the command whose result you need. A final `echo` can otherwise make a failing shell wrapper exit successfully. With `set -e`, use explicit conditionals for expected failures rather than assuming an assignment after the failed command will run.

Common shell statuses include 126 for a found command that cannot execute and 127 for a command not found. Signal-related statuses and application-defined codes need context; “nonzero” identifies failure according to a contract, not a diagnosis.

## Recipe 27. Write a structured execution log

**Implementation:** The `.jsonl` event file uses `json.dumps`, so quotes, newlines, and unusual text are escaped correctly. It does not interleave raw traceback lines into a stream that claims every line is JSON.

```bash
python3 code/run_job.py structured-report -- report
python3 - <<'PY'
import json
from pathlib import Path
for line in Path('runtime/logs/structured-report.jsonl').read_text().splitlines():
    row=json.loads(line)
    print(row['timestamp'],row['event'],row.get('exit_code','-'))
PY
python3 code/render_crontab.py --profile recipe27
```

A typical pair contains a shared `run_id`, a UTC start time, and an end result with `duration_seconds`. A missing end event can indicate termination, a host failure, or a logging failure; it must not be treated as completed success.

The per-job event file and lock avoid many local interleaving problems. For several hosts or shared/network storage, use a logging system with appropriate concurrency and durability guarantees. Rotate both raw and structured logs, and keep credentials or sensitive payloads out of event fields.

# 17. Failure and missed-run alerts

Two different questions need monitoring: **Did an execution fail?** and **Did the expected execution never produce a successful result?** A stopped cron daemon cannot send its own failure message.

## Recipe 28. Alert on unsuccessful execution

The wrapper saves a failure message for nonzero task exits. To test local message construction:

```bash
python3 code/run_job.py alert-test -- fail
ls -lh runtime/outbox
python3 code/cookbook.py notify
```

Inspect the newest `.eml` file locally. It should identify Veriqta, the job, and the failure without including a password or bearer token.

### Configure real email delivery

1. Choose an approved SMTP relay or local mail-transfer service and configure its authenticated delivery according to that provider and operating system.
2. Set `alert_sender`, `alert_recipient`, and the executable `sendmail_path` in the private `config/settings.json`.
3. Send a deliberate test and confirm receipt at the destination:

```bash
python3 code/cookbook.py notify --deliver
```

The code submits a message through the configured sendmail-compatible executable; a relay’s acceptance is not proof of inbox delivery. Check provider logs, bounces, filtering, and the actual recipient. `MAILTO` in a crontab also depends on a working mail setup and generally concerns captured output rather than an application’s business success.

### Example: a sendmail-compatible SMTP client on Ubuntu

If the host has no mail-transfer service, `msmtp` can submit through an SMTP relay that supports your account’s authentication method. See the [msmtp manual](https://marlam.de/msmtp/msmtp.html) for its sendmail-compatible mode and account settings:

```bash
sudo apt install msmtp ca-certificates
mkdir -p "$HOME/.config/veriqta"
chmod 700 "$HOME/.config/veriqta"
cp config/msmtprc.example "$HOME/.msmtprc"
chmod 600 "$HOME/.msmtprc"
nano "$HOME/.msmtprc"
nano "$HOME/.config/veriqta/mail-password"
chmod 600 "$HOME/.config/veriqta/mail-password"
```

Run these as the intended cron identity, and do not overwrite an existing mail configuration without reviewing it. Fill in the relay host, verified sender, SMTP username, and absolute password-file path. Use a provider-approved application password or other supported SMTP credential, not an account’s general password when the provider requires a different mechanism. The template uses TLS with certificate verification on port 587; follow your relay’s documented connection/authentication requirements.

Set `sendmail_path` to `/usr/bin/msmtp` in the private settings, set matching sender/recipient addresses, and run `notify --deliver`. Keep both local files private. A hosted provider that requires OAuth or a dedicated API needs its supported client instead of assuming username/password SMTP will work everywhere.

To enable failure delivery on a wrapper invocation, place `--deliver` before its `--` separator:

```bash
python3 code/run_job.py delivered-alert-test --deliver -- fail
```

This deliberately sends a test failure when delivery has been configured. Keep real schedules in preview/local-alert mode until the chosen destination is tested. The generated recipe 28 schedule runs a report with local alert capture; add the wrapper’s delivery flag when ready.

### Optional Slack and Telegram routes

The companion `notify_channels.py` supports previews and explicit delivery:

```bash
python3 code/notify_channels.py slack --text 'Veriqta notification preview'
python3 code/notify_channels.py telegram --text 'Veriqta notification preview'
```

For Slack, create an approved app, enable incoming webhooks, select a test channel, and provide its secret URL as `SLACK_WEBHOOK_URL` through a protected environment. See [Slack incoming webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/).

For Telegram, create an approved bot and destination, arrange the bot’s access, and provide `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. The script calls `sendMessage`; see the [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage).

After setting the chosen credentials securely, add `--deliver` to the corresponding command and confirm receipt. These optional channel scripts are standalone adapters; the core wrapper uses its email/outbox notifier. Integrate an adapter deliberately if that channel should receive automatic job alerts. Never put webhook URLs or bot tokens in the public notes, source control, or ordinary logs.

## Recipe 29. Detect missing scheduled execution

**Implementation:** Successful wrapper runs write `runtime/state/JOB.success.json` atomically. Failed or skipped executions do not refresh it. `watch` checks its timestamp, treats missing/malformed/future timestamps as abnormal, and alerts when the last successful completion is too old.

```bash
python3 code/run_job.py freshness-demo -- tick
python3 code/cookbook.py watch --job freshness-demo --max-age 60
python3 code/cookbook.py watch --job never-ran --max-age 60
python3 code/render_crontab.py --profile recipe29
```

Expect `FRESH` for the recent task and a failure alert for the nonexistent one. A threshold is in seconds, not rounded whole hours. The default daily-maintenance allowance is 93,600 seconds, or 26 hours.

An hourly watcher can detect a threshold breach up to about an hour after it occurs, plus runtime and scheduling delay. Choose a tighter schedule when required. Establish an initial successful baseline before enabling monitoring to avoid an unexplained “never succeeded” alert.

A watcher on the same server and cron daemon shares their failure modes. For host, daemon, or network loss, use an independent external heartbeat/dead-man monitor. Monitor that monitor and test alert delivery. Watching a general log file’s modification time is insufficient: failed attempts and unrelated writes can keep it fresh.

# 18. Security and job audits

Scheduled work often runs unattended with durable access. A writable script, untrusted PATH directory, or excessive execution identity can turn a minor mistake into a serious incident.

## Recipe 30. Audit existing cron jobs

**Implementation:** `audit` reviews the project’s script/configuration paths for world-writable entries and symlinks, and reports possible secret assignment locations without printing their values. It is a starting point, not a complete security scanner.

```bash
python3 code/cookbook.py audit
crontab -l
ls -ld /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly
ls -l /etc/crontab
python3 code/render_crontab.py --profile recipe30
```

The default audit schedule is Mondays at 06:00. Authorized administrators can also inspect root’s crontab with `sudo crontab -l` and selected service-user crontabs with `sudo -u USER crontab -l`.

On Linux, preview world-writable system cron entries:

```bash
sudo find /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly -type f -perm -0002 -print
```

Missing directories vary by distribution; inspect those that exist. Check parent-directory ownership and permissions as well as the script itself. A non-writable file in a replaceable directory may still be unsafe. Search for suspected secrets by filename/line location and review them privately; do not dump matching secret values into an audit report.

## Use a dedicated service account

For a controlled Linux deployment, create an account used only by the automation:

```bash
sudo useradd --system --user-group --create-home --home-dir /var/lib/veriqta-cron --shell /usr/sbin/nologin veriqta-cron
```

This is a first-run example. Inspect an existing account before reusing it. Keep deployed executable code owned by an administrator and writable only through the deployment process; give the service account write access only to its runtime data/log/state directories. A user able to change a privileged job’s code effectively controls that job.

A service account’s cron command does not need an interactive login shell, but local PAM/cron policy may impose additional account rules. Install a reviewed system cron entry with its explicit user field, or administer that user’s crontab. Run the complete manual test under that same identity before enabling its schedule.

Use least-privilege database and cloud identities, private credential files, controlled executable search paths, bounded inputs, and appropriate network access. Environment variables are not a secret-management system by themselves. Avoid root unless the specific operation requires it, and never grant blanket permissions simply because cron lacks the interactive user’s access.

# 19. Troubleshooting playbook

Start with the promised outcome, not with a restart. Record job name, intended schedule/timezone, execution identity, expected output, last known success, and recent changes.

## Incident 1: It works manually but fails in cron

```bash
crontab -l
systemctl status cron --no-pager
sudo journalctl -u cron --since '1 hour ago' --no-pager
command -v python3
ls -ld "$PWD" "$PWD/code" "$PWD/runtime" "$PWD/runtime/logs"
```

On Cronie systems use `crond` for the service query. Logs may also appear in `/var/log/syslog`, `/var/log/cron`, or `/var/log/messages`. A scheduler log can show launch attempts without capturing the child’s full outcome.

Check interpreter path, execution user, environment, working directory, permissions, credential expiry, output redirection, file format, and executable bit when running a script directly. Look for Windows CRLF line endings or a missing shebang. Use the minimal-environment test from chapter 4 with the actual cron identity.

## Incident 2: It runs at the wrong time

Check the daemon’s schedule timezone, host clock, daylight-saving behavior, and any implementation-specific timezone setting. Re-read each of the five fields. Search for duplicate entries in user and system schedules. Do not change a server’s global timezone during an unrelated incident merely to make one job appear aligned.

## Incident 3: Permission denied

Inspect permissions on every directory in the path, the executable, configuration, credential file, output directory, and lock directory. Check the identity that actually ran the job. Security mechanisms such as SELinux, AppArmor, or account/PAM policy may impose additional restrictions. Apply the narrow correction supported by evidence; `chmod 777` is not a diagnosis.

## Incident 4: It runs twice or corrupts output

Check duplicate schedules, overlap duration, manual starts, retries, and multiple hosts. Confirm all cooperating invocations use the same protected lock scope. Use unique temporary files and atomic publication. For a database or remote API, a local filesystem lock cannot establish global exactly-once processing.

## Incident 5: It exits successfully but produces no useful result

Read both stdout/stderr and the final result. Check input row count, destination path, output size and schema, external API response, and business-level postconditions. A command that returns zero after ignoring an earlier failure needs correction. Verify a report can be read and a backup can be restored.

## Incident 6: No alert arrived

Distinguish a saved preview from submitted delivery. Check whether `--deliver` was enabled, whether the relay/provider accepted the message, and whether the recipient received it. If the host or daemon stopped, a same-host watcher may also have stopped. Inspect the independent monitoring path.

## Useful diagnosis sequence

1. Preserve relevant schedule, task log, event log, success state, and UTC timestamps.
2. Compare expected behavior with the actual result.
3. Identify the execution identity, interpreter, PATH, configuration, and working directory.
4. Reproduce a bounded failure in the practice environment.
5. Correct one supported cause and rerun manually.
6. Verify the next real scheduled execution and output.
7. Record the cause, correction, and prevention action in [the incident worksheet](exercises/incident-report.md).

# 20. Complete maintenance project

The final workflow checks application health, checks disk usage, creates and restore-verifies a configuration backup, generates a report, prevents same-job overlap, limits runtime, records execution events, and alerts on failed or overdue successful completion.

```text
Daily schedule → per-job lock → health check → disk check → backup + restore test → report
                      ↓                         ↓
                bounded runtime            structured result
                                                ↓
                                      last-success record
                                                ↑
                                   separate overdue check
```

## Step 1. Establish a healthy baseline

Initialize the practice data if needed and keep the local endpoint running in another terminal:

```bash
python3 code/cookbook.py init
python3 code/demo_server.py
```

In the project terminal:

```bash
python3 code/run_job.py maintenance --timeout 120 -- maintenance
python3 code/cookbook.py watch --job maintenance --max-age 93600
cat runtime/logs/maintenance.jsonl
cat runtime/state/maintenance.success.json
ls -lh runtime/backups runtime/reports
```

Expect a successful health contract, disk measurement below the configured threshold, verified backup, published report, exit 0, and a fresh success timestamp. If the machine already exceeds the threshold, inspect capacity and choose an appropriate practice setting rather than filling or deleting unrelated data.

## Step 2. Exercise failure and recovery

```bash
touch runtime/unhealthy
python3 code/run_job.py maintenance --timeout 120 -- maintenance
cat runtime/state/maintenance.success.json
rm runtime/unhealthy
python3 code/run_job.py maintenance --timeout 120 -- maintenance
```

During the failure, the old last-success record must remain unchanged. A new successful result should update it. Read the event log and saved failure message. This workflow stops at the first failing step; a failed health check does not pretend the backup/report stages ran.

## Step 3. Exercise missing-success detection

```bash
python3 code/cookbook.py watch --job missing-maintenance --max-age 93600
```

Expect a missing-success alert. For an overdue-success test, make a temporary copy of a practice success record with an old `finished_at` value under a new test job name, then run its watcher. Do not change a real job’s success evidence to simulate a failure.

## Step 4. Install the selected schedule

```bash
python3 code/render_crontab.py --profile maintenance > runtime/maintenance.crontab
cat runtime/maintenance.crontab
crontab -e
```

The block schedules maintenance daily at 02:00 and its last-success check hourly. They use the cron daemon’s schedule timezone unless the target implementation is configured otherwise. Preserve existing jobs, and remove duplicate practice blocks that would run the same operations unintentionally.

Wait for an actual scheduled execution and verify the end event, output files, backup restoration, success freshness, and alert path. Manual success is not a substitute for observing the scheduler identity/environment.

## Step 5. Register operational ownership

Complete [the job register](exercises/job-register.md) with purpose, owner, identity, schedule/timezone, deadlines, expected output, retry/lock policy, alert route, and recovery action. Review code/config changes and repeat failure/restore tests after changes that affect behavior.

Use a separate host or external service for the final missed-heartbeat check when host failure must be detected. If a daily backup has a 26-hour freshness allowance, state that detection window and any additional watcher delay explicitly.

## When another scheduler is a better fit

A systemd timer can pair calendar scheduling with service supervision, runtime controls, journal output, and catch-up behavior using `Persistent=true` for supported calendar timers. Add randomized delay to spread fleet load where appropriate. See [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).

A managed cloud scheduler or Kubernetes CronJob can centralize scheduling, credentials, retries, and execution history, but still needs verified outcomes and idempotent work. Choose based on where the task runs, required availability, missed-run policy, access model, and recovery needs.

# Worked answers

- `*/5` in minutes matches fixed wall-clock slots; it does not mean five minutes after the previous completion.
- `0 2 */7 * *` steps through dates within each month. It does not maintain a seven-day interval across month boundaries.
- On common Vixie-derived cron, restricted day-of-month and day-of-week fields use either-day matching.
- A command can work interactively and fail in cron because its user, environment, interpreter, current directory, and access differ.
- Unescaped inline `%` is parsed by cron before shell quoting can protect it. Keeping date formatting in a script avoids this trap.
- A 200 status with the wrong health body fails the practice health contract. A listening port alone proves even less.
- A saved `.eml` is evidence of message construction; relay acceptance and confirmed receipt are separate checks.
- A skip caused by a lock must not refresh last-success state. Otherwise a permanently stuck job could appear healthy.
- A timeout can leave partial side effects. Atomic output and idempotency/transactions address different parts of that problem.
- A dump with a readable catalog is not yet a proven restore. The practice database restore also checks demonstration data.
- Retention preserves a minimum number of verified copies and requires a recent good copy before removing old ones.
- Cost Explorer uses an exclusive end date. Yesterday-to-today requests one day; using the same start and end does not.
- A Kubernetes history limit removes Job history; it is not a backup-retention policy. `emptyDir` is not durable backup storage.
- A same-host watcher cannot reliably detect the loss of its own host or scheduler. Use an independent monitor for that failure mode.

# Recipe index

| Recipe | Task | Default schedule |
| --- | --- | --- |
| 01 | Timestamp | Every minute |
| 02 | Heartbeat input check | Every five minutes |
| 03 | Python execution | Every five minutes |
| 04 | Configuration load | Hourly |
| 05 | Disk usage | Every ten minutes |
| 06 | Temporary-file preview | Daily 02:00 |
| 07 | Log rotation | Daily 00:00 |
| 08 | Completed-log archive | Daily 00:30 |
| 09 | Configuration backup | Daily 02:00 |
| 10 | Backup verification | Daily 02:15 |
| 11 | PostgreSQL backup | Daily 02:00 |
| 12 | Verified-backup retention preview | Daily 03:30 |
| 13 | HTTP health contract | Every five minutes |
| 14 | Health failure notification | Every five minutes |
| 15 | Application report | Daily 01:00 |
| 16 | Export cleanup preview | Daily 02:00 |
| 17 | Lock-protected maintenance | Daily 02:00 |
| 18 | Runtime-bounded maintenance | Daily 02:00 |
| 19 | Retried health request | Every ten minutes |
| 20 | Failed-run recording | Every ten minutes |
| 21 | Docker health/status report | Every fifteen minutes |
| 22 | Docker storage report | Daily 04:00 |
| 23 | AWS inventory | Daily 02:00 |
| 24 | AWS cost report | Daily 03:00 |
| 25 | Kubernetes CronJob | Daily 02:00 UTC |
| 26 | Full execution evidence | Daily 01:00 |
| 27 | Structured execution events | Daily 01:00 |
| 28 | Failure alert | Daily 01:00 |
| 29 | Last-success watcher | Hourly |
| 30 | Cron security audit | Mondays 06:00 |

Use `python3 code/render_crontab.py --profile recipeNN` for a host recipe, replacing `NN` with its two-digit number. Recipe 25 uses the Kubernetes manifests. Generated schedules do not install themselves. Select the jobs needed for the exercise rather than enabling all overlapping demonstrations.

# Cleanup

1. Open `crontab -e` and remove only the Veriqta practice blocks you added. Preserve unrelated jobs. Use `crontab -l` to confirm the result; do not use `crontab -r` to remove one project.
2. Stop the local endpoint with Ctrl+C in its terminal.
3. If you created the dedicated kind cluster, remove it only after saving any needed backup data:

```bash
kind delete cluster --name veriqta-cron
```

4. If you created the isolated PostgreSQL demonstration roles/database, remove them only after finishing restore tests and confirming no other work uses them:

```bash
sudo -u postgres dropdb veriqta_lab
sudo -u postgres psql --dbname postgres --command 'DROP ROLE veriqta_backup; DROP ROLE veriqta_restore;'
```

5. Remove the dedicated password file when it is no longer required. Do not remove shared AWS profiles, Docker resources, or mail-relay configuration merely because a reporting recipe used them.
6. Preserve useful logs/reports privately, then remove the project’s disposable `runtime/` data if desired. Cron schedules must be removed before moving or deleting their project directory.

# Ready-to-operate checklist

- Purpose, owner, execution identity, schedule, and timezone are documented.
- Absolute interpreter/command paths and required environment are known.
- Manual and actual scheduled executions both produce verified outcomes.
- Permissions and credentials grant only the needed access.
- Runtime, retries, overlap, and interruption behavior are defined.
- Output is published completely and sensitive data is protected.
- Backups have tested restores and an explicit retention/recovery policy.
- Failure alerts and independent missed-success monitoring reach the intended operator.
- Logs have bounded retention and can support an investigation.
- Cleanup and recovery actions target only the job’s owned resources.

# Complete code and configuration

File paths below are relative to the project directory. These files are also included in their corresponding folders for the exercises. Initialize the practice data with `python3 code/cookbook.py init`.

## File: `.gitignore`

```text
runtime/
config/settings.json
__pycache__/
*.pyc
.venv/
.env
.pgpass
.DS_Store
```

## File: `bin/locked-maintenance.sh`

```bash
#!/bin/bash
# Linux: util-linux flock and GNU coreutils timeout.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$ROOT/runtime/locks"
exec /usr/bin/flock --nonblock --conflict-exit-code 75 \
  "$ROOT/runtime/locks/linux-maintenance.lock" \
  /usr/bin/timeout --kill-after=5s 60s \
  "${VERIQTA_PYTHON:-/usr/bin/python3}" "$ROOT/code/run_job.py" linux-maintenance --timeout 50 -- maintenance
```

## File: `bin/run-job.sh`

```bash
#!/bin/bash
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "${VERIQTA_PYTHON:-/usr/bin/python3}" "$ROOT/code/run_job.py" "$@"
```

## File: `code/cookbook.py`

```python
"""Veriqta cron tasks. Run from any working directory; practice data stays in runtime/."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runtime'

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def atomic_text(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as stream:
        tmp=Path(stream.name)
        try:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True);raise
    os.replace(tmp,path)
def save(path,data):atomic_text(path,json.dumps(data,indent=2,ensure_ascii=True)+'\n')
def settings():
    return json.loads((ROOT/'config/settings.json').read_text())
def init():
    os.umask(0o077)
    for name in ['logs','state','locks','backups','restore-tests','outbox','reports','tmp','exports','completed-logs','archive','app-config']:
        (BASE/name).mkdir(parents=True,exist_ok=True)
    config=ROOT/'config/settings.json'
    if not config.exists():shutil.copyfile(ROOT/'config/settings.example.json',config)
    files={BASE/'app-config/app.json':json.dumps({'app':'veriqta','mode':'practice'})+'\n',
           BASE/'sales.csv':'date,product,quantity,unit_price\n2026-01-15,Notebook,2,5.00\n2026-01-15,Pen,3,1.50\n',
           BASE/'heartbeat-input.txt':'Veriqta practice input\n'}
    for p,text in files.items():
        if not p.exists():p.write_text(text)
    print('Veriqta practice environment ready:',BASE)
def stamp():return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def scoped(path,parent):
    path=Path(path);parent=Path(parent).resolve()
    if path.is_symlink():raise ValueError('Symbolic-link target is not accepted')
    resolved=path.resolve()
    if resolved==parent or parent not in resolved.parents:raise ValueError('Path is outside the permitted directory')
    return resolved

def tick():print(now(),'Veriqta scheduled timestamp')
def heartbeat():
    p=BASE/'heartbeat-input.txt'
    if not p.is_file() or not p.read_text().strip():raise ValueError('Heartbeat input is missing or empty')
    print(now(),'Veriqta heartbeat input readable')
def config_report():
    s=settings();print(json.dumps({k:s[k] for k in ['app_name','environment']},indent=2))
def disk():
    s=settings();threshold=int(s['disk_threshold_percent'])
    if not 1<=threshold<=100:raise ValueError('Disk threshold must be 1..100')
    usage=shutil.disk_usage(BASE)
    percent=100*usage.used/usage.total
    print(json.dumps({'path':str(BASE),'used_percent':round(percent,2),'threshold':threshold,'free_bytes':usage.free}))
    if percent>=threshold:raise RuntimeError('Disk usage threshold reached')

def cleanup(kind,apply=False,days=None):
    # Fixed directories and patterns prevent a configured path from targeting system files.
    folder,pattern={'tmp':('tmp','*.log'),'exports':('exports','*.csv')}[kind]
    days=int(settings()['retention_days'] if days is None else days)
    if days<1:raise ValueError('Retention must be at least one day')
    cutoff=time.time()-days*86400
    for p in sorted((BASE/folder).glob(pattern)):
        if p.is_symlink() or not p.is_file():continue
        scoped(p,BASE/folder)
        if p.stat().st_mtime<cutoff:
            print('DELETE' if apply else 'WOULD_DELETE',p)
            if apply:p.unlink()

def archive_logs(days=30):
    if days<1:raise ValueError('Archive age must be at least one day')
    cutoff=time.time()-days*86400
    for p in sorted((BASE/'completed-logs').glob('*.log.*')):
        if p.is_symlink() or not p.is_file() or p.name.endswith(('.gz','.partial')) or p.stat().st_mtime>=cutoff:continue
        scoped(p,BASE/'completed-logs')
        target=BASE/'archive'/(p.name+'.gz')
        if target.exists():raise FileExistsError('Archive already exists: '+str(target))
        partial=target.with_suffix(target.suffix+'.partial')
        try:
            with p.open('rb') as source,gzip.open(partial,'wb') as dest:shutil.copyfileobj(source,dest)
            with gzip.open(partial,'rb') as stream:
                h=hashlib.sha256()
                for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=digest(p):raise ValueError('Archive verification failed')
            os.replace(partial,target);p.unlink();print('ARCHIVED',target)
        finally:partial.unlink(missing_ok=True)

def backup_config():
    source=BASE/'app-config';target=BASE/'backups'/('veriqta-config-'+stamp()+'.tar.gz')
    partial=target.with_suffix(target.suffix+'.partial')
    source_hashes={}
    try:
        with tarfile.open(partial,'w:gz') as archive:
            for p in sorted(source.rglob('*')):
                if p.is_symlink():raise ValueError('Symlinks are not supported in this practice backup')
                if p.is_file():
                    rel=p.relative_to(source).as_posix();source_hashes[rel]=digest(p)
                    archive.add(p,arcname=rel,recursive=False)
        if not source_hashes:raise ValueError('Backup input is empty')
        os.replace(partial,target)
        metadata={'archive':target.name,'created_at':now(),'sha256':digest(target),'files':source_hashes,'restore_verified':False}
        save(str(target)+'.json',metadata)
        verify_backup(target)
        print('BACKUP',target);return target
    finally:partial.unlink(missing_ok=True)

def verify_backup(path):
    path=scoped(path,BASE/'backups');meta_path=Path(str(path)+'.json')
    meta=json.loads(meta_path.read_text())
    if digest(path)!=meta['sha256']:raise ValueError('Backup content differs from its recorded digest')
    # Extract only regular files under a new isolated directory; never extract links/devices.
    with tempfile.TemporaryDirectory(prefix='veriqta-',dir=BASE/'restore-tests') as directory:
        dest=Path(directory);seen=set()
        with tarfile.open(path,'r:gz') as archive:
            for member in archive.getmembers():
                rel=Path(member.name)
                if not member.isfile() or rel.is_absolute() or '..' in rel.parts or member.name in seen:
                    raise ValueError('Unexpected archive member')
                if member.name not in meta['files']:raise ValueError('Unexpected file')
                seen.add(member.name);out=scoped(dest/rel,dest);out.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as source,out.open('wb') as target:shutil.copyfileobj(source,target)
                if digest(out)!=meta['files'][member.name]:raise ValueError('Restored content differs')
        if seen!=set(meta['files']):raise ValueError('Missing backup members')
    meta['restore_verified']=True;meta['verified_at']=now();save(meta_path,meta)
    print('VERIFIED',path.name)

def latest_backup():
    files=sorted((BASE/'backups').glob('veriqta-config-*.tar.gz'),key=lambda p:p.stat().st_mtime)
    if not files:raise FileNotFoundError('Create a configuration backup first')
    return files[-1]

def retention(apply=False):
    s=settings();keep=int(s['retain_at_least']);days=int(s['retention_days'])
    if keep<1 or days<1:raise ValueError('Invalid retention settings')
    candidates=[]
    for meta_path in (BASE/'backups').glob('*.json'):
        if meta_path.is_symlink():continue
        meta=json.loads(meta_path.read_text());p=scoped(BASE/'backups'/meta['archive'],BASE/'backups')
        if p.is_file() and meta.get('restore_verified') and digest(p)==meta['sha256']:
            candidates.append((p,meta_path))
    # Apply retention separately to configuration archives and PostgreSQL dumps.
    for suffix in ['.tar.gz','.dump']:
        group=sorted([(p,m) for p,m in candidates if p.name.endswith(suffix)],key=lambda pair:pair[0].stat().st_mtime,reverse=True)
        if not group:continue
        # Require a recent verified backup before removing old history.
        if group[0][0].stat().st_mtime<time.time()-days*86400:
            print('RETAIN_ALL no recent verified backup',suffix);continue
        for p,m in group[keep:]:
            if p.stat().st_mtime<time.time()-days*86400:
                print('DELETE' if apply else 'WOULD_DELETE',p)
                if apply:p.unlink();m.unlink()

def command(args,timeout=30,env=None):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout,env=env)
    if result.returncode:
        # Tool output may contain resource names; inspect detailed errors locally as needed.
        raise RuntimeError(Path(args[0]).name+' failed with exit '+str(result.returncode))
    return result.stdout

def pg_backup():
    required=['PGHOST','PGDATABASE','PGUSER','PGPASSFILE']
    if any(not os.environ.get(k) for k in required):raise ValueError('Set PGHOST, PGDATABASE, PGUSER, PGPASSFILE')
    password=Path(os.environ['PGPASSFILE'])
    if not password.is_file() or stat.S_IMODE(password.stat().st_mode)&0o077:raise ValueError('PGPASSFILE must be a private file (0600)')
    target=BASE/'backups'/('veriqta-postgres-'+stamp()+'.dump');partial=Path(str(target)+'.partial')
    try:
        command(['pg_dump','--no-password','--format=custom','--file',str(partial)],timeout=120)
        command(['pg_restore','--list',str(partial)],timeout=30)
        if not partial.stat().st_size:raise ValueError('Empty database backup')
        os.replace(partial,target)
        save(str(target)+'.json',{'archive':target.name,'created_at':now(),'sha256':digest(target),'restore_verified':False})
        print('PG_BACKUP',target)
    finally:partial.unlink(missing_ok=True)

def pg_restore_test(path):
    path=scoped(path,BASE/'backups')
    if not path.name.endswith('.dump'):raise ValueError('Select a custom-format dump')
    meta_path=Path(str(path)+'.json');meta=json.loads(meta_path.read_text())
    if digest(path)!=meta['sha256']:raise ValueError('Database backup digest mismatch')
    # PG* environment must target an isolated test server and a restore-capable role.
    name='veriqta_restore_'+uuid.uuid4().hex[:12]
    command(['createdb','--no-password',name])
    try:
        command(['pg_restore','--no-password','--exit-on-error','--no-owner','--no-privileges','--dbname',name,str(path)],timeout=120)
        result=command(['psql','--no-password','--dbname',name,'--tuples-only','--no-align','--command','SELECT count(*) FROM public.veriqta_events;'])
        if int(result.strip())!=2:raise ValueError('Expected two demonstration rows after restore')
        meta['restore_verified']=True;meta['verified_at']=now();save(meta_path,meta);print('PG_RESTORE_VERIFIED',path.name)
    finally:command(['dropdb','--no-password',name])

def probe(url,timeout):
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an HTTP(S) URL without embedded credentials')
    try:
        with urlopen(Request(url,headers={'User-Agent':'veriqta-cron/1.0'}),timeout=timeout) as response:
            status=response.status;body=response.read(4097)
    except HTTPError as exc:
        status=exc.code;exc.close();return status,None
    except (URLError,TimeoutError,OSError):return 0,None
    try:data=json.loads(body) if len(body)<=4096 else None
    except (ValueError,UnicodeError):data=None
    return status,data

def health(retry=False):
    s=settings();attempts=int(s['retry_attempts']) if retry else 1
    delay=float(s['retry_base_seconds']);timeout=float(s['http_timeout_seconds'])
    if not 1<=attempts<=5 or not 0<=delay<=10 or not 0<timeout<=10:raise ValueError('Invalid HTTP limits')
    for attempt in range(1,attempts+1):
        status,data=probe(s['health_url'],timeout)
        print(json.dumps({'attempt':attempt,'http_status':status,'healthy':status==200 and isinstance(data,dict) and data.get('status')=='ok'}))
        if status==200 and isinstance(data,dict) and data.get('status')=='ok':return
        if status not in {0,408,429,500,502,503,504} or attempt==attempts:break
        time.sleep(min(delay*2**(attempt-1),10))
    raise RuntimeError('Health request did not satisfy the status/body contract')

def report():
    totals={}
    with (BASE/'sales.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            quantity=int(row['quantity']);price=Decimal(row['unit_price'])
            if quantity<0 or price<0:raise ValueError('Negative quantity or price')
            totals[row['product']]=totals.get(row['product'],Decimal('0'))+quantity*price
    if not totals:raise ValueError('No report input rows')
    target=BASE/'reports'/('veriqta-report-'+stamp()+'.csv');temp=Path(str(target)+'.partial')
    try:
        with temp.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['product','revenue'])
            for product,total in sorted(totals.items()):writer.writerow([product,f'{total:.2f}'])
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    print('REPORT',target)

def docker_report(storage=False):
    if storage:
        commands=[['docker','system','df','-v'],['docker','image','ls','--filter','dangling=true'],['docker','container','ls','-a','--filter','status=exited']]
    else:
        commands=[['docker','ps','-a','--format','table {{.Names}}\t{{.Status}}\t{{.Image}}'],['docker','stats','--no-stream']]
    text='\n'.join(command(args,timeout=30) for args in commands)
    target=BASE/'reports'/('veriqta-docker-'+('storage-' if storage else 'health-')+stamp()+'.txt')
    atomic_text(target,text);print('DOCKER_REPORT',target)

def aws_json(args,region):
    env=dict(os.environ,AWS_PAGER='',AWS_CLI_AUTO_PROMPT='off',AWS_RETRY_MODE='standard',AWS_MAX_ATTEMPTS='2')
    return json.loads(command(['aws',*args,'--region',region,'--output','json','--cli-connect-timeout','3','--cli-read-timeout','10'],timeout=60,env=env))
def aws_inventory():
    region=settings()['aws_region'];result={'region':region,'captured_at':now()}
    result['identity']=aws_json(['sts','get-caller-identity'],region)
    for key,args in [('ec2',['ec2','describe-instances']),('s3',['s3api','list-buckets']),('rds',['rds','describe-db-instances']),('lambda',['lambda','list-functions'])]:
        result[key]=aws_json(args,region)
    p=BASE/'reports'/('veriqta-inventory-'+stamp()+'.json');save(p,result);print('AWS_INVENTORY',p)
def cost_rows(data):
    rows=[]
    for window in data.get('ResultsByTime',[]):
        for group in window.get('Groups',[]):
            metric=group['Metrics']['UnblendedCost']
            rows.append([window['TimePeriod']['Start'],group['Keys'][0],metric['Amount'],metric['Unit'],str(window.get('Estimated',False)).lower()])
    return rows

def aws_cost():
    end=datetime.now(timezone.utc).date();start=end-timedelta(days=1)
    args=['ce','get-cost-and-usage','--time-period',f'Start={start},End={end}','--granularity','DAILY','--metrics','UnblendedCost','--group-by','Type=DIMENSION,Key=SERVICE']
    result=aws_json(args,'us-east-1');base=BASE/'reports'/('veriqta-cost-'+stamp())
    save(str(base)+'.json',result)
    temp=Path(str(base)+'.csv.partial');target=Path(str(base)+'.csv')
    try:
        with temp.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['date','service','unblended_cost','unit','estimated']);writer.writerows(cost_rows(result))
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    print('AWS_COST',target)

def notify(subject,body,deliver=False):
    s=settings();msg=EmailMessage();msg['Subject']=subject
    msg['From']=s['alert_sender'] or 'veriqta@localhost';msg['To']=s['alert_recipient'] or 'operator@localhost'
    msg.set_content(body)
    target=BASE/'outbox'/('veriqta-alert-'+stamp()+'.eml');atomic_text(target,msg.as_string())
    print('ALERT_SAVED',target)
    if deliver:
        if not s['alert_recipient'] or not s['alert_sender']:raise ValueError('Configure alert sender and recipient before delivery')
        result=subprocess.run([s['sendmail_path'],'-t','-oi'],input=msg.as_string(),text=True,timeout=15)
        if result.returncode:raise RuntimeError('Mail relay rejected alert')
        print('ALERT_SUBMITTED_TO_RELAY')

def watch(job,max_age,deliver=False):
    if not job or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in job):raise ValueError('Invalid job name')
    if max_age<=0:raise ValueError('Age must be positive')
    p=BASE/'state'/(job+'.success.json')
    try:
        data=json.loads(p.read_text());last=datetime.fromisoformat(data['finished_at'].replace('Z','+00:00'))
        if last.tzinfo is None:raise ValueError('Ambiguous success timestamp')
        age=(datetime.now(timezone.utc)-last).total_seconds()
        reason='success timestamp is in the future' if age < -60 else 'last success is too old' if age>max_age else ''
    except (FileNotFoundError,ValueError,KeyError,TypeError):reason='no valid successful execution record'
    if reason:
        notify('Veriqta missed run: '+job,reason,deliver);raise RuntimeError(reason)
    print('FRESH',job,round(age,1),'seconds since success')

def audit():
    paths=[ROOT/'bin',ROOT/'code',ROOT/'config']
    for parent in paths:
        for p in [parent,*parent.rglob('*')]:
            mode=p.lstat().st_mode
            if stat.S_ISLNK(mode):print('REVIEW_SYMLINK',p)
            if mode&0o002:print('WORLD_WRITABLE',p)
    # Print only matching file/line locations, never a possible secret value.
    import re
    pattern=re.compile(r'(password|secret|api[_-]?key|token)\s*[:=]',re.I)
    for p in (ROOT/'config').glob('*'):
        if p.is_file() and not p.is_symlink():
            for number,line in enumerate(p.read_text().splitlines(),1):
                if pattern.search(line):print('REVIEW_SECRET_LOCATION',p,number)
    print('Review crontab -l and system cron locations separately; absence of findings is not a complete audit')

def maintenance():
    health(retry=True);disk();path=backup_config();verify_backup(path);report()
    print('Veriqta maintenance completed successfully')

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['init','tick','heartbeat','python','config','disk','clean-temp','archive-logs','rotate','backup','verify','pg-backup','pg-restore-test','retention','health','retry-health','report','clean-exports','docker-health','docker-storage','aws-inventory','aws-cost','notify','watch','audit','maintenance','fail','slow'])
    p.add_argument('--apply',action='store_true');p.add_argument('--archive');p.add_argument('--days',type=int)
    p.add_argument('--job',default='maintenance');p.add_argument('--max-age',type=float,default=93600)
    p.add_argument('--deliver',action='store_true');p.add_argument('--seconds',type=float,default=5)
    a=p.parse_args()
    if a.action=='init':init();return
    if not (ROOT/'config/settings.json').exists():p.error('Run init first')
    actions={'tick':tick,'heartbeat':heartbeat,'python':tick,'config':config_report,'disk':disk,
      'clean-temp':lambda:cleanup('tmp',a.apply,a.days),'archive-logs':lambda:archive_logs(a.days or 30),
      'rotate':lambda:print(command(['logrotate','--state',str(BASE/'state/logrotate.state'),str(BASE/'logrotate.conf')])),
      'backup':backup_config,'verify':lambda:verify_backup(a.archive or latest_backup()),
      'pg-backup':pg_backup,'pg-restore-test':lambda:pg_restore_test(a.archive or ''),
      'retention':lambda:retention(a.apply),'health':health,'retry-health':lambda:health(True),
      'report':report,'clean-exports':lambda:cleanup('exports',a.apply,a.days),
      'docker-health':docker_report,'docker-storage':lambda:docker_report(True),
      'aws-inventory':aws_inventory,'aws-cost':aws_cost,
      'notify':lambda:notify('Veriqta alert delivery test','Veriqta test message; no production incident.',a.deliver),
      'watch':lambda:watch(a.job,a.max_age,a.deliver),'audit':audit,'maintenance':maintenance,
      'fail':lambda:sys.exit(7),'slow':lambda:time.sleep(a.seconds)}
    actions[a.action]()
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr);sys.exit(1)
```

## File: `code/demo_server.py`

```python
"""Loopback-only endpoint for health-check exercises."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status=503 if (ROOT/'runtime/unhealthy').exists() else 200
        if self.path!='/health':status=404
        body=json.dumps({'status':'ok' if status==200 else 'unavailable','service':'veriqta-demo'}).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
if __name__=='__main__':
    print('Veriqta health endpoint: http://127.0.0.1:8050/health',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',8050),Handler)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
```

## File: `code/notify_channels.py`

```python
"""Optional Slack/Telegram delivery. Preview is the default; credentials stay in environment."""
import argparse
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import cookbook as cb

def payload(channel,text):
    if channel=='slack':
        url=os.environ.get('SLACK_WEBHOOK_URL','')
        if not url.startswith('https://hooks.slack.com/services/'):raise ValueError('Set a Slack incoming webhook URL')
        return url,{'text':text}
    token=os.environ.get('TELEGRAM_BOT_TOKEN','');chat=os.environ.get('TELEGRAM_CHAT_ID','')
    if not token or not chat:raise ValueError('Set Telegram token and chat ID')
    if any(c not in '0123456789:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-' for c in token):raise ValueError('Invalid bot token format')
    return 'https://api.telegram.org/bot'+token+'/sendMessage',{'chat_id':chat,'text':text}
def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('channel',choices=['slack','telegram']);p.add_argument('--text',default='Veriqta scheduled-job notification test');p.add_argument('--deliver',action='store_true');a=p.parse_args()
    if not a.deliver:
        cb.save(cb.BASE/'outbox'/('veriqta-'+a.channel+'-'+cb.stamp()+'.json'),{'channel':a.channel,'text':a.text})
        print('Preview saved; nothing sent');return
    url,data=payload(a.channel,a.text)
    # Do not log URLs or exception text: bot tokens/webhook secrets are part of the URL.
    try:
        with urlopen(Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'}),timeout=10) as response:
            raw=response.read(65536)
            if response.status!=200:raise ValueError('Notification endpoint rejected request')
        if a.channel=='telegram' and not json.loads(raw).get('ok'):raise ValueError('Telegram rejected request')
        print('Notification accepted; confirm receipt in the destination')
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):raise SystemExit('Notification delivery failed; check protected provider configuration')
if __name__=='__main__':main()
```

## File: `code/render_crontab.py`

```python
"""Print a user-crontab block. Never installs or replaces a crontab."""
import argparse
from pathlib import Path
import shlex
import sys
ROOT=Path(__file__).resolve().parents[1]

def render(profile='first',python=None):
    python=python or sys.executable
    if not Path(python).is_absolute():raise ValueError('Python path must be absolute')
    for path in [str(ROOT),python]:
        if '\n' in path or '\r' in path or '\\' in path:raise ValueError('Use a path without newlines or backslashes')
    def line(schedule,args,log):
        cmd=shlex.join([python,*args])+' >> '+shlex.quote(str(ROOT/'runtime/logs'/log))+' 2>&1'
        # Cron interprets percent signs before the command reaches its shell.
        return schedule+' '+cmd.replace('%',r'\%')
    run=str(ROOT/'code/run_job.py');task=str(ROOT/'code/cookbook.py')
    lines=['# BEGIN VERIQTA '+profile,'SHELL=/bin/sh','PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin']
    if profile=='first':
        lines += [line('* * * * *',[run,'tick','--','tick'],'scheduler.log'),line('*/5 * * * *',[run,'heartbeat','--','heartbeat'],'scheduler.log')]
    elif profile=='health':
        lines += [line('*/5 * * * *',[run,'health','--timeout','30','--','retry-health'],'scheduler.log')]
    elif profile=='maintenance':
        lines += [line('0 2 * * *',[run,'maintenance','--timeout','120','--','maintenance'],'scheduler.log'),line('0 * * * *',[task,'watch','--job','maintenance','--max-age','93600'],'monitor.log')]
    elif profile.startswith('recipe'):
        number=int(profile[6:])
        recipes={
          1:('* * * * *','tick'),2:('*/5 * * * *','heartbeat'),3:('*/5 * * * *','python'),
          4:('0 * * * *','config'),5:('*/10 * * * *','disk'),6:('0 2 * * *','clean-temp'),
          7:('0 0 * * *','rotate'),8:('30 0 * * *','archive-logs'),9:('0 2 * * *','backup'),
          10:('15 2 * * *','verify'),11:('0 2 * * *','pg-backup'),12:('30 3 * * *','retention'),
          13:('*/5 * * * *','health'),14:('*/5 * * * *','health'),15:('0 1 * * *','report'),
          16:('0 2 * * *','clean-exports'),17:('0 2 * * *','maintenance'),18:('0 2 * * *','maintenance'),
          19:('*/10 * * * *','retry-health'),20:('*/10 * * * *','retry-health'),
          21:('*/15 * * * *','docker-health'),22:('0 4 * * *','docker-storage'),
          23:('0 2 * * *','aws-inventory'),24:('0 3 * * *','aws-cost'),
          26:('0 1 * * *','report'),27:('0 1 * * *','report'),28:('0 1 * * *','report'),
          29:('0 * * * *','watch'),30:('0 6 * * 1','audit')}
        if number not in recipes:raise ValueError('Recipe 25 uses Kubernetes; select a host recipe')
        schedule,action=recipes[number]
        limit='400' if number==23 else '180' if number==11 else '120' if number in {17,18} else '60'
        if number==29:
            lines += [line(schedule,[task,'watch','--job','maintenance','--max-age','93600'],'monitor.log')]
        else:
            lines += [line(schedule,[run,'recipe'+str(number).zfill(2),'--timeout',limit,'--',action],'scheduler.log')]
    else:raise ValueError('Unknown profile')
    lines+=['# END VERIQTA '+profile]
    return '\n'.join(lines)+'\n'
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=['first','health','maintenance']+['recipe'+str(i).zfill(2) for i in range(1,31) if i!=25],default='first');a=p.parse_args()
    print(render(a.profile),end='')
```

## File: `code/render_logrotate.py`

```python
"""Render a standalone logrotate configuration for the short-lived task logs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if any(c in str(ROOT) for c in ['"','\n','\r']):raise SystemExit('Use a path without quotes or newlines')
print('"'+str(ROOT/'runtime/logs/*.log')+'" "'+str(ROOT/'runtime/logs/*.jsonl')+'" {')
print('    daily\n    rotate 7\n    compress\n    delaycompress\n    missingok\n    notifempty\n    create 0600\n}')
```

## File: `code/run_job.py`

```python
"""Run one cookbook task with a lock, runtime limit, logs and success evidence."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid
import cookbook as cb


def event(path,**fields):
    row={'timestamp':cb.now(),'service':'veriqta-cron',**fields}
    raw=(json.dumps(row,ensure_ascii=True)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:os.write(fd,raw)
    finally:os.close(fd)


class StopRequested(Exception):
    pass

def stop_child(child):
    if child.poll() is not None:return
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()

def execute(job,args,limit=60,deliver=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',job):raise ValueError('Invalid job name')
    if not 0<limit<=3600:raise ValueError('Runtime limit must be 0..3600 seconds')
    if not args or args[0] in {'init'}:raise ValueError('Specify a cookbook task after --')
    os.umask(0o077)
    for folder in ['logs','locks','state','outbox']:(cb.BASE/folder).mkdir(parents=True,exist_ok=True)
    path=cb.BASE/'logs'/(job+'.jsonl');raw_path=cb.BASE/'logs'/(job+'.log')
    with (cb.BASE/'locks'/(job+'.lock')).open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            event(path,event='skipped',job=job,reason='lock_held',exit_code=75);return 75
        run=uuid.uuid4().hex;started=time.monotonic()
        event(path,event='start',job=job,run_id=run)
        rc=1
        try:
            with raw_path.open('ab') as output:
                with subprocess.Popen([sys.executable,str(cb.ROOT/'code/cookbook.py'),*args],
                    cwd=cb.ROOT,stdout=output,stderr=subprocess.STDOUT,start_new_session=True) as child:
                    def interrupted(signum,frame):raise StopRequested(signum)
                    previous={sig:signal.signal(sig,interrupted) for sig in [signal.SIGTERM,signal.SIGINT]}
                    try:
                        try:rc=child.wait(timeout=limit)
                        except subprocess.TimeoutExpired:
                            stop_child(child);rc=124
                        except StopRequested as exc:
                            stop_child(child);rc=128+exc.args[0]
                    finally:
                        for sig,handler in previous.items():signal.signal(sig,handler)
        except OSError as exc:
            event(path,event='launch_failed',job=job,run_id=run,error_type=type(exc).__name__)
        if rc<0:rc=128-rc
        elapsed=round(time.monotonic()-started,3)
        if rc==0:
            try:cb.save(cb.BASE/'state'/(job+'.success.json'),{'job':job,'run_id':run,'finished_at':cb.now()})
            except OSError:
                rc=1;event(path,event='state_write_failed',job=job,run_id=run)
        event(path,event='end',job=job,run_id=run,exit_code=rc,duration_seconds=elapsed)
        if rc:
            try:cb.notify('Veriqta job failed: '+job,f'Job {job} ended with exit {rc}. Inspect its protected execution logs.',deliver)
            except Exception as exc:event(path,event='alert_failed',job=job,run_id=run,error_type=type(exc).__name__)
        print(json.dumps({'job':job,'run_id':run,'exit_code':rc,'duration_seconds':elapsed}))
        return rc


def main():
    # Split wrapper options from task options; the task may have its own flags.
    try:separator=sys.argv.index('--')
    except ValueError:raise SystemExit('Usage: run_job.py JOB [--timeout SECONDS] [--deliver] -- TASK [OPTIONS]')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job');p.add_argument('--timeout',type=float,default=60);p.add_argument('--deliver',action='store_true')
    a=p.parse_args(sys.argv[1:separator])
    return execute(a.job,sys.argv[separator+1:],a.timeout,a.deliver)
if __name__=='__main__':sys.exit(main())
```

## File: `config/inventory-policy.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InventoryReads",
      "Effect": "Allow",
      "Action": ["ec2:DescribeInstances", "s3:ListAllMyBuckets", "rds:DescribeDBInstances", "lambda:ListFunctions"],
      "Resource": "*"
    },
    {
      "Sid": "CostReportRead",
      "Effect": "Allow",
      "Action": "ce:GetCostAndUsage",
      "Resource": "*"
    }
  ]
}
```

## File: `config/msmtprc.example`

```text
defaults
auth on
tls on
tls_starttls on
tls_trust_file /etc/ssl/certs/ca-certificates.crt

account veriqta
host YOUR_SMTP_HOST
port 587
from YOUR_VERIFIED_SENDER
user YOUR_SMTP_USERNAME
passwordeval "cat /ABSOLUTE/PATH/TO/PRIVATE/mail-password"

account default : veriqta
```

## File: `config/settings.example.json`

```json
{
  "app_name": "veriqta",
  "environment": "practice",
  "health_url": "http://127.0.0.1:8050/health",
  "disk_threshold_percent": 80,
  "http_timeout_seconds": 3,
  "retry_attempts": 3,
  "retry_base_seconds": 1,
  "retention_days": 30,
  "retain_at_least": 2,
  "aws_region": "us-east-1",
  "alert_recipient": "",
  "alert_sender": "",
  "sendmail_path": "/usr/sbin/sendmail"
}
```

## File: `exercises/incident-report.md`

```markdown
# Scheduled task incident

- Expected job, schedule, timezone, identity, and output:
- Observed behavior and user impact:
- First failure or missed-success time:
- Timeline with UTC timestamps and evidence:
- Root cause and contributing conditions:
- Targeted correction:
- Manual verification:
- Verification under the scheduler identity/environment:
- Next scheduled execution and output verification:
- Alert and missed-run verification:
- Prevention action, owner, and completion check:
```

## File: `exercises/job-register.md`

```markdown
# Scheduled job register

| Job | Purpose | Owner | Execution identity | Schedule and timezone | Maximum runtime | Last-success deadline | Output to verify | Alert route | Recovery action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | | |

For each job, record input dependencies, required permissions, lock scope, retry policy, retention rules, and cleanup. Test one failure and one missed execution. Record notification receipt and the result of a restore exercise where backups are involved.
```

## File: `kubernetes/cronjob.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: veriqta-cron
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: veriqta-backup
  namespace: veriqta-cron
spec:
  schedule: "0 2 * * *"
  timeZone: "Etc/UTC"
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 300
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      activeDeadlineSeconds: 60
      template:
        spec:
          restartPolicy: Never
          automountServiceAccountToken: false
          securityContext:
            runAsNonRoot: true
            runAsUser: 10001
            runAsGroup: 10001
            fsGroup: 10001
          containers:
            - name: backup
              image: alpine:3.22
              command:
                - /bin/sh
                - -ec
                - |
                  mkdir -p /work/source /work/restore
                  printf '%s\n' 'Veriqta configuration demonstration' > /work/source/app.conf
                  tar -czf /work/backup.tar.gz -C /work/source app.conf
                  tar -xzf /work/backup.tar.gz -C /work/restore
                  cmp /work/source/app.conf /work/restore/app.conf
                  printf '%s\n' 'Veriqta backup round trip verified'
              resources:
                requests: {cpu: 20m, memory: 16Mi}
                limits: {cpu: 100m, memory: 64Mi}
              securityContext:
                allowPrivilegeEscalation: false
                readOnlyRootFilesystem: true
                capabilities: {drop: [ALL]}
              volumeMounts:
                - {name: work, mountPath: /work}
          volumes:
            - name: work
              emptyDir: {}
```

## File: `kubernetes/persistent-backup.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: veriqta-backup-source
  namespace: veriqta-cron
data:
  app.conf: |
    application=veriqta
    environment=practice
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: veriqta-backups
  namespace: veriqta-cron
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: veriqta-persistent-backup
  namespace: veriqta-cron
spec:
  schedule: "0 2 * * *"
  timeZone: "Etc/UTC"
  concurrencyPolicy: Forbid
  startingDeadlineSeconds: 300
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      activeDeadlineSeconds: 120
      template:
        spec:
          restartPolicy: Never
          automountServiceAccountToken: false
          securityContext:
            runAsNonRoot: true
            runAsUser: 10001
            runAsGroup: 10001
            fsGroup: 10001
          containers:
            - name: backup
              image: alpine:3.22
              env:
                - name: POD_UID
                  valueFrom:
                    fieldRef:
                      fieldPath: metadata.uid
              command:
                - /bin/sh
                - -ec
                - |
                  archive="/backups/veriqta-config-${POD_UID}.tar.gz"
                  tar -czf "${archive}.partial" -C /source app.conf
                  mv "${archive}.partial" "$archive"
                  tar -xzf "$archive" -C /work
                  cmp /source/app.conf /work/app.conf
                  printf 'Veriqta persistent archive verified: %s\n' "$archive"
              resources:
                requests: {cpu: 20m, memory: 16Mi}
                limits: {cpu: 100m, memory: 64Mi}
              securityContext:
                allowPrivilegeEscalation: false
                readOnlyRootFilesystem: true
                capabilities: {drop: [ALL]}
              volumeMounts:
                - {name: source, mountPath: /source, readOnly: true}
                - {name: backups, mountPath: /backups}
                - {name: work, mountPath: /work}
          volumes:
            - name: source
              configMap:
                name: veriqta-backup-source
            - name: backups
              persistentVolumeClaim:
                claimName: veriqta-backups
            - name: work
              emptyDir: {}
```

## File: `tests/test_cookbook.py`

```python
"""Offline behavior tests. All mutable files live in temporary directories."""
import contextlib
import csv
from datetime import datetime,timedelta,timezone
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
CODE=Path(__file__).resolve().parents[1]/'code'
sys.path.insert(0,str(CODE))
import cookbook as cb
import render_crontab as cron

class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'config').mkdir();shutil.copyfile(CODE.parent/'config/settings.example.json',self.root/'config/settings.example.json')
        self.root_patch=patch.object(cb,'ROOT',self.root);self.base_patch=patch.object(cb,'BASE',self.root/'runtime')
        self.root_patch.start();self.base_patch.start()
        with contextlib.redirect_stdout(io.StringIO()):cb.init()
    def tearDown(self):self.base_patch.stop();self.root_patch.stop();self.tmp.cleanup()
    def quiet(self,fn,*args,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):return fn(*args,**kwargs)
    def test_init_preserves_configuration(self):
        p=self.root/'config/settings.json';p.write_text('{"preserved":true}')
        self.quiet(cb.init);self.assertTrue(json.loads(p.read_text())['preserved'])
    def test_backup_round_trip(self):
        path=self.quiet(cb.backup_config);meta=json.loads(Path(str(path)+'.json').read_text())
        self.assertTrue(meta['restore_verified']);self.assertEqual(set(meta['files']),{'app.json'})
    def test_backup_corruption_detected(self):
        path=self.quiet(cb.backup_config);path.write_bytes(path.read_bytes()+b'corrupt')
        with self.assertRaisesRegex(ValueError,'digest'):cb.verify_backup(path)
    def test_backup_rejects_symlink_input(self):
        (cb.BASE/'app-config/link').symlink_to(cb.BASE/'sales.csv')
        with self.assertRaises(ValueError):cb.backup_config()
    def test_archive_traversal_rejected(self):
        path=cb.BASE/'backups/bad.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            member=tarfile.TarInfo('../escape');member.size=1;archive.addfile(member,io.BytesIO(b'x'))
        cb.save(str(path)+'.json',{'sha256':cb.digest(path),'files':{'../escape':cb.digest(path)}})
        with self.assertRaises(ValueError):cb.verify_backup(path)
    def test_cleanup_preview_does_not_delete(self):
        p=cb.BASE/'tmp/old.log';p.write_text('old');os.utime(p,(1,1))
        self.quiet(cb.cleanup,'tmp',False,7);self.assertTrue(p.exists())
    def test_cleanup_apply_scoped(self):
        old=cb.BASE/'tmp/old.log';new=cb.BASE/'tmp/new.log';other=cb.BASE/'tmp/old.txt'
        for p in [old,new,other]:p.write_text('x')
        os.utime(old,(1,1));os.utime(other,(1,1));self.quiet(cb.cleanup,'tmp',True,7)
        self.assertFalse(old.exists());self.assertTrue(new.exists());self.assertTrue(other.exists())
    def test_cleanup_skips_symlink(self):
        target=self.root/'external.log';target.write_text('keep');os.utime(target,(1,1))
        (cb.BASE/'tmp/link.log').symlink_to(target);self.quiet(cb.cleanup,'tmp',True,1);self.assertTrue(target.exists())
    def test_report_totals(self):
        self.quiet(cb.report);p=next((cb.BASE/'reports').glob('*.csv'))
        with p.open() as stream:rows=list(csv.DictReader(stream))
        self.assertEqual({r['product']:r['revenue'] for r in rows},{'Notebook':'10.00','Pen':'4.50'})
    def test_retention_preserves_minimum(self):
        paths=[self.quiet(cb.backup_config) for _ in range(3)]
        for p in paths[:2]:os.utime(p,(1,1))
        self.quiet(cb.retention,True)
        self.assertEqual(sum(p.exists() for p in paths),2)
    def test_retention_preserves_unverified(self):
        paths=[self.quiet(cb.backup_config) for _ in range(3)]
        old=paths[0];os.utime(old,(1,1));meta=Path(str(old)+'.json');data=json.loads(meta.read_text());data['restore_verified']=False;cb.save(meta,data)
        self.quiet(cb.retention,True);self.assertTrue(old.exists())
    def test_retention_requires_recent_copy(self):
        paths=[self.quiet(cb.backup_config) for _ in range(3)]
        for p in paths:os.utime(p,(1,1))
        self.quiet(cb.retention,True);self.assertTrue(all(p.exists() for p in paths))
    def test_alert_saved_without_delivery(self):
        self.quiet(cb.notify,'Veriqta test','body')
        self.assertEqual(len(list((cb.BASE/'outbox').glob('*.eml'))),1)
    def test_delivery_requires_configuration(self):
        with self.assertRaises(ValueError):self.quiet(cb.notify,'test','body',True)
    def test_missing_success_alert(self):
        with self.assertRaises(RuntimeError):self.quiet(cb.watch,'never-ran',60)
        self.assertEqual(len(list((cb.BASE/'outbox').glob('*.eml'))),1)
    def test_fresh_success(self):
        cb.save(cb.BASE/'state/task.success.json',{'finished_at':cb.now()});self.quiet(cb.watch,'task',60)
    def test_stale_success(self):
        cb.save(cb.BASE/'state/task.success.json',{'finished_at':'2000-01-01T00:00:00Z'})
        with self.assertRaises(RuntimeError):self.quiet(cb.watch,'task',60)
    def test_future_timestamp_is_not_healthy(self):
        stamp=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        cb.save(cb.BASE/'state/task.success.json',{'finished_at':stamp})
        with self.assertRaises(RuntimeError):self.quiet(cb.watch,'task',60)
    def test_http_contract_requires_body(self):
        with patch.object(cb,'probe',return_value=(200,{'status':'wrong'})):
            with self.assertRaises(RuntimeError):self.quiet(cb.health)
    def test_transient_retry_succeeds(self):
        with patch.object(cb,'probe',side_effect=[(503,None),(200,{'status':'ok'})]) as probe,patch.object(cb.time,'sleep') as sleep:
            self.quiet(cb.health,True);self.assertEqual(probe.call_count,2);sleep.assert_called_once_with(1)
    def test_permanent_http_error_not_retried(self):
        with patch.object(cb,'probe',return_value=(403,None)) as probe:
            with self.assertRaises(RuntimeError):self.quiet(cb.health,True)
            self.assertEqual(probe.call_count,1)
    def test_cost_json_to_csv_rows(self):
        data={'ResultsByTime':[{'TimePeriod':{'Start':'2026-01-15'},'Estimated':True,'Groups':[{'Keys':['Amazon EC2'],'Metrics':{'UnblendedCost':{'Amount':'1.25','Unit':'USD'}}}]}]}
        self.assertEqual(cb.cost_rows(data),[['2026-01-15','Amazon EC2','1.25','USD','true']])
    def test_scoped_rejects_outside(self):
        with self.assertRaises(ValueError):cb.scoped(self.root/'outside',cb.BASE)
    def test_catalog_check_does_not_fake_restore(self):
        # Retention only trusts an explicit successful restore record, not file size alone.
        p=cb.BASE/'backups/veriqta-postgres-test.dump';p.write_bytes(b'not a real dump')
        cb.save(str(p)+'.json',{'archive':p.name,'sha256':cb.digest(p),'restore_verified':False})
        os.utime(p,(1,1));self.quiet(cb.retention,True);self.assertTrue(p.exists())

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        shutil.copytree(CODE,self.root/'code',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(CODE.parent/'config',self.root/'config')
        subprocess.run([sys.executable,str(self.root/'code/cookbook.py'),'init'],check=True,capture_output=True)
    def tearDown(self):self.tmp.cleanup()
    def run_task(self,job,task,limit='5'):
        return subprocess.run([sys.executable,str(self.root/'code/run_job.py'),job,'--timeout',limit,'--',*task],capture_output=True,text=True,timeout=10)
    def test_success_written(self):
        r=self.run_task('tick',['tick']);self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue((self.root/'runtime/state/tick.success.json').exists())
    def test_failure_propagated(self):
        r=self.run_task('failed',['fail']);self.assertEqual(r.returncode,7,r.stderr)
        self.assertFalse((self.root/'runtime/state/failed.success.json').exists())
        self.assertEqual(len(list((self.root/'runtime/outbox').glob('*.eml'))),1)
    def test_timeout_propagated(self):
        r=self.run_task('slow',['slow','--seconds','2'],'0.2');self.assertEqual(r.returncode,124,r.stderr)
    def test_lock_conflict_skips(self):
        lock=self.root/'runtime/locks/shared.lock'
        with lock.open('w') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            result=self.run_task('shared',['tick']);self.assertEqual(result.returncode,75,result.stderr)
        self.assertFalse((self.root/'runtime/state/shared.success.json').exists())
    def test_logs_are_valid_json(self):
        self.run_task('tick',['tick'])
        rows=[json.loads(line) for line in (self.root/'runtime/logs/tick.jsonl').read_text().splitlines()]
        self.assertEqual([r['event'] for r in rows],['start','end'])
        self.assertEqual(rows[-1]['exit_code'],0)

class ScheduleTests(unittest.TestCase):
    def test_no_install_side_effect(self):
        text=cron.render('first',sys.executable)
        self.assertIn('* * * * *',text);self.assertNotIn('crontab -',text)
    def test_maintenance_has_independent_watch(self):
        text=cron.render('maintenance',sys.executable)
        self.assertIn('0 2 * * *',text);self.assertIn('--max-age 93600',text)
    def test_percent_in_path_escaped(self):
        with patch.object(cron,'ROOT',Path('/tmp/Veriqta%Practice')):
            self.assertIn(r'Veriqta\%Practice',cron.render('first',sys.executable))
    def test_relative_python_rejected(self):
        with self.assertRaises(ValueError):cron.render('first','python3')
if __name__=='__main__':unittest.main()
```
