"""Uniform LOGIC connectors and RF option frame; preserve RF/copper/mask bytes."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/cad'))
from style_v2_power_annotations import k,text,HELD,silk_blocks,without_silk_drawings
from place_v2_power_front_labels import box,overlaps,pos

def style(pcb,scratch):
    raw=pcb.read_bytes();b=k.LoadBoard(str(pcb));HELD.append(b)
    fps={f.GetReference():f for f in b.GetFootprints()};labels={}
    for t in list(b.GetDrawings()):
        if isinstance(t,k.PCB_TEXT):
            m=re.match(r'^([A-Z]+\d+)(?:\s|$)',t.GetText())
            if m and m[1] in fps:labels[m[1]]=t
    selected={'J3','J4','J5','J10','J13','J201','FL1','NT1','R43'}
    before_maps={r:labels[r].GetText() for r in selected}
    for ref in selected:b.Remove(labels[ref]);HELD.append(labels[ref])
    for t in list(b.GetDrawings()):
        if isinstance(t,k.PCB_TEXT) and t.GetText()=='RF':b.Remove(t);HELD.append(t)
        elif isinstance(t,k.PCB_SHAPE) and t.GetLayer() in (k.F_SilkS,k.B_SilkS):b.Remove(t);HELD.append(t)
    masks={s:[] for s in (k.F_SilkS,k.B_SilkS)};graphics={s:[] for s in masks}
    for silk,mask,cu in ((k.F_SilkS,k.F_Mask,k.F_Cu),(k.B_SilkS,k.B_Mask,k.B_Cu)):
        for f in fps.values():
            for pad in f.Pads():
                if pad.IsOnLayer(mask):
                    p=k.SHAPE_POLY_SET();pad.TransformShapeToPolygon(p,cu,pad.GetSolderMaskExpansion(mask),1000,k.ERROR_OUTSIDE)
                    masks[silk].append((box(pad),p))
            for g in f.GraphicalItems():
                if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==silk:
                    p=k.SHAPE_POLY_SET();g.TransformShapeToPolygon(p,silk,0,1000,k.ERROR_OUTSIDE);graphics[silk].append((box(g),p))
        for via in b.GetTracks():
            if isinstance(via,k.PCB_VIA) and not via.IsTented(cu):masks[silk].append((box(via),None))
    def clear(item):
        bb=box(item);layer=item.GetLayer()
        edge=.12 if isinstance(item,k.PCB_SHAPE) else .35
        if bb[0]<edge or bb[1]<edge or bb[2]>90-edge or bb[3]>60-edge:return False
        p=k.SHAPE_POLY_SET();item.TransformShapeToPolygon(p,layer,k.FromMM(.105),1000,k.ERROR_OUTSIDE)
        for q,shape in masks[layer]+graphics[layer]:
            if overlaps(bb,q,.35) and (shape is None or p.Collide(shape,0)):
                if isinstance(item,k.PCB_SHAPE):print('Outline blocker mask/footprint graphic:',q)
                return False
        for other in b.GetDrawings():
            if other.GetLayer()!=layer or not overlaps(bb,box(other),.35):continue
            shape=k.SHAPE_POLY_SET();other.TransformShapeToPolygon(shape,layer,0,1000,k.ERROR_OUTSIDE)
            if p.Collide(shape,0):
                if isinstance(item,k.PCB_SHAPE):print('Outline blocker board item:',other.GetText() if isinstance(other,k.PCB_TEXT) else 'shape',box(other))
                return False
        return True
    specs=[('J3',before_maps['J3'],(85.4,8.6)),('J4',before_maps['J4'],(52.,4.)),
           ('J10',before_maps['J10'],(36.97,26.5)),('J201',before_maps['J201'],(70.5,43.7)),
           ('J5','J5 UART',(4.,7.8)),('J13','J13 SMA',(26.5,1.1)),
           ('J5 pins','1 GND\n2 3V3\n3 TX\n4 RX',(6.5,14.31))]
    report={'connectors':[]}
    for owner,value,xy in specs:
        t=text(b,value,xy,0,k.B_SilkS)
        assert clear(t),'Connector legend blocked: '+owner
        b.Add(t);report['connectors'].append(dict(owner=owner,text=value,at_mm=xy,angle=0,layer='B.SilkS',font_mm=.8,stroke_mm=.12))
    # The vertical Q3 caption occupies the old right-adjacent R43 location.
    # Keep R43 exactly beneath its own physical component instead.
    t=text(b,'R43\n100k',(71.5,20.8),0,k.B_SilkS)
    assert clear(t),'R43 back projection blocked'
    b.Add(t);report['R43']={'text':t.GetText(),'at_mm':[71.5,20.8],'layer':'B.SilkS','angle':0}
    # Keep the long RF part code compact and along the square footprint's
    # pin orientation. One owner caption remains inside the option frame.
    t=text(b,'FL1\nS869M000\nS003',(40.7,4.25),90,k.B_SilkS)
    assert clear(t),'RF part caption blocked'
    b.Add(t)
    t=text(b,'NT1',(40.7,7.1),0,k.F_SilkS)
    assert clear(t),'Cut-link caption blocked'
    b.Add(t)
    pts=[(38.57,.4),(43.2,.4),(43.2,8.1),(38.57,8.1),(38.57,.4)]
    for layer in (k.F_SilkS,k.B_SilkS):
        outlines=[]
        for a,z in zip(pts,pts[1:]):
            g=k.PCB_SHAPE(b);HELD.append(g);g.SetShape(k.SHAPE_T_SEGMENT);g.SetLayer(layer)
            g.SetStart(pos(*a));g.SetEnd(pos(*z));g.SetWidth(k.FromMM(.3))
            assert clear(g),f'RF option outline blocked: {layer} {a} {z}'
            outlines.append(g)
        for g in outlines:b.Add(g)
        t=text(b,'RF',(40.7,9.4),0,layer,1.,.22,True)
        assert clear(t),'RF title blocked'
        b.Add(t)
    report['RF_option']={'refs':['FL1','NT1'],'outline_mm':pts,'line_mm':.3,'identical_physical_F_B':True,
                        'title':'RF','title_at_mm':[40.7,9.4],'title_font_mm':1.,'title_stroke_mm':.22,
                        'NT1_cut_window_copper_and_mask_preserved':True}
    scratch.parent.mkdir(parents=True,exist_ok=True);k.SaveBoard(str(scratch),b)
    saved=scratch.read_text('utf-8');s=raw.decode('utf-8')
    for row in reversed(silk_blocks(s)):s=s[:row['start']]+s[row['end']:]
    end=s.rfind(')');s=s[:end]+'\n'+'\n'.join(row['block'] for row in silk_blocks(saved))+'\n'+s[end:]
    s=re.sub(r'(?m)^[\t ]+(?=\r?$)','',s)
    assert without_silk_drawings(raw.decode('utf-8'))==without_silk_drawings(s)
    report.update(before_sha256=hashlib.sha256(raw).hexdigest(),after_sha256=hashlib.sha256(s.encode('utf-8')).hexdigest(),only_F_B_silkscreen_drawings_changed=True)
    return s.encode('utf-8'),report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pcb',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    for x in (a.pcb,a.out,a.report):assert x.resolve().is_relative_to(ROOT)
    raw,proof=style(a.pcb,a.out.with_suffix('.serialization.kicad_pcb'));a.out.write_bytes(raw)
    a.report.write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(proof,ensure_ascii=False))
