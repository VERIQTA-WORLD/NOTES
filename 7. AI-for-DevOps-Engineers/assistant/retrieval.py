"""Small local lexical retriever with stable source IDs and no external storage."""
import math,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]/'runbooks'
def tokens(text):return set(re.findall(r'[a-z0-9_]+',text.lower()))
def retrieve(question,limit=3):
    query=tokens(question);items=[]
    for path in sorted(ROOT.glob('*.md')):
        if path.is_symlink():continue
        text=path.read_text()[:8000];words=tokens(text)
        score=len(query & words)/math.sqrt(max(1,len(words)))
        if score:items.append({'id':'runbook:'+path.name,'text':text,'score':round(score,6)})
    return sorted(items,key=lambda x:(-x['score'],x['id']))[:limit]
