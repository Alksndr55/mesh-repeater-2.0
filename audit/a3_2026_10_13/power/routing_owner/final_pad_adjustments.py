from pathlib import Path
import json
from complete_owner_routes import ROOT,HERE,PCB,KEEP,k,save
BASE='R_Vishay_WSL2512_A3'
REFS=('R1','R40','R41','R55')

def main():
 b=k.LoadBoard(str(PCB));KEEP.append(b);fps={f.GetReference():f for f in b.GetFootprints()};library=PCB.parent/'Meshcore.pretty'
 (HERE/'before_maker_lands.kicad_pcb').write_bytes(PCB.read_bytes())
 # Vishay WSL2512 recommended lands, doc30100 page2: two1.65x3.68,
 # inner gap4.06, centre pitch5.71. These are manufacturer copper lands;
 # mask0.05 and the outer0.25 courtyard are explicit engineering margins.
 (library/(BASE+'.kicad_mod')).write_text(f'''(footprint "{BASE}" (version 20260206) (generator "pcbnew")
 (layer "F.Cu") (descr "Vishay WSL2512 manufacturer recommended lands, doc30100p2:1.65x3.68mm, gap4.06mm, pitch5.71mm. Courtyard outer7.36x3.68+0.25mm. Body and STEP are nominal envelopes.")
 (attr smd)
 (fp_text reference "REF**"(at 0 -2.6)(layer "F.Fab")hide(effects(font(size 0.8 0.8)(thickness 0.12))))
 (fp_text value "WSL2512"(at 0 2.6)(layer "F.Fab")hide(effects(font(size 0.8 0.8)(thickness 0.12))))
 (fp_rect(start -3.175 -1.59)(end 3.175 1.59)(stroke(width 0.1)(type default))(fill none)(layer "F.Fab"))
 (fp_rect(start -3.93 -2.09)(end 3.93 2.09)(stroke(width 0.05)(type default))(fill none)(layer "F.CrtYd"))
 (fp_line(start -1.65 -1.71)(end 1.65 -1.71)(stroke(width 0.12)(type default))(layer "F.SilkS"))
 (fp_line(start -1.65 1.71)(end 1.65 1.71)(stroke(width 0.12)(type default))(layer "F.SilkS"))
 (pad "1" smd rect(at -2.855 0)(size 1.65 3.68)(layers "F.Cu" "F.Paste" "F.Mask")(solder_mask_margin 0.05))
 (pad "2" smd rect(at 2.855 0)(size 1.65 3.68)(layers "F.Cu" "F.Paste" "F.Mask")(solder_mask_margin 0.05))
 (model "${{KICAD10_3DMODEL_DIR}}/Resistor_SMD.3dshapes/R_2512_6332Metric.step"
 (offset(xyz 0 0 0))(scale(xyz 1 1 1))(rotate(xyz 0 0 0))))\n''',encoding='utf8')
 changed=[]
 for ref in REFS:
  old=fps[ref];fp=k.FootprintLoad(str(library),BASE);KEEP.append(fp)
  fp.SetUuid(old.m_Uuid);fp.SetPath(old.GetPath());fp.SetReference(ref);fp.SetValue(old.GetValue());fp.SetPosition(old.GetPosition());fp.SetOrientation(old.GetOrientation())
  for field in old.GetFields():
   if field.GetName()not in('Reference','Value','Footprint'):fp.SetField(field.GetName(),field.GetText())
  for p in fp.Pads():p.SetNet(next(q for q in old.Pads()if q.GetNumber()==p.GetNumber()).GetNet())
  for field in fp.GetFields():field.SetVisible(False)
  name=BASE+'__A3_'+ref;fp.SetFPID(k.LIB_ID('Meshcore',name));b.Remove(old);KEEP.append(old);b.Add(fp)
  proto=k.Cast_to_FOOTPRINT(fp.Duplicate(False));KEEP.append(proto);proto.SetPosition(k.VECTOR2I(0,0));proto.SetOrientationDegrees(0);proto.SetReference('REF**');proto.SetValue(name)
  for p in proto.Pads():p.SetNetCode(0)
  k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(library),proto)
  changed.append({'ref':ref,'footprint':'Meshcore:'+name,'source_footprint':'Meshcore:'+BASE})
 for ref in('TP1','TP6','TP9'):
  f=fps[ref];p=f.GetPosition();f.SetPosition(k.VECTOR2I(p.x,k.FromMM(1.3)))
 r3=fps['R3'];r3.SetPosition(k.VECTOR2I(k.FromMM(19),k.FromMM(36.6)));r3.SetOrientationDegrees(180)
 save(b)
 modelpath=PCB.parent/'model.json';m=json.loads(modelpath.read_text(encoding='utf8'));mp={p['ref']:p for p in m['parts']}
 for row in changed:mp[row['ref']].update(footprint=row['footprint'],source_footprint_before_v2_graphic_variant=row['source_footprint'])
 for ref in('TP1','TP6','TP9'):mp[ref]['y']=1.3
 mp['R3'].update(x=19.,y=36.6,rotation=180,native_layer='F.Cu')
 modelpath.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
 (HERE/'manufacturer_land_changes.json').write_text(json.dumps({'WSL_lands_mm':[1.65,3.68],'gap_mm':4.06,'pitch_mm':5.71,'courtyard_outer_mm':[7.86,4.18],'changed':changed,'TP_row_y_mm':1.3,'R3_new_pose':[19.,36.6,180],'R56_R71_generic_lands_unchanged':True},indent=2),encoding='utf8')
 print(json.dumps({'WSL_footprints':4,'top_TP_row_y':1.3,'R3_pose':[19.,36.6,180]}))
if __name__=='__main__':main()
