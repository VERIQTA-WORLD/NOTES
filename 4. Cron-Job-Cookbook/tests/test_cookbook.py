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
