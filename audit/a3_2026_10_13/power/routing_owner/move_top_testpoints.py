from pathlib import Path
import sys,json,shutil
from complete_owner_routes import ROOT,HERE,PCB,KEEP,k,save,pad,exact,drc,lookup,component_points,route,xy
NAME='TestPoint_Pad_D1p5mm_A3_Edge_R0p9'
POSES={'TP6':(7.6,1.2),'TP9':(18.6,1.2),'TP1':(29.6,1.2)}

def main():
 b=k.LoadBoard(str(PCB));KEEP.append(b);fps={f.GetReference():f for f in b.GetFootprints()};library=PCB.parent/'Meshcore.pretty'
 (HERE/'before_top_tp.kicad_pcb').write_bytes(PCB.read_bytes())
 (library/(NAME+'.kicad_mod')).write_text(f'''(footprint "{NAME}" (version 20260206) (generator "pcbnew")
 (layer "F.Cu") (descr "A3 board-only exposed copper test pad D1.5mm, F.Mask D1.6mm; physical pad+mask courtyard R0.9mm. No populated hardware; fixture probe accessibility checked separately.")
 (attr board_only exclude_from_pos_files exclude_from_bom)
 (fp_text reference "REF**" (at 0 1.8) (layer "F.Fab") hide (effects(font(size 0.8 0.8)(thickness 0.12))))
 (fp_text value "TEST PAD" (at 0 -1.8) (layer "F.Fab") hide (effects(font(size 0.8 0.8)(thickness 0.12))))
 (fp_circle(center 0 0)(end 0.75 0)(stroke(width 0.05)(type default))(fill none)(layer "F.Fab"))
 (fp_circle(center 0 0)(end 0.9 0)(stroke(width 0.05)(type default))(fill none)(layer "F.CrtYd"))
 (pad "1" smd circle(at 0 0)(size 1.5 1.5)(layers "F.Cu" "F.Mask")(solder_mask_margin 0.05)(zone_connect 2))
)\n''',encoding='utf8')
 for ref,(x,y)in POSES.items():
  old=fps[ref];f=k.FootprintLoad(str(library),NAME);KEEP.append(f);f.SetUuid(old.m_Uuid);f.SetPath(old.GetPath());f.SetReference(ref);f.SetValue(old.GetValue());f.SetFPID(k.LIB_ID('Meshcore',NAME));f.SetPosition(k.VECTOR2I(k.FromMM(x),k.FromMM(y)))
  for field in old.GetFields():
   if field.GetName()not in('Reference','Value','Footprint'):f.SetField(field.GetName(),field.GetText())
  for p in f.Pads():p.SetNet(next(iter(old.Pads())).GetNet())
  for field in f.GetFields():field.SetVisible(False)
  b.Remove(old);KEEP.append(old);b.Add(f)
 save(b)
 modelpath=PCB.parent/'model.json';m=json.loads(modelpath.read_text(encoding='utf8'))
 for part in m['parts']:
  if part['ref']in POSES:
   x,y=POSES[part['ref']];part.update(x=x,y=y,rotation=0,native_layer='F.Cu',footprint='Meshcore:'+NAME,source_footprint_before_v2_graphic_variant='Meshcore:'+NAME)
 modelpath.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
 removed=[]
 for it in range(12):
  data=drc('top_tp_trim_'+str(it));bad=[v for v in data['violations']if v['type']in('track_dangling','via_dangling')]
  if not bad:break
  b=k.LoadBoard(str(PCB));KEEP.append(b);items=lookup(b)
  for v in bad:
   for item in v['items']:
    t=items.get(item['uuid'])
    if t is not None:
     removed.append({'net':t.GetNetname(),'uuid':item['uuid']});b.Remove(t);KEEP.append(t)
  save(b)
 b=k.LoadBoard(str(PCB));KEEP.append(b);routes=[]
 # Sense pads carry probe current only. Join the nearest real connected feed
 # rather than retaining long former test-point branches around the perimeter.
 for net,tp,connector in [('BAT','TP1','J8'),('SOLAR','TP9','J7')]:
  a,z=pad(b,tp,'1'),pad(b,connector,'1')
  routes.append(route(b,net,xy(a.GetPosition()),xy(z.GetPosition()),.25,(0,),(0,),False,[(xy(a.GetPosition()),0)],component_points(b,z)))
 save(b)
 (HERE/'top_testpoints.json').write_text(json.dumps({'poses':POSES,'pad_diameter_mm':1.5,'mask_diameter_mm':1.6,'courtyard_radius_mm':.9,'component_hardware':False,'footprint':'Meshcore:'+NAME,'routes':routes,'removed_old_leaf_copper':removed},indent=2),encoding='utf8')
 print(json.dumps({'top_TP_row_y_mm':1.2,'equal_pitch_mm':11,'native_routes':len(routes),'removed_old_leaves':len(removed)}))
if __name__=='__main__':main()
