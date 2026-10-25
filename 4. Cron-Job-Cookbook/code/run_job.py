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
