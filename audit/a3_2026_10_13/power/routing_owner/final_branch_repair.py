from complete_owner_routes import *
b=k.LoadBoard(str(PCB));KEEP.append(b)
fps={f.GetReference():f for f in b.GetFootprints()}
fps['R1'].SetPosition(k.VECTOR2I(k.FromMM(24.7),k.FromMM(29.0)))
def remove(t):b.Remove(t);KEEP.append(t)
def track(net,a,z,width,layer):
 t=k.PCB_TRACK(b);t.SetStart(k.VECTOR2I(k.FromMM(a[0]),k.FromMM(a[1])));t.SetEnd(k.VECTOR2I(k.FromMM(z[0]),k.FromMM(z[1])));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(b.FindNet(net));b.Add(t);KEEP.append(t)
cs=b.FindNet('CS_P')
ids=('6201bbca-d971-44c8-9a39-3fd4240eb0d3','c0d366c4-9fc8-4fb6-bb43-75db31e979ec','0c2000ce-c858-435e-b189-6ca7b8a8b3da','e62091a4-d9d0-4f84-b313-0a610d7bd0ae','2d483a5f-cdb1-4860-9395-be463ac245cd')
for t in list(b.GetTracks()):
 if str(t.m_Uuid.AsString()) in ids:remove(t)
 elif str(t.m_Uuid.AsString())=='dd9719bc-7bc0-4399-9fe2-d775cec9766d':t.SetPosition(k.VECTOR2I(k.FromMM(26),k.FromMM(30.4)))
compvias=[]
for t in list(b.GetTracks()):
 if t.GetNetname()=='Net-(U1-COM2)' and isinstance(t,k.PCB_VIA) and xy(t.GetPosition())==(20.6,31.0):compvias.append(t)
for v in compvias:
 old=xy(v.GetPosition());v.SetPosition(k.VECTOR2I(k.FromMM(20.525),k.FromMM(31.3)))
 for t in list(b.GetTracks()):
  if isinstance(t,k.PCB_VIA) or t.GetNetname()!=v.GetNetname():continue
  a,z=xy(t.GetStart()),xy(t.GetEnd())
  if old not in(a,z):continue
  other=z if a==old else a;layer=t.GetLayer();width=t.GetWidth()/1e6;remove(t)
  if layer==k.F_Cu:
   # Explicit compensation pin neck preserves right angle/45-degree routing.
   for q in list(b.GetTracks()):
    if not isinstance(q,k.PCB_VIA) and q.GetNetname()==v.GetNetname() and q.GetLayer()==k.F_Cu:remove(q)
   track(v.GetNetname(),(19.7625,30.775),(20.0,30.775),.15,k.F_Cu)
   track(v.GetNetname(),(20.0,30.775),(20.525,31.3),.15,k.F_Cu)
  else:
   dy=other[1]-31.3;dx=other[0]-20.525;sx=1 if dx>0 else-1;sy=1 if dy>0 else-1
   d=min(abs(dx),abs(dy));corner=(20.525+sx*d,31.3+sy*d)
   track(v.GetNetname(),(20.525,31.3),corner,width,layer)
   if corner!=other:track(v.GetNetname(),corner,other,width,layer)
for a,z in[((26,30.4),(24.6,31.8)),((24.6,31.8),(24.6,33.1)),((24.6,33.1),(23.3,33.1))]:track('CS_P',a,z,.8,k.F_Cu)
for a,z in[((26,30.4),(27.2,30.4)),((27.2,30.4),(27.6,30.8)),((27.6,30.8),(29,30.8))]:track('CS_P',a,z,.8,k.B_Cu)
save(b)
mfile=PCB.parent/'model.json';m=json.loads(mfile.read_text(encoding='utf8'));next(p for p in m['parts']if p['ref']=='R1').update(x=24.7,y=29.0,rotation=180);mfile.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
(HERE/'final_R1_clearance_pose.json').write_text(json.dumps({'R1':[24.7,29.0,180],'R56':[24.7,33.15,0],'CS_P_via':[26.,30.4],'COM2_via':[20.525,31.3]}),encoding='utf8')
print('Saved local branch repair; compensation vias moved',len(compvias))
