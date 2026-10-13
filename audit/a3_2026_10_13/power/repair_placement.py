from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
PCB=ROOT/'design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb'
b=k.LoadBoard(str(PCB));fps={f.GetReference():f for f in b.GetFootprints()};KEEP=[b]
def v(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
changes={'R71':(50,4.5,180),'U12':(57,10.5,180),'C63':(56,5.8,0),'C64':(51.8,11.6,90),
 'R73':(48.5,7.7,0),'R72':(48.5,10.2,0),'C53':(48,13.4,0),'R17':(52.3,15.2,180),
 'R1':(24.7,28.95,180),'R56':(24.7,33.15,0),'R6':(24.7,36.25,0),'C6':(24.7,38.5,180),
 'C54':(45.5,26.3,90),'C55':(45.5,31.5,90),'R58':(42.9,34.3,90),'R55':(49,28,-90),
 'TP3':(49.3,33,0),'C61':(49.9,44.1,-90),'J11':(86,23,90),'NT2':(83,20.46,0)}
for ref,(x,y,a) in changes.items():fps[ref].SetPosition(v(x,y));fps[ref].SetOrientationDegrees(a)
report=json.loads((OUT/'placed_drc.json').read_text(encoding='utf-8'))
lookup={t.m_Uuid.AsString():t for t in b.GetTracks()};removed=[]
for issue in report['violations']:
 if issue['type'] not in {'clearance','shorting_items','hole_clearance','hole_to_hole','solder_mask_bridge','track_dangling','via_dangling'}:continue
 for item in issue['items']:
  key=item['uuid']
  if key in lookup:
   t=lookup.pop(key);removed.append({'uuid':key,'net':t.GetNetname(),'reason':issue['type']});b.Remove(t);KEEP.append(t)
# Every obsolete SOLAR LED spur, moved monitor/BAT tap and CN fine-pitch stub is rerouted.
for t in list(b.GetTracks()):
 ax,ay=k.ToMM(t.GetStart().x),k.ToMM(t.GetStart().y);zx,zy=k.ToMM(t.GetEnd().x),k.ToMM(t.GetEnd().y)
 net=t.GetNetname()
 top_old=(net in {'SOLAR','BAT','BAT_SYS','SDA','SCL'} and max(ay,zy)<14 and max(ax,zx)>43)
 old_cn_stub=net.startswith('Net-(U1-') or net=='CHG_CS_M'
 if top_old or old_cn_stub:
  removed.append({'uuid':t.m_Uuid.AsString(),'net':net,'reason':'rebuild changed monitor/CN leaves'});b.Remove(t);KEEP.append(t)
modelpath=PCB.parent/'model.json';model=json.loads(modelpath.read_text(encoding='utf-8'))
for part in model['parts']:
 if part['ref'] in changes:
  x,y,a=changes[part['ref']];part.update(x=x,y=y,rotation=a,native_layer='F.Cu')
modelpath.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
settings=PCB.with_suffix('.kicad_pro').read_bytes();k.SaveBoard(str(PCB),b);PCB.with_suffix('.kicad_pro').write_bytes(settings)
(OUT/'placement_repair.json').write_text(json.dumps({'changes':changes,'removed_tracks':removed},indent=2),encoding='utf-8')
print(json.dumps({'poses_adjusted':len(changes),'obsolete_or_colliding_tracks_removed':len(removed)}))
