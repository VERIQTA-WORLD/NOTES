"""Create a synthetic credential canary in a disposable Git repository."""
import pathlib,secrets,string,subprocess,sys
path=pathlib.Path(sys.argv[1]).resolve()
if path.exists():raise SystemExit('Choose a new temporary directory')
path.mkdir(mode=0o700,parents=True)
subprocess.run(['git','init',str(path)],check=True,stdout=subprocess.DEVNULL)
marker='VERIQTA_'+'CANARY_'+''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(24))
(path/'example.env').write_text('VERIQTA_DEMO_TOKEN='+marker+'\n')
for args in (['add','example.env'],['-c','user.name=Veriqta','-c','user.email=training@example.invalid','commit','-m','Add synthetic credential challenge']):
    subprocess.run(['git','-C',str(path),*args],check=True,stdout=subprocess.DEVNULL)
print('Synthetic challenge repository created. Scan with redaction enabled.')
