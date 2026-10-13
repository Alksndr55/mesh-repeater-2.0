from pathlib import Path
import sys,json,math
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
from collections import defaultdict
def xy(v):return [k.ToMM(v.x),k.ToMM(v.y)]
def main():
 result={}
 for name in ['Power','Logic','Shield']:
  b=k.LoadBoard(str(ROOT/f'design/MeshRepeater2_{name}/MeshRepeater2_{name}.kicad_pcb'));allitems=list(b.GetTracks())+[p for f in b.GetFootprints() for p in f.Pads()];ground={}
  for l in [k.F_Cu,k.B_Cu]:
   cu=k.SHAPE_POLY_SET()
   for z in b.Zones():
    if z.GetNetname()=='GND' and not z.GetIsRuleArea() and z.HasFilledPolysForLayer(l):cu.BooleanAdd(z.GetFilledPolysList(l))
   for o in allitems:
    if o.GetNetname()!='GND' or not o.IsOnLayer(l):continue
    if isinstance(o,k.PAD):cu.BooleanAdd(o.GetEffectivePolygon(l))
    else:
     s=k.SHAPE_POLY_SET();o.TransformShapeToPolygon(s,l,0,1000,k.ERROR_OUTSIDE);cu.BooleanAdd(s)
   ground[l]=cu
  islands={};edges=defaultdict(set);touch={}
  for l,cu in ground.items():
   for i in range(cu.OutlineCount()):
    p=k.SHAPE_POLY_SET();p.AddOutline(cu.COutline(i))
    for j in range(cu.HoleCount(i)):p.AddHole(cu.CHole(i,j),0)
    islands[(l,i)]=p
  for o in allitems:
   if o.GetNetname()!='GND':continue
   ts=[key for key,p in islands.items() if o.IsOnLayer(key[0]) and p.Contains(o.GetPosition())]
   if isinstance(o,k.PCB_VIA) or isinstance(o,k.PAD) and o.GetDrillSize().x:
    for a in ts:
     for c in ts:edges[a].add(c)
   touch[o.m_Uuid.AsString()]=ts
  todo=set(islands);components=[];lookup={}
  while todo:
   first=next(iter(todo));seen={first};queue=[first]
   while queue:
    a=queue.pop()
    for c in edges[a]:
     if c not in seen:seen.add(c);queue.append(c)
   todo-=seen
   for a in seen:lookup[a]=len(components)
   components.append({'islands':[[b.GetLayerName(l),i] for l,i in seen],'area_mm2':sum(islands[a].Area()/1e12 for a in seen)})
  refs={}
  for f in b.GetFootprints():
   for p in f.Pads():
    if p.GetNetname()=='GND':refs[f.GetReference()+'.'+p.GetNumber()+'@'+str(xy(p.GetPosition()))]=sorted({lookup[a] for a in touch[p.m_Uuid.AsString()]})
  rf=[]
  for t in b.GetTracks():
   if isinstance(t,k.PCB_VIA) or 'ANT' not in t.GetNetname():continue
   p=k.VECTOR2I(round((t.GetStart().x+t.GetEnd().x)/2),round((t.GetStart().y+t.GetEnd().y)/2))
   rf.append({'net':t.GetNetname(),'midpoint':xy(p),'width_mm':k.ToMM(t.GetWidth()),'top_GND_gap_midpoint_mm':k.ToMM(ground[k.F_Cu].Distance(p))-k.ToMM(t.GetWidth())/2,'bottom_GND_at_midpoint':ground[k.B_Cu].Contains(p)})
  result[name]={'GND_components':components,'GND_pad_membership':refs,'RF_midpoints':rf}
  print(name,'groundgroups',len(components),'rf',rf)
 (OUT/'MECHANICAL_RF_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
