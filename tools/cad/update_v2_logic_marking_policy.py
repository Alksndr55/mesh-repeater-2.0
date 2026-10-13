"""LOGIC owner captions: one per part, real-body axis, only printed silk edits."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
from update_v2_power_marking_policy import text_blocks,without_silk
from place_v2_power_front_labels import box,union,relocate

def update(pcb):
    raw=pcb.read_bytes(); s=raw.decode('utf-8'); b=k.LoadBoard(str(pcb)); held=[b]
    fps={f.GetReference():f for f in b.GetFootprints()}; axes={}; owners={}
    for ref,f in fps.items():
        shapes=[box(g) for g in f.GraphicalItems() if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==k.F_Fab]
        q=union(shapes or [box(p) for p in f.Pads()]); w,h=q[2]-q[0],q[3]-q[1]
        axes[ref]=0 if w>h*1.15 else 90 if h>w*1.15 else (90 if abs(f.GetOrientationDegrees()%180-90)<.01 else 0)
    rows=text_blocks(s)
    for t in rows:
        m=re.match(r'^([A-Z]+\d+)(?:\s|$)',t['text'])
        if t['layer'] in ('F.SilkS','B.SilkS') and m and m[1] in fps: owners.setdefault(m[1],[]).append(t)
    changes=[];removed=[];kept={}
    for ref,options in owners.items():
        maps=[t for t in options if ref.startswith('J') and re.search(r'(?:^|\n| )[1-9](?:/[1-9])? ',t['text'])]
        front=[t for t in options if t['layer']=='F.SilkS']
        if front and not ref.startswith(('J','H','TP','NT')):
            oldangle=float(re.search(r'\(at [^ )]+ [^ )]+(?: ([^ )]+))?\)',front[0]['block'])[1] or 0)%180
            if abs(oldangle-axes[ref])>.01: front=[]
        choices=maps or front or [t for t in options if t['layer']=='B.SilkS'] or options
        t=max(choices,key=lambda t:len(t['text']));kept[ref]=t
        for duplicate in options:
            if duplicate is not t: changes.append((duplicate['start'],duplicate['end'],'')); removed.append({'ref':ref,'text':duplicate['text'],'layer':duplicate['layer'],'uuid':duplicate['uuid']})
        value=t['text']; new=value
        if ref=='U7':new=new.replace('74LVC\n2G125','74LVC2G125')
        if ref=='FL1':new=new.replace('S869M000\nS003','S869M000S003')
        if ref.startswith('R'):
            new=re.sub(r'(\d+)\.(\d+)([kMR])',lambda m:m[1]+m[3]+m[2],new)
        block=t['block'].replace(json.dumps(value,ensure_ascii=False),json.dumps(new,ensure_ascii=False),1)
        if not ref.startswith(('J','H','TP','NT')):
            m=re.search(r'\(at ([^ )]+) ([^ )]+)(?: [^ )]+)?\)',block)
            block=block[:m.start()]+f'(at {m[1]} {m[2]} {axes[ref]})'+block[m.end():]
        if block!=t['block']:changes.append((t['start'],t['end'],block))
    for start,end,v in sorted(changes,reverse=True):s=s[:start]+v+s[end:]
    s=re.sub(r'(?m)^[\t ]+(?=\r?$)','',s)
    assert without_silk(raw.decode('utf-8'))==without_silk(s)
    pcb.write_bytes(s.encode('utf-8'))
    relocation=relocate(pcb,priority=['M1','M2','BT1','U4','U6','U7','FL1'],axis_ratio=1.15)
    from style_v2_logic_annotations import style
    styled,annotation_proof=style(pcb,ROOT/'tmp/logic_annotation_serialization.kicad_pcb')
    pcb.write_bytes(styled)
    return dict(before_sha256=hashlib.sha256(raw).hexdigest(),removed_duplicates=removed,
                removed_count=len(removed),owner_count=len(kept),axes=axes,front_relocation=relocation,
                annotation_style=annotation_proof,only_F_B_silkscreen_drawings_changed=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pcb',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    for x in (a.pcb,a.out,a.report):assert x.resolve().is_relative_to(ROOT)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(a.pcb.read_bytes())
    proof=update(a.out);proof['after_sha256']=hashlib.sha256(a.out.read_bytes()).hexdigest()
    a.report.write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'owners':proof['owner_count'],'removed':proof['removed_count'],'front_placements':len(proof['front_relocation']['placements'])}))
