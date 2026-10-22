from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import hashlib, json, re, subprocess
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src') and v:self.links.append(v)
proof={}
for name in ['V2_OVERVIEW_RU.html','V2_ROUTING_CLEANUP_2026_10_22_RU.html']:
    p=ROOT/'output'/name;page=p.read_text('utf-8');parser=Links();parser.feed(page)
    local=[x for x in parser.links if not urlsplit(x).scheme and not x.startswith('#')]
    missing=[x for x in local if not (p.parent/unquote(urlsplit(x).path)).exists()]
    assert not missing,missing
    assert '__AUDIT_BASE__' not in page
    js=re.search(r'<script>(.*?)</script>',page,re.S).group(1)
    test="const els={};global.document={getElementById(id){return els[id]||(els[id]={})}};\n"+js+"\nsetView('test','before','POWER','front');if(!els.test.src.endsWith('/before/POWER/POWER_routes_front.png'))throw Error('Before view');setView('test','after','LOGIC','back');if(!els.test.src.endsWith('/after/LOGIC/LOGIC_routes_back.png'))throw Error('After view');"
    node=r'C:/Users/Alksndr/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    r=subprocess.run([node,'-e',test],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    proof[name]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),local_links=len(local),missing_links=missing,before_after_switch_logic='PASS')
assert (ROOT/'output/V2_OVERVIEW_RU.html').read_bytes()==(ROOT/'output/V2_ROUTING_CLEANUP_2026_10_22_RU.html').read_bytes()
(HERE/'report_QA.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(proof,indent=2))
