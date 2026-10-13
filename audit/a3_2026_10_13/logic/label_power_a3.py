"""POWER adapter for the same owner-axis label algorithm used on LOGIC.

Without --apply this is strictly a placement proposal; it never saves CAD.
--apply is to be called only after the routing owner's explicit handoff.
"""
from pathlib import Path
import argparse, collections, json, math, re, sys
import label_logic_a3 as e
import rework_logic_a3 as c

ROOT=c.ROOT
OUT=ROOT/'audit/a3_2026_10_13/power_labels'
PCB=ROOT/'design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb'
MODEL=PCB.with_name('model.json')
GROUPS={'BAL1':['R47','R48','R49','R50','U8','C58'],
        'BAL2':['R51','R52','R53','R54','U9','C59'],
        'COLD_A':['Q4','Q6','Q7']}

def bare(value, ref):
    value=value.split()[0]
    if ref.startswith('C'):value=value.replace('uF','u').replace('nF','n').replace('pF','p')
    if ref.startswith('R'):
        match=re.fullmatch(r'(\d+)\.(\d+)([kMR])',value)
        if match:value=match[1]+match[3]+match[2]
    return value

def setup():
    OUT.mkdir(parents=True,exist_ok=True)
    e.PCB=c.PCB=PCB; e.OUT=c.OUT=OUT
    model=json.loads(MODEL.read_text(encoding='utf8'))
    parts={p['ref']:p for p in model['parts']}
    e.POWER_FRONT_ONLY={'C2','C30','R13'}
    e.POWER_BACK_SINGLE={'C6','R16'}
    def nominal(f):
        ref=f.GetReference();part=parts.get(ref,{})
        if ref=='J8':return 'Na-ion'
        if ref=='J12':return 'LTO'
        if ref=='J11':return '3V3'
        if ref=='J101':return '2x6'
        if ref.startswith(('TP','NT')):return ''
        if ref.startswith('H'):return 'M3'
        value=bare(part.get('value',f.GetValue()),ref)
        lto=bare(part.get('value_lto2s',part.get('value',f.GetValue())),ref)
        if ref in ('R3','R4','R15','R16','C30','R56') and value!=lto:
            if ref=='R56':return value+'/'+lto
            return 'N'+value+'\nL'+lto
        special={'U1':'CN3722','U2':'TPS6\n3802','U8':'LMV431A','U9':'LMV431A',
                 'U10':'LM393','U11':'LM285 2.5','U12':'INA219','TH1':'10k NTC',
                 'J1':'SOLAR','J6':'NTC','J9':'NTC'}
        if ref in special:return special[ref]
        if ref in ('Q4','Q6','Q7') and value=='AO3401A':return 'AO34\n01A'
        if ref.startswith('Q'):return value
        if ref.startswith('L'):return value.replace('uH','u')
        return value
    e.nominal=nominal
    groups=dict(GROUPS)
    groups['COLD_B']=[p['ref'] for p in model['parts'] if p.get('group')=='cold_charge'
                      and p['ref'] not in GROUPS['COLD_A']+['R56']]
    return parts,groups

def polygon(b,refs,name):
    fs={f.GetReference():f for f in b.GetFootprints()}
    boxes=[e.component_box(fs[r]) for r in refs]
    def expanded(bb,m=.8):return [bb[0]-m,bb[1]-m,bb[2]+m,bb[3]+m]
    if name=='COLD_B':
        upper=[e.component_box(fs[r]) for r in refs if c.xy(fs[r].GetPosition())[1]<43]
        lower=[e.component_box(fs[r]) for r in refs if c.xy(fs[r].GetPosition())[1]>=43]
        u,l=expanded(e.union(upper)),expanded(e.union(lower))
        # A narrow upper stem excludes mandatory R56; lower area encloses the
        # comparator/reference and its optional passives as one orthogonal block.
        pts=[(u[0],u[1]),(u[2],u[1]),(u[2],l[1]),(l[2],l[1]),
             (l[2],l[3]),(l[0],l[3]),(l[0],l[1]),(u[0],l[1])]
    else:
        x0,y0,x1,y1=expanded(e.union(boxes));pts=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    return pts+[pts[0]]

def frames(groups,b=None,save=True):
    if b is None:b=c.k.LoadBoard(str(PCB));c.HELD.append(b)
    removed=[];removed_optional_front=[]
    for s in list(b.GetDrawings()):
        if isinstance(s,c.k.PCB_SHAPE) and s.GetLayer() in (c.k.F_SilkS,c.k.B_SilkS):
            removed.append(c.uid(s));b.Remove(s);c.HELD.append(s)
        elif isinstance(s,c.k.PCB_TEXT) and s.GetLayer()==c.k.F_SilkS and s.GetText()=='C54 DNP':
            # C54 retains its exact back projection. Its duplicate front text
            # occupies the only local title corridor of the COLD A option.
            removed_optional_front.append(c.uid(s));b.Remove(s);c.HELD.append(s)
    pads=[c.mm_box(p) for f in b.GetFootprints() for p in f.Pads()
          if p.IsOnLayer(c.k.F_Mask) or p.IsOnLayer(c.k.B_Mask)]
    bodies=[e.component_box(f) for f in b.GetFootprints()]
    labels=[c.mm_box(t) for t in b.GetDrawings() if isinstance(t,c.k.PCB_TEXT)
            and t.GetLayer() in (c.k.F_SilkS,c.k.B_SilkS)]
    def title_clear(label,at,angle,size,thickness):
        for layer,mask,cu in ((c.k.F_SilkS,c.k.F_Mask,c.k.F_Cu),(c.k.B_SilkS,c.k.B_Mask,c.k.B_Cu)):
            title=e.text(b,label,at,angle,layer,size);title.SetBold(True)
            title.SetTextThickness(c.k.FromMM(thickness));bb=c.mm_box(title)
            shape=c.k.SHAPE_POLY_SET()
            title.TransformShapeToPolygon(shape,layer,c.k.FromMM(.105),1000,c.k.ERROR_OUTSIDE)
            for f in b.GetFootprints():
                for pad in f.Pads():
                    if not pad.IsOnLayer(mask) or not e.overlap(bb,c.mm_box(pad),.2):continue
                    poly=c.k.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(poly,cu,pad.GetSolderMaskExpansion(mask),1000,c.k.ERROR_OUTSIDE)
                    if shape.Collide(poly,0):return False
            for via in b.GetTracks():
                if isinstance(via,c.k.PCB_VIA) and not via.IsTented(cu) and e.overlap(bb,c.mm_box(via),.2):return False
            for old in b.GetDrawings():
                if not isinstance(old,c.k.PCB_TEXT) or old.GetLayer()!=layer or not e.overlap(bb,c.mm_box(old),.15):continue
                poly=c.k.SHAPE_POLY_SET();old.TransformShapeToPolygon(poly,layer,0,1000,c.k.ERROR_OUTSIDE)
                if shape.Collide(poly,0):return False
        return True
    report=[]
    for name,refs in groups.items():
        points=polygon(b,refs,name);segments=[]
        bbox=e.union([[p[0],p[1],p[0],p[1]] for p in points])
        caption={'BAL1':'BAL1','BAL2':'BAL2','COLD_A':'COLD A','COLD_B':'COLD B'}[name]
        title_size={'BAL1':.9,'COLD_A':.8}.get(name,1.)
        title_thickness=.16 if name=='COLD_A' else .2
        accepted=None
        xc,yc=(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2
        preferred=[(xc,bbox[1]-1.15),(xc,bbox[3]+1.15),
                   (bbox[0]-3.5,yc),(bbox[2]+3.5,yc)]+[
                       (xc+dx,y) for y in (bbox[1]-1.15,bbox[3]+1.15) for dx in (-2,2,-4,4)]+[
                       (x,yc+dy) for x in (bbox[0]-3.5,bbox[2]+3.5) for dy in (-2,2,-4,4)]
        candidates=([((43.4,28.75),90)] if name=='COLD_A' else [])+[(at,0) for at in preferred]
        # Dense options can use a vertical title along a short side. Scan the
        # actual boundary instead of insisting that all titles be horizontal.
        for a,z in zip(points,points[1:]):
            distance=math.dist(a,z);steps=max(1,math.ceil(distance/.5))
            angle=0 if a[1]==z[1] else 90
            normal=(0,1) if angle==0 else (1,0)
            for offset in (.90,-.90,1.15,-1.15,2.15,-2.15,3.15,-3.15):
                for i in range(steps+1):
                    at=tuple(a[j]+(z[j]-a[j])*i/steps+normal[j]*offset for j in (0,1))
                    candidates.append((at,angle))
        for at,angle in candidates:
            t=e.text(b,caption,at,angle,c.k.F_SilkS,title_size);t.SetBold(True)
            t.SetTextThickness(c.k.FromMM(title_thickness));tb=c.mm_box(t)
            if tb[0]<.35 or tb[1]<.35 or tb[2]>89.65 or tb[3]>59.65:continue
            if any(e.overlap(tb,p,.10) for p in bodies):continue
            if not title_clear(caption,at,angle,title_size,title_thickness):continue
            accepted=(at,tb,angle);break
        if accepted is None:raise RuntimeError('No local option caption room: '+name)
        for layer in (c.k.F_SilkS,c.k.B_SilkS):
            t=e.text(b,caption,accepted[0],accepted[2],layer,title_size);t.SetBold(True)
            t.SetTextThickness(c.k.FromMM(title_thickness));b.Add(t)
        labels.append(accepted[1])
        for a,z in zip(points,points[1:]):
            distance=math.dist(a,z);count=max(1,math.ceil(distance/.1));run=[]
            for i in range(count):
                aa=tuple(a[j]+(z[j]-a[j])*i/count for j in (0,1))
                zz=tuple(a[j]+(z[j]-a[j])*(i+1)/count for j in (0,1))
                bb=[min(aa[0],zz[0])-.1,min(aa[1],zz[1])-.1,
                    max(aa[0],zz[0])+.1,max(aa[1],zz[1])+.1]
                allowed=not any(e.overlap(bb,p,.12) for p in pads+bodies+labels)
                if allowed:
                    if not run:run=[aa]
                    run.append(zz)
                elif run:
                    if math.dist(run[0],run[-1])>=.35:segments.append([run[0],run[-1]])
                    run=[]
            if run and math.dist(run[0],run[-1])>=.35:segments.append([run[0],run[-1]])
        for layer in (c.k.F_SilkS,c.k.B_SilkS):
            for a,z in segments:
                t=c.k.PCB_SHAPE(b);c.HELD.append(t);t.SetShape(c.k.SHAPE_T_SEGMENT)
                t.SetStart(c.vec(a));t.SetEnd(c.vec(z));t.SetWidth(c.k.FromMM(.2));t.SetLayer(layer);b.Add(t)
        report.append(dict(option=name,refs=refs,outline_proposal=points,caption=caption,caption_at=accepted[0],caption_angle=accepted[2],caption_size=title_size,
                           front_and_back_identical_native_segments=segments))
    if save:c.k.SaveBoard(str(PCB),b)
    (OUT/('option_outline_changes.json' if save else 'option_outline_proposal.json')).write_text(json.dumps(dict(removed_old_outline_uuids=removed,removed_optional_front_duplicate_uuids=removed_optional_front,
        groups=report,R56_excluded_from_cold_option=True),indent=2),encoding='utf8')
    return b

def legends(save=True):
    """Actual connector pin maps, board identity and single-jumper USB warning."""
    b=c.k.LoadBoard(str(PCB));c.HELD.append(b)
    specs=[('J7','J7 SOLAR\n1 VIN\n2 GND',(9.5,15.)),
           ('J8','J8 Na-ion\n1 BAT+\n2 GND',(18.5,10.8)),
           ('J12','1 BAT 2 MID\n3 GND 4 NC',(39.,2.4)),
           ('J101','J101 1/3 SYS 5/7 RADIO\n2/4/6 GND 8 NC\n9 BAT 10 SDA\n11 MODE 12 SCL',(70.5,16.)),
           ('J11','J11\n1 LC\n2 3V3',(79.7,22.)),
           ('USB warning','USB: снять J11',(79.,29.2)),
           ('variant key','N: Na-ion / L: LTO 2S',(65.,55.4)),
           ('R56 no-cold rule','R56: 0R без ХОЛОДА',(65.,57.4)),
           ('branding','Mesh Repeater ver 2.0\nDesigned by @Alksndritm',(26.,57.))]
    report=[]
    for owner,label,at in specs:
        accepted=None
        for dx,dy in ((0,0),(.5,0),(-.5,0),(0,.5),(0,-.5),(1,0),(-1,0),(0,1),(0,-1),(2,0),(-2,0)):
            t=e.text(b,label,(at[0]+dx,at[1]+dy),0,c.k.B_SilkS,.8);bb=c.mm_box(t)
            if bb[0]<.35 or bb[1]<.35 or bb[2]>89.65 or bb[3]>59.65:continue
            glyph=c.k.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(glyph,c.k.B_SilkS,c.k.FromMM(.105),1000,c.k.ERROR_OUTSIDE)
            blocked=False
            for f in b.GetFootprints():
                for pad in f.Pads():
                    if not pad.IsOnLayer(c.k.B_Mask) or not e.overlap(bb,c.mm_box(pad),.2):continue
                    poly=c.k.SHAPE_POLY_SET()
                    pad.TransformShapeToPolygon(poly,c.k.B_Cu,pad.GetSolderMaskExpansion(c.k.B_Mask),1000,c.k.ERROR_OUTSIDE)
                    if glyph.Collide(poly,0):blocked=True;break
                if blocked:break
            if blocked:continue
            for old in b.GetDrawings():
                if not isinstance(old,c.k.PCB_TEXT) or old.GetLayer()!=c.k.B_SilkS:continue
                if not e.overlap(bb,c.mm_box(old),.15):continue
                poly=c.k.SHAPE_POLY_SET();old.TransformShapeToPolygon(poly,c.k.B_SilkS,0,1000,c.k.ERROR_OUTSIDE)
                if glyph.Collide(poly,0):blocked=True;break
            if blocked:continue
            accepted=t;break
        if accepted is None:raise RuntimeError('No owner-adjacent POWER legend room: '+owner)
        b.Add(accepted);report.append(dict(owner=owner,text=label,at=c.xy(accepted.GetPosition()),uuid=c.uid(accepted)))
    if save:c.k.SaveBoard(str(PCB),b)
    (OUT/('power_connector_legends.json' if save else 'power_connector_legends_proposal.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    return b

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true')
    args=ap.parse_args();parts,groups=setup()
    if args.apply:
        backup=OUT/'before_power_labels.kicad_pcb'
        if backup.exists():raise RuntimeError('Initial label backup already exists; do not replay --apply blindly')
        backup.write_bytes(PCB.read_bytes())
    e.main(save=args.apply,profile='POWER',model_parts=parts,run_check=False)
    if args.apply:
        legends();frames(groups);c.check('POWER_labels_final')
    else:print('Proposal only. POWER CAD was not written.')

if __name__=='__main__':main()
