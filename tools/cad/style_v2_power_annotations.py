"""Uniform POWER connector legends and visible option frames; silk-only patch.

Native KiCad glyph/pad shapes determine clearance. SaveBoard is used only for
a scratch serialization; live copper, footprints and all other layers retain
their original text byte for byte (apart from whitespace normalization).
"""
from pathlib import Path
import argparse, hashlib, json, math, re, sys, uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
from place_v2_power_front_labels import box, overlaps, pos
from update_v2_power_marking_policy import text_blocks

HELD = []
def sha(raw): return hashlib.sha256(raw).hexdigest()

def silk_blocks(s):
    rows = []
    for m in re.finditer(r'\(gr_(?:text|line|rect|poly|arc|circle)\b', s):
        i=m.start(); depth=0; quoted=False; escaped=False
        for j in range(i, len(s)):
            ch=s[j]
            if quoted:
                if escaped: escaped=False
                elif ch=='\\': escaped=True
                elif ch=='"': quoted=False
            elif ch=='"': quoted=True
            elif ch=='(': depth+=1
            elif ch==')':
                depth-=1
                if depth==0: break
        block=s[i:j+1]
        layer=re.search(r'\(layer "([^"]+)"\)', block)
        if layer and layer[1] in ('F.SilkS','B.SilkS'):
            rows.append(dict(start=i,end=j+1,block=block))
    return rows

def without_silk_drawings(s):
    for t in reversed(silk_blocks(s)): s=s[:t['start']]+s[t['end']:]
    return re.sub(r'\s+',' ',s).strip()

def text(b, value, at, angle, layer, size=.8, stroke=.12, bold=False):
    t=k.PCB_TEXT(b); HELD.append(t)
    t.SetText(value); t.SetPosition(pos(*at)); t.SetLayer(layer)
    t.SetMirrored(layer==k.B_SilkS); t.SetTextAngle(k.EDA_ANGLE(angle,k.DEGREES_T))
    t.SetTextSize(pos(size,size)); t.SetTextThickness(k.FromMM(stroke)); t.SetBold(bold)
    return t

def style(pcb, scratch):
    raw=pcb.read_bytes(); b=k.LoadBoard(str(pcb)); HELD.append(b)
    fps={f.GetReference():f for f in b.GetFootprints()}
    labels={}
    for t in b.GetDrawings():
        if isinstance(t,k.PCB_TEXT):
            m=re.match(r'^([A-Z]+\d+)(?:\s|$)', t.GetText())
            if m and m[1] in fps: labels.setdefault(m[1],[]).append(t)
    for t in list(b.GetDrawings()):
        if isinstance(t,k.PCB_SHAPE) and t.GetLayer() in (k.F_SilkS,k.B_SilkS):
            b.Remove(t); HELD.append(t)
        elif isinstance(t,k.PCB_TEXT) and t.GetText() in ('BAL1','BAL2','COLD A','COLD B'):
            b.Remove(t); HELD.append(t)
    # Pin maps are deliberately retained as one owner caption on the reverse.
    selected={'J7','J8','J12','J101','J11','U2','R58','C61'}
    for ref in selected:
        for t in labels[ref]: b.Remove(t); HELD.append(t)
    # J12's old pin-only map did not own a component reference.
    for t in list(b.GetDrawings()):
        if isinstance(t,k.PCB_TEXT) and t.GetText()=='1 BAT 2 MID\n3 GND 4 NC':
            b.Remove(t); HELD.append(t)

    masks={layer:[] for layer in (k.F_SilkS,k.B_SilkS)}
    graphics={layer:[] for layer in masks}
    for silk,mask,cu in ((k.F_SilkS,k.F_Mask,k.F_Cu),(k.B_SilkS,k.B_Mask,k.B_Cu)):
        for f in fps.values():
            for p in f.Pads():
                if p.IsOnLayer(mask):
                    shape=k.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(shape,cu,p.GetSolderMaskExpansion(mask),1000,k.ERROR_OUTSIDE)
                    masks[silk].append((box(p),shape))
            for g in f.GraphicalItems():
                if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==silk:
                    shape=k.SHAPE_POLY_SET(); g.TransformShapeToPolygon(shape,silk,0,1000,k.ERROR_OUTSIDE)
                    graphics[silk].append((box(g),shape))
        for v in b.GetTracks():
            if isinstance(v,k.PCB_VIA) and not v.IsTented(cu):
                # Exposed vias are round; conservative box excludes silk.
                masks[silk].append((box(v),None))

    def clear(item, both=False):
        bb=box(item)
        if bb[0]<.35 or bb[1]<.35 or bb[2]>89.65 or bb[3]>59.65: return False
        for layer in (k.F_SilkS,k.B_SilkS) if both else (item.GetLayer(),):
            glyph=k.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(glyph,layer,k.FromMM(.105),1000,k.ERROR_OUTSIDE)
            for q,p in masks[layer]+graphics[layer]:
                if overlaps(bb,q,.35) and (p is None or glyph.Collide(p,0)): return False
            for other in b.GetDrawings():
                if other.GetLayer()!=layer: continue
                if not overlaps(bb,box(other),.35): continue
                p=k.SHAPE_POLY_SET(); other.TransformShapeToPolygon(p,layer,0,1000,k.ERROR_OUTSIDE)
                if glyph.Collide(p,0): return False
        return True

    specs=[('J7','J7 SOLAR\n1 VIN\n2 GND',(12.6,2.7)),
           ('J8','J8 Na-ion\n1 BAT+\n2 GND',(24.,2.7)),
           ('J12','J12 LTO\n1 BAT 2 MID\n3 GND 4 NC',(39.,2.7)),
           ('J101','J101 1/3 SYS 5/7 RADIO\n2/4/6 GND 8 NC\n9 BAT 10 SDA\n11 MODE 12 SCL',(70.5,3.4)),
           ('J11','J11\n1 LC\n2 3V3',(86.,18.5))]
    report={'connectors':[],'options':[]}
    for ref,value,xy in specs:
        t=text(b,value,xy,0,k.B_SilkS)
        assert clear(t), 'Connector label blocked: '+ref
        b.Add(t); report['connectors'].append(dict(ref=ref,text=value,at_mm=xy,angle=0,layer='B.SilkS',font_mm=.8))
    for xy in ((42.,20.5),(43.,20.9),(43.,21.5),(42.,22.)):
        t=text(b,'U2 TPS63802',xy,0,k.B_SilkS)
        if clear(t): break
    else: raise RuntimeError('No uninterrupted U2 label site')
    b.Add(t); report['U2']=dict(text=t.GetText(),at_mm=[k.ToMM(t.GetPosition().x),k.ToMM(t.GetPosition().y)],angle=0,layer='B.SilkS')
    # Narrow owner-oriented captions open two continuous outline corridors.
    report['outline_corridor_captions']=[]
    for ref,value,xy in [('R58','R58 100k',(42.9,35.)),('C61','C61 1n',(49.9,44.1))]:
        t=text(b,value,xy,90,k.B_SilkS)
        assert clear(t), 'Corridor caption blocked: '+ref
        b.Add(t); report['outline_corridor_captions'].append(dict(ref=ref,text=value,at_mm=xy,angle=90))

    sys.path.insert(0,str(ROOT/'audit/a3_2026_10_13/logic'))
    import label_power_a3 as old
    _,groups=old.setup()
    # A thicker common contour has identical physical XY on both sides.
    title_sites={'BAL1':((30.39,12.175),0,.9), 'BAL2':((6.425,46.765),0,1.),
                 'COLD_A':((43.4,28.75),90,.8), 'COLD_B':((39.35,56.525),0,1.)}
    for name,refs in groups.items():
        caption=name.replace('_',' '); xy,angle,size=title_sites[name]
        for layer in (k.F_SilkS,k.B_SilkS):
            t=text(b,caption,xy,angle,layer,size,.22 if size>=.9 else .18,True)
            assert clear(t), 'Option title blocked: '+name
            b.Add(t)
    for name,refs in groups.items():
        pts=old.polygon(b,refs,name)
        if name=='BAL1':
            # The lower-left recess excludes the mandatory input C8 body.
            pts=[(12.7,13.075),(33.375,13.075),(33.375,19.175),
                 (17.,19.175),(17.,16.4),(12.7,16.4),(12.7,13.075)]
        elif name=='COLD_A':
            # Route inside the vertical title and above the L1 aperture.
            pts=[(28.8,26.225),(42.55,26.225),(42.55,30.75),
                 (28.8,30.75),(28.8,26.225)]
        elif name=='COLD_B':
            # Keep the upper stem outside L1 and the lower side before the
            # filter capacitors. R56 remains outside this option.
            pts=[(41.8,31.795),(50.575,31.795),(50.575,41.575),
                 (50.95,41.575),(50.95,55.375),(22.995,55.375),
                 (22.995,44.0),(41.8,44.0),(41.8,31.795)]
        segments=[]
        for a,z in zip(pts,pts[1:]):
            distance=math.dist(a,z); count=max(1,math.ceil(distance/.05)); run=[]
            for i in range(count):
                aa=tuple(a[j]+(z[j]-a[j])*i/count for j in (0,1))
                zz=tuple(a[j]+(z[j]-a[j])*(i+1)/count for j in (0,1))
                line=k.PCB_SHAPE(b); HELD.append(line); line.SetShape(k.SHAPE_T_SEGMENT)
                line.SetStart(pos(*aa)); line.SetEnd(pos(*zz)); line.SetWidth(k.FromMM(.3)); line.SetLayer(k.F_SilkS)
                if clear(line,True):
                    if not run: run=[aa]
                    run.append(zz)
                elif run:
                    if math.dist(run[0],run[-1])>=.75: segments.append((run[0],run[-1]))
                    run=[]
            if run and math.dist(run[0],run[-1])>=.75: segments.append((run[0],run[-1]))
        for layer in (k.F_SilkS,k.B_SilkS):
            for a,z in segments:
                line=k.PCB_SHAPE(b); HELD.append(line); line.SetShape(k.SHAPE_T_SEGMENT)
                line.SetStart(pos(*a)); line.SetEnd(pos(*z)); line.SetWidth(k.FromMM(.3)); line.SetLayer(layer); b.Add(line)
        report['options'].append(dict(name=name,refs=refs,polygon=pts,segments=segments,width_mm=.3))
    scratch.parent.mkdir(parents=True,exist_ok=True)
    k.SaveBoard(str(scratch),b)
    saved=scratch.read_text('utf-8'); original=raw.decode('utf-8')
    result=original
    for row in reversed(silk_blocks(result)): result=result[:row['start']]+result[row['end']:]
    insert='\n'.join(row['block'] for row in silk_blocks(saved))
    end=result.rfind(')'); result=result[:end]+'\n'+insert+'\n'+result[end:]
    result=re.sub(r'(?m)^[\t ]+(?=\r?$)','',result)
    assert without_silk_drawings(original)==without_silk_drawings(result),'Non-silk drawing/CAD changed'
    report.update(before_sha256=sha(raw),after_sha256=sha(result.encode('utf-8')),only_F_B_silkscreen_drawings_changed=True)
    return result.encode('utf-8'),report

def main():
    p=argparse.ArgumentParser(); p.add_argument('--pcb',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--report',type=Path,required=True); a=p.parse_args()
    for x in (a.pcb,a.out,a.report): assert x.resolve().is_relative_to(ROOT)
    candidate=a.out.with_suffix('.serialization.kicad_pcb')
    raw,proof=style(a.pcb,candidate); a.out.write_bytes(raw); a.report.write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(proof,ensure_ascii=False))
if __name__=='__main__': main()
