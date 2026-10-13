from pathlib import Path
import json,sys,subprocess,time,hashlib
from router import k,route,component_points,item_layers,xy
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
PCB=ROOT/'design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb'
CLI='C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
KEEP=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(b):
 settings=PCB.with_suffix('.kicad_pro').read_bytes();k.ZONE_FILLER(b).Fill(b.Zones());k.SaveBoard(str(PCB),b);PCB.with_suffix('.kicad_pro').write_bytes(settings)
def drc(label):
 p=HERE/(label+'_drc.json');subprocess.run([CLI,'pcb','drc','--format','json','--severity-all','--schematic-parity','-o',str(p),str(PCB)],check=True,stdout=subprocess.PIPE)
 return json.loads(p.read_text(encoding='utf8'))
def lookup(b):
 out={str(t.m_Uuid.AsString()):t for t in b.GetTracks()}
 for f in b.GetFootprints():
  for p in f.Pads():out[str(p.m_Uuid.AsString())]=p
 return out
def pad(b,ref,num):return next(p for f in b.GetFootprints()if f.GetReference()==ref for p in f.Pads()if p.GetNumber()==num)
def exact(b,net,a,z,width):
 return route(b,net,xy(a.GetPosition()),xy(z.GetPosition()),width,(0,),(0,),False,[(xy(a.GetPosition()),0)],[(xy(z.GetPosition()),0)])

def main():
 logpath=HERE/'route_log.json';logs=json.loads(logpath.read_text(encoding='utf8'))if logpath.exists()else {'routes':[],'candidate_failures':[],'initial_owner_sha256':sha(PCB)}
 stage=sys.argv[1]if len(sys.argv)>1 else 'main'
 if stage=='main' and not logs['routes']:
  b=k.LoadBoard(str(PCB));KEEP.append(b)
  for net,ref,num,ref2,num2,width in [('BAT','J8','1','R71','2',.8),('BAT_SYS','R71','1','C53','1',.8),('CS_P','L1','2','R56','1',.8),('FILTER_OUT','L4','2','J11','1',.8),('SYS_3V3','J11','2','NT2','1',1.0),('SYS_3V3','NT2','1','J101','3',.8),('RADIO_3V3','NT2','2','J101','5',.8)]:
   try:logs['routes'].append(exact(b,net,pad(b,ref,num),pad(b,ref2,num2),width))
   except RuntimeError as ex:logs['candidate_failures'].append(str(ex));print('special route failed',ex,flush=True)
  save(b);logpath.write_text(json.dumps(logs,indent=2),encoding='utf8')
 if stage=='kelvin':
  b=k.LoadBoard(str(PCB));KEEP.append(b)
  for net,r,p,r2,p2 in [('BAT','R71','2','R73','1'),('BAT_SYS','R71','1','R72','1')]:
   logs['routes'].append(exact(b,net,pad(b,r,p),pad(b,r2,p2),.2))
  save(b);logpath.write_text(json.dumps(logs,indent=2),encoding='utf8');return
 for iteration in range(4):
  data=drc('main_'+str(len(logs['routes'])));missing=data['unconnected_items'];print('missing',len(missing),'violations',len(data['violations']),flush=True)
  if not missing:break
  b=k.LoadBoard(str(PCB));KEEP.append(b);items=lookup(b);count=0
  # Leave the two intentional high-impedance shunt branches for a separate
  # Kelvin pass from the exact lands, after the bulk-current routes are fixed.
  for issue in missing:
   ai,zi=issue['items'];a,z=items.get(ai['uuid']),items.get(zi['uuid'])
   if a is None or z is None:continue
   if isinstance(a,k.PAD) and a.GetParentFootprint().GetReference()in('R72','R73')and a.GetNumber()=='1':continue
   if isinstance(z,k.PAD) and z.GetParentFootprint().GetReference()in('R72','R73')and z.GetNumber()=='1':continue
   net=a.GetNetname();assert net==z.GetNetname()
   sp=component_points(b,a);tp=component_points(b,z)
   start=(ai['pos']['x'],ai['pos']['y']);end=(zi['pos']['x'],zi['pos']['y'])
   # Long power traces remain broad. Small IC sense/supply pins get a short
   # neck appropriate to their pad geometry and actual low branch current.
   fine=any(isinstance(t,k.PAD)and t.GetParentFootprint().GetReference()in('U1','U2','U12')for t in(a,z))
   widths=[.5]if net=='GND'else([.8,.4]if any(n in net for n in('BAT','CS_P','CHG_CS_M','FILTER','SYS_','D1-K'))and not fine else [.2])
   if net.startswith('Net-(U12-'):widths=[.2]
   success=False
   for width in widths:
    try:
     logs['routes'].append(route(b,net,start,end,width,item_layers(ai['description']),item_layers(zi['description']),False,sp,tp));count+=1;success=True;break
    except RuntimeError as ex:print('failure',net,width,ex,flush=True);last=str(ex)
   if not success:logs['candidate_failures'].append(last)
  save(b);logpath.write_text(json.dumps(logs,indent=2),encoding='utf8')
  if not count:break
 print('routing pass complete',len(logs['routes']),flush=True)
if __name__=='__main__':main()
