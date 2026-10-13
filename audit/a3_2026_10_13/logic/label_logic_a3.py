"""Labels use the actual courtyard centre and component axis, never group scale."""
from pathlib import Path
import collections, json, math, re, sys
from rework_logic_a3 import ROOT, OUT, PCB, HELD, k, xy, vec, mm_box, uid, sha, check

def overlap(a,b,margin=0):
    return not(a[2]+margin <= b[0] or b[2]+margin <= a[0] or
               a[3]+margin <= b[1] or b[3]+margin <= a[1])

def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),
            max(b[2] for b in boxes),max(b[3] for b in boxes)]

def component_box(f):
    courts=[mm_box(g) for g in f.GraphicalItems() if g.GetLayer()==k.F_CrtYd]
    return union(courts) if courts else union([mm_box(p) for p in f.Pads()])

def nominal(f):
    ref,value=f.GetReference(),f.GetValue()
    if ref.startswith('C'): return value.split()[0].replace('uF','u').replace('nF','n').replace('pF','p')
    if ref.startswith('R'): return value.split()[0]
    special={'M1':'Nice!Nano','M2':'HT-RA62','FB1':'60R',
             'J201':'2x6','J3':'I2C','J4':'GPS','J5':'UART','J10':'ISP',
             'J13':'SMA','SW1':'USER','SW2':'RESET','BT1':'CR2032',
             'U4':'DS3231M','U6':'ATtiny13A','U7':'74LVC\n2G125','FL1':'S869M000\nS003'}
    if ref in special:return special[ref]
    if ref.startswith('TP'):return ''
    if ref.startswith('H'):return 'M3'
    if ref.startswith('NT'):return ''
    return value.split()[0]

def axis(f):
    # A connector's native zero rotation can have a vertical pad row. Use its
    # actual body axis rather than mistaking that library convention for a
    # horizontal physical component. Square bodies retain their pin orientation.
    bb=component_box(f);w,h=bb[2]-bb[0],bb[3]-bb[1]
    if w>h*1.15:return 0
    if h>w*1.15:return 90
    a=f.GetOrientationDegrees()%180
    return 90 if abs(a-90)<.01 else 0

def text(b,value,at,angle,layer,font=.75):
    t=k.PCB_TEXT(b);HELD.append(t);t.SetText(value);t.SetPosition(vec(at))
    t.SetLayer(layer);t.SetMirrored(layer==k.B_SilkS)
    t.SetTextAngle(k.EDA_ANGLE(angle,k.DEGREES_T));t.SetTextSize(vec((font,font)))
    t.SetTextThickness(k.FromMM(.12 if font<.9 else .15));return t

def main(save=True, profile='LOGIC', model_parts=None, run_check=True):
    b=k.LoadBoard(str(PCB));HELD.append(b);before=sha(PCB)
    # This label pass may be replayed safely after DRC-based annotation repair.
    for g in list(b.GetDrawings()):
        if isinstance(g,k.PCB_TEXT) and g.GetLayer() in (k.F_SilkS,k.B_SilkS):
            b.Remove(g);HELD.append(g)
    footprints=list(b.GetFootprints())
    placed={k.F_SilkS:[],k.B_SilkS:[]};report=[];unplaced=[];optional_front=[]
    pads={k.F_SilkS:[],k.B_SilkS:[]};pad_objects={k.F_SilkS:[],k.B_SilkS:[]}
    for f in footprints:
        for p in f.Pads():
            for layer,mask in ((k.F_SilkS,k.F_Mask),(k.B_SilkS,k.B_Mask)):
                if p.IsOnLayer(mask):
                    pads[layer].append(mm_box(p));pad_objects[layer].append((p,mask))
    for t in b.GetTracks():
        if isinstance(t,k.PCB_VIA) and not t.IsTented(k.F_Cu):
            pads[k.F_SilkS].append(mm_box(t))
        if isinstance(t,k.PCB_VIA) and not t.IsTented(k.B_Cu):
            pads[k.B_SilkS].append(mm_box(t))
    def clear(t,layer,front_body=None):
        bb=mm_box(t)
        if bb[0]<.35 or bb[1]<.35 or bb[2]>89.65 or bb[3]>59.65:return False
        if any(overlap(bb,p,.2) for p in pads[layer]):
            if profile!='POWER':return False
            glyph=k.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(glyph,layer,k.FromMM(.105),1000,k.ERROR_OUTSIDE)
            for pad,mask in pad_objects[layer]:
                if not overlap(bb,mm_box(pad),.2):continue
                outline=k.SHAPE_POLY_SET()
                copper=k.F_Cu if layer==k.F_SilkS else k.B_Cu
                pad.TransformShapeToPolygon(outline,copper,pad.GetSolderMaskExpansion(mask),1000,k.ERROR_OUTSIDE)
                if glyph.Collide(outline,0):return False
            for via in b.GetTracks():
                copper=k.F_Cu if layer==k.F_SilkS else k.B_Cu
                if isinstance(via,k.PCB_VIA) and not via.IsTented(copper) and overlap(bb,mm_box(via),.2):return False
        if any(overlap(bb,p,.15) for p in placed[layer]):
            if profile!='POWER':return False
            # Text boxes contain empty space between strokes. Exact native glyph
            # polygons resolve close rows without changing size or displacing the
            # projected owner label. Native DRC remains the final saved-board gate.
            shape=k.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(shape,layer,k.FromMM(.105),1000,k.ERROR_OUTSIDE)
            for other in b.GetDrawings():
                if not isinstance(other,k.PCB_TEXT) or other.GetLayer()!=layer:continue
                if not overlap(bb,mm_box(other),.15):continue
                oldshape=k.SHAPE_POLY_SET()
                other.TransformShapeToPolygon(oldshape,layer,0,1000,k.ERROR_OUTSIDE)
                if shape.Collide(oldshape,0):return False
        if front_body is not None and any(overlap(bb,component_box(f),.05) for f in footprints):return False
        return True
    # Every back label is exactly below its native physical body. Large/through
    # hole connectors which cannot fit there get a directly adjacent front label.
    for f in sorted(footprints,key=lambda f: (not f.GetReference().startswith('H'),f.GetReference())):
        ref=f.GetReference();bb=component_box(f);center=((bb[0]+bb[2])/2,(bb[1]+bb[3])/2)
        angle=axis(f);value=nominal(f);label=ref+('\n'+value if value else '')
        if ref.startswith('H'):label=ref+' '+value
        front_bb=union([bb,component_box(next(ff for ff in footprints if ff.GetReference()=='FL1'))]) if ref=='NT1' else bb
        font=.8
        back_label=ref+' '+value if ref in ('R23','R24','R25') or (profile=='POWER' and ref in globals().get('POWER_BACK_SINGLE',set())) else label
        t=text(b,back_label,center,angle,k.B_SilkS,font)
        back_ok=clear(t,k.B_SilkS)
        if profile=='POWER' and not back_ok and '\n' not in value:
            t=text(b,ref+' '+value,center,angle,k.B_SilkS,font)
            back_ok=clear(t,k.B_SilkS)
        if profile=='POWER' and ref in globals().get('POWER_FRONT_ONLY',set()):back_ok=False
        back_uuid=uid(t) if back_ok else None
        if back_ok:b.Add(t);placed[k.B_SilkS].append(mm_box(t))
        candidates=[]
        # Axis remains constant, while location is searched only next to owner.
        for fontf in (.8,):
            for side in ('top','bottom','right','left'):
                probe=text(b,label,center,angle,k.F_SilkS,fontf);pb=mm_box(probe)
                w,h=pb[2]-pb[0],pb[3]-pb[1]
                offsets={'top':(center[0],front_bb[1]-.3-h/2),
                         'bottom':(center[0],front_bb[3]+.3+h/2),
                         'right':(front_bb[2]+.3+w/2,center[1]),
                         'left':(front_bb[0]-.3-w/2,center[1])}
                for along in (0,.5,-.5,1.,-1.,1.5,-1.5):
                    at=offsets[side]
                    at=(at[0]+along,at[1]) if side in ('top','bottom') else (at[0],at[1]+along)
                    t=text(b,label,at,angle,k.F_SilkS,fontf)
                    if clear(t,k.F_SilkS,bb):candidates.append((abs(along),t,side))
            if candidates:break
        front=None
        if profile=='POWER' and not candidates and '\n' not in value:
            # One line keeps adjacent small-row components legible at 0.8 mm.
            single=ref+' '+value
            for side in ('top','bottom','right','left'):
                probe=text(b,single,center,angle,k.F_SilkS,.8);pb=mm_box(probe)
                w,h=pb[2]-pb[0],pb[3]-pb[1]
                offsets={'top':(center[0],front_bb[1]-.3-h/2),
                         'bottom':(center[0],front_bb[3]+.3+h/2),
                         'right':(front_bb[2]+.3+w/2,center[1]),
                         'left':(front_bb[0]-.3-w/2,center[1])}
                for along in (0,.5,-.5,1.,-1.,1.5,-1.5):
                    at=offsets[side]
                    at=(at[0]+along,at[1]) if side in ('top','bottom') else (at[0],at[1]+along)
                    t=text(b,single,at,angle,k.F_SilkS,.8)
                    if clear(t,k.F_SilkS,bb):candidates.append((abs(along),t,side))
        if candidates:
            _,t,side=min(candidates,key=lambda x:x[0])
            if profile=='POWER' and back_ok:
                optional_front.append((ref,t,side,bb))
            else:
                b.Add(t);placed[k.F_SilkS].append(mm_box(t));front=dict(at=xy(t.GetPosition()),side=side,box=mm_box(t),uuid=uid(t))
        if not back_ok and front is None:
            nearby=sorted([(math.dist(center,xy(ff.GetPosition())),ff.GetReference())
                           for ff in footprints if ff.GetReference()!=ref])[:8]
            probe=text(b,back_label,center,angle,k.B_SilkS,.8);probe_box=mm_box(probe)
            blockers=[dict(text=g.GetText(),box=mm_box(g)) for g in b.GetDrawings()
                      if isinstance(g,k.PCB_TEXT) and g.GetLayer()==k.B_SilkS and overlap(probe_box,mm_box(g),.15)]
            unplaced.append(dict(ref=ref,label=label,body_center=center,box=bb,axis_deg=angle,nearest=nearby,
                                 back_label_box=probe_box,back_text_blockers=blockers))
        report.append(dict(ref=ref,value=value,axis_deg=angle,body_center=center,
                           back=dict(at=center,uuid=back_uuid) if back_ok else None,front=front))
    # Required front labels get priority over optional duplicates of an already
    # complete back projection, which prevents earlier labels starving a dense
    # neighbouring component of its only usable location.
    for ref,t,side,bb in optional_front:
        if clear(t,k.F_SilkS,bb):
            b.Add(t);placed[k.F_SilkS].append(mm_box(t))
            next(row for row in report if row['ref']==ref)['front']=dict(
                at=xy(t.GetPosition()),side=side,box=mm_box(t),uuid=uid(t))
    # Keep concise orientation-independent external functions as owner-adjacent
    # labels above already-labelled power/IO connectors.
    operators=[('Mesh Repeater ver 2.0',(44,49),0,k.B_SilkS,.9),
               ('Designed by @Alksndritm',(44,46.8),0,k.B_SilkS,.8),
               ('USB: снять J11 на POWER',(20,40),0,k.B_SilkS,.8)]
    if profile=='POWER':operators=[]
    for value,at,angle,layer,font in operators:
        t=text(b,value,at,angle,layer,font)
        if clear(t,layer):b.Add(t);placed[layer].append(mm_box(t))
    if unplaced:
        (OUT/'proposal_unplaced.json').write_text(json.dumps(dict(profile=profile,
            coverage=len(report)-len(unplaced),unplaced=unplaced),indent=2,ensure_ascii=False),encoding='utf8')
        raise RuntimeError('No legible owner-aligned labels for: '+', '.join(r['ref'] for r in unplaced))
    if save:k.SaveBoard(str(PCB),b)
    (OUT/'label_changes.json').write_text(json.dumps(dict(before_sha256=before,
        after_sha256=sha(PCB),labels=report,group_scale_labels_removed=True,
        label_back_centres='native courtyard/body centres, no scale transforms',
        front_or_back_coverage=len(report)),indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(dict(covered=len(report),front=sum(bool(r['front']) for r in report),
                         back=sum(bool(r['back']) for r in report))))
    if save and run_check:check('labels',False)
    return report

if __name__=='__main__':main()
