import datetime,importlib.util,json,pathlib,tempfile,unittest,io
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
gate=load('gate','tools/gate.py');drift=load('drift','tools/drift.py');costs=load('costs','tools/costs.py');env=load('env','tools/environments.py');replay=load('replay','tools/replay.py');api=load('api','app/api.py')
class Tools(unittest.TestCase):
    def test_release_good_and_bad(self):
        for file,expected in [('canary-good.json',True),('canary-bad.json',False)]:
            data=json.loads((ROOT/'fixtures'/file).read_text());self.assertEqual(gate.decide(data['v1'],data['v2'])[0],expected)
    def test_missing_traffic_and_nan_block(self):
        good={'requests':1000,'error_ratio':0,'p95_seconds':.1}
        for bad in ({**good,'requests':0},{**good,'error_ratio':float('nan')},{**good,'p95_seconds':.31}):self.assertFalse(gate.decide(good,bad)[0])
        self.assertFalse(gate.decide({**good,'error_ratio':.03},good)[0])
    def test_drift_direction(self):
        data=json.loads((ROOT/'fixtures/drift.json').read_text());self.assertEqual(drift.classify(data)['observed_drift'][0]['risk'],'high')
        data['resource_drift'][0]['change']['after']['cidr_ipv4']='10.42.0.0/16'
        self.assertEqual(drift.classify(data)['observed_drift'][0]['risk'],'unclassified')
    def test_normalized_costs(self):
        rows=[{'date':'2026-01-01','service':'EC2','owner':'a','usd':'300'},{'date':'2026-01-31','service':'EC2','owner':'a','usd':'70'}]
        r=costs.compare(rows,'2026-01-01','2026-01-31','2026-02-07')[0]
        self.assertEqual(r['baseline_per_day'],r['recent_per_day']);self.assertFalse(r['flag'])
    def test_cost_fixture_forty_percent(self):
        from decimal import Decimal
        r=costs.compare(json.loads((ROOT/'fixtures/costs.json').read_text()),'2026-01-01','2026-01-08','2026-01-15')
        b=sum(x['baseline_per_day'] for x in r);a=sum(x['recent_per_day'] for x in r)
        self.assertAlmostEqual(float((a-b)/b),.4)
    def test_expiry_and_scope(self):
        now=datetime.datetime(2026,1,1,tzinfo=datetime.timezone.utc)
        ns=env.render('veriqta-env-demo','reader',1,now)['items'][0]
        self.assertFalse(env.expired(ns,now));self.assertTrue(env.expired(ns,now+datetime.timedelta(hours=2)))
        ns['metadata']['name']='kube-system';self.assertFalse(env.expired(ns,now+datetime.timedelta(hours=2)))
        with self.assertRaises(ValueError):env.render('default','reader',24)
        with self.assertRaises(ValueError):env.render('veriqta-env-demo','reader',0)
    def test_timeline_utc_and_html_escape(self):
        self.assertEqual(replay.timestamp('2026-01-01T01:00:00+01:00').hour,0)
        with self.assertRaises(ValueError):replay.timestamp('2026-01-01T01:00:00')
        with tempfile.TemporaryDirectory() as directory:
            timeline,gaps=replay.build({s:ROOT/'fixtures/incident'/s for s in ('logs','events','traces','deployments')},directory)
            self.assertEqual(len(timeline),4);self.assertFalse(gaps)
            self.assertEqual(timeline,sorted(timeline,key=lambda r:(r['timestamp'],r['source'],r['evidence'])))
    def test_request_metrics_and_deterministic_errors(self):
        previous=api.ERROR_EVERY;api.ERROR_EVERY=5;api.REQUESTS=0
        results=[api.business()[0] for _ in range(10)]
        self.assertEqual(results.count(500),2)
        api.COUNTS={};api.HIST=[0]*len(api.BUCKETS);api.TOTAL=0
        api.observe(200,.2);api.observe(500,.4)
        data=api.metrics();self.assertIn('le="0.3"} 1',data);self.assertIn('code="500"} 1',data)
        api.ERROR_EVERY=previous
    def test_http_routes_in_memory(self):
        class Handler(api.Handler):
            def __init__(self,path):self.path=path;self.wfile=io.BytesIO();self.status=None;self.headers={}
            def send_response(self,code):self.status=code
            def send_header(self,key,value):self.headers[key]=value
            def end_headers(self):pass
        with patch.object(api,'log'):
            for path,expected in [('/api',200),('/healthz',200),('/readyz',200),('/metrics',200),('/missing',404)]:
                handler=Handler(path);handler.do_GET();self.assertEqual(handler.status,expected)
                self.assertEqual(int(handler.headers['Content-Length']),len(handler.wfile.getvalue()))
    def test_gate_scrape_failure_blocks(self):
        with patch.object(gate,'query',return_value=0):
            with self.assertRaises(ValueError):gate.sample('http://unused','v2')
        with patch.object(gate,'query',side_effect=[1,60,20]):
            with self.assertRaises(ValueError):gate.sample('http://unused','v1')
    def test_uid_delete_precondition(self):
        ns={'metadata':{'name':'veriqta-env-test','uid':'original-uid','resourceVersion':'123'}}
        with patch.object(env,'kube') as call:
            env.delete(ns)
            self.assertEqual(call.call_args.kwargs['body']['preconditions']['uid'],'original-uid')
            self.assertEqual(call.call_args.kwargs['body']['preconditions']['resourceVersion'],'123')
            self.assertEqual(call.call_args.args[2],'/api/v1/namespaces/veriqta-env-test')
    def test_retry_budget_is_bounded(self):
        class BrokenPool:
            def connection(self):raise RuntimeError('do not log secret details')
        with patch.object(api,'POOL',BrokenPool()), patch.object(api,'ERROR_EVERY',0), patch.object(api,'DB_RETRIES',2), patch.object(api,'log') as log, patch.object(api.time,'sleep'):
            self.assertEqual(api.business()[0],503)
            self.assertEqual(log.call_count,3)
            self.assertNotIn('secret',str(log.call_args_list))
    def test_replay_escapes_untrusted_html_and_reports_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);logs=root/'logs';logs.mkdir()
            (logs/'a.json').write_text(json.dumps({'timestamp':'2026-01-01T00:00:00Z','service':'api','event':'<script>alert(1)</script>'}))
            output=root/'report'
            rows,gaps=replay.build({'logs':logs,'events':root/'absent'},output)
            self.assertEqual(len(rows),1);self.assertEqual(len(gaps),1)
            self.assertNotIn('<script>',(output/'timeline.html').read_text())
    def test_expiry_invalid_time_and_missing_owner(self):
        ns=env.render('veriqta-env-test','reader',1)['items'][0]
        ns['metadata']['annotations']['veriqta.io/expires-at']='2020-01-01T00:00:00'
        self.assertFalse(env.expired(ns))
        ns['metadata']['annotations']['veriqta.io/expires-at']='2020-01-01T00:00:00Z'
        del ns['metadata']['annotations']['veriqta.io/owner']
        self.assertFalse(env.expired(ns))
if __name__=='__main__':unittest.main()
