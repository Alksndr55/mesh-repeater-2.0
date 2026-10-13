from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
OUT=Path(__file__).resolve().parent
PCB=ROOT/'design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb'
b=k.LoadBoard(str(PCB))
def xy(p):return [round(k.ToMM(p.x),4),round(k.ToMM(p.y),4)]
parts=[]
for f in sorted(b.GetFootprints(),key=lambda f:f.GetReference()):
 parts.append({'ref':f.GetReference(),'value':f.GetValue(),'at':xy(f.GetPosition()),'rotation':f.GetOrientationDegrees(),'layer':k.LayerName(f.GetLayer()),'footprint':str(f.GetFPID().GetLibItemName()),'pads':[{'pin':p.GetNumber(),'at':xy(p.GetPosition()),'net':p.GetNetname(),'size':xy(p.GetSize())} for p in f.Pads()]})
report={'sha256':hashlib.sha256(PCB.read_bytes()).hexdigest(),'parts':parts,'tracks':len(list(b.GetTracks())),'silk_texts':[{'text':g.GetText(),'at':xy(g.GetPosition()),'layer':k.LayerName(g.GetLayer())} for g in b.GetDrawings() if isinstance(g,k.PCB_TEXT)]}
OUT.mkdir(parents=True,exist_ok=True)
snapshot=OUT/'before_power.kicad_pcb'
if not snapshot.exists():snapshot.write_bytes(PCB.read_bytes())
(OUT/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'parts':[{'ref':p['ref'],'value':p['value'],'at':p['at'],'rotation':p['rotation'],'layer':p['layer'],'footprint':p['footprint']} for p in parts]},ensure_ascii=True))
