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
