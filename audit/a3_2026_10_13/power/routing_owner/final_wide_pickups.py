from complete_owner_routes import *
b=k.LoadBoard(str(PCB));KEEP.append(b)
def track(net,a,z,width):
 t=k.PCB_TRACK(b);t.SetStart(k.VECTOR2I(k.FromMM(a[0]),k.FromMM(a[1])));t.SetEnd(k.VECTOR2I(k.FromMM(z[0]),k.FromMM(z[1])));t.SetWidth(k.FromMM(width));t.SetLayer(k.F_Cu);t.SetNet(b.FindNet(net));b.Add(t);KEEP.append(t)
track('BAT_SYS',(21.845,29.0),(23.7375,29.0),.8)
track('RADIO_3V3',(70.5,11.0),(71.77,11.0),.8)
for t in b.GetTracks():
 if str(t.m_Uuid.AsString())=='01b99584-5be7-4f64-8c53-55b2e9c20de4':t.SetWidth(k.FromMM(.8))
save(b)
print('Added width0.8 pad pickups R1/J101.7; widened existing BAT_SYS bridge')
