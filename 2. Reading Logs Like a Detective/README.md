# Reading Logs Like a Detective

## A Beginner’s Playbook

**VERIQTA**

A failed request is the beginning of an investigation. A useful log entry tells you what happened, where it happened, and which event to inspect next. This handbook develops that habit through application, Linux, web server, container, Kubernetes, and database investigations.

You will build a small application, generate successful and failed requests, follow those requests through several components, and reconstruct an outage from evidence. Each exercise explains the commands, expected observations, and the conclusion the evidence supports.

## Contents

1. [Read logs as evidence](#01-read-logs-as-evidence)
2. [Build your first investigation lab](#02-build-your-first-investigation-lab)
3. [Understand every part of a log entry](#03-understand-every-part-of-a-log-entry)
4. [Find logs on a Linux server](#04-find-logs-on-a-linux-server)
5. [Read files with cat, less, head, and tail](#05-read-files-with-cat-less-head-and-tail)
6. [Watch logs while an application runs](#06-watch-logs-while-an-application-runs)
7. [Search with grep](#07-search-with-grep)
8. [Reconstruct a failure timeline](#08-reconstruct-a-failure-timeline)
9. [Investigate services with journalctl](#09-investigate-services-with-journalctl)
10. [Troubleshoot a service that will not start](#10-troubleshoot-a-service-that-will-not-start)
11. [Investigate HTTP errors with NGINX](#11-investigate-http-errors-with-nginx)
12. [Find the cause of a 502](#12-find-the-cause-of-a-502)
13. [Read Docker logs](#13-read-docker-logs)
14. [Explain why a container exits](#14-explain-why-a-container-exits)
15. [Read Kubernetes Pod logs](#15-read-kubernetes-pod-logs)
16. [Investigate CrashLoopBackOff](#16-investigate-crashloopbackoff)
17. [Correlate events across services](#17-correlate-events-across-services)
18. [Recognize patterns, spikes, and repeated failures](#18-recognize-patterns-spikes-and-repeated-failures)
19. [Work through a complete outage](#19-work-through-a-complete-outage)
20. [Complete the detective challenge](#20-complete-the-detective-challenge)

The [worked answers](#worked-answers), [command reference](#command-reference), and [complete code and configuration](#complete-code-and-configuration) follow the lessons.

## 01. Read logs as evidence

A log is a record of an event produced by software or its operating environment. Applications log requests and exceptions; a database logs startup and query failures; a kernel records device and memory problems. Reading one component rarely explains an entire incident.

Treat every entry as a claim with a time, an origin, and a limited viewpoint. “Connection refused” establishes that a connection attempt was rejected at that moment. It does not establish why the destination was unavailable. The service may have stopped, listened on another port, or been addressed incorrectly.

Use five questions:

1. What did the user experience?
2. When did it start, and in which timezone?
3. Which component recorded the symptom?
4. What happened immediately before it?
5. What additional evidence could confirm or disprove the explanation?

A practical investigation moves from **symptom → affected request → failing component → dependency → trigger → recovery verification**. Keep a timeline rather than a collection of disconnected error messages.

Consider this sequence:

```text
10:15:20Z INFO  Server started
10:16:05Z INFO  Connected to database
10:17:12Z ERROR Connection lost
10:17:30Z INFO  Retrying database connection
10:18:05Z INFO  Connected to database
```

The first connection-loss record is at 10:17:12 UTC. The next connection-success record is 53 seconds later. That interval describes these records; it does not prove every user request failed for exactly 53 seconds. Request logs or monitoring would establish the user impact.

**Practice:** Write one observation, one hypothesis, and one next check. Example: observation: the client lost its database connection; hypothesis: the database restarted; next check: inspect database startup and shutdown logs over the same interval.

## 02. Build your first investigation lab

### Environment

Use Python 3.12 or newer, a Bash-compatible terminal, and `curl`. The core application and analysis exercises use the Python standard library. Flask and database exercises add packages later. Windows readers can use Ubuntu through WSL2. Linux service exercises require a Linux host running systemd. Docker and Kubernetes exercises use their own tools and can be completed separately.

Official setup guides: [Python](https://www.python.org/downloads/), [WSL](https://learn.microsoft.com/windows/wsl/install), [Docker](https://docs.docker.com/get-started/get-docker/), [kubectl](https://kubernetes.io/docs/tasks/tools/), and [kind](https://kind.sigs.k8s.io/docs/user/quick-start/).

Open a terminal in the `Veriqta-Reading-Logs` project directory. Unless a lesson says otherwise, run its commands from this directory. The project contains:

```text
Reading-Logs-Like-a-Detective.md
code/          Application, analysis tools, and infrastructure configurations
datasets/      Ready-made investigation evidence
exercises/     Incident report and worked answers
```

On a new Ubuntu practice machine, install the local tools if needed:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv curl git less
```

`apt update` refreshes package metadata; `apt upgrade` upgrades installed packages and is a separate system-maintenance decision. The virtual environment keeps Flask packages separate from the operating system Python. A local Linux virtual machine is suitable for the systemd lessons; macOS can run the core file and HTTP exercises directly.

Confirm the tools and inspect the prepared data:

```bash
python3 --version
curl --version
python3 code/analyze.py summary datasets/basics.jsonl
```

Expected summary: five events, four `INFO`, one `ERROR`, and zero invalid lines. To recreate the practice datasets, run the following command. It replaces the practice files under `datasets/`; preserve your own evidence elsewhere.

```bash
python3 code/generate_data.py
```

### Start the application

In terminal A:

```bash
python3 code/app.py
```

The listener uses `127.0.0.1:5000`. Terminal output is JSON. The application also writes `logs/app.log` and `logs/app.jsonl`. Keep terminal A running.

In terminal B, from the same project directory:

```bash
curl -i http://127.0.0.1:5000/health
curl -i -H 'X-Request-ID: veriqta-first-request' http://127.0.0.1:5000/api/users
curl -i http://127.0.0.1:5000/missing
curl -i http://127.0.0.1:5000/error
curl -i http://127.0.0.1:5000/slow
```

| Route | Expected status | Evidence |
| --- | --- | --- |
| `/` or `/health` | 200 | Successful response and completion log |
| `/api/users` | 200 | Demo user; later, an optional database query |
| `/missing` | 404 | Unknown route; warning completion record |
| `/error` | 500 | Deliberate exception and error completion record |
| `/slow` | 200 | About 300 ms delay and a warning event |

`curl -i` displays response headers and body. An HTTP 500 response is an intentional exercise result here. Plain `curl` can exit successfully even when the HTTP status is 500; use `--fail-with-body` when a script should treat an HTTP error response as failure.

The completion event also records the peer IP and a bounded, sanitized user agent. Generate five more requests, including a custom client label:

```bash
for i in 1 2 3 4 5; do
  curl -sS -A 'veriqta-practice/1.0' http://127.0.0.1:5000/health
  printf '\n'
done
tail -n 10 logs/app.log
```

Behind NGINX, the peer IP seen by the application is the proxy. Forwarded client-address headers require a configured trust boundary; do not accept them blindly from arbitrary clients. Query strings are deliberately omitted from the logged path.

Stop the application with Ctrl+C in terminal A. If port 5000 is occupied, use `PORT=5002 python3 code/app.py` and change every corresponding application URL and standalone proxy upstream for that exercise.

### Optional Flask application

Stop the standard-library application before starting Flask on the same port:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r code/requirements.txt
python code/flask_app.py
```

The Flask application uses the same routes and shared logging code. Debug mode is disabled. Both local servers are learning tools; a public service needs a suitable production application server, access controls, and deployment configuration.

**Checkpoint:** Generate a 200, a 404, and a 500 response, then find their completion records. Explain why the `/slow` warning can coexist with a successful HTTP response.

## 03. Understand every part of a log entry

A useful text entry might look like this:

```text
2026-01-15T10:17:12Z ERROR [db-client] request_id=veriqta-001 Connection lost
```

| Field | Meaning | Investigation use |
| --- | --- | --- |
| Timestamp | Event time, including timezone | Reconstruct order and select a window |
| Severity | Producer’s classification | Find unusual events without ignoring context |
| Component | Service or subsystem | Locate the next source of evidence |
| Process or container identity | Specific running instance | Separate replicas and restarts |
| Request ID | Identifier carried with a request | Follow a user operation across components |
| Event name | Stable machine-readable category | Count and group repeated behavior |
| Message | Human-readable explanation | Understand the event |
| Status and duration | Outcome and elapsed time | Measure failures and slow responses |

Common levels are `DEBUG`, `INFO`, `WARNING`/`WARN`, `ERROR`, and `CRITICAL`/`FATAL`. Some systems also define `TRACE` for very fine-grained diagnostics; Python does not provide a built-in TRACE level. Their exact use depends on the application. A warning is not automatically a customer incident, and an error message is not automatically the root cause. Debug logs can help diagnose behavior but increase volume and may expose sensitive data.

Structured JSON preserves named fields:

```json
{"timestamp":"2026-01-15T10:17:12Z","level":"ERROR","service":"db-client","event":"db_connection_lost","request_id":"veriqta-001","message":"Connection lost"}
```

JSON Lines, or JSONL, stores one JSON object per physical line. An exception can contain escaped `\n` characters inside a JSON string while remaining one JSONL event. A text traceback may span many lines; a search result containing only its final line can lose the original request and context.

`Z` means UTC. `16:21:15+02:00` and `14:21:15Z` represent the same instant. Never compare local clock strings from different zones without normalization. Even normalized timestamps can be affected by clock skew, buffering, or asynchronous delivery.

```bash
python3 code/analyze.py timeline datasets/mixed-offsets.jsonl
```

Expected order: 14:21:12 UTC, then 14:21:15 UTC. The analyzer rejects timestamps without a zone so an ambiguous local time cannot silently become incident evidence.

## 04. Find logs on a Linux server

Logs may be files, journal entries, container output, or records in a central platform. Find the actual logging configuration before assuming a path exists.

| Common location | Typical contents |
| --- | --- |
| `/var/log/syslog` | General system events on some distributions |
| `/var/log/messages` | General events on other distributions |
| `/var/log/auth.log` or `/var/log/secure` | Authentication and authorization events |
| `/var/log/nginx/access.log` | NGINX request records when configured |
| `/var/log/nginx/error.log` | NGINX operational errors when configured |
| Application-specific directory | Application events and tracebacks |
| systemd journal | Service, kernel, and system records |

Paths differ across distributions and installations. A missing `/var/log/syslog` does not mean the machine has no system logs. Container images often write to standard output and standard error instead of these files.

On a Linux practice host:

```bash
ls -lah /var/log
sudo find /var/log -maxdepth 2 -type f -name '*.log' -print
systemctl status systemd-journald --no-pager
```

Read only the files relevant to your task and account permissions. `sudo` is needed for some protected system records; do not loosen log permissions globally to make a command work.

Practice without administrator access:

```bash
ls -lh datasets
cat datasets/auth.log
```

The practice authentication sequence shows a login attempt, an invalid password, and a later lockout. Do not infer a confirmed intrusion from a few failed logins alone. Look for source, account, rate, successful access, and surrounding activity.

Other common directories include `/var/log/apache2/` for Apache and `/var/log/mysql/` for MySQL; kernel records may be in `kern.log` or the journal. These are conventions, so inspect the local configuration.

```bash
ls -ld /var/log/*/
ls -lh datasets/app.log
```

On Linux, `logrotate` commonly uses `/etc/logrotate.conf` and files under `/etc/logrotate.d/` to define rotation, compression, and retention. The application may instead rotate its own files. Avoid overlapping rotation mechanisms without checking how the writer reopens its destination. Rotation reduces uncontrolled growth but cannot guarantee sufficient free space if volume or retention is misconfigured.

Rotated logs may be named `app.log.1`, `app.log.2.gz`, or include dates. The file currently receiving writes may not contain the beginning of the incident. Read compressed evidence without modifying it:

```bash
python3 -c 'import gzip; print(gzip.open("datasets/app.log.1.gz", "rt").read(), end="")'
python3 code/analyze.py summary datasets/basics.jsonl
```

**Checkpoint:** Identify the log destination for the lab application and distinguish it from Linux system logs.

## 05. Read files with cat, less, head, and tail

Choose a reader based on file size and the question you are answering.

```bash
cat datasets/app.log
head -n 3 datasets/app.log
tail -n 3 datasets/app.log
less datasets/app.log
```

- `cat` prints the whole file; useful for a short sample.
- `head -n 3` prints the first three lines; useful for understanding a format or startup.
- `tail -n 3` prints the last three lines; useful for recent events.
- `less` lets you navigate a large file without sending it all to the terminal.

Inside `less`, use Space to move forward, `b` to move backward, `/ERROR` to search forward, `n` for the next match, `g` for the beginning, `G` for the end, and `q` to quit. Search matching depends on pager options; use exact capitalization when learning.

Get line numbers for a small evidence excerpt:

```bash
nl -ba datasets/app.log
sed -n '2,5p' datasets/app.log
```

Line numbers identify positions in a specific captured file. Rotation or rewriting changes them. Record the filename and capture time with any excerpt.

A huge traceback is one event with several lines. Start a few lines before the exception and read until the final exception type and message. Then locate the operation that triggered it. The application’s text log includes multiline exceptions; its JSON log keeps the exception inside a single object.

**Practice:** Find the first connection-success record, the connection-loss record, and the final recovery record. Record their timestamps and line numbers.

## 06. Watch logs while an application runs

Start the application in terminal A:

```bash
python3 code/app.py
```

In terminal B:

```bash
tail -n 0 -f logs/app.log
```

In terminal C:

```bash
curl -i -H 'X-Request-ID: veriqta-live-1' http://127.0.0.1:5000/error
```

The follower displays a request-start event, an exception, and a completion with status 500. Stop following with Ctrl+C; this does not stop the application.

`tail -f` normally prints the last ten existing lines before following. `-n 0` suppresses existing content. If rotation renames and replaces the file, `tail -F` follows the filename and retries when necessary:

```bash
tail -n 0 -F logs/app.log
```

The lab rotates each file at roughly 1 MiB and retains three backups. Rotation limits local growth; retention must still be chosen to preserve enough investigation history. Multiprocess applications need a logging design suitable for multiple writers; this lab’s rotating handlers assume one application process.

When no new line appears, check whether you are watching the right process and path, whether logging is buffered, whether a severity threshold excluded the event, and whether the destination is standard output rather than a file. Empty output alone is not proof that no event occurred.

For a minimal file-following experiment, use your own separate practice file. In one terminal:

```bash
touch veriqta-stream-demo.log
tail -n 0 -f veriqta-stream-demo.log
```

In another terminal:

```bash
printf '%s\n' 'INFO Test request' 'INFO Processing' 'ERROR Demonstration failure' >> veriqta-stream-demo.log
```

These manually appended lines demonstrate file streaming, while the HTTP exercises demonstrate actual application logging. Do not append invented events to real incident evidence.

**Checkpoint:** Trigger `/slow` and explain the difference between its warning event and its successful completion record. Stop the follower and application before the next deployment mode.

## 07. Search with grep

Search text logs with a specific question:

```bash
grep -n 'ERROR' datasets/app.log
grep -in 'connection' datasets/app.log
grep -n -C 1 'Connection lost' datasets/app.log
grep -nE 'ERROR|WARN' datasets/auth.log
grep -F 'veriqta-001' datasets/app.log
grep -v 'INFO' datasets/app.log
```

| Option | Purpose |
| --- | --- |
| `-n` | Include line number |
| `-i` | Ignore case |
| `-C 1` | Include one line before and after each match |
| `-A 2`, `-B 2` | Include following or preceding context |
| `-E` | Use extended regular expressions |
| `-F` | Match a literal string |
| `-v` | Show nonmatching lines |
| `-c` | Count matching lines |

The first command should match line 3. `grep` exits with 0 for a match, 1 for no match, and a larger value for an error. “No match” is a valid investigation result. In scripts, handle it deliberately instead of treating every nonzero result as an unreadable file.

Use `-F` when a string contains punctuation that would otherwise act as a pattern. Prefer a specific time window and request ID over a broad search across every log on a machine.

Search several selected files recursively when useful:

```bash
grep -rn 'ERROR' datasets/challenge
```

Limit the directory and file types for a large dataset so unrelated files do not overwhelm the results.

Text search is a discovery tool. It cannot reliably distinguish an `ERROR` severity field from the word “ERROR” quoted inside a message. JSON whitespace and field order also vary. Use the analyzer for field-aware questions:

```bash
python3 code/analyze.py summary datasets/basics.jsonl
python3 code/analyze.py request datasets/basics.jsonl --id veriqta-001
```

**Practice:** Count lines containing `ERROR` in `datasets/app.log`, then count actual error events with the JSON summary. Both are one in this dataset. Explain why the counts could differ for multiline tracebacks or quoted messages.

## 08. Reconstruct a failure timeline

A timeline joins relevant events in normalized time order while preserving where each event came from. Start slightly before the first reported symptom; the initiating failure may precede it.

```bash
python3 code/analyze.py timeline datasets/timeline-unsorted.jsonl
```

The input is deliberately out of order. The output preserves filename and line number and sorts by UTC time. Focus on this sequence:

| UTC time | Event | What it tells you |
| --- | --- | --- |
| 14:21:05 | Proxy receives checkout | Request entered the system |
| 14:21:10 | API starts processing | Application received it |
| 14:21:12 | Payment call | A dependency was contacted |
| 14:21:15 | Database connection refused | Earliest recorded failure in this sequence |
| 14:21:18 | Slow dependency warning | Downstream effect begins |
| 14:21:20 | Payment timeout | Time limit reached |
| 14:21:25 | Order failure | User operation fails |
| 14:21:30 | Retry limit reached | Background recovery also fails |

Select an exact interval:

```bash
python3 code/analyze.py timeline datasets/timeline-unsorted.jsonl \
  --since 2026-01-15T14:21:12Z --until 2026-01-15T14:21:21Z
```

Expected: four events, from the payment call through the timeout. `--since` is inclusive and `--until` is exclusive in this tool.

Do not call the database refusal the root cause yet. It is the earliest failure visible in these records. Next inspect the database listener, process state, and its own logs. A chronological relationship suggests a path to investigate; it does not prove causation.

On Linux, check the machine’s clock and timezone with `date -u` and `timedatectl`. Plain `sort` is safe for chronological ordering only when the relevant timestamp strings share a sortable format and timezone; it does not normalize offsets or infer missing years.

For equal timestamps, the analyzer uses filename and line number as stable display tie-breakers. That ordering does not establish which event caused another. Distributed traces, sequence numbers, and known request flow can supply stronger evidence.

**Checkpoint:** State the first visible symptom, the earliest recorded failure, and the additional evidence still needed.

## 09. Investigate services with journalctl

On Linux systems using systemd, the journal collects service output and system events with metadata. `journalctl` reads these records. It is different from searching a text file: journal fields can identify the unit, boot, process, and native priority.

```bash
sudo journalctl -n 30 --no-pager
sudo journalctl -b -n 30 --no-pager
sudo journalctl -k -b -n 30 --no-pager
sudo journalctl --list-boots
```

`-b` selects the current boot; `-k` selects kernel messages. A previous boot is available only if retained. `--no-pager` prints directly instead of opening an interactive reader.

List available running services before choosing a unit:

```bash
systemctl list-units --type=service --state=running --no-pager
```

Native journal priorities run from most severe to least severe: `emerg`, `alert`, `crit`, `err`, `warning`, `notice`, `info`, and `debug`. Use exact unit names. An absolute time window can include an explicit timezone, for example:

```bash
sudo journalctl -u veriqta-api --since '2026-01-15 10:00:00 UTC' --until '2026-01-15 10:30:00 UTC' --utc --no-pager
```

This historical example returns records only if that interval exists on your host.

### Create a service to investigate

Use a disposable Ubuntu or Debian Linux practice host running systemd. From the project directory:

```bash
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin veriqta
sudo install -d -o root -g root -m 755 /opt/veriqta-log-lab
sudo install -o root -g root -m 644 code/app.py code/logging_core.py /opt/veriqta-log-lab/
sudo install -o root -g root -m 644 code/systemd/veriqta-api.service /etc/systemd/system/veriqta-api.service
sudo systemctl daemon-reload
sudo systemctl start veriqta-api
sudo systemctl status veriqta-api --no-pager
curl -i http://127.0.0.1:5001/health
```

If the dedicated `veriqta` account already exists, inspect it with `id veriqta` and reuse it only if it belongs to this lab. The unit runs the service on port 5001 and sends output to the journal. It disables file logging because `/opt` is read-only to the service.

Query the service:

```bash
sudo journalctl -u veriqta-api -n 30 --no-pager
sudo journalctl -u veriqta-api --since '10 minutes ago' --utc -o short-iso --no-pager
sudo journalctl -u veriqta-api -n 0 -f -o cat
```

While following in one terminal, request `/error` at port 5001 from another. Stop following with Ctrl+C. `-o cat` prints message content, making the application’s JSON easier to inspect. Other output modes include journal metadata.

Native journal priority and an application’s JSON `level` are different fields. `journalctl -p err` filters journal priorities; it does not parse the `"level":"ERROR"` text written to stdout. In this lab, inspect JSON explicitly:

```bash
sudo journalctl -u veriqta-api --since '10 minutes ago' -o cat --no-pager | grep -F '"level": "ERROR"'
```

For general system errors, native priority filtering is useful:

```bash
sudo journalctl -p warning -b --no-pager
sudo journalctl --disk-usage
```

`-p warning` includes warning and more severe journal priorities. Journal retention and persistence depend on configuration; data may be in `/run/log/journal` or `/var/log/journal`. Use the [journalctl manual](https://www.freedesktop.org/software/systemd/man/latest/journalctl.html) for the options supported by your host.

## 10. Troubleshoot a service that will not start

An inactive service is a symptom. First inspect status, then detailed logs, then the effective configuration and referenced files.

```bash
sudo systemctl status veriqta-api --no-pager
sudo journalctl -u veriqta-api -n 50 --utc --no-pager
sudo systemctl cat veriqta-api
sudo systemctl show veriqta-api -p ExecStart -p User -p WorkingDirectory -p Result
```

### Deliberately break the lab service

Create a service-specific override pointing to a nonexistent script:

```bash
sudo mkdir -p /etc/systemd/system/veriqta-api.service.d
sudo tee /etc/systemd/system/veriqta-api.service.d/10-veriqta-lab.conf > /dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/veriqta-log-lab/missing.py
EOF
sudo systemctl daemon-reload
sudo systemctl restart veriqta-api
```

The restart should fail. Inspect the evidence:

```bash
sudo systemctl status veriqta-api --no-pager
sudo journalctl -u veriqta-api -n 30 --no-pager
ls -l /opt/veriqta-log-lab/app.py
sudo systemctl cat veriqta-api
```

Expected explanation: Python exists, but the configured script does not. The precise status text varies. A Python exit code for an unreadable script differs from systemd’s `203/EXEC`, which indicates a problem executing the configured program itself.

Repair only the override created by this exercise:

```bash
sudo rm /etc/systemd/system/veriqta-api.service.d/10-veriqta-lab.conf
sudo systemctl daemon-reload
sudo systemctl reset-failed veriqta-api
sudo systemctl start veriqta-api
curl -i http://127.0.0.1:5001/health
```

For other startup failures, check the evidence before changing anything:

| Symptom | Next checks |
| --- | --- |
| Missing file or module | `ExecStart`, working directory, installed environment |
| Permission denied | Unit user, directory traversal permissions, file access, security policy |
| Address already in use | Intended port and current listener, using `sudo ss -ltnp` on Linux |
| Missing configuration | Environment variable names, configuration file location |
| Dependency unavailable | Database or API listener, DNS, network, dependency logs |
| Start limit reached | Original failure before repeated retries; repair, then reset failed state |

A restart can restore service temporarily while hiding the initiating evidence. Capture useful status and logs before restarting.

**Cleanup:** Stop the lab service after this exercise. Final cleanup commands appear later.

## 11. Investigate HTTP errors with NGINX

NGINX can receive a client request and forward it to an application. Its **access log** records completed requests; its **error log** records operational problems such as upstream connection failures. Application logs explain what happened inside the application.

A combined access record commonly contains client address, timestamp, request method and target, status, response size, referrer, and user agent. Timing and request IDs require a configured format; they are not part of the default combined format. See the [NGINX access log reference](https://nginx.org/en/docs/http/ngx_http_log_module.html).

```text
198.51.100.10 - - [15/Jan/2026:14:00:03 +0000] "GET /api/users HTTP/1.1" 500 100 "-" "veriqta-client/1.0" 0.010 veriqta-0003
```

The last two fields in this lab are request duration in seconds and request ID. The client address is a documentation example. In a real deployment it may be another proxy rather than the original user.

| Status | Meaning for investigation |
| --- | --- |
| 200 | HTTP request succeeded; verify the returned result too |
| 301/302 | Redirect; inspect target and redirect loops |
| 400 | Invalid request |
| 401/403 | Authentication or authorization issue |
| 404 | Requested resource not found |
| 429 | Request rate limited |
| 500 | Server encountered an internal error |
| 502 | Gateway could not obtain a valid upstream response |
| 503 | Service unavailable, possibly application or capacity related |
| 504 | Gateway timed out waiting for an upstream operation |

### Analyze a prepared access log

```bash
awk '{print $9}' datasets/access.log | sort | uniq -c
awk '$9 == 500 {count++} END {print count+0}' datasets/access.log
awk '$9 ~ /^5[0-9][0-9]$/ {count++} END {print count+0}' datasets/access.log
python3 code/analyze.py access datasets/access.log
```

Expected: 12 requests; six 200, two 404, three 500, one 502. There are four 5xx responses, or 33.333% of requests. The `awk` field position is specific to this known log format. Arbitrary log formats need a matching parser.

### Run a local proxy

Install NGINX using its [official package guidance](https://nginx.org/en/linux_packages.html), or use the Docker alternative in chapter 13. On Ubuntu, `sudo apt update` followed by `sudo apt install nginx` installs the package; a distribution-managed NGINX service may also start on port 80. This exercise starts a separate process on loopback port 8081.

Keep the Python application running on port 5000. In another terminal, from the project directory:

```bash
mkdir -p runtime/nginx/logs
cp code/nginx/standalone.conf runtime/nginx/nginx.conf
nginx -p "$PWD/runtime/nginx/" -c nginx.conf -t
nginx -p "$PWD/runtime/nginx/" -c nginx.conf
curl -i http://127.0.0.1:8081/health
curl -i http://127.0.0.1:8081/error
curl -i http://127.0.0.1:8081/missing
tail -n 10 runtime/nginx/logs/access.log
tail -n 10 runtime/nginx/logs/error.log
```

Expect 200, 500, and 404 respectively. A 500 returned by the application may have no matching NGINX error entry: the proxy successfully forwarded an application failure. Read `logs/app.jsonl` to find its exception.

## 12. Find the cause of a 502

The request path in this lab is:

```text
Client → NGINX on 8081 → Python application on 5000 → optional dependency
```

A proxy-side symptom does not mean the proxy configuration is necessarily broken. Trace the next hop.

### Reproduce an unavailable upstream

1. Confirm `/health` returns 200 through NGINX.
2. Stop the Python application with Ctrl+C, leaving NGINX running.
3. Request the same URL and inspect both proxy logs.

```bash
curl -i http://127.0.0.1:8081/health
tail -n 5 runtime/nginx/logs/access.log
tail -n 10 runtime/nginx/logs/error.log
curl -i --max-time 3 http://127.0.0.1:5000/health
```

Expect an NGINX 502 and an upstream connection-refused message. The direct application request should fail to connect. Here you know the cause because you stopped that process; during an incident, prove why it stopped using process, service, container, and application evidence.

Other possibilities include an incorrect upstream port, DNS resolution trouble, a reset connection, or an invalid upstream response. Check the specific error message and destination address before choosing the next test.

### Contrast with a timeout

Restart the Python application and request the deliberately slow path through the proxy:

```bash
curl -i http://127.0.0.1:8081/health
curl -i http://127.0.0.1:8081/timeout
tail -n 10 runtime/nginx/logs/error.log
```

The `/timeout` location forwards to `/slow`, which waits about 300 ms. Its configured read timeout is 100 ms, so a 504 is expected. Raising a timeout changes how long a gateway waits; it does not repair an overloaded or blocked dependency.

The edge generates a request ID and passes it to the application. Copy the returned `X-Request-ID` value to search `logs/app.jsonl`. When the upstream connection never succeeds, an application record for that request may not exist.

**Cleanup:** Stop only this standalone proxy:

```bash
nginx -p "$PWD/runtime/nginx/" -c nginx.conf -s quit
```

Stop the Python process before chapter 13 so host port 5000 is free.

## 13. Read Docker logs

Containers commonly send application output to standard output and standard error. Docker collects those streams using a logging driver. `docker logs` does not automatically search arbitrary files inside a container. Its availability and retention depend on the logging configuration. See [Docker logs](https://docs.docker.com/reference/cli/docker/container/logs/).

Build and start the application and proxy from the project directory:

```bash
docker compose -f code/compose.yaml up -d --build
docker compose -f code/compose.yaml ps
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/error
docker compose -f code/compose.yaml logs --tail 30 app proxy
```

The Docker application listens internally on port 8000. Host port 5000 reaches it directly; host port 8080 reaches the proxy. The proxy uses Compose DNS name `app`, not `localhost`, to reach the other container.

Follow only the application output:

```bash
docker compose -f code/compose.yaml logs --follow --since 5m --tail 20 app
```

Stop following with Ctrl+C. The containers keep running. For the equivalent container command:

```bash
VERIQTA_APP_ID=$(docker compose -f code/compose.yaml ps -q app)
docker logs --timestamps --since 5m --tail 30 "$VERIQTA_APP_ID"
```

Docker’s added timestamp is a collection-side timestamp; the JSON timestamp was generated by the application. Standard output versus standard error is a stream distinction, not a universal severity scale. This app sends structured records of all severities to stdout.

Inspect the active logging driver rather than assuming the daemon default:

```bash
docker inspect --format '{{.HostConfig.LogConfig.Type}}' "$VERIQTA_APP_ID"
docker logs --since 5m "$VERIQTA_APP_ID" 2>&1 | grep -i 'error'
```

Docker supports several drivers, including `local`, `json-file`, `journald`, and remote destinations. Logging options vary by driver. Merging stderr into stdout helps text search cover both streams, but preserve original stream information when it matters to the investigation.

The Compose file selects the `local` driver with three files of roughly 5 MB each per container. Rotation bounds storage but also limits history. Export evidence promptly if an incident could outlast retention.

```bash
docker compose -f code/compose.yaml logs --no-color --since 10m app proxy > veriqta-compose-capture.txt
```

Do not assume text containing Compose prefixes is raw JSONL. Use an individual container’s unprefixed output when a JSON parser expects one object per line.

## 14. Explain why a container exits

Start with state and logs. A container can exit because its main process completes, encounters an exception, receives a signal, or is terminated by the runtime. An exit code alone rarely explains the entire cause.

```bash
docker compose -f code/compose.yaml ps -a
VERIQTA_APP_ID=$(docker compose -f code/compose.yaml ps -a -q app)
docker inspect --format '{{json .State}}' "$VERIQTA_APP_ID"
docker logs --tail 50 "$VERIQTA_APP_ID"
```

Inspect status, exit code, start/finish times, `OOMKilled`, and any runtime error. Exit 137 often corresponds to SIGKILL but does not by itself prove an out-of-memory kill. Check `OOMKilled`, host/kernel evidence, and operator actions. Exit 0 can mean the intended foreground process ended normally even though the service is no longer available.

Inspect the configured command, mounts, restart count, and policy when the state alone is inconclusive:

```bash
docker inspect --format 'Command={{json .Config.Cmd}} RestartCount={{.RestartCount}} Policy={{.HostConfig.RestartPolicy.Name}} Mounts={{json .Mounts}}' "$VERIQTA_APP_ID"
```

Full inspection output can contain environment secrets. Inspect variable names and required configuration locally, and redact values before sharing evidence. A bad executable, absent module, inaccessible mounted file, or dependency failure needs its own targeted correction. The supplied application containers have no automatic Docker restart policy, making their first failure easier to inspect.

### Produce a configuration failure

With the Compose application still available or stopped, start a separate one-shot container:

```bash
docker run --name veriqta-config-failure -e REQUIRE_DB=1 veriqta-log-lab:1.0
docker inspect --format '{{json .State}}' veriqta-config-failure
docker logs veriqta-config-failure
```

The process requires a database host and password but neither was supplied. Expect a configuration error followed by exit code 1. No database installation is needed for this exercise.

Restarting the same container preserves its environment. It will fail again until the configuration or image is corrected. Read the evidence first, then remove the exercise container:

```bash
docker rm veriqta-config-failure
```

### Observe a real database dependency

Start the database extension, which uses a fixed password only for this isolated local lab and does not publish a database port:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml up -d --build
curl -i http://127.0.0.1:8080/api/users
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --tail 30 app db proxy
```

Expect a successful database-backed response. The application checks the database during startup. Compose waits for the database health check before starting the dependent application; that ordering does not continuously manage later database failures.

Stop the database and repeat the request:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml stop db
curl -i http://127.0.0.1:8080/api/users
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --tail 20 app proxy
```

Expect an application-generated 503 while `/health` can still return 200. That health endpoint establishes process responsiveness, not database readiness. Restart the database, wait for readiness, and verify a database-backed operation:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml start db
curl -i http://127.0.0.1:8080/api/users
```

If startup is still in progress, retry after inspecting its health and logs. Avoid repeated application restarts as a substitute for restoring the dependency.

## 15. Read Kubernetes Pod logs

A Pod runs one or more containers. Select the namespace, Pod, and container deliberately, especially when several replicas have similar names. `kubectl logs` reads container output; `kubectl describe` also shows lifecycle state and events. See the [kubectl logs reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/).

### Create a local cluster

Use a local Docker runtime with kind and kubectl installed. This exercise creates a dedicated cluster:

```bash
kind create cluster --name veriqta-logs
docker build -t veriqta-log-lab:1.0 code
kind load docker-image veriqta-log-lab:1.0 --name veriqta-logs
kubectl --context kind-veriqta-logs apply -f code/k8s/app.yaml
kubectl --context kind-veriqta-logs -n veriqta-logs rollout status deployment/veriqta-api --timeout=120s
kubectl --context kind-veriqta-logs -n veriqta-logs get pods -o wide
```

Every command names the local context to keep the target explicit. If image loading fails, inspect the kind cluster and local image before changing the deployment. `ImagePullBackOff` means image acquisition is failing; it is different from a process that started and crashed.

In terminal A:

```bash
kubectl --context kind-veriqta-logs -n veriqta-logs port-forward service/veriqta-api 5003:80
```

In terminal B:

```bash
curl -i http://127.0.0.1:5003/health
curl -i http://127.0.0.1:5003/error
VERIQTA_POD=$(kubectl --context kind-veriqta-logs -n veriqta-logs get pods -l app=veriqta-api -o jsonpath='{.items[0].metadata.name}')
kubectl --context kind-veriqta-logs -n veriqta-logs logs "$VERIQTA_POD" -c api --tail=30 --timestamps
kubectl --context kind-veriqta-logs -n veriqta-logs logs "$VERIQTA_POD" -c api --since=5m --follow
```

Stop following with Ctrl+C. For a group of Pods, a label selector is useful, but label output so you can identify which Pod produced each record:

```bash
kubectl --context kind-veriqta-logs -n veriqta-logs logs -l app=veriqta-api -c api --prefix --tail=20
kubectl --context kind-veriqta-logs -n veriqta-logs describe pod "$VERIQTA_POD"
kubectl --context kind-veriqta-logs -n veriqta-logs get events --sort-by=.metadata.creationTimestamp
```

Events are retained for a limited period. Pod deletion or replacement can remove access to local container logs; centralized collection is needed for durable history.

## 16. Investigate CrashLoopBackOff

`CrashLoopBackOff` means Kubernetes is delaying repeated restarts of a failing container. It is a retry state, not a diagnosis. The preceding process failure explains what to investigate.

Create the deliberate failure:

```bash
kubectl --context kind-veriqta-logs apply -f code/k8s/crash.yaml
kubectl --context kind-veriqta-logs -n veriqta-logs get pods -l app=veriqta-broken -w
```

After at least one restart appears, stop watching with Ctrl+C and capture the Pod name:

```bash
VERIQTA_BROKEN_POD=$(kubectl --context kind-veriqta-logs -n veriqta-logs get pods -l app=veriqta-broken -o jsonpath='{.items[0].metadata.name}')
kubectl --context kind-veriqta-logs -n veriqta-logs describe pod "$VERIQTA_BROKEN_POD"
kubectl --context kind-veriqta-logs -n veriqta-logs logs "$VERIQTA_BROKEN_POD" -c api --tail=30
kubectl --context kind-veriqta-logs -n veriqta-logs logs "$VERIQTA_BROKEN_POD" -c api --previous --tail=30
```

`--previous` reads the previous terminated instance of that container in the same Pod. It does not retrieve logs from a deleted Pod. If no previous instance exists yet, wait for a restart and try again.

The log should report required database configuration missing. The deployment sets `REQUIRE_DB=1` without providing its required host and password. That is the demonstrated cause. A different workload could fail because of code errors, permissions, resource limits, or probes; inspect its evidence rather than borrowing this diagnosis.

Fix this lab by disabling its optional dependency:

```bash
kubectl --context kind-veriqta-logs -n veriqta-logs set env deployment/veriqta-broken REQUIRE_DB=0
kubectl --context kind-veriqta-logs -n veriqta-logs rollout status deployment/veriqta-broken --timeout=120s
kubectl --context kind-veriqta-logs -n veriqta-logs get pods -l app=veriqta-broken
```

This changes the Pod template and creates a replacement Pod. Capture previous evidence before making the change. In a real database-dependent service, supply correct secret and connection configuration instead of removing a required dependency.

**Checkpoint:** Explain the difference between application exit, `CrashLoopBackOff`, and `ImagePullBackOff`. Identify which command shows the previous container’s logs.

## 17. Correlate events across services

A request ID connects records for one operation. Correlation works only when each participating component receives or derives the identifier and includes it in its logs. A field does not propagate itself simply because several services use JSON.

In this lab, the proxy creates an ID, forwards it in `X-Request-ID`, and returns it in the response. The app includes it in its events. For successful database connections, the client sets PostgreSQL’s `application_name` to `veriqta-` plus that ID, and the database log prefix includes the application name.

### Follow a direct request

With the local Python application running without its database extension:

```bash
curl -i -H 'X-Request-ID: veriqta-follow-1' http://127.0.0.1:5000/api/users
python3 code/analyze.py request logs/app.jsonl --id veriqta-follow-1
```

Expect start and completion events for the same ID. The direct app accepts a valid identifier of 1–64 letters, digits, underscores, or hyphens; invalid values are replaced. Production edge services should define their trust policy for caller-supplied identifiers and avoid allowing arbitrary untrusted text into logs.

### Follow a proxy and database request

Start the three-service Compose lab if it is not running:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml up -d --build
curl -sS -D veriqta-response-headers.txt http://127.0.0.1:8080/api/users
VERIQTA_REQUEST_ID=$(awk 'tolower($1)=="x-request-id:" {gsub("\r", "", $2); print $2}' veriqta-response-headers.txt)
printf '%s\n' "$VERIQTA_REQUEST_ID"
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --no-color --since 5m app proxy db | grep -F "$VERIQTA_REQUEST_ID"
```

The response header is the authoritative ID for this edge-generated request. A client-supplied ID will be replaced by this proxy configuration. In the database record, expect an application name such as `veriqta-<returned-ID>`.

PostgreSQL does not automatically understand an HTTP request ID. The lab establishes the mapping explicitly and uses a short-lived connection per request. A real application using a connection pool needs careful per-request context assignment and reset so IDs do not leak between users. The lab’s `log_statement=all` helps show the demonstration query; use selective logging in real services because full statement logging can reveal data and create substantial volume. See [PostgreSQL logging configuration](https://www.postgresql.org/docs/current/runtime-config-logging.html).

If the connection is refused before reaching the database server, no matching server-side request entry may exist. Search connection and server lifecycle records around the same time. Absence of an ID is a clue about observability, not proof that a component was healthy.

### Follow prepared evidence

```bash
python3 code/analyze.py request datasets/timeline-unsorted.jsonl --id veriqta-001
python3 code/analyze.py request datasets/challenge/*.jsonl --id veriqta-checkout-42
```

One underlying failure can produce a database write error, an application startup failure, a container restart, and a proxy 502. These are several observations of a chain; do not count them as independent user incidents without understanding their relationship.

## 18. Recognize patterns, spikes, and repeated failures

A single request explains one experience. Aggregation tells you whether the problem is isolated, repeated, or growing.

### Count failures by status and endpoint

For the supplied combined-style dataset:

```bash
wc -l datasets/access.log
awk '$9 ~ /^[45][0-9][0-9]$/ {print $7, $9}' datasets/access.log | sort | uniq -c | sort -nr
python3 code/analyze.py access datasets/access.log
```

Expected failing endpoint/status groups:

| Endpoint and status | Count |
| --- | --- |
| `/missing 404` | 2 |
| `/api/users 500` | 2 |
| `/api/orders 500` | 1 |
| `/ 502` | 1 |

These commands assume the documented field positions. They do not apply directly to JSON or a custom NGINX format with different ordering. Query strings, encoded spaces, and escaped characters can require a more capable parser and a deliberate path-normalization strategy.

### Group repeated event types

Whole-line grouping can be misleading because timestamps and request IDs make repeated failures look different. Group stable fields instead:

```bash
python3 code/analyze.py summary datasets/challenge/*.jsonl
python3 - <<'PY'
from collections import Counter
from pathlib import Path
import json
counts = Counter()
for path in Path('datasets/challenge').glob('*.jsonl'):
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row['level'] in {'ERROR', 'FATAL', 'CRITICAL'}:
            counts[(row['service'], row['event'])] += 1
for (service, event), count in counts.most_common(5):
    print(count, service, event)
PY
```

For plain text with variable prefixes, isolate a stable message field before using `sort | uniq -c | sort -nr`. Otherwise you count unique timestamps rather than repeated failure categories.

### Find a spike over time

Count 5xx failures in each minute for this known format:

```bash
awk '$9 ~ /^5[0-9][0-9]$/ {print substr($4, 2, 17)}' datasets/access.log | sort | uniq -c
```

Expect two 5xx responses in 14:00 and two in 14:01. The analyzer reports the same groups normalized to UTC. Counting every access record per minute measures traffic; filter failure statuses first when measuring error spikes.

### Compare before and after fairly

```bash
python3 code/analyze.py access datasets/access-before.log
python3 code/analyze.py access datasets/access-after.log
```

| Window | Requests | 5xx responses | Error rate |
| --- | --- | --- | --- |
| Before | 1,000 | 20 | 2% |
| After | 100 | 5 | 5% |

The failure count fell, but the failure rate increased. A lower raw count can simply reflect less traffic. Compare equal-duration windows, request volume, endpoint mix, latency, and deployment versions before claiming improvement. Small samples also make rates unstable.

**Practice:** Explain the assumptions behind each command, then decide what evidence would establish whether a deployment improved the customer experience.

## 19. Work through a complete outage

This lab links a failed backend dependency to application startup failure and a proxy-side 502. Use the disposable Compose environment; do not stop a shared database to practice.

### Establish a healthy baseline

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml up -d --build
docker compose -f code/compose.yaml -f code/compose.database.yaml ps
curl -i http://127.0.0.1:8080/api/users
```

Wait until the database is healthy and the database-backed request succeeds. Record UTC time with `date -u` before changing state. Capture logs over a short interval rather than mixing several previous exercises.

### Introduce the failure

Stop the database, then restart only the application without starting its dependency:

```bash
date -u
docker compose -f code/compose.yaml -f code/compose.database.yaml stop db
docker compose -f code/compose.yaml -f code/compose.database.yaml restart --no-deps app
docker compose -f code/compose.yaml -f code/compose.database.yaml ps -a
curl -i http://127.0.0.1:8080/api/users
```

The application’s startup check cannot connect and exits. The proxy is still running but cannot obtain a response from its upstream; a 502 is expected. Immediately after stopping/restarting there may be a short transition while connections fail; inspect settled state before recording the result.

### Collect evidence at each layer

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --since 5m --tail 100 proxy
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --since 5m --tail 100 app
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --since 5m --tail 100 db
VERIQTA_APP_ID=$(docker compose -f code/compose.yaml -f code/compose.database.yaml ps -a -q app)
docker inspect --format '{{json .State}}' "$VERIQTA_APP_ID"
```

| Layer | Expected observation | Conclusion |
| --- | --- | --- |
| Client | 502 | Request fails through the proxy |
| Proxy | Connection refused or unavailable upstream | Application cannot serve this request |
| App | Database startup check failed; exit 1 | Required dependency prevented startup |
| Database | Stopped; orderly shutdown records | Dependency was deliberately stopped |
| Change record | Your stop command and time | Known initiating action in this lab |

Here the initiating action is known. In an unfamiliar incident, “database stopped” is still only an intermediate finding. Inspect its shutdown reason, storage, memory, configuration, and recent changes.

### Restore the dependency, then the application

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml start db
docker compose -f code/compose.yaml -f code/compose.database.yaml ps
```

Wait for the database health check to pass. Then:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml up -d app
curl -i http://127.0.0.1:8080/api/users
docker compose -f code/compose.yaml -f code/compose.database.yaml logs --since 2m --tail 30 app db proxy
```

Verify several database-backed requests and stable process state. A single `/health` response is insufficient because that endpoint does not query the database. Check that the application no longer exits and that requests succeed through the proxy, not only directly.

### When the database says its files are incompatible

A message such as `database files are incompatible with server` points to a PostgreSQL major-version/data-directory mismatch. Repeated restarts do not migrate those files. Do not delete the volume or initialize over valuable data to make the message disappear.

Record the image version and data-directory history, preserve the existing data and backups, and restore a compatible server or perform a supported upgrade using the correct source and target versions. PostgreSQL documents dump/restore and `pg_upgrade` approaches in its [upgrade guide](https://www.postgresql.org/docs/current/upgrading.html). Validate backups and application compatibility before a real migration. The supplied Compose database uses PostgreSQL 17 consistently so this destructive failure does not need to be created for the lesson.

## 20. Complete the detective challenge

Investigate `datasets/challenge/` as a captured incident. It contains proxy, application, database, Kubernetes, change, storage, and recovery evidence. Some records are unrelated distractions. You do not need running infrastructure for this challenge.

### Investigation brief

Users report failed requests to `/api/users`. The request path includes a proxy, application, and PostgreSQL. Your task is to establish impact, reconstruct the failure chain, identify the trigger and contributing conditions, propose a targeted mitigation, and assess the recovery evidence.

Begin without reading the worked answer:

```bash
ls -lh datasets/challenge
python3 code/analyze.py summary datasets/challenge/*.jsonl
python3 code/analyze.py timeline datasets/challenge/*.jsonl
cat datasets/challenge/proxy-error.log
cat datasets/challenge/storage-before.txt
```

Narrow the time window and request:

```bash
python3 code/analyze.py timeline datasets/challenge/*.jsonl \
  --since 2026-01-15T10:04:00Z --until 2026-01-15T10:06:00Z
python3 code/analyze.py request datasets/challenge/*.jsonl --id veriqta-checkout-42
```

The challenge JSON files use a common teaching schema so you can practice cross-component reasoning. Native Kubernetes events and PostgreSQL text logs have different formats; a central logging pipeline would need to normalize them while preserving their origins.

### Write an incident report

Use [the incident report worksheet](exercises/incident-report.md). Include:

1. User-visible symptom and the affected operation.
2. Timeline with UTC times, source files, and line numbers.
3. Earliest relevant failure and how it propagated.
4. Initiating change and the evidence connecting it to the failure.
5. At least two misleading records and why they are not the primary explanation.
6. Mitigation that preserves required data.
7. Recovery checks at the database, application, proxy, and user-operation layers.
8. Prevention actions with ownership and measurable completion criteria.
9. Remaining unknowns, including the limits of the captured request sample.

Read `storage-after.txt` and `recovery.jsonl` only after writing your proposed mitigation. Compare the recorded recovery with your plan. Do not equate one successful request with a measured global recovery time.

### Assessment

Award one point each for a defensible timeline, supported causal chain, rejection of distractions, data-preserving mitigation, and recovery plan. Rework any unsupported conclusion before comparing your report with the worked answer.

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

## Write logs that make investigations easier

Good logs answer operational questions without requiring access to secrets or full request bodies. Use consistent UTC timestamps, stable event names, component identity, request/trace IDs, outcome, and duration. Include software version and instance identity where these help separate deployments.

Keep credentials, access tokens, cookies, private keys, payment details, and unnecessary personal data out of messages. Prefer an internal actor identifier to an email address. Treat paths, headers, and user agents as untrusted data: limit length, escape newlines and control characters, and avoid logging query strings that may contain tokens.

Python’s [logging reference](https://docs.python.org/3/library/logging.html) describes handlers, formatters, levels, and exception logging. The lab uses a stream handler plus rotating text and JSON files. It disables propagation to avoid duplicate records through parent loggers. It uses monotonic time for elapsed durations so a wall-clock adjustment does not produce a negative request time.

For production collection, applications commonly write structured events to stdout or managed files; a collector forwards them to a central system such as Loki, OpenSearch, Elastic, or a cloud logging service. Plan access control, encryption, retention, ingestion limits, sensitive-field filtering, and alerts for collection failures. A central platform is useful only if the necessary events arrive and remain searchable.

Logs describe events; metrics summarize measurements over time; traces connect spans within an operation. Use all three when available. A trace ID in a log helps navigation but does not create distributed tracing by itself.

## Preserve evidence and record uncertainty

Capture a narrow incident window before rotation, restart, or replacement removes context. Preserve original files and make a separate working copy for analysis. Record UTC capture time, host or context, command, service version, and any gaps. Redact a copy before sharing outside the authorized investigation group.

```bash
mkdir -p evidence/veriqta-incident
cp datasets/challenge/*.jsonl evidence/veriqta-incident/
cp datasets/challenge/*.txt evidence/veriqta-incident/
cp datasets/challenge/proxy-error.log evidence/veriqta-incident/
date -u > evidence/veriqta-incident/captured-at.txt
```

These commands copy the practice evidence; they do not establish chain of custody for a real incident. Follow the organization’s evidence-handling process when one applies.

Track statements as observations, hypotheses, or confirmed explanations. If the log window starts after the failure, say so. If a request ID is missing, search by time and component but retain that uncertainty. If a record is malformed, count it rather than silently pretending the dataset is complete:

```bash
python3 code/analyze.py summary datasets/malformed.jsonl
```

Expected: one valid event and two invalid lines. The analyzer reports invalid counts and preserves file/line origin for valid timeline entries. It reads all selected JSON events into memory; use bounded windows or a streaming/central platform for very large datasets.

## Run the code checks

The included tests check application responses, request IDs, structured exceptions, database failure handling, time normalization, malformed input, file provenance, and the known dataset results:

```bash
python3 -m unittest discover -s code/tests -v
```

They do not require Flask, a database, or a network listener. Complete the live exercise checkpoints on each deployment platform to verify the corresponding environment.

## Cleanup

Stop local Python/Flask processes, log followers, and port-forward sessions with Ctrl+C in their own terminals. Quit the standalone NGINX process with the command from chapter 12.

Remove the Compose containers and network while retaining the database volume:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml down
```

After finishing the disposable database exercise, the following removes that project’s database volume and its lab data:

```bash
docker compose -f code/compose.yaml -f code/compose.database.yaml down --volumes
```

Remove the dedicated local Kubernetes cluster:

```bash
kind delete cluster --name veriqta-logs
```

On the Linux host used for the systemd lab:

```bash
sudo systemctl stop veriqta-api
sudo systemctl disable veriqta-api
sudo rm /etc/systemd/system/veriqta-api.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

If you did not remove the deliberate override earlier, remove only `/etc/systemd/system/veriqta-api.service.d/10-veriqta-lab.conf` and reload again. Preserve any investigation captures you need. You may remove the lab’s `/opt/veriqta-log-lab` files and its dedicated account after confirming they are used only by this exercise.

## Command reference

| Question | Command or approach |
| --- | --- |
| What happened most recently? | `tail -n 20 datasets/app.log` |
| What happened around this error? | `grep -n -C 2 'ERROR' datasets/app.log` |
| Where is this exact identifier? | `grep -F 'veriqta-001' datasets/app.log` |
| What happens live? | `tail -n 0 -F logs/app.log` |
| What did this service record? | `journalctl -u veriqta-api --since '10 minutes ago'` |
| What happened in the previous boot? | `journalctl -b -1` if retained |
| Why did a container exit? | Targeted `docker inspect` state plus `docker logs` |
| What happened before its restart? | `kubectl logs POD -c CONTAINER --previous` in the correct context/namespace |
| What failed most frequently? | Group stable event or endpoint/status fields |
| Did recovery improve outcomes? | Compare rates, volumes, latency, and user operations |

## Investigation checklist

- Define user impact and the affected time window.
- Confirm timezone, component identity, and deployment context.
- Find the request or operation and preserve its evidence.
- Read events before and after the first visible symptom.
- Follow the failing dependency to its own logs and state.
- Separate the initiating failure from downstream effects.
- Test competing explanations against the evidence.
- Apply a targeted correction that preserves required data.
- Verify recovery through the user path and dependencies.
- Record uncertainty, prevention actions, ownership, and follow-up checks.

## Complete code and configuration

The following files form the application and investigation lab. Paths are relative to the project directory. The same files are supplied in `code/` and `exercises/` so you can run the lessons directly.

### `code/.dockerignore`

```text
logs
__pycache__
.venv
*.log
*.jsonl
.git
tests
```

### `code/.gitignore`

```text
.venv/
__pycache__/
*.pyc
logs/
.env
```

### `code/Dockerfile`

```text
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py logging_core.py flask_app.py ./
ENV HOST=0.0.0.0 PORT=8000 LOG_DIR="" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8000
CMD ["python","app.py"]
```

### `code/analyze.py`

```python
"""Read-only JSONL and combined-access-log investigation commands."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import re
import sys

ACCESS=re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" (?P<status>\d{3}) (?P<bytes>\d+|-) "(?P<referrer>[^"]*)" "(?P<agent>[^"]*)"(?: (?P<seconds>[0-9.]+) (?P<request_id>[A-Za-z0-9_-]+))?$')
MONTHS={m:i for i,m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],1)}
def timestamp(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp must include UTC Z or an explicit offset")
    return dt.astimezone(timezone.utc)
def access_timestamp(value):
    # Month labels in this NGINX format are English regardless of reader locale.
    date,offset=value.split(" ")
    day,month,rest=date.split("/",2)
    year,hour,minute,second=rest.split(":")
    return timestamp(f"{year}-{MONTHS[month]:02d}-{int(day):02d}T{hour}:{minute}:{second}{offset[:3]}:{offset[3:]}")
def open_text(path):
    return gzip.open(path,"rt",encoding="utf-8") if str(path).endswith(".gz") else open(path,encoding="utf-8")
def read_json(paths):
    rows=[];invalid=0
    for path in paths:
        with open_text(path) as stream:
            for line_number,line in enumerate(stream,1):
                if not line.strip():continue
                try:
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError("Object required")
                    row=dict(row);dt=timestamp(row["timestamp"])
                    row["_time"]=dt;row["_file"]=str(path);row["_line"]=line_number
                    rows.append(row)
                except (ValueError,TypeError,KeyError,AttributeError):invalid+=1
    return rows,invalid

def access_summary(path):
    total=0;invalid=0;statuses=Counter();endpoints=Counter();minutes=Counter()
    with open_text(path) as stream:
        for line in stream:
            if not line.strip():continue
            m=ACCESS.fullmatch(line.rstrip("\n"))
            if not m:invalid+=1;continue
            try:dt=access_timestamp(m["time"])
            except (ValueError,KeyError):invalid+=1;continue
            status=int(m["status"]);total+=1;statuses[str(status)]+=1
            if status>=400:endpoints[f'{m["path"]} {status}']+=1
            if status>=500:minutes[dt.strftime("%Y-%m-%dT%H:%MZ")]+=1
    bad=sum(n for code,n in statuses.items() if 500<=int(code)<=599)
    return {"requests":total,"invalid_lines":invalid,"status_counts":dict(sorted(statuses.items())),
            "server_errors":bad,"server_error_percent":round(100*bad/total,3) if total else None,
            "failing_endpoints":dict(endpoints.most_common()),"server_errors_per_minute":dict(sorted(minutes.items()))}

def serial(row):
    return {**{k:v for k,v in row.items() if not k.startswith("_") and k not in {"timestamp","file","line"}},
            "timestamp":row["_time"].isoformat().replace("+00:00","Z"),
            "file":row["_file"],"line":row["_line"]}

def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=["summary","timeline","request","access"])
    p.add_argument("files",nargs="+");p.add_argument("--id");p.add_argument("--since");p.add_argument("--until")
    args=p.parse_args()
    if args.command=="access":
        if len(args.files)!=1:p.error("access requires one file")
        print(json.dumps(access_summary(args.files[0]),indent=2));return
    rows,invalid=read_json(args.files)
    start=timestamp(args.since) if args.since else None;end=timestamp(args.until) if args.until else None
    rows=[r for r in rows if (start is None or r["_time"]>=start) and (end is None or r["_time"]<end)]
    rows.sort(key=lambda r:(r["_time"],r["_file"],r["_line"]))
    if args.command=="summary":
        errors=Counter(r.get("event","unknown") for r in rows if r.get("level") in {"ERROR","FATAL","CRITICAL"})
        result={"events":len(rows),"invalid_lines":invalid,"levels":dict(Counter(r.get("level","unknown") for r in rows)),"error_events":dict(errors.most_common())}
        print(json.dumps(result,indent=2))
    else:
        if args.command=="request":
            if not args.id:p.error("request requires --id")
            rows=[r for r in rows if r.get("request_id")==args.id]
        for row in rows:print(json.dumps(serial(row)))
        if invalid:print(f"Skipped invalid lines: {invalid}",file=sys.stderr)
if __name__=="__main__":main()
```

### `code/app.py`

```python
"""Local standard-library HTTP entry point; binds to loopback by default."""
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from logging_core import configure_logging,emit,handle,request_id,startup_check,safe_text

LOG=None
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        started=time.monotonic()
        rid=request_id(self.headers.get("X-Request-ID"))
        path=urlsplit(self.path).path
        status,body=handle(path,rid,LOG)
        raw=json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("X-Request-ID",rid)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):
            emit(LOG,logging.WARNING,"client_disconnected","Client disconnected before response completed",request_id=rid)
        emit(LOG,logging.ERROR if status>=500 else logging.WARNING if status>=400 else logging.INFO,
             "request_completed","Request completed",request_id=rid,path=path,status=status,
             duration_ms=round((time.monotonic()-started)*1000,3),
             client_ip=self.client_address[0],user_agent=safe_text(self.headers.get("User-Agent","")))
    def log_message(self,*args):pass

def main():
    global LOG
    LOG=configure_logging(os.getenv("LOG_DIR","logs"))
    try:
        startup_check(LOG)
        host=os.getenv("HOST","127.0.0.1");port=int(os.getenv("PORT","5000"))
        server=ThreadingHTTPServer((host,port),Handler)
    except Exception as exc:
        emit(LOG,logging.ERROR,"startup_failed","Application could not start",error_type=type(exc).__name__)
        return 1
    emit(LOG,logging.INFO,"listening","HTTP listener ready",host=host,port=port)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();emit(LOG,logging.INFO,"shutdown","Application stopped")
    return 0

if __name__=="__main__":sys.exit(main())
```

### `code/compose.database.yaml`

```yaml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: veriqta
      POSTGRES_PASSWORD: veriqta-lab-only-password
      POSTGRES_DB: veriqta
    command: ["postgres", "-c", "log_connections=on", "-c", "log_disconnections=on", "-c", "log_statement=all", "-c", "log_line_prefix=%m [%p] app=%a "]
    volumes: ["veriqta-db:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U veriqta -d veriqta"]
      interval: 2s
      timeout: 2s
      retries: 15
    logging:
      driver: local
      options: {max-size: "5m", max-file: "3"}
  app:
    environment:
      REQUIRE_DB: "1"
      DB_HOST: db
      DB_PORT: "5432"
      DB_NAME: veriqta
      DB_USER: veriqta
      DB_PASSWORD: veriqta-lab-only-password
    depends_on:
      db: {condition: service_healthy}
volumes:
  veriqta-db:
```

### `code/compose.yaml`

```yaml
name: veriqta-log-lab
services:
  app:
    build: .
    image: veriqta-log-lab:1.0
    ports: ["127.0.0.1:5000:8000"]
    logging:
      driver: local
      options: {max-size: "5m", max-file: "3"}
  proxy:
    image: nginx:1.28-alpine
    ports: ["127.0.0.1:8080:8080"]
    volumes: ["./nginx/nginx.conf:/etc/nginx/nginx.conf:ro"]
    depends_on: [app]
    logging:
      driver: local
      options: {max-size: "5m", max-file: "3"}
```

### `code/flask_app.py`

```python
"""Flask entry point using the same lab routes and logging behavior."""
import logging
import os
import time
from flask import Flask,g,jsonify,request
from logging_core import configure_logging,emit,handle,request_id,startup_check,safe_text

app=Flask(__name__)
log=configure_logging(os.getenv("LOG_DIR","logs"))
startup_check(log)
@app.before_request
def before_request():
    g.started=time.monotonic();g.request_id=request_id(request.headers.get("X-Request-ID"))
@app.route("/",defaults={"path":""})
@app.route("/<path:path>")
def route(path):
    status,body=handle("/"+path,g.request_id,log)
    return jsonify(body),status
@app.after_request
def after_request(response):
    response.headers["X-Request-ID"]=g.request_id
    emit(log,logging.ERROR if response.status_code>=500 else logging.WARNING if response.status_code>=400 else logging.INFO,
         "request_completed","Request completed",request_id=g.request_id,path=request.path,status=response.status_code,
         duration_ms=round((time.monotonic()-g.started)*1000,3),
         client_ip=request.remote_addr,user_agent=safe_text(request.headers.get("User-Agent","")))
    return response
if __name__=="__main__":
    app.run(host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","5000")),debug=False)
```

### `code/generate_data.py`

```python
"""Create deterministic Veriqta investigation datasets."""
from pathlib import Path
import json
import gzip
from datetime import datetime,timedelta,timezone

BASE=Path(__file__).resolve().parents[1]/"datasets"
def write(path,text):
    p=BASE/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding="utf-8")
def jsonlines(rows):return "".join(json.dumps(r)+"\n" for r in rows)
def event(at,level,service,name,message,rid="veriqta-001",**extra):
    return dict(timestamp="2026-01-15T"+at+"Z",level=level,service=service,event=name,message=message,request_id=rid,**extra)
def access_line(i,status,path="/api/users",minute=0):
    stamp=f"15/Jan/2026:14:{minute:02d}:{i%60:02d} +0000"
    return f'198.51.100.10 - - [{stamp}] "GET {path} HTTP/1.1" {status} 100 "-" "veriqta-client/1.0" 0.010 veriqta-{i:04d}\n'
def main():
    rows=[event("10:15:20","INFO","web","startup","Server started"),
          event("10:16:05","INFO","db-client","db_connected","Connected to database"),
          event("10:17:12","ERROR","db-client","db_connection_lost","Connection lost"),
          event("10:17:30","INFO","web","db_retry","Retrying database connection"),
          event("10:18:05","INFO","db-client","db_connected","Connected to database")]
    write(Path("basics.jsonl"),jsonlines(rows))
    text="".join(f'{r["timestamp"]} {r["level"]} [{r["service"]}] request_id={r["request_id"]} {r["message"]}\n' for r in rows)
    write(Path("app.log"),text)
    with gzip.open(BASE/"app.log.1.gz","wt",encoding="utf-8") as f:f.write(text)
    write(Path("auth.log"),'2026-01-15T11:00:00Z INFO [auth] actor=veriqta-demo Login attempt\n2026-01-15T11:00:02Z WARN [auth] actor=veriqta-demo Invalid password\n2026-01-15T11:01:02Z ERROR [auth] actor=veriqta-demo Account locked after repeated failures\n')
    timeline=[event("14:21:05","INFO","proxy","request_received","Checkout request received"),
              event("14:21:10","INFO","api","request_started","Processing request"),
              event("14:21:12","INFO","api","payment_call","Calling payment service"),
              event("14:21:15","ERROR","db-client","db_connection_failed","Database connection refused"),
              event("14:21:18","WARN","payment","slow_dependency","Slow response while waiting for dependency"),
              event("14:21:20","ERROR","api","payment_timeout","Payment service timeout"),
              event("14:21:25","ERROR","api","order_failed","Failed to complete order"),
              event("14:21:30","ERROR","worker","retry_exhausted","Job failed: retry limit reached")]
    write(Path("timeline-unsorted.jsonl"),jsonlines([timeline[i] for i in [1,3,2,5,0,6,4,7]]))
    offset=[dict(timeline[3],timestamp="2026-01-15T16:21:15+02:00"),dict(timeline[2],timestamp="2026-01-15T09:21:12-05:00")]
    write(Path("mixed-offsets.jsonl"),jsonlines(offset))
    status=[200,200,404,500,200,500,200,404,502,200,500,200]
    paths=["/","/api/users","/missing","/api/users","/","/api/users","/health","/missing","/","/health","/api/orders","/"]
    write(Path("access.log"),"".join(access_line(i,s,p,i//6) for i,(s,p) in enumerate(zip(status,paths))))
    accessrows=[]
    for i,(s,p) in enumerate(zip(status,paths)):
        accessrows.append(event(f"14:{i//6:02d}:{i%60:02d}","ERROR" if s>=500 else "WARN" if s>=400 else "INFO",
            "veriqta-proxy","request_completed","Request completed",rid=f"veriqta-{i:04d}",status=s,path=p,duration_ms=10))
    write(Path("access.jsonl"),jsonlines(accessrows))
    write(Path("access-before.log"),"".join(access_line(i,500 if i<20 else 200,minute=i//60) for i in range(1000)))
    write(Path("access-after.log"),"".join(access_line(i,500 if i<5 else 200,minute=i//60) for i in range(100)))
    write(Path("malformed.jsonl"),jsonlines([rows[0]])+'not JSON\n'+json.dumps({"timestamp":"2026-01-15T10:00:00","level":"INFO"})+'\n')
    request="veriqta-checkout-42"
    proxy=[event("10:05:06","ERROR","proxy","request_completed","Upstream unavailable",request,status=502,path="/api/users",duration_ms=1),
           event("10:06:12","INFO","proxy","request_completed","Request completed","veriqta-recovery-1",status=200,path="/api/users",duration_ms=8)]
    app=[event("10:04:20","WARN","api","cache_miss","Cache miss; database fallback expected","unrelated-cache"),
         event("10:05:02","ERROR","api","db_connection_failed","Could not connect to database",request,error_code="ECONNREFUSED"),
         event("10:05:03","ERROR","api","startup_failed","Application exiting after failed startup check",request),
         event("10:06:10","INFO","api","db_connected","Database connection restored","veriqta-recovery-1")]
    db=[event("10:04:58","ERROR","postgres","write_failed","could not write to file pg_wal: No space left on device",request,error_code="ENOSPC"),
        event("10:04:59","FATAL","postgres","shutdown","Database shutting down after write failure",request),
        event("10:06:08","INFO","postgres","ready","Database is ready to accept connections","veriqta-recovery-1")]
    change=[event("09:55:00","INFO","deploy","config_change","Debug export job enabled without retention or size cap","veriqta-change-17")]
    kube=[event("09:40:00","WARN","kubelet","old_container_terminated","Previous analytics Pod OOMKilled; different workload","unrelated-analytics",pod="analytics-old"),
          event("10:05:05","WARN","kubelet","BackOff","Back-off restarting failed container api",request,pod="veriqta-api-incident")]
    for name,events in [("proxy",proxy),("app",app),("database",db),("changes",change),("kubernetes",kube)]:write(Path("challenge")/(name+".jsonl"),jsonlines(events))
    write(Path("challenge/proxy-error.log"),'2026/01/15 10:05:06 [error] 34#34: *12 connect() failed (111: Connection refused) while connecting to upstream, upstream: "http://app:8000/api/users"\n')
    write(Path("challenge/storage-before.txt"),'Captured: 2026-01-15T10:05:00Z\nFilesystem         Size Used Avail Use% Mounted on\n/dev/veriqta-data    10G  10G     0 100% /var/lib/postgresql/data\nExport job output: /var/lib/postgresql/data/debug-exports = 8G\n')
    write(Path("challenge/storage-after.txt"),'Captured: 2026-01-15T10:06:05Z\nFilesystem         Size Used Avail Use% Mounted on\n/dev/veriqta-data    10G   2G    8G  20% /var/lib/postgresql/data\nMitigation record: capped export job; moved reviewed disposable debug exports off database volume; retained database/WAL files intact.\n')
    write(Path("challenge/recovery.jsonl"),jsonlines([event("10:06:05","INFO","operator","mitigation","Export job disabled; approved disposable exports moved to separate storage","veriqta-recovery-1"),event("10:06:20","INFO","probe","verification","Three application/database reads succeeded; storage stable","veriqta-recovery-1")]))
    print("Veriqta datasets ready:",BASE)
if __name__=="__main__":main()
```

### `code/k8s/app.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: veriqta-logs
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: veriqta-api
  namespace: veriqta-logs
spec:
  replicas: 1
  selector:
    matchLabels: {app: veriqta-api}
  template:
    metadata:
      labels: {app: veriqta-api}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
      containers:
        - name: api
          image: veriqta-log-lab:1.0
          imagePullPolicy: IfNotPresent
          ports: [{containerPort: 8000}]
          resources:
            requests: {cpu: 50m, memory: 48Mi}
            limits: {cpu: 300m, memory: 192Mi}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
          readinessProbe:
            httpGet: {path: /health, port: 8000}
            periodSeconds: 3
          livenessProbe:
            httpGet: {path: /health, port: 8000}
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: veriqta-api
  namespace: veriqta-logs
spec:
  selector: {app: veriqta-api}
  ports: [{port: 80, targetPort: 8000}]
```

### `code/k8s/crash.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: veriqta-broken
  namespace: veriqta-logs
spec:
  replicas: 1
  selector:
    matchLabels: {app: veriqta-broken}
  template:
    metadata:
      labels: {app: veriqta-broken}
    spec:
      containers:
        - name: api
          image: veriqta-log-lab:1.0
          imagePullPolicy: IfNotPresent
          env:
            - {name: REQUIRE_DB, value: "1"}
          resources:
            requests: {cpu: 20m, memory: 48Mi}
            limits: {cpu: 200m, memory: 192Mi}
```

### `code/logging_core.py`

```python
"""Shared logging and application behavior for the Veriqta log lab."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import time
import uuid
from datetime import datetime, timezone

RID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")

def request_id(value):
    return value if isinstance(value,str) and RID.fullmatch(value) else uuid.uuid4().hex

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def safe_text(value, limit=200):
    return str(value).replace("\r"," ").replace("\n"," ").replace("\x1b"," ")[:limit]

class JsonFormatter(logging.Formatter):
    def format(self,record):
        data={"timestamp":utc_now(),"level":record.levelname,"service":"veriqta-api",
              "pid":os.getpid(),"event":getattr(record,"event","message"),
              "message":record.getMessage()}
        data.update(getattr(record,"fields",{}))
        if record.exc_info:
            data["exception"]=self.formatException(record.exc_info)
        return json.dumps(data,ensure_ascii=True,allow_nan=False)

class TextFormatter(logging.Formatter):
    def format(self,record):
        fields=getattr(record,"fields",{})
        text=f'{utc_now()} {record.levelname} [veriqta-api] pid={os.getpid()} request_id={fields.get("request_id","-")} event={getattr(record,"event","message")} {safe_text(record.getMessage())}'
        details=" ".join(f"{key}={safe_text(value)}" for key,value in fields.items() if key!="request_id")
        if details:text += " "+details
        if record.exc_info:text += "\n"+self.formatException(record.exc_info)
        return text

def configure_logging(directory=None):
    log=logging.getLogger("veriqta")
    log.setLevel(logging.INFO);log.propagate=False
    for handler in list(log.handlers):
        log.removeHandler(handler);handler.close()
    stream=logging.StreamHandler(sys.stdout);stream.setFormatter(JsonFormatter());log.addHandler(stream)
    if directory:
        path=Path(directory);path.mkdir(parents=True,exist_ok=True)
        for filename,formatter in [("app.log",TextFormatter()),("app.jsonl",JsonFormatter())]:
            handler=RotatingFileHandler(path/filename,maxBytes=1048576,backupCount=3,encoding="utf-8")
            handler.setFormatter(formatter);log.addHandler(handler)
    return log

def emit(log,level,event,message,**fields):
    log.log(level,message,extra={"event":event,"fields":fields})

def query_database(rid):
    # No real credentials are written to logs. Connections are short-lived in this lab.
    import psycopg
    with psycopg.connect(host=os.getenv("DB_HOST","db"),port=int(os.getenv("DB_PORT","5432")),
            dbname=os.getenv("DB_NAME","veriqta"),user=os.getenv("DB_USER","veriqta"),
            password=os.environ["DB_PASSWORD"],connect_timeout=2,
            application_name="veriqta-"+rid[:48],options="-c statement_timeout=2000") as conn:
        return conn.execute("SELECT 'Veriqta database reachable' AS result").fetchone()[0]

def startup_check(log):
    if os.getenv("REQUIRE_DB","0")=="1":
        if not os.getenv("DB_HOST") or not os.getenv("DB_PASSWORD"):
            emit(log,logging.ERROR,"config_invalid","Required database configuration is missing")
            raise ValueError("DB_HOST and DB_PASSWORD are required")
        try:
            query_database("startup")
        except Exception as exc:
            emit(log,logging.ERROR,"db_startup_failed","Database startup check failed",error_type=type(exc).__name__)
            raise RuntimeError("Database startup check failed") from None
    emit(log,logging.INFO,"startup","Veriqta Log Lab starting",require_db=os.getenv("REQUIRE_DB","0"))

def handle(path,rid,log):
    emit(log,logging.INFO,"request_started","Request received",request_id=rid,path=path)
    if path in {"/","/health"}:
        return 200,{"message":"Veriqta Log Lab is running","request_id":rid}
    if path=="/error":
        try:raise RuntimeError("Veriqta deliberate lab exception")
        except RuntimeError:
            log.exception("Deliberate lab exception",extra={"event":"lab_exception","fields":{"request_id":rid,"path":path}})
        return 500,{"error":"Deliberate lab failure","request_id":rid}
    if path=="/slow":
        time.sleep(0.3)
        emit(log,logging.WARNING,"slow_operation","Simulated slow operation",request_id=rid,path=path)
        return 200,{"message":"Slow operation completed","request_id":rid}
    if path=="/api/users":
        if os.getenv("REQUIRE_DB","0")!="1":
            return 200,{"users":[{"id":"veriqta-demo"}],"request_id":rid}
        try:
            result=query_database(rid)
            emit(log,logging.INFO,"db_query_ok","Database query completed",request_id=rid)
            return 200,{"result":result,"request_id":rid}
        except Exception as exc:
            emit(log,logging.ERROR,"db_query_failed","Database query failed",request_id=rid,error_type=type(exc).__name__)
            return 503,{"error":"Database unavailable","request_id":rid}
    return 404,{"error":"Route not found","request_id":rid}
```

### `code/nginx/nginx.conf`

```nginx
worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;
events { worker_connections 256; }
http {
    log_format veriqta_json escape=json '{"timestamp":"$time_iso8601","level":"INFO","service":"veriqta-proxy","event":"request_completed","request_id":"$request_id","method":"$request_method","path":"$uri","status":$status,"duration_seconds":$request_time,"upstream_status":"$upstream_status","upstream_seconds":"$upstream_response_time"}';
    access_log /dev/stdout veriqta_json;
    server {
        listen 8080;
        add_header X-Request-ID $request_id always;
        location / {
            proxy_pass http://app:8000;
            proxy_set_header X-Request-ID $request_id;
            proxy_hide_header X-Request-ID;
            proxy_set_header Host $host;
            proxy_connect_timeout 1s;
            proxy_read_timeout 2s;
        }
    }
}
```

### `code/nginx/standalone.conf`

```nginx
worker_processes 1;
pid logs/nginx.pid;
error_log logs/error.log warn;
events { worker_connections 128; }
http {
    log_format veriqta '$remote_addr - $remote_user [$time_local] "$request" '
                        '$status $body_bytes_sent "$http_referer" "$http_user_agent" '
                        '$request_time $request_id';
    access_log logs/access.log veriqta;
    server {
        listen 127.0.0.1:8081;
        add_header X-Request-ID $request_id always;
        location / {
            proxy_pass http://127.0.0.1:5000;
            proxy_set_header X-Request-ID $request_id;
            proxy_hide_header X-Request-ID;
            proxy_connect_timeout 1s;
            proxy_read_timeout 2s;
        }
        location = /timeout {
            proxy_pass http://127.0.0.1:5000/slow;
            proxy_set_header X-Request-ID $request_id;
            proxy_hide_header X-Request-ID;
            proxy_read_timeout 100ms;
        }
    }
}
```

### `code/requirements.txt`

```text
Flask>=3.1,<4
psycopg[binary]>=3.2,<4
```

### `code/systemd/veriqta-api.service`

```ini
[Unit]
Description=Veriqta log investigation application
After=network.target

[Service]
Type=simple
User=veriqta
Group=veriqta
WorkingDirectory=/opt/veriqta-log-lab
Environment=HOST=127.0.0.1
Environment=PORT=5001
Environment=LOG_DIR=
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 /opt/veriqta-log-lab/app.py
Restart=no
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### `code/tests/test_lab.py`

```python
"""Offline behavioral checks for the Veriqta investigation lab."""
import io
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

CODE=Path(__file__).resolve().parents[1]
ROOT=CODE.parent
sys.path.insert(0,str(CODE))
import analyze
import app
import logging_core as core

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.stream=io.StringIO()
        self.log=logging.Logger('veriqta-test')
        handler=logging.StreamHandler(self.stream)
        handler.setFormatter(core.JsonFormatter())
        self.log.addHandler(handler)
        self.env=patch.dict(os.environ,{'REQUIRE_DB':'0'},clear=True)
        self.env.start()
    def tearDown(self):self.env.stop()
    def rows(self):return [json.loads(line) for line in self.stream.getvalue().splitlines()]
    def test_health(self):
        status,body=core.handle('/health','veriqta-test',self.log)
        self.assertEqual(status,200)
        self.assertEqual(body['request_id'],'veriqta-test')
    def test_users_without_database(self):
        status,body=core.handle('/api/users','veriqta-test',self.log)
        self.assertEqual((status,body['users'][0]['id']),(200,'veriqta-demo'))
    def test_missing_route(self):self.assertEqual(core.handle('/missing','id',self.log)[0],404)
    def test_error_has_exception_in_one_json_line(self):
        self.assertEqual(core.handle('/error','id',self.log)[0],500)
        rows=self.rows()
        error=next(r for r in rows if r['event']=='lab_exception')
        self.assertIn('RuntimeError',error['exception'])
        self.assertEqual(error['request_id'],'id')
    def test_slow_route_warns(self):
        with patch.object(core.time,'sleep') as sleep:
            self.assertEqual(core.handle('/slow','id',self.log)[0],200)
            sleep.assert_called_once_with(0.3)
        self.assertEqual(self.rows()[-1]['level'],'WARNING')
    def test_missing_database_configuration(self):
        with patch.dict(os.environ,{'REQUIRE_DB':'1'}):
            with self.assertRaises(ValueError):core.startup_check(self.log)
        self.assertEqual(self.rows()[0]['event'],'config_invalid')
    def test_database_startup_failure_hides_details(self):
        with patch.dict(os.environ,{'REQUIRE_DB':'1','DB_HOST':'db','DB_PASSWORD':'private-value'}):
            with patch.object(core,'query_database',side_effect=RuntimeError('private-value')):
                with self.assertRaises(RuntimeError):core.startup_check(self.log)
        self.assertNotIn('private-value',self.stream.getvalue())
    def test_query_failure_returns_503_without_secret(self):
        with patch.dict(os.environ,{'REQUIRE_DB':'1'}):
            with patch.object(core,'query_database',side_effect=RuntimeError('private-value')):
                status,body=core.handle('/api/users','id',self.log)
        self.assertEqual(status,503)
        self.assertNotIn('private-value',json.dumps(body)+self.stream.getvalue())
    def test_valid_request_id(self):self.assertEqual(core.request_id('veriqta-A_1'),'veriqta-A_1')
    def test_untrusted_request_ids_replaced(self):
        for value in [None,'','a'*65,'id\nforged','id space','id\r']:
            result=core.request_id(value)
            self.assertRegex(result,r'^[a-f0-9]{32}$')
    def test_text_formatter_sanitizes_controls(self):
        record=logging.LogRecord('x',logging.INFO,'',0,'unsafe\nline\r\x1b',(),None)
        self.assertNotRegex(core.TextFormatter().format(record),r'[\r\n\x1b]')
    def test_http_handler_response_without_socket(self):
        handler=app.Handler.__new__(app.Handler)
        handler.headers={'X-Request-ID':'veriqta-handler','User-Agent':'veriqta-test'}
        handler.client_address=('127.0.0.1',12345)
        handler.path='/health?private=value'
        handler.wfile=io.BytesIO()
        statuses=[];headers={}
        handler.send_response=statuses.append
        handler.send_header=lambda key,value:headers.update({key:value})
        handler.end_headers=lambda:None
        with patch.object(app,'LOG',self.log):handler.do_GET()
        self.assertEqual(statuses,[200])
        self.assertEqual(headers['X-Request-ID'],'veriqta-handler')
        self.assertEqual(int(headers['Content-Length']),len(handler.wfile.getvalue()))
        self.assertEqual(json.loads(handler.wfile.getvalue())['request_id'],'veriqta-handler')
        completion=self.rows()[-1]
        self.assertEqual(completion['status'],200)
        self.assertEqual(completion['path'],'/health')
        self.assertNotIn('private=value',self.stream.getvalue())

class AnalysisTests(unittest.TestCase):
    def test_offset_normalization(self):
        self.assertEqual(analyze.timestamp('2026-01-15T16:21:15+02:00'),analyze.timestamp('2026-01-15T14:21:15Z'))
    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):analyze.timestamp('2026-01-15T14:21:15')
    def test_english_access_month(self):
        self.assertEqual(analyze.access_timestamp('15/Jan/2026:14:00:00 +0000'),analyze.timestamp('2026-01-15T14:00:00Z'))
    def test_access_status_counts(self):
        result=analyze.access_summary(ROOT/'datasets/access.log')
        self.assertEqual(result['status_counts'],{'200':6,'404':2,'500':3,'502':1})
    def test_access_error_rate(self):
        result=analyze.access_summary(ROOT/'datasets/access.log')
        self.assertEqual((result['requests'],result['server_errors'],result['server_error_percent']),(12,4,33.333))
    def test_minute_groups(self):
        values=analyze.access_summary(ROOT/'datasets/access.log')['server_errors_per_minute']
        self.assertEqual(list(values.values()),[2,2])
    def test_endpoint_groups(self):
        values=analyze.access_summary(ROOT/'datasets/access.log')['failing_endpoints']
        self.assertEqual(values['/api/users 500'],2)
        self.assertEqual(values['/missing 404'],2)
    def test_before_after_rates(self):
        before=analyze.access_summary(ROOT/'datasets/access-before.log')
        after=analyze.access_summary(ROOT/'datasets/access-after.log')
        self.assertLess(after['server_errors'],before['server_errors'])
        self.assertGreater(after['server_error_percent'],before['server_error_percent'])
    def test_malformed_count(self):
        rows,invalid=analyze.read_json([ROOT/'datasets/malformed.jsonl'])
        self.assertEqual((len(rows),invalid),(1,2))
    def test_first_timeline_failure(self):
        rows,invalid=analyze.read_json([ROOT/'datasets/timeline-unsorted.jsonl'])
        errors=sorted((r for r in rows if r['level']=='ERROR'),key=lambda r:r['_time'])
        self.assertEqual(invalid,0)
        self.assertEqual(errors[0]['event'],'db_connection_failed')
        self.assertEqual(len(rows),8)
    def test_gzip_read(self):
        with analyze.open_text(ROOT/'datasets/app.log.1.gz') as stream:
            self.assertIn('Connection lost',stream.read())
    def test_provenance_cannot_be_spoofed(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'test.jsonl'
            p.write_text(json.dumps({'timestamp':'2026-01-15T00:00:00Z','file':'forged','line':900,'_file':'forged','_line':900})+'\n')
            rows,invalid=analyze.read_json([p])
            result=analyze.serial(rows[0])
            self.assertEqual((result['file'],result['line']),(str(p),1))
            self.assertEqual(invalid,0)
    def test_challenge_failure_precedes_symptom(self):
        rows,invalid=analyze.read_json(sorted((ROOT/'datasets/challenge').glob('*.jsonl')))
        times={r['event']:r['_time'] for r in rows if r.get('request_id')=='veriqta-checkout-42'}
        self.assertLess(times['write_failed'],times['startup_failed'])
        self.assertLess(times['startup_failed'],times['request_completed'])
        self.assertEqual(invalid,0)

if __name__=='__main__':unittest.main()
```

### `.gitignore`

```text
logs/
runtime/
evidence/
.venv/
__pycache__/
*.pyc
.env
.DS_Store
```

### `exercises/incident-report.md`

```markdown
# Incident investigation

## Impact

- Affected service, endpoint and users:
- Start and end, with timezone:
- Request volume, error count and error rate:

## Evidence

| UTC time | Component | Event | File and line | What it establishes |
| --- | --- | --- | --- | --- |
| | | | | |

## Investigation

- First visible symptom:
- Earliest relevant failure:
- Trigger and contributing conditions:
- Causal chain:
- Competing explanation and evidence against it:
- Unknowns and next checks:

## Recovery

- Mitigation and owner:
- User journey checks:
- Dependency and resource checks:
- Observation window:
- Prevention action, owner and due date:
```
