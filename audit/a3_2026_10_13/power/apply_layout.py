"""A3 placement on the existing POWER board, never reconstructing A2 copper."""
from pathlib import Path
import json,math,sys,hashlib,shutil
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
PROJECT=ROOT/'design/MeshRepeater2_Power'
PCB=PROJECT/'MeshRepeater2_Power.kicad_pcb'
KEEP=[]
def v(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def xy(p):return [k.ToMM(p.x),k.ToMM(p.y)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 modelpath=PROJECT/'model.json';model=json.loads(modelpath.read_text(encoding='utf-8'));parts={p['ref']:p for p in model['parts']}
 assert 'NT2' not in parts,'Initial placement script is single-use'
 handoff=json.loads((OUT.parent/'schematic/POWER_electrical_handoff.json').read_text(encoding='utf-8'))
 before=sha(PCB);b=k.LoadBoard(str(PCB));KEEP.append(b);fps={f.GetReference():f for f in b.GetFootprints()}
 nets={n.GetNetname():n for n in b.GetNetInfo().NetsByNetcode().values()}
 for name in ('SYS_3V3','RADIO_3V3'):
  if name not in nets:
   n=k.NETINFO_ITEM(b,name,max(x.GetNetCode() for x in nets.values())+1);b.Add(n);nets[name]=n
 for ref,updates in handoff['update_references'].items():
  parts[ref].update(updates)
  if ref.startswith('R'):
   parts[ref]['source_footprint_before_v2_graphic_variant']='Meshcore:R_2512_6332Metric'
 for part in handoff['add_parts']:
  parts[part['ref']]=part;model['parts'].append(part)
 # A footprint for the physical star point, no resistor and no extra drop.
 name='NetTie_2_SMD_Power_Star_A3'
 star=f'''(footprint "{name}" (version 20260206) (generator "pcbnew") (layer "F.Cu")
 (descr "Copper star immediately after J11; two independent outgoing power branches, no populated component.")
 (property "Reference" "REF**" (at 0 -1.5) (layer "F.Fab") (hide yes) (effects (font (size 0.8 0.8))))
 (property "Value" "3V3 STAR" (at 0 1.5) (layer "F.Fab") (hide yes) (effects (font (size 0.8 0.8))))
 (attr smd exclude_from_pos_files exclude_from_bom)
 (net_tie_pad_groups "1,2")
 (fp_rect (start -1.5 -1) (end 1.5 1) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
 (pad "1" smd rect (at 1 0) (size 2 1.6) (layers "F.Cu"))
 (pad "2" smd rect (at -1 0) (size 2 1.6) (layers "F.Cu")))
'''
 (PROJECT/'Meshcore.pretty'/f'{name}.kicad_mod').write_text(star,encoding='utf-8')
 # Standard, identical 2512 lands for all six series/sense/damping resistors.
 resistorlib=Path('C:/Program Files/KiCad/10.0/share/kicad/footprints/Resistor_SMD.pretty')
 poses={
  'D3':(67,2.4,180),'D4':(73,2.4,0),'R10':(67,5.0,0),'R11':(73,5.0,0),
  'R71':(47.5,4.6,180),'U12':(56.0,7.4,180),'R72':(48.5,10.0,0),'R73':(48.5,7.5,0),
  'C64':(51.5,8.65,90),'C63':(54.5,3.5,90),
  'U1':(16.9,28.5,0),'R1':(24.7,28.4,180),'R56':(24.7,32.6,0),
  'Q4':(32,28.75,0),'L1':(35.1,37.5,0),'U10':(46.05,39.4,0),'R58':(44,33.8,90),
  'C7':(18.6,33.6,0),'R6':(24.7,35.1,0),'C6':(24.7,37.6,180),
  'R55':(49.3,28.0,-90),'C54':(44.3,27.3,180),'C55':(44.3,30.3,180),
  'R40':(57.5,32.5,180),'R41':(75.5,32.5,180),
  'TP9':(3.3,11.5,0),'TP6':(3.3,14.5,0),'TP1':(3.3,17.5,0),
  'J11':(86,23,0),'NT2':(83,25.54,0)}
 changed=[];oldpads=[]
 for ref in poses:
  if ref in fps:
   f=fps[ref];oldpads.extend({'ref':ref,'pin':p.GetNumber(),'at':xy(p.GetPosition()),'net':p.GetNetname(),'layer':k.LayerName(f.GetLayer())} for p in f.Pads() if p.GetNetCode())
 for ref in handoff['update_references']:
  if ref.startswith('R'):
   old=fps[ref];f=k.FootprintLoad(str(resistorlib),'R_2512_6332Metric');KEEP.append(f)
   f.SetUuid(old.m_Uuid);f.SetPath(old.GetPath());f.SetReference(ref);f.SetValue(parts[ref]['value'])
   for field in old.GetFields():
    if field.GetName() not in ('Reference','Value','Footprint'):f.SetField(field.GetName(),field.GetText())
   for p in f.Pads():
    previous=next(q for q in old.Pads() if q.GetNumber()==p.GetNumber());p.SetNet(previous.GetNet())
   b.Remove(old);KEEP.append(old);b.Add(f);fps[ref]=f
   variant='R_2512_6332Metric__A3_'+ref
   f.SetFPID(k.LIB_ID('Meshcore',variant));parts[ref]['footprint']='Meshcore:'+variant
   proto=k.Cast_to_FOOTPRINT(f.Duplicate(False));KEEP.append(proto);proto.SetReference('REF**');proto.SetValue(variant)
   for p in proto.Pads():p.SetNetCode(0)
   k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(PROJECT/'Meshcore.pretty'),proto)
 for ref in ('J11','NT2'):
  part=parts[ref];lib,fpname=part['footprint'].split(':')
  if ref=='J11':
   source=ROOT/'design/MeshRepeater2_Logic/Meshcore.pretty'/f'{fpname}.kicad_mod'
   shutil.copy2(source,PROJECT/'Meshcore.pretty'/source.name)
  f=k.FootprintLoad(str(PROJECT/(lib+'.pretty')),fpname);assert f is not None
  f.SetReference(ref);f.SetValue(part['value']);f.SetFPID(k.LIB_ID(lib,fpname));b.Add(f);fps[ref]=f
  for p in f.Pads():p.SetNet(nets[part['nets'][p.GetNumber()]])
 for ref,(x,y,angle) in poses.items():
  f=fps[ref];beforepose={'at':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'side':k.LayerName(f.GetLayer())}
  if f.GetLayer()==k.B_Cu:f.Flip(f.GetPosition(),False)
  f.SetPosition(v(x,y));f.SetOrientationDegrees(angle)
  parts[ref].update(x=x,y=y,rotation=angle,native_layer='F.Cu')
  for field in f.GetFields():field.SetVisible(False)
  changed.append({'ref':ref,'before':beforepose,'after':{'at':[x,y],'angle':angle,'side':'F.Cu'}})
 for ref in handoff['update_references']:
  f=fps[ref];part=parts[ref];f.SetValue(part['value'])
  for key,attr in [('MPN','mpn'),('Package','package_short'),('Datasheet','datasheet'),('Vendor URL','vendor_url')]:
   if attr in part:f.SetField(key,str(part[attr]))
  for field in f.GetFields():field.SetVisible(False)
 for p in fps['J101'].Pads():
  net=parts['J101']['nets'][p.GetNumber()]
  if net is None:p.SetNetCode(0)
  else:p.SetNet(nets[net])
 # Remove the obsolete filter/header feed and bottom-side monitor routes.
 removed=[]
 erase_nets={'FILTER_OUT','SYS_3V3','CHRG','DONE','Net-(D3-A)','Net-(D4-A)','Net-(U12-IN+)','Net-(U12-IN-)'}
 for t in list(b.GetTracks()):
  if t.GetNetname() in erase_nets:
   removed.append({'net':t.GetNetname(),'start':xy(t.GetStart()),'end':xy(t.GetEnd()),'reason':'superseded A2 feed/monitor/LED route'})
   b.Remove(t);KEEP.append(t)
 # Text is regenerated after routing; delete old group callouts immediately.
 for g in list(b.GetDrawings()):
  if isinstance(g,k.PCB_TEXT) and g.GetLayer() in (k.F_SilkS,k.B_SilkS):b.Remove(g);KEEP.append(g)
 model.update(revision='V2.0-A3-SINGLE-FACE',schematic_revision='V2.0-A3',schematic_date='2026-10-13')
 model['parts']=list(parts.values())
 model['power_isolation']={'board':'POWER','ref':'J11','filter_net':'FILTER_OUT','load_net':'SYS_3V3','star_ref':'NT2','radio_branch':'RADIO_3V3','shunt':'remove before USB; fit only with USB disconnected'}
 modelpath.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
 settings=PCB.with_suffix('.kicad_pro').read_bytes();k.SaveBoard(str(PCB),b);PCB.with_suffix('.kicad_pro').write_bytes(settings)
 result={'input_sha256':before,'placed_sha256':sha(PCB),'changed':changed,'removed_tracks':removed,'old_pads':oldpads,'pending':'Copper rerouting, parity, markings and native DRC are not complete.'}
 (OUT/'placement_changes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'placed':len(changed),'removed_obsolete_tracks':len(removed),'all_power_components_on_F':all(f.GetLayer()==k.F_Cu for f in fps.values()),'routing_pending':True}))
if __name__=='__main__':main()
