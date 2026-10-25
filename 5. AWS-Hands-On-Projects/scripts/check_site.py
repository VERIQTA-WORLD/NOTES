"""Check required pages and local href/src targets without network access."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[1]/'site'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=[]
    def handle_starttag(self,tag,attrs):
        self.targets += [value for key,value in attrs if key in {'href','src'} and value]
def validate(root=ROOT):
    root=Path(root).resolve();errors=[]
    for name in ['index.html','about.html','style.css']:
        if not (root/name).is_file():errors.append('Missing required file: '+name)
    for page in root.rglob('*.html'):
        parser=Links();parser.feed(page.read_text())
        for target in parser.targets:
            url=urlsplit(target)
            if url.scheme or url.netloc or not url.path:continue
            dest=(root/unquote(url.path.lstrip('/')) if url.path.startswith('/') else page.parent/unquote(url.path)).resolve()
            if root not in dest.parents or not dest.is_file():errors.append(f'{page.name}: invalid local target {target}')
    return errors
if __name__=='__main__':
    errors=validate()
    if errors:raise SystemExit('\n'.join(errors))
    print('Veriqta website file/link checks passed')
