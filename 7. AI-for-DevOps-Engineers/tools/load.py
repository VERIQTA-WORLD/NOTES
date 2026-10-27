"""Bounded HTTP load. No implicit retries; HTTP error responses are measured."""
import argparse, collections, concurrent.futures, json, time, urllib.error, urllib.request

def request(url):
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            response.read(); code = response.status
    except urllib.error.HTTPError as exc:
        exc.read(); code = exc.code
    except (urllib.error.URLError, TimeoutError): code = 0
    return code, time.monotonic() - start

def main():
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--requests',type=int,default=1000)
    p.add_argument('--concurrency',type=int,default=10);p.add_argument('--pause',type=float,default=.02)
    a=p.parse_args()
    if not 1 <= a.requests <= 100000 or not 1 <= a.concurrency <= 100: p.error('bounded load: 1..100000 requests; 1..100 workers')
    def run(_):
        result=request(a.url);time.sleep(a.pause);return result
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as executor:
        results=list(executor.map(run,range(a.requests)))
    latencies=sorted(t for _,t in results)
    print(json.dumps({'requests':len(results),'codes':dict(collections.Counter(c for c,_ in results)),
       'p95_seconds':latencies[max(0, int(.95*len(latencies)+.999)-1)],
       'elapsed_seconds':time.monotonic()-start},indent=2))
if __name__=='__main__':main()
