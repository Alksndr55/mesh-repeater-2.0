"""Plan owner-aligned POWER labels with native mask/glyph clearance; save text only."""
from pathlib import Path
import json,math,re,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
from update_v2_power_marking_policy import text_blocks,without_silk

def box(o):
 b=o.GetBoundingBox();return tuple(k.ToMM(x) for x in (b.GetLeft(),b.GetTop(),b.GetRight(),b.GetBottom()))
def overlaps(a,b,m=0):return not(a[2]+m<=b[0] or b[2]+m<=a[0] or a[3]+m<=b[1] or b[3]+m<=a[1])
def union(rows):return min(a[0] for a in rows),min(a[1] for a in rows),max(a[2] for a in rows),max(a[3] for a in rows)
def pos(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))

def relocate(pcb, priority=None, axis_ratio=1.05):
 raw=pcb.read_bytes();b=k.LoadBoard(str(pcb));held=[b];fps={f.GetReference():f for f in b.GetFootprints()}
 labels={}
 for t in b.GetDrawings():
  if not isinstance(t,k.PCB_TEXT) or t.GetLayer() not in [k.F_SilkS,k.B_SilkS]:continue
  m=re.match(r'^([A-Z]+\d+)(?:\s|$)',t.GetText())
  if m and m[1] in fps:labels[m[1]]=t
 bodies={};courts={}
 for ref,f in fps.items():
  fab=[box(g) for g in f.GraphicalItems() if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==k.F_Fab]
  court=[box(g) for g in f.GraphicalItems() if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==k.F_CrtYd]
  padbox=[box(p) for p in f.Pads()]
  bodies[ref]=union(fab or court or padbox);courts[ref]=union(court or fab or padbox)
 masks=[];graphics=[]
 for f in fps.values():
  for pad in f.Pads():
   if not pad.IsOnLayer(k.F_Mask):continue
   p=k.SHAPE_POLY_SET();pad.TransformShapeToPolygon(p,k.F_Cu,pad.GetSolderMaskExpansion(k.F_Mask),1000,k.ERROR_OUTSIDE)
   masks.append((box(pad),p))
  for g in f.GraphicalItems():
   if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==k.F_SilkS:
    p=k.SHAPE_POLY_SET();g.TransformShapeToPolygon(p,k.F_SilkS,0,1000,k.ERROR_OUTSIDE);graphics.append((box(g),p))
 for g in b.GetDrawings():
  if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==k.F_SilkS:
   p=k.SHAPE_POLY_SET();g.TransformShapeToPolygon(p,k.F_SilkS,0,1000,k.ERROR_OUTSIDE);graphics.append((box(g),p))
 vias=[box(v) for v in b.GetTracks() if isinstance(v,k.PCB_VIA) and not v.IsTented(k.F_Cu)]
 def angle(ref):
  q=bodies[ref];w,h=q[2]-q[0],q[3]-q[1]
  # IC lead rows can make the courtyard wider than the actual vertical body.
  if w>h*axis_ratio:return 0
  if h>w*axis_ratio:return 90
  return 90 if abs(fps[ref].GetOrientationDegrees()%180-90)<.01 else 0
 def make(value,xy,ang,font):
  t=k.PCB_TEXT(b);held.append(t);t.SetText(value);t.SetLayer(k.F_SilkS);t.SetMirrored(False)
  t.SetPosition(pos(*xy));t.SetTextAngle(k.EDA_ANGLE(ang,k.DEGREES_T));t.SetTextSize(pos(font,font));t.SetTextThickness(k.FromMM(.15 if font>=.9 else .12));return t
 def clear(t,old,ref,under=False):
  bb=box(t)
  if bb[0]<.35 or bb[1]<.35 or bb[2]>89.65 or bb[3]>59.65:return False
  if under:
   q=bodies[ref]
   if bb[0]<q[0] or bb[1]<q[1] or bb[2]>q[2] or bb[3]>q[3]:return False
  elif any(overlaps(bb,q,.08) for q in courts.values()):return False
  if any(overlaps(bb,q,.11) for q in vias):return False
  glyph=k.SHAPE_POLY_SET();t.TransformShapeToPolygon(glyph,k.F_SilkS,k.FromMM(.105),1000,k.ERROR_OUTSIDE)
  for q,p in masks+graphics:
   if overlaps(bb,q,.2) and glyph.Collide(p,0):return False
  for other in b.GetDrawings():
   if other is old or not isinstance(other,k.PCB_TEXT) or other.GetLayer()!=k.F_SilkS:continue
   if not overlaps(bb,box(other),.2):continue
   p=k.SHAPE_POLY_SET();other.TransformShapeToPolygon(p,k.F_SilkS,0,1000,k.ERROR_OUTSIDE)
   if glyph.Collide(p,0):return False
  return True
 plans={}
 def accept(ref,t,mode):
  old=labels[ref];b.Remove(old);held.append(old);b.Add(t);labels[ref]=t
  plans[ref]={'uuid':old.m_Uuid.AsString(),'text':t.GetText(),'xy_mm':[k.ToMM(t.GetPosition().x),k.ToMM(t.GetPosition().y)],'angle':t.GetTextAngle().AsDegrees(),'font_mm':k.ToMM(t.GetTextSize().x),'stroke_mm':k.ToMM(t.GetTextThickness()),'layer':'F.SilkS','mode':mode}
 # Larger bodies own their markings; these become hidden only after assembly.
 priority=list(priority) if priority is not None else ['L1','L3','L4','R1','R40','R41','R55','R71','U1','U10','U12','L2','R56']
 priority += sorted(r for r in labels if r not in priority and not r.startswith(('J','H','NT','TP')) and min(bodies[r][2]-bodies[r][0],bodies[r][3]-bodies[r][1])>=2.6)
 for ref in priority:
  if ref not in labels:continue
  old=labels[ref];v=old.GetText();v=ref+'\n'+v[len(ref):].strip() if '\n' not in v and v.strip()!=ref else v
  q=bodies[ref];xy=((q[0]+q[2])/2,(q[1]+q[3])/2)
  fonts=(1.,.9,.8) if ref.startswith('L') else (.9,.8)
  for font in fonts:
   t=make(v,xy,angle(ref),font)
   if clear(t,old,ref,True):accept(ref,t,'within_own_body');break
 # A remaining caption may move only immediately beside its own component.
 waiting=[r for r,t in labels.items() if t.GetLayer()==k.B_SilkS and not r.startswith(('J','H','NT'))]
 for ref in sorted(waiting,key=lambda r:(len(labels[r].GetText()),r)):
  old=labels[ref];text=old.GetText();variants=[text]
  if text.count('\n')==1:variants.append(text.replace('\n',' '))
  q=courts[ref];cx,cy=(q[0]+q[2])/2,(q[1]+q[3])/2;done=False
  for value in variants:
   probe=make(value,(0,0),angle(ref),.8);bb=box(probe);w,h=bb[2]-bb[0],bb[3]-bb[1]
   for gap in (.25,.45,.7,1.):
    sites=[(cx,q[1]-gap-h/2),(cx,q[3]+gap+h/2),(q[0]-gap-w/2,cy),(q[2]+gap+w/2,cy)]
    for side,(x,y) in enumerate(sites):
     for shift in (0,-.5,.5,-1.,1.,-1.5,1.5):
      xy=(x+shift,y) if side<2 else (x,y+shift)
      t=make(value,xy,angle(ref),.8)
      if clear(t,old,ref):accept(ref,t,'adjacent_to_owner');done=True;break
     if done:break
    if done:break
   if done:break
 s=raw.decode('utf-8');changes=[]
 for row in text_blocks(s):
  plan=next((p for p in plans.values() if p['uuid']==row['uuid']),None)
  if plan is None:continue
  v=row['block'];v=v.replace(json.dumps(row['text'],ensure_ascii=False),json.dumps(plan['text'],ensure_ascii=False),1)
  v=re.sub(r'\(at [^\)]+\)',f'(at {plan["xy_mm"][0]} {plan["xy_mm"][1]} {plan["angle"]})',v,count=1)
  v=v.replace('(layer "B.SilkS")','(layer "F.SilkS")').replace('(justify mirror)','')
  v=re.sub(r'\(size [^\)]+\)',f'(size {plan["font_mm"]} {plan["font_mm"]})',v,count=1)
  v=re.sub(r'\(thickness [^\)]+\)',f'(thickness {plan["stroke_mm"]})',v,count=1)
  changes.append((row['start'],row['end'],v))
 for start,end,value in sorted(changes,reverse=True):s=s[:start]+value+s[end:]
 s=re.sub(r'(?m)^[\t ]+(?=\r?$)','',s)
 assert without_silk(raw.decode('utf-8'))==without_silk(s)
 pcb.write_bytes(s.encode('utf-8'))
 return {'placements':plans,'front_owner_count':sum(t.GetLayer()==k.F_SilkS for t in labels.values()),'back_owner_count':sum(t.GetLayer()==k.B_SilkS for t in labels.values()),'remaining_back_owners':[r for r,t in labels.items() if t.GetLayer()==k.B_SilkS],'method':'Native glyphs expanded0.105mm, mask apertures, exposed vias, current silk text/graphics; body containment or owner-adjacent only; 0/90deg component axis. No PCB geometry save.'}
