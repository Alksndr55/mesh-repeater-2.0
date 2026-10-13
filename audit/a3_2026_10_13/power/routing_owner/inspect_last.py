from complete_owner_routes import *
b=k.LoadBoard(str(PCB));KEEP.append(b)
for f in b.GetFootprints():
 if f.GetReference() in ('R1','R56','D2','C1','U1','L1'):
  print('FP',f.GetReference(),xy(f.GetPosition()),f.GetOrientationDegrees())
  for p in f.Pads():print(' PAD',p.GetNumber(),p.GetNetname(),xy(p.GetPosition()),xy(p.GetSize()))
  for g in f.GraphicalItems():
   if g.GetLayer()==k.F_CrtYd:print(' CRT',xy(g.GetStart()),xy(g.GetEnd()))
for t in b.GetTracks():
 p=xy(t.GetPosition())
 if isinstance(t,k.PCB_VIA):
  if 22<p[0]<29 and 27<p[1]<34:print('VIA',t.GetNetname(),str(t.m_Uuid.AsString()),p,t.GetWidth(k.F_Cu)/1e6,t.GetDrillValue()/1e6)
 else:
  if t.GetNetname() in ('BAT_SYS','CS_P','CHG_CS_M') and (22<p[0]<30 and 27<p[1]<34):print('TRACK',str(t.m_Uuid.AsString()),t.GetNetname(),t.GetLayerName(),xy(t.GetStart()),xy(t.GetEnd()),t.GetWidth()/1e6)
