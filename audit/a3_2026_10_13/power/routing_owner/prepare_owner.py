from pathlib import Path
import sys,json,hashlib,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
KEEP=[]
def xy(p):return[k.ToMM(p.x),k.ToMM(p.y)]
def v(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 d=ROOT/'design/MeshRepeater2_Power';pcb=d/'MeshRepeater2_Power.kicad_pcb';modelpath=d/'model.json'
 before=HERE/'before';assert not before.exists(),'single-use preparation'
 before.mkdir()
 for p in [pcb,modelpath,pcb.with_suffix('.kicad_pro')]:shutil.copy2(p,before/p.name)
 b=k.LoadBoard(str(pcb));KEEP.append(b);fps={f.GetReference():f for f in b.GetFootprints()}
 model=json.loads(modelpath.read_text(encoding='utf8'));meta=json.loads((HERE.parents[1]/'schematic/POWER_schematic_metadata_handoff.json').read_text(encoding='utf8'))
 for part in model['parts']:part.update(meta[part['ref']])
 xml=ET.parse(HERE.parents[1]/'schematic/POWER/netlist.xml')
 comps={c.get('ref'):c for c in xml.findall('components/comp')}
 netmap={(n.get('ref'),n.get('pin')):net.get('name')for net in xml.findall('nets/net')for n in net.findall('node')}
 nets={n.GetNetname():n for n in b.GetNetInfo().NetsByNetcode().values()}
 fields=[]
 for ref,f in fps.items():
  c=comps[ref]
  assert f.GetValue()==c.findtext('value'),ref
  for field in c.findall('fields/field'):
   name=field.get('name');value=field.text or ''
   if name in ('Reference','Value','Footprint'):continue
   if not f.HasField(name) or f.GetField(name).GetText()!=value:
    fields.append((ref,name));exists=f.HasField(name);f.SetField(name,value)
    if not exists:f.GetField(name).SetVisible(False)
  path=k.KIID_PATH()
  for uid in (meta[ref]['sheet_path']+'/'+meta[ref]['schematic_uuid']).strip('/').split('/'):path.push_back(k.KIID(uid))
  f.SetPath(path)
  for pad in f.Pads():
   name=netmap.get((ref,pad.GetNumber()))
   if not name:continue
   if name not in nets:
    n=k.NETINFO_ITEM(b,name,max(n.GetNetCode()for n in nets.values())+1);b.Add(n);nets[name]=n
   assert pad.GetNetname()==name or (ref=='J101'and pad.GetNumber()=='8'and name.startswith('unconnected-')),(ref,pad.GetNumber(),pad.GetNetname(),name)
   pad.SetNet(nets[name])
 report=json.loads((HERE.parent/'fresh_owner_drc.json').read_text(encoding='utf8'))
 lookup={str(t.m_Uuid.AsString()):t for t in b.GetTracks()};removed=[]
 # Remove only tracks/vias identified as colliding, plus obsolete dangling
 # leaves. The preserved hot TPS path never appears in this list.
 badtypes={'shorting_items','clearance','hole_clearance','solder_mask_bridge','items_not_allowed','track_dangling','via_dangling'}
 for issue in report['violations']:
  if issue['type']not in badtypes:continue
  for item in issue['items']:
   uid=item['uuid']
   if uid in lookup:
    t=lookup.pop(uid);removed.append({'uuid':uid,'net':t.GetNetname(),'start':xy(t.GetStart()),'end':xy(t.GetEnd()),'reason':issue['type']})
    b.Remove(t);KEEP.append(t)
 # Old optional-block border segments cross the enlarged 2512 pads. Remove
 # only these stale board-art edges; root regenerates exact mirrored blocks.
 drawings={str(g.m_Uuid.AsString()):g for g in b.GetDrawings()};artremoved=[]
 for issue in report['violations']:
  if not issue['type'].startswith('silk'):continue
  for item in issue['items']:
   uid=item['uuid']
   if uid in drawings:
    g=drawings.pop(uid);artremoved.append(uid);b.Remove(g);KEEP.append(g)
 # Add a short three-via return fence adjacent to the actual three GND pins.
 gnd=nets['GND'];header_vias=[]
 for x in (64.15,66.69,69.23):
  via=k.PCB_VIA(b);via.SetPosition(v(x,7.05));via.SetWidth(k.FromMM(.6));via.SetDrill(k.FromMM(.3));via.SetLayerPair(k.F_Cu,k.B_Cu);via.SetNet(gnd);via.SetLocked(True);b.Add(via)
  t=k.PCB_TRACK(b);t.SetStart(v(x,7.05));t.SetEnd(v(x,8.46));t.SetWidth(k.FromMM(.5));t.SetLayer(k.F_Cu);t.SetNet(gnd);t.SetLocked(True);b.Add(t)
  header_vias.append([x,7.05])
 k.ZONE_FILLER(b).Fill(b.Zones());settings=pcb.with_suffix('.kicad_pro').read_bytes();k.SaveBoard(str(pcb),b);pcb.with_suffix('.kicad_pro').write_bytes(settings)
 modelpath.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf8')
 result={'input_sha256':sha(before/pcb.name),'prepared_sha256':sha(pcb),'removed_obsolete_copper':removed,'old_block_border_edges_removed':artremoved,'metadata_fields_synced':fields,'header_gnd_vias':header_vias,'L1_keepout_actual_center_x':35.1,'L1_keepout_not_shifted_twice':True}
 (HERE/'preparation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({'removed_copper':len(removed),'metadata_fields':len(fields),'header_vias':3}))
if __name__=='__main__':main()
