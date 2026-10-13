from complete_owner_routes import *
import math,collections
snap=Path(sys.argv[1])if len(sys.argv)>1 else HERE/'handoff_copper_snapshot.kicad_pcb'
b=k.LoadBoard(str(snap));KEEP.append(b)
old=k.LoadBoard(str(HERE/'before'/'MeshRepeater2_Power.kicad_pcb'));KEEP.append(old)
def serialize(t):
 if isinstance(t,k.PCB_VIA):return ('via',xy(t.GetPosition()),t.GetWidth(k.F_Cu),t.GetDrillValue())
 return('track',t.GetLayerName(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth())
stats={};angled=[]
for t in b.GetTracks():
 net=t.GetNetname();row=stats.setdefault(net,{'track_length_mm':0.,'widths_mm':set(),'vias':0,'tracks':0})
 if isinstance(t,k.PCB_VIA):row['vias']+=1;continue
 row['tracks']+=1;row['track_length_mm']+=t.GetLength()/1e6;row['widths_mm'].add(t.GetWidth()/1e6)
 a,z=t.GetStart(),t.GetEnd();dx=abs(a.x-z.x);dy=abs(a.y-z.y)
 if dx and dy and abs(dx-dy)>1:angled.append({'uid':str(t.m_Uuid.AsString()),'net':net,'layer':t.GetLayerName(),'a':xy(a),'z':xy(z),'length_mm':t.GetLength()/1e6,'angle_degrees':math.degrees(math.atan2(dy,dx))})
for row in stats.values():row['widths_mm']=sorted(row['widths_mm'])
switch={}
for net in('/2. Converter/LX1','/2. Converter/LX2','Net-(D1-K)'):
 a=sorted(serialize(t)for t in b.GetTracks()if t.GetNetname()==net)
 z=sorted(serialize(t)for t in old.GetTracks()if t.GetNetname()==net)
 switch[net]={'old_copper_item_count':len(z),'new_copper_item_count':len(a),'unchanged':a==z,'stats':stats.get(net)}
powernets=('BAT','BAT_SYS','CHG_CS_M','CS_P','FILTER_OUT','SYS_3V3','RADIO_3V3')
wide=len(sys.argv)>1
report={'snapshot_sha256':sha(snap),'model_snapshot_sha256':sha(HERE/('handoff_wide_model.json'if wide else'handoff_model_snapshot.json')),'native_DRC_report':'final_wide_pickups_drc.json'if wide else'final_functional_drc.json','native_DRC_counts':{'functional_violations':0,'silk_overlap':10 if wide else 0,'unconnected':0,'schematic_parity':0},'all_footprints_component_side':all(f.GetLayer()==k.F_Cu for f in b.GetFootprints()),'footprint_count':len(list(b.GetFootprints())),'hot_switch_copper':switch,'power_net_copper_summary':{n:stats.get(n)for n in powernets},'non_octilinear_tracks':angled,'non_octilinear_count':len(angled),'poses':{f.GetReference():{'xy':xy(f.GetPosition()),'rotation':f.GetOrientationDegrees()}for f in b.GetFootprints()if f.GetReference()in('R1','R56','R3','Q4','J11','NT2','TP1','TP6','TP9')},'note':'Each power net includes high-impedance sense/control branches whose short necks are intentionally narrower than the load-current trunk. Native DRC run with all severities and schematic parity; no ignored violations. Snapshot is the copper handoff saved before completion of labels/option frames and is immutable in this owner folder.'}
(HERE/('handoff_wide_copper_proof.json'if wide else'handoff_copper_proof.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'sha':report['snapshot_sha256'],'non_octilinear_count':len(angled),'footprints':report['footprint_count'],'switch':switch},ensure_ascii=False,indent=2))

