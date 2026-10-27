#!/usr/bin/env python3
"""HTTP probe: 0 healthy, 1 HTTP failure, 2 timeout, 3 connection, 4 usage."""
import argparse,json,socket,time,urllib.error,urllib.parse,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_):return None

def validate_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTP(S) URL without credentials, query or fragment')
    return url

def check(url,timeout=2,opener=None):
    validate_url(url)
    if not .05<=timeout<=30:raise ValueError('timeout must be 0.05..30 seconds')
    opened=opener or urllib.request.build_opener(NoRedirect()).open
    start=time.monotonic();result={'service':url,'healthy':False}
    try:
        # No body download and no redirect following. A 200 login page still needs semantic checks.
        with opened(urllib.request.Request(url,method='GET'),timeout=timeout) as response:
            result['status_code']=response.status
            result['healthy']=200<=response.status<300
            code=0 if result['healthy'] else 1
    except urllib.error.HTTPError as exc:
        result.update(status_code=exc.code,error='http_error');exc.close();code=1
    except (TimeoutError,socket.timeout):result['error']='timeout';code=2
    except urllib.error.URLError as exc:
        timed=isinstance(exc.reason,(TimeoutError,socket.timeout))
        result['error']='timeout' if timed else 'connection_error';code=2 if timed else 3
    except OSError:result['error']='connection_error';code=3
    result['elapsed_seconds']=round(time.monotonic()-start,6)
    return code,result

def main():
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--timeout',type=float,default=2);a=p.parse_args()
    try:code,result=check(a.url,a.timeout)
    except ValueError as exc:print(json.dumps({'healthy':False,'error':str(exc)}));return 4
    print(json.dumps(result,indent=2));return code
if __name__=='__main__':raise SystemExit(main())
