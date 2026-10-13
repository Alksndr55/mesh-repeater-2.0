"""Independent read-only BRep checks, reports limited to nominal envelopes."""
from pathlib import Path
import sys,gzip,json,hashlib,math
sys.dont_write_bytecode=True
import FreeCAD as A
import Part
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
result={'method':'Independent FreeCAD BRep read. No CAD/FCStd save; temporary decompressed STEP confined to audit directory and deleted. All mechanical/connector models are nominal envelopes, not hardware qualification.','models':{},'boards':{},'collisions':[]}
shapes={}
for name in ['POWER','SHIELD','LOGIC']:
 p=ROOT/'output'/name/('MeshRepeater2_'+name.title()+'.step')
 compressed=Path(str(p)+'.gz')
 data=gzip.decompress(compressed.read_bytes()) if compressed.exists() else p.read_bytes()
 temp=OUT/f'MECHANICAL_RF_TMP_{name}.step';temp.write_bytes(data)
 s=Part.Shape();s.read(str(temp));temp.unlink()
 core=max([x for x in s.Solids if abs(x.BoundBox.XLength-90)<.01 and abs(x.BoundBox.YLength-60)<.01 and 1<x.BoundBox.ZLength<2],key=lambda x:x.Volume)
 bb=core.BoundBox
 anchor=(bb.ZMin+bb.ZMax)/2+1.52/2
 if name=='SHIELD':anchor=max(x.BoundBox.ZMax for x in s.Solids if .015<x.BoundBox.ZLength<.06)
 s.translate(A.Vector(-bb.XMin,-bb.YMax,-anchor))
 if name=='POWER':s.translate(A.Vector(0,0,1.52))
 else:s.rotate(A.Vector(),A.Vector(1,0,0),180);s.translate(A.Vector(0,-60,20.02 if name=='SHIELD' else 37.54))
 shapes[name]=s
 result['boards'][name]={'step_uncompressed_sha256':hashlib.sha256(data).hexdigest(),'nominal_dielectric_mm':bb.ZLength,'solid_count':len(s.Solids),'assembled_bbox':[s.BoundBox.XMin,s.BoundBox.YMin,s.BoundBox.ZMin,s.BoundBox.XMax,s.BoundBox.YMax,s.BoundBox.ZMax]}
for na,nb in [('POWER','SHIELD'),('SHIELD','LOGIC'),('POWER','LOGIC')]:
 total=0.;count=0
 for a in shapes[na].Solids:
  aa=a.BoundBox
  for b in shapes[nb].Solids:
   bb=b.BoundBox
   if aa.XMax<=bb.XMin or bb.XMax<=aa.XMin or aa.YMax<=bb.YMin or bb.YMax<=aa.YMin or aa.ZMax<=bb.ZMin or bb.ZMax<=aa.ZMin:continue
   count+=1;total+=a.common(b).Volume
 result['collisions'].append({'pair':[na,nb],'candidate_solid_pairs':count,'intersection_mm3':total})
for name in ['Heltec_HT_RA62_Approx','SMA_KLS1_SMA002_B_Approx','S869M000S003_Approx','NiceNano_Clone_Approx','Ali_PinHeader_2x06_P2.54_L35_A3C6','Ali_PinSocket_2x06_P2.54_H8.5_v2_mirror','SW_TE_1825027_2_Side','TDK_B57861S_Vertical_Approx']:
 p=ROOT/'design/MeshRepeater2_Logic/3dmodels'/(name+'.step');s=Part.Shape();s.read(str(p));b=s.BoundBox
 result['models'][name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bbox':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],'valid':s.isValid(),'solid_count':len(s.Solids)}
print(json.dumps(result,ensure_ascii=False,indent=2))
(OUT/'MECHANICAL_RF_brep.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
