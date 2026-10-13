from verify_handoff_paths import *
for ref in('C53','R1','J101'):
 for p in fps[ref].Pads():print('PAD',ref,p.GetNumber(),p.GetNetname(),xy(p.GetPosition()),xy(p.GetSize()))
for net in('RADIO_3V3','BAT_SYS'):
 print('NET',net)
 for t in b.GetTracks():
  if t.GetNetname()==net:
   if isinstance(t,k.PCB_VIA):print(' VIA',xy(t.GetPosition()),t.GetWidth(k.F_Cu)/1e6)
   else:print(' TR',t.GetLayerName(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth()/1e6)
 for z in b.Zones():
  if z.GetNetname()==net:print('ZONE',z.GetNetname(),z.GetLayerName())
print('unfiltered C53R1',path('BAT_SYS',('C53','1'),('R1','2'),0))
