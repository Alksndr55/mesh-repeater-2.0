from complete_owner_routes import *
b=k.LoadBoard(str(PCB));KEEP.append(b);old=k.LoadBoard(str(HERE/'before_maker_lands.kicad_pcb'));KEEP.append(old)
def remove(t):b.Remove(t);KEEP.append(t)
def vec(a):return k.VECTOR2I(k.FromMM(a[0]),k.FromMM(a[1]))
def track(net,a,z,width,layer):
 t=k.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(b.FindNet(net));b.Add(t);KEEP.append(t);return t
for t in list(b.GetTracks()):
 if t.GetNetname()=='Net-(U1-COM2)':remove(t)
def adjust(p):return {(20.6,31.0):(20.5,30.9),(20.6,29.4):(20.5,29.3)}.get(p,p)
for t in old.GetTracks():
 if t.GetNetname()!='Net-(U1-COM2)':continue
 if isinstance(t,k.PCB_VIA):
  n=k.PCB_VIA(b);n.SetPosition(vec(adjust(xy(t.GetPosition()))));n.SetWidth(t.GetWidth(k.F_Cu));n.SetDrill(t.GetDrillValue());n.SetViaType(k.VIATYPE_THROUGH);n.SetLayerPair(k.F_Cu,k.B_Cu);n.SetNet(b.FindNet(t.GetNetname()));b.Add(n);KEEP.append(n)
 else:n=track(t.GetNetname(),adjust(xy(t.GetStart())),adjust(xy(t.GetEnd())),t.GetWidth()/1e6,t.GetLayer())
 n.SetUuid(t.m_Uuid)
ids=('99af731c-1c1d-46ca-a70d-331fa61c2eed','473ab7ef-d715-45db-9904-386bf3d09934')
for t in list(b.GetTracks()):
 if str(t.m_Uuid.AsString()) in ids:remove(t)
 elif t.GetNetname()=='CS_P' and isinstance(t,k.PCB_VIA) and xy(t.GetPosition())==(26.,30.4):t.SetPosition(vec((26.,30.6)))
 elif t.GetNetname()=='CS_P' and not isinstance(t,k.PCB_VIA):
  if t.GetLayer()==k.B_Cu and xy(t.GetStart())==(27.2,30.4) and xy(t.GetEnd())==(27.6,30.8):remove(t)
  elif t.GetLayer()==k.F_Cu and xy(t.GetStart())==(26.,30.4):
   t.SetStart(vec((26.,30.6)));t.SetEnd(vec((24.6,32.0)))
  elif t.GetLayer()==k.F_Cu and xy(t.GetStart())==(24.6,31.8):t.SetStart(vec((24.6,32.0)))
  elif str(t.m_Uuid.AsString())=='9e5c1ccc-0b08-472c-9bf8-ada09d8742ef':t.SetEnd(vec((27.7,30.8)))
for a,z in[((26,30.6),(27.4,30.6)),((27.4,30.6),(27.6,30.8)),((27.6,30.8),(29,30.8))]:track('CS_P',a,z,.8,k.B_Cu)
save(b)
print('Saved exact COM2 reconnection and CS_P clean corridor')
