from verify_handoff_paths import *
specs=[]
for ref in('U2','R55','L3','L4','R40','R41'):
 print('FP',ref,[(p.GetNumber(),p.GetNetname(),xy(p.GetPosition()))for p in fps[ref].Pads()])
for a,z in[(('R55','2'),('L3','1')),(('L3','2'),('L4','1')),(('L4','2'),('J11','1'))]:
 p=pad(b,*a);q=pad(b,*z);specs.append((p.GetNetname(),a,z,.8));assert p.GetNetname()==q.GetNetname(),(a,z)
rows=[path(*s)for s in specs]
icpaths=[path('/2. Converter/SYS_PRE',('U2','6'),('R55','1'),0),path('BAT_SYS',('C53','1'),('U2','10'),0)]
necks=[]
for row in icpaths:
 ids=set(row.get('track_or_via_uuids',[]));thin=[]
 for t in b.GetTracks():
  if str(t.m_Uuid.AsString())not in ids or isinstance(t,k.PCB_VIA)or t.GetWidth()>=k.FromMM(.8):continue
  length=t.GetLength()/1e6;width=t.GetWidth()/1e6
  thin.append({'width_mm':width,'length_mm':length,'a':xy(t.GetStart()),'z':xy(t.GetEnd()),'resistance_milliohm_35umCu_20C':.01724*length/(width*.035),'uuid':str(t.m_Uuid.AsString())})
 necks.append({'from':row['from'],'to':row['to'],'found':row['found'],'narrow_pieces':thin})
(HERE/'handoff_wide_filter_proof.json').write_text(json.dumps({'snapshot_sha256':sha(SNAP),'filter_bulk_witnesses':rows,'IC_pin_escapes':necks,'resistance_assumptions':'Geometrical straight copper-only resistance, resistivity0.01724 ohm*mm2/m at20C and nominal35umCu. Values in milliohms, numerically equal to mV/A. Excludes pads/vias/heating/etch tolerances; not an IPC current-rating claim.'},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'filter':rows,'IC_necks':necks},ensure_ascii=False,indent=2))
