"""Veriqta instrumented API: deterministic release errors and optional real DB pool."""
import contextlib
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.getenv('VERSION', 'v1')
if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', VERSION):
    raise ValueError('VERSION must be a short metric-safe identifier')
ERROR_EVERY = int(os.getenv('ERROR_EVERY', '0'))
DB_RETRIES = int(os.getenv('DB_RETRIES', '0'))
DB_HOLD = float(os.getenv('DB_HOLD', '.01'))
if not 0 <= ERROR_EVERY <= 10000 or not 0 <= DB_RETRIES <= 3 or not 0 <= DB_HOLD <= 5:
    raise ValueError('Failure settings exceed the bounded lab range')
READY = os.getenv('READY', 'true') == 'true'
BUCKETS = (.05, .1, .3, .5, 1, 2, 5, 10, float('inf'))
LOCK = threading.Lock()
COUNTS, HIST, TOTAL = {}, [0] * len(BUCKETS), 0.0
REQUESTS = 0
POOL = None
TRACER = None
if os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'):
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    provider = TracerProvider(resource=Resource.create({'service.name': 'veriqta-api', 'service.version': VERSION}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    TRACER = trace.get_tracer('veriqta.api')
if os.getenv('DB_HOST'):
    from psycopg_pool import ConnectionPool
    # Keyword arguments avoid DSN interpolation and keep passwords out of logs.
    POOL = ConnectionPool('', min_size=1, max_size=int(os.getenv('POOL_SIZE', '8')),
        timeout=float(os.getenv('POOL_TIMEOUT', '.25')),
        kwargs={'host': os.environ['DB_HOST'], 'dbname': os.getenv('DB_NAME', 'veriqta'),
                'user': os.getenv('DB_USER', 'veriqta'), 'password': os.environ['DB_PASSWORD'],
                'connect_timeout': 3, 'port': int(os.getenv('DB_PORT', '5432'))}, open=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def log(event, **fields):
    if TRACER:
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            fields.setdefault('trace_id', f'{context.trace_id:032x}')
            fields.setdefault('span_id', f'{context.span_id:016x}')
    print(json.dumps({'timestamp': now(), 'service': 'api', 'version': VERSION,
                      'event': event, **fields}), flush=True)

def span(name):
    return TRACER.start_as_current_span(name) if TRACER else contextlib.nullcontext(None)

def business():
    global REQUESTS
    with LOCK:
        REQUESTS += 1
        seq = REQUESTS
    if ERROR_EVERY and seq % ERROR_EVERY == 0:
        return 500, {'status': 'error', 'version': VERSION}
    if POOL:
        retries = DB_RETRIES
        for attempt in range(retries + 1):
            try:
                with span('db.pool-and-query') as s:
                    if s: s.set_attribute('db.system', 'postgresql')
                    with POOL.connection() as conn:
                        conn.execute('SELECT pg_sleep(%s)', (DB_HOLD,))
                        count = conn.execute('SELECT count(*) FROM veriqta_records').fetchone()[0]
                return 200, {'status': 'ok', 'version': VERSION, 'records': count}
            except Exception as exc:
                # Class names only: connection exceptions may contain host names/credentials.
                log('db_attempt_failed', attempt=attempt + 1, error_type=type(exc).__name__)
                if attempt == retries:
                    return 503, {'status': 'db_unavailable', 'version': VERSION}
                time.sleep(.02 * (attempt + 1))
    return 200, {'status': 'ok', 'version': VERSION}

def observe(code, elapsed):
    global TOTAL
    with LOCK:
        COUNTS[str(code)] = COUNTS.get(str(code), 0) + 1
        TOTAL += elapsed
        for i, bound in enumerate(BUCKETS):
            if elapsed <= bound: HIST[i] += 1

def metrics():
    with LOCK:
        lines = ['# TYPE http_requests_total counter']
        for code, value in sorted(COUNTS.items()):
            lines.append(f'http_requests_total{{version="{VERSION}",code="{code}"}} {value}')
        lines.append('# TYPE http_request_duration_seconds histogram')
        for bound, value in zip(BUCKETS, HIST):
            le = '+Inf' if bound == float('inf') else str(bound)
            lines.append(f'http_request_duration_seconds_bucket{{version="{VERSION}",le="{le}"}} {value}')
        lines += [f'http_request_duration_seconds_count{{version="{VERSION}"}} {sum(COUNTS.values())}',
                  f'http_request_duration_seconds_sum{{version="{VERSION}"}} {TOTAL}']
        if POOL:
            for key, value in POOL.get_stats().items():
                lines.append(f'db_pool_{key}{{version="{VERSION}"}} {value}')
        return '\n'.join(lines) + '\n'

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/metrics':
            self.reply(200, metrics().encode(), 'text/plain; version=0.0.4'); return
        if path == '/healthz':
            self.reply(200, b'alive'); return
        if path == '/readyz':
            healthy = READY
            if healthy and POOL:
                try:
                    with POOL.connection(timeout=.2) as conn: conn.execute('SELECT 1')
                except Exception: healthy = False
            self.reply(200 if healthy else 503, b'ready' if healthy else b'not ready'); return
        if path != '/api':
            self.reply(404, b'not found'); return
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        with span('GET /api') as s:
            code, body = business()
            elapsed = time.monotonic() - started
            observe(code, elapsed)
            trace_id = f'{s.get_span_context().trace_id:032x}' if s else None
            if s:
                s.set_attribute('http.response.status_code', code)
                s.set_attribute('request.id', request_id)
            log('request', code=code, duration_seconds=round(elapsed, 6),
                request_id=request_id, trace_id=trace_id)
            self.reply(code, json.dumps(body).encode())
    def reply(self, code, payload, content_type='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try: self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError): pass

if __name__ == '__main__':
    if os.getenv('CRASH') == 'true': raise SystemExit('Veriqta simulated startup configuration failure')
    log('startup')
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
