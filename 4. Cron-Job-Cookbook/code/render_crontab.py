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
