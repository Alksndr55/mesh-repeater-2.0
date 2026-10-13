from verify_handoff_paths import *
r=path('BAT_SYS',('C53','1'),('R1','2'),0);ids=set(r.get('track_or_via_uuids',[]))
for t in b.GetTracks():
 if str(t.m_Uuid.AsString())in ids and not isinstance(t,k.PCB_VIA)and t.GetWidth()<k.FromMM(.8):print(str(t.m_Uuid.AsString()),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth()/1e6)
