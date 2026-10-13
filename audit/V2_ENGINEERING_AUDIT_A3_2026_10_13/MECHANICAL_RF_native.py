"""Read-only saved A3 geometry/copper evidence. No refill or save."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json, hashlib, math
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
def xy(v): return [round(k.ToMM(v.x),6),round(k.ToMM(v.y),6)]
def bb(v):return [k.ToMM(v.GetX()),k.ToMM(v.GetY()),k.ToMM(v.GetRight()),k.ToMM(v.GetBottom())]
def uid(o):return o.m_Uuid.AsString()
def chain(c):return [xy(c.CPoint(i)) for i in range(c.PointCount())]
def poly(s):return [{'shell':chain(s.COutline(i)),'holes':[chain(s.CHole(i,j)) for j in range(s.HoleCount(i))]} for i in range(s.OutlineCount())]
def main():
 result={'method':'KiCad 10.0.6 saved PCB only; no zone fill, save or mutation','boards':{}}
 for name in ['Power','Logic','Shield']:
  path=ROOT/f'design/MeshRepeater2_{name}/MeshRepeater2_{name}.kicad_pcb';digest=hashlib.sha256(path.read_bytes()).hexdigest()
  b=k.LoadBoard(str(path));r={'sha256':digest,'path':str(path.relative_to(ROOT)),'edge_bbox':bb(b.GetBoardEdgesBoundingBox()),'thickness_mm':k.ToMM(b.GetDesignSettings().GetBoardThickness()),'footprints':{},'tracks':[],'zones':[],'edge_cuts':[]}
  for f in b.GetFootprints():
   fp={'value':f.GetValue(),'lib':str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),'at':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'layer':b.GetLayerName(f.GetLayer()),'pads':[],'models':[{'filename':m.m_Filename,'offset':[m.m_Offset.x,m.m_Offset.y,m.m_Offset.z],'rotation':[m.m_Rotation.x,m.m_Rotation.y,m.m_Rotation.z]} for m in f.Models()]}
   for p in f.Pads():fp['pads'].append({'n':p.GetNumber(),'at':xy(p.GetPosition()),'size':xy(p.GetSize()),'drill':xy(p.GetDrillSize()),'net':p.GetNetname(),'uuid':uid(p),'layer':b.GetLayerName(p.GetLayer()),'mask_expansion_mm':k.ToMM(p.GetSolderMaskExpansion(k.F_Mask))})
   r['footprints'][f.GetReference()]=fp
  for t in b.GetTracks():
   if isinstance(t,k.PCB_VIA):r['tracks'].append({'kind':'via','uuid':uid(t),'at':xy(t.GetPosition()),'net':t.GetNetname(),'diameter_mm':k.ToMM(t.GetWidth(k.F_Cu)),'drill_mm':k.ToMM(t.GetDrill())})
   else:r['tracks'].append({'kind':'track','uuid':uid(t),'start':xy(t.GetStart()),'end':xy(t.GetEnd()),'net':t.GetNetname(),'layer':b.GetLayerName(t.GetLayer()),'width_mm':k.ToMM(t.GetWidth()),'length_mm':k.ToMM(t.GetLength())})
  for d in list(b.GetDrawings())+[g for f in b.GetFootprints() for g in f.GraphicalItems()]:
   if isinstance(d,k.PCB_SHAPE) and d.GetLayer()==k.Edge_Cuts:
    r['edge_cuts'].append({'shape':int(d.GetShape()),'start':xy(d.GetStart()),'end':xy(d.GetEnd()),'bbox':bb(d.GetBoundingBox())})
  ground={}
  for l in [k.F_Cu,k.B_Cu]:
   cu=k.SHAPE_POLY_SET()
   for z in b.Zones():
    if not z.GetIsRuleArea() and z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l):cu.BooleanAdd(z.GetFilledPolysList(l))
   for f in b.GetFootprints():
    for p in f.Pads():
     if p.GetNetname()=='GND' and p.IsOnLayer(l):cu.BooleanAdd(p.GetEffectivePolygon(l))
   for t in b.GetTracks():
    if t.GetNetname()=='GND' and t.IsOnLayer(l):
     s=k.SHAPE_POLY_SET();t.TransformShapeToPolygon(s,l,0,1000,k.ERROR_OUTSIDE);cu.BooleanAdd(s)
   ground[l]=cu
  for z in b.Zones():
   r['zones'].append({'net':z.GetNetname(),'rule_area':z.GetIsRuleArea(),'name':z.GetZoneName(),'layers':[b.GetLayerName(l) for l in [k.F_Cu,k.B_Cu] if z.IsOnLayer(l)],'outline':poly(z.Outline()),'fills':{b.GetLayerName(l):poly(z.GetFilledPolysList(l)) for l in [k.F_Cu,k.B_Cu] if z.HasFilledPolysForLayer(l)}})
  r['gnd_copper']={b.GetLayerName(l):poly(cu) for l,cu in ground.items()}
  samples=[]
  for t in b.GetTracks():
   if isinstance(t,k.PCB_VIA) or not any(n in t.GetNetname() for n in ['ANT','SW','LX','SCK','MOSI','MISO']):continue
   l=k.B_Cu if t.GetLayer()==k.F_Cu else k.F_Cu
   a,e=t.GetStart(),t.GetEnd();n=max(1,math.ceil(k.ToMM(t.GetLength())/.05));missing=[]
   for i in range(n+1):
    p=k.VECTOR2I(round(a.x+(e.x-a.x)*i/n),round(a.y+(e.y-a.y)*i/n))
    if not ground[l].Contains(p):missing.append(i)
   samples.append({'net':t.GetNetname(),'uuid':uid(t),'start':xy(a),'end':xy(e),'width_mm':k.ToMM(t.GetWidth()),'reference_layer':b.GetLayerName(l),'samples':n+1,'missing':len(missing),'length_mm':k.ToMM(t.GetLength())})
  r['reference_samples']=samples
  r['source_unchanged']=digest==hashlib.sha256(path.read_bytes()).hexdigest()
  result['boards'][name]=r
  print(name,'fps',len(r['footprints']),'tracks',len(r['tracks']),'GND outlines',[len(r['gnd_copper'][b.GetLayerName(l)]) for l in [k.F_Cu,k.B_Cu]],flush=True)
 (OUT/'MECHANICAL_RF_native.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
