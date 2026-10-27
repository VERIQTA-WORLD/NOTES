"""Fail-closed canary gate. Exit 0 pass, 2 reject, 1 telemetry/input error."""
import argparse,json,math,urllib.parse,urllib.request

def decide(stable,canary,minimum=500):
    for name, data in [('stable',stable),('canary',canary)]:
        for key in ('requests','error_ratio','p95_seconds'):
            if key not in data or not isinstance(data[key],(float,int)) or not math.isfinite(data[key]):
                return False,f'{name}: missing/non-finite {key}'
        if data['requests'] < minimum: return False,f'{name}: insufficient traffic'
        if not 0 <= data['error_ratio'] <= 1 or data['p95_seconds'] < 0: return False,f'{name}: invalid measurement'
    if stable['error_ratio'] >= .02 or stable['p95_seconds'] >= .3:
        return False,'baseline unhealthy: pause release and investigate'
    if canary['error_ratio'] >= .02 or canary['p95_seconds'] >= .3:
        return False,'canary violates error/latency budget'
    if canary['error_ratio'] - stable['error_ratio'] > .01:
        return False,'canary regression exceeds one percentage point'
    return True,'canary meets release policy'

def query(base,expr):
    url=base.rstrip('/')+'/api/v1/query?'+urllib.parse.urlencode({'query':expr})
    with urllib.request.urlopen(url,timeout=10) as response: data=json.load(response)
    if data.get('status') != 'success': raise ValueError('Prometheus query failed')
    result=data['data']['result']
    if len(result)!=1: raise ValueError('expected exactly one measurement')
    value=float(result[0]['value'][1])
    if not math.isfinite(value): raise ValueError('missing or non-finite telemetry')
    return value

def sample(base,version):
    if version not in ('v1','v2'):raise ValueError('unknown version')
    target='stable' if version=='v1' else 'canary'
    health='{job="api",track="'+target+'"}'
    if query(base,'min(min_over_time(up'+health+'[5m]))') != 1 or query(base,'min(count_over_time(up'+health+'[5m]))') < 55:
        raise ValueError(target+': require five minutes of healthy scrapes')
    if query(base,'max(time() - timestamp(up'+health+'))') > 15:
        raise ValueError(target+': stale scrape telemetry')
    match='{version="'+version+'"}'
    allreq='sum(increase(http_requests_total'+match+'[5m]))'
    errors='sum(increase(http_requests_total{version="'+version+'",code=~"5.."}[5m]))'
    return {'requests':query(base,allreq),
      'error_ratio':query(base,'('+errors+' or vector(0)) / '+allreq),
      'p95_seconds':query(base,'histogram_quantile(0.95, sum by(le) (rate(http_request_duration_seconds_bucket'+match+'[5m])))')}

def main():
    p=argparse.ArgumentParser();p.add_argument('--prometheus',default='http://localhost:9090');p.add_argument('--fixture')
    a=p.parse_args()
    try:
        data=json.load(open(a.fixture)) if a.fixture else {v:sample(a.prometheus,v) for v in ('v1','v2')}
        passed,reason=decide(data['v1'],data['v2'])
        print(json.dumps({'passed':passed,'reason':reason,'measurements':data},indent=2))
        return 0 if passed else 2
    except Exception as exc:
        print(json.dumps({'passed':False,'reason':str(exc)}));return 1
if __name__=='__main__':raise SystemExit(main())
