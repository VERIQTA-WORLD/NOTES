"""Best-effort preparation filter. A human data review is still required."""
import argparse,json,pathlib,re
SENSITIVE=re.compile(r'password|passwd|secret|token|authorization|api[_-]?key|private[_-]?key|cookie',re.I)

def redact(text):
    text=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[REDACTED PRIVATE KEY]',text,flags=re.S)
    text=re.sub(r'(?i)(https?://|postgres(?:ql)?://)([^\s/@]+):([^\s/@]+)@',r'\1[REDACTED]@',text)
    text=re.sub(r'(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+',r'\1[REDACTED]',text)
    text=re.sub(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b','[REDACTED ACCESS ID]',text)
    text=re.sub(r'(?i)(\b(?:password|passwd|secret|token|api_key|api-key)\s*[=:]\s*)[^\s,;]+',r'\1[REDACTED]',text)
    return text

def clean(value):
    if isinstance(value,dict):return {k:'[REDACTED]' if SENSITIVE.search(str(k)) else clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str):return redact(value)
    return value

def sanitize(text):
    try:return json.dumps(clean(json.loads(text)),indent=2)+'\n'
    except json.JSONDecodeError:return redact(text)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',required=True);a=p.parse_args()
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(sanitize(pathlib.Path(a.input).read_text()));target.chmod(0o600)
    print('Prepared a filtered copy; review it before sharing.')
