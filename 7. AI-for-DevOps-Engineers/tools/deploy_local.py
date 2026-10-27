"""Local candidate validation and rollback; no database backup or zero-downtime claim."""
import argparse,json,pathlib,re,subprocess,time
from tools.check_service import check
CURRENT='veriqta-review-app';CANDIDATE='veriqta-review-candidate';BACKUP='veriqta-review-previous'

def docker(*args,check_error=True):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=120)
    if check_error and result.returncode:raise RuntimeError('Docker step failed: '+args[0])
    return result

def exists(name):return docker('container','inspect',name,check_error=False).returncode==0

def start(name,image,port):
    docker('run','-d','--name',name,'--read-only','--tmpfs','/tmp','--cap-drop','ALL',
       '--security-opt','no-new-privileges','--memory','256m','--cpus','1',
       '-e','APP_CONFIG=lab','-p',f'127.0.0.1:{port}:8000',image)

def wait_healthy(port):
    for _ in range(20):
        if check(f'http://127.0.0.1:{port}/health',timeout=1)[0]==0:return
        time.sleep(.5)
    raise RuntimeError('Business health did not pass')

def deploy(image):
    if not re.fullmatch(r'[a-z0-9][a-z0-9./:@_-]{1,240}',image):raise ValueError('invalid image reference')
    if '@sha256:' not in image and not image.startswith('veriqta-ai-api:'):raise ValueError('Use an immutable registry digest or a local Veriqta lab tag')
    docker('info');docker('image','inspect',image)
    if exists(CANDIDATE) or exists(BACKUP):raise RuntimeError('Previous candidate/backup exists; inspect it before another deployment')
    old=exists(CURRENT);switched=False;old_stopped=False;new_attempted=False
    try:
        start(CANDIDATE,image,8005);wait_healthy(8005)
        if old:
            docker('stop',CURRENT);old_stopped=True
            docker('rename',CURRENT,BACKUP);switched=True
        new_attempted=True;start(CURRENT,image,8004);wait_healthy(8004)
        if old:docker('rm',BACKUP)
        return {'result':'deployed','image':image,'business_health':'passed'}
    except Exception:
        if new_attempted and exists(CURRENT):docker('rm','-f',CURRENT,check_error=False)
        if switched:
            docker('rename',BACKUP,CURRENT);docker('start',CURRENT);wait_healthy(8004)
        elif old_stopped:
            docker('start',CURRENT);wait_healthy(8004)
        raise
    finally:
        if exists(CANDIDATE):docker('rm','-f',CANDIDATE,check_error=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);a=p.parse_args()
    print(json.dumps(deploy(a.image),indent=2))
