#!/usr/bin/env python3
"""Requests variant with explicit connect/read timeout and response cleanup."""
import argparse,json,time
from tools.check_service import validate_url

def check(url,timeout=2,client=None):
    validate_url(url)
    if not .05<=timeout<=30:raise ValueError('timeout must be 0.05..30 seconds')
    if client is None:
        import requests
        client=requests
    start=time.monotonic();result={'service':url,'healthy':False}
    try:
        with client.get(url,timeout=(timeout,timeout),allow_redirects=False,stream=True) as response:
            result['status_code']=response.status_code;result['healthy']=200<=response.status_code<300
            code=0 if result['healthy'] else 1
    except client.exceptions.Timeout:result['error']='timeout';code=2
    except client.exceptions.RequestException:result['error']='connection_error';code=3
    result['elapsed_seconds']=round(time.monotonic()-start,6);return code,result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--timeout',type=float,default=2);a=p.parse_args()
    try:code,result=check(a.url,a.timeout)
    except ValueError as exc:print(json.dumps({'healthy':False,'error':str(exc)}));raise SystemExit(4)
    print(json.dumps(result,indent=2));raise SystemExit(code)
