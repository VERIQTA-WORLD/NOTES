"""Threaded API with bounded failure settings, business checks, metrics and tracing."""
import contextlib,json,os,re,resource,threading,time,uuid
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

class Settings:
    def __init__(self,env=None):
        env=os.environ if env is None else env
        self.app_config=env.get('APP_CONFIG','')
        self.release=env.get('RELEASE','v1')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,60}',self.release):raise ValueError('invalid release identifier')
        self.port=int(env.get('PORT','8000'))
        self.delay=float(env.get('DELAY_SECONDS','0'))
        self.error_every=int(env.get('ERROR_EVERY','0'))
        if not 0<=self.delay<=3 or not 0<=self.error_every<=10000:raise ValueError('failure setting out of range')
        self.db_enabled=env.get('DB_ENABLED','false')=='true'
        self.db_host=env.get('DB_HOST','db')
        self.db_port=int(env.get('DB_PORT','5432'))
        self.db_name=env.get('DB_NAME','veriqta')
        self.db_user=env.get('DB_USER','veriqta')
        self.db_password=env.get('DB_PASSWORD','')
        self.readiness_db=env.get('READINESS_CHECK_DB','false')=='true'
        self.otel=env.get('OTEL_EXPORTER_OTLP_ENDPOINT')

SETTINGS=None
LOCK=threading.Lock()
REQUESTS=0
COUNTS={}
BOUNDS=(.05,.1,.3,.5,1,2,5,float('inf'))
HIST=[0]*len(BOUNDS)
DURATION_SUM=0.0
TRACER=None

def utcnow():return datetime.now(timezone.utc).isoformat()

def log(event,**fields):
    if TRACER:
        from opentelemetry import trace
        ctx=trace.get_current_span().get_span_context()
        if ctx.is_valid:fields.update(trace_id=f'{ctx.trace_id:032x}',span_id=f'{ctx.span_id:016x}')
    print(json.dumps({'timestamp':utcnow(),'service':'veriqta-api','release':SETTINGS.release if SETTINGS else 'unknown','event':event,**fields}),flush=True)

def tracing(settings):
    global TRACER
    if not settings.otel:return
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    provider=TracerProvider(resource=Resource.create({'service.name':'veriqta-api','service.version':settings.release}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider);TRACER=trace.get_tracer('veriqta.api')

def span(name):return TRACER.start_as_current_span(name) if TRACER else contextlib.nullcontext(None)

def database(settings):
    import psycopg
    with psycopg.connect(host=settings.db_host,port=settings.db_port,dbname=settings.db_name,
          user=settings.db_user,password=settings.db_password,connect_timeout=2,
          options='-c statement_timeout=2000') as connection:
        return connection.execute('SELECT id,name FROM veriqta_users ORDER BY id').fetchall()

def business(settings,path):
    global REQUESTS
    with LOCK:REQUESTS+=1;sequence=REQUESTS
    if settings.error_every and sequence%settings.error_every==0:
        return 500,{'status':'error','error_kind':'injected_failure'}
    with span('dependency.users') as current:
        if settings.delay:time.sleep(settings.delay)
        if settings.db_enabled:
            try:rows=database(settings)
            except Exception as exc:
                # Keep DSNs, passwords, addresses and raw exception text out of logs.
                if current:
                    from opentelemetry.trace import Status,StatusCode
                    current.set_status(Status(StatusCode.ERROR,'database request failed'))
                    current.set_attribute('error.type',type(exc).__name__)
                log('dependency_failed',error_kind='database_unavailable',error_type=type(exc).__name__)
                return 500,{'status':'error','error_kind':'database_unavailable'}
        else:rows=[(1,'veriqta-alpha'),(2,'veriqta-beta')]
    body={'status':'ok','release':settings.release}
    if path=='/api/users':body['users']=[{'id':i,'name':name} for i,name in rows]
    return 200,body

def observe(path,code,elapsed):
    global DURATION_SUM
    # Only fixed business routes enter metrics; never use a request ID or raw URL label.
    with LOCK:
        key=(path,str(code));COUNTS[key]=COUNTS.get(key,0)+1;DURATION_SUM+=elapsed
        for i,bound in enumerate(BOUNDS):
            if elapsed<=bound:HIST[i]+=1

def metrics(settings):
    with LOCK:
        rows=['# TYPE http_requests_total counter']
        for (path,code),count in sorted(COUNTS.items()):
            rows.append(f'http_requests_total{{release="{settings.release}",path="{path}",status="{code}"}} {count}')
        rows.append('# TYPE http_request_duration_seconds histogram')
        for bound,count in zip(BOUNDS,HIST):
            le='+Inf' if bound==float('inf') else str(bound)
            rows.append(f'http_request_duration_seconds_bucket{{release="{settings.release}",le="{le}"}} {count}')
        rows += [f'http_request_duration_seconds_count{{release="{settings.release}"}} {sum(COUNTS.values())}',
                 f'http_request_duration_seconds_sum{{release="{settings.release}"}} {DURATION_SUM}']
    usage=resource.getrusage(resource.RUSAGE_SELF)
    rows+=['# TYPE process_cpu_seconds_total counter',f'process_cpu_seconds_total {usage.ru_utime+usage.ru_stime}']
    try:
        with open('/proc/self/statm') as f:rss=int(f.read().split()[1])*os.sysconf('SC_PAGE_SIZE')
        rows+=['# TYPE process_resident_memory_bytes gauge',f'process_resident_memory_bytes {rss}']
    except (OSError,ValueError,IndexError):pass
    return '\n'.join(rows)+'\n'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path=='/healthz':self.reply(200,{'status':'alive'});return
        if path=='/readyz':
            ready=bool(SETTINGS.app_config)
            if ready and SETTINGS.readiness_db and SETTINGS.db_enabled:
                try:database(SETTINGS)
                except Exception:ready=False
            self.reply(200 if ready else 503,{'ready':ready});return
        if path=='/metrics':self.reply(200,metrics(SETTINGS),'text/plain; version=0.0.4');return
        if path not in ('/api/users','/health'):
            self.reply(404,{'status':'not_found'});return
        start=time.monotonic()
        with span('GET '+path) as current:
            code,body=business(SETTINGS,path);elapsed=time.monotonic()-start
            if current:current.set_attribute('http.response.status_code',code)
            observe(path,code,elapsed)
            log('request',path=path,status=code,duration_seconds=round(elapsed,6),request_id=uuid.uuid4().hex)
            self.reply(code,body)
    def reply(self,code,body,content_type='application/json'):
        raw=(body if isinstance(body,str) else json.dumps(body)).encode()
        self.send_response(code);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(raw)));self.end_headers()
        try:self.wfile.write(raw)
        except (BrokenPipeError,ConnectionResetError):pass

def main():
    global SETTINGS
    SETTINGS=Settings()
    if not SETTINGS.app_config:
        log('startup_failed',error_kind='missing_app_config');raise SystemExit(1)
    tracing(SETTINGS);log('startup')
    ThreadingHTTPServer(('0.0.0.0',SETTINGS.port),Handler).serve_forever()
if __name__=='__main__':main()
