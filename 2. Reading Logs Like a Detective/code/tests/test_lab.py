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
