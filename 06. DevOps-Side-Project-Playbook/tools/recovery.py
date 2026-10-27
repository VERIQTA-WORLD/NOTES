"""Encrypted logical backups and verified restore into a separate disposable DB."""
import argparse,datetime,json,os,pathlib,subprocess,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','-f',str(ROOT/'recovery/compose.yaml')]

def sql(service,statement):
    result=subprocess.run(COMPOSE+['exec','-T',service,'psql','-X','-A','-t','-v','ON_ERROR_STOP=1','-U','veriqta','-d','veriqta','-c',statement],capture_output=True,text=True,check=True)
    return result.stdout.strip()

def fingerprint(service):
    # Content comparison lives inside the encrypted backup envelope, not in a public manifest.
    return sql(service,"SELECT coalesce(json_agg(t ORDER BY id)::text,'[]') FROM (SELECT id,name,committed_at FROM veriqta_records) t;")

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('--file');p.add_argument('--passphrase-file',required=True);p.add_argument('--directory',default='artifacts/backups');p.add_argument('--bucket');a=p.parse_args()
    key=pathlib.Path(a.passphrase_file).resolve()
    if not key.is_file() or os.stat(key).st_mode & 0o077:raise SystemExit('Passphrase file must exist with mode 600 or stricter')
    out=pathlib.Path(a.directory);out.mkdir(mode=0o700,parents=True,exist_ok=True)
    crypt=['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(key)]
    with tempfile.TemporaryDirectory(prefix='veriqta-restore-') as temp:
        temp=pathlib.Path(temp)
        if a.action=='backup':
            # Quiesce writes for this small exercise. For concurrent systems, use an exported snapshot.
            backup_started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
            before=fingerprint('db')
            with (temp/'database.dump').open('wb') as stream:
                subprocess.run(COMPOSE+['exec','-T','db','pg_dump','-U','veriqta','-d','veriqta','-Fc','--no-owner','--no-privileges'],stdout=stream,check=True)
            after=fingerprint('db')
            if before!=after:raise SystemExit('Data changed during backup; pause writers and retry')
            metadata={'backup_started_at':backup_started_at,'backup_completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expected_rows':json.loads(after)}
            (temp/'metadata.json').write_text(json.dumps(metadata))
            import tarfile
            with tarfile.open(temp/'backup.tar','w') as archive:
                archive.add(temp/'database.dump',arcname='database.dump');archive.add(temp/'metadata.json',arcname='metadata.json')
            stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            target=out/(stamp+'.tar.gpg');pending=target.with_suffix('.partial')
            subprocess.run(crypt+['--symmetric','--cipher-algo','AES256','--output',str(pending),str(temp/'backup.tar')],check=True)
            pending.replace(target)
            if a.bucket:
                import boto3
                response=boto3.client('s3').put_object(Bucket=a.bucket,Key='postgres/'+target.name,Body=target.read_bytes(),ServerSideEncryption='AES256')
                print(json.dumps({'object':'postgres/'+target.name,'version_id':response.get('VersionId')}))
            print(target)
        else:
            if not a.file:raise SystemExit('--file required; choose a completed backup explicitly')
            started=time.monotonic()
            subprocess.run(crypt+['--decrypt','--output',str(temp/'backup.tar'),a.file],check=True)
            import tarfile
            with tarfile.open(temp/'backup.tar') as archive:
                # Read exact expected regular files only; never extract arbitrary archive paths.
                for name in ('database.dump','metadata.json'):
                    member=archive.getmember(name)
                    if not member.isfile():raise SystemExit('Invalid archive member')
                    (temp/name).write_bytes(archive.extractfile(member).read())
            metadata=json.loads((temp/'metadata.json').read_text())
            # This affects only the separate restored service, never the source db service.
            sql('restored','DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
            with (temp/'database.dump').open('rb') as stream:
                subprocess.run(COMPOSE+['exec','-T','restored','pg_restore','-U','veriqta','-d','veriqta','--no-owner','--no-privileges','--exit-on-error'],stdin=stream,check=True)
            actual=json.loads(fingerprint('restored'))
            passed=actual==metadata['expected_rows']
            report={'content_matches':passed,'restored_rows':len(actual),'restore_validation_seconds':time.monotonic()-started,'backup_started_at':metadata.get('backup_started_at'),'backup_completed_at':metadata['backup_completed_at'],'rto_note':'Add detection, provisioning, retrieval and application recovery time to measure end-to-end RTO.'}
            (out/'restore-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
            if not passed:raise SystemExit(2)
if __name__=='__main__':main()
