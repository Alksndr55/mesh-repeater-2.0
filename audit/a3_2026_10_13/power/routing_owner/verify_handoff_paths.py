from complete_owner_routes import *
import math,heapq,collections
SNAP=Path(sys.argv[1])if len(sys.argv)>1 else HERE/'handoff_copper_snapshot.kicad_pcb'
b=k.LoadBoard(str(SNAP));KEEP.append(b)
fps={f.GetReference():f for f in b.GetFootprints()}
def ip(p):return(p.x,p.y)
def graph(net,minwidth=0):
 tracks=[t for t in b.GetTracks()if t.GetNetname()==net and not isinstance(t,k.PCB_VIA)and t.GetWidth()>=k.FromMM(minwidth)]
 vias=[t for t in b.GetTracks()if t.GetNetname()==net and isinstance(t,k.PCB_VIA)]
 pads=[p for f in b.GetFootprints()for p in f.Pads()if p.GetNetname()==net]
 pts={k.F_Cu:set(),k.B_Cu:set()};adj=collections.defaultdict(list);bridges=[]
 for t in tracks:pts[t.GetLayer()].update((ip(t.GetStart()),ip(t.GetEnd())))
 for v in vias:
  for l in pts:pts[l].add(ip(v.GetPosition()))
 # Native copper often joins by overlapping track widths, rather than by
 # exactly coincident centrelines. Subdivide the touched segment as well.
 for s in tracks:
  for endpoint in(ip(s.GetStart()),ip(s.GetEnd())):
   for t in tracks:
    if s is t or s.GetLayer()!=t.GetLayer():continue
    a,z=ip(t.GetStart()),ip(t.GetEnd());dx=z[0]-a[0];dy=z[1]-a[1];ll=dx*dx+dy*dy
    u=max(0.,min(1.,((endpoint[0]-a[0])*dx+(endpoint[1]-a[1])*dy)/ll))
    q=(round(a[0]+u*dx),round(a[1]+u*dy))
    if math.dist(endpoint,q)<=(s.GetWidth()+t.GetWidth())/2:
     pts[t.GetLayer()].add(q);bridges.append(((s.GetLayer(),endpoint),(t.GetLayer(),q),math.dist(endpoint,q)/1e6))
 for v in vias:
  endpoint=ip(v.GetPosition())
  for t in tracks:
   a,z=ip(t.GetStart()),ip(t.GetEnd());dx=z[0]-a[0];dy=z[1]-a[1];ll=dx*dx+dy*dy
   u=max(0.,min(1.,((endpoint[0]-a[0])*dx+(endpoint[1]-a[1])*dy)/ll));q=(round(a[0]+u*dx),round(a[1]+u*dy))
   if math.dist(endpoint,q)<=(v.GetWidth(k.F_Cu)+t.GetWidth())/2:
    pts[t.GetLayer()].add(q);bridges.append(((t.GetLayer(),endpoint),(t.GetLayer(),q),math.dist(endpoint,q)/1e6))
 for p in pads:
  center=ip(p.GetPosition())
  for l in pts:
   if p.IsOnLayer(l):pts[l].add(center)
  for t in tracks:
   if not p.IsOnLayer(t.GetLayer()):continue
   a,z=ip(t.GetStart()),ip(t.GetEnd());dx=z[0]-a[0];dy=z[1]-a[1];ll=dx*dx+dy*dy
   u=max(0.,min(1.,((center[0]-a[0])*dx+(center[1]-a[1])*dy)/ll))
   q=(round(a[0]+u*dx),round(a[1]+u*dy))
   if p.HitTest(k.VECTOR2I(*q)):pts[t.GetLayer()].add(q)
 def edge(a,z,length,t=None):
  adj[a].append((z,length,t));adj[z].append((a,length,t))
 for a,z,length in bridges:edge(a,z,length)
 for t in tracks:
  a,z=ip(t.GetStart()),ip(t.GetEnd());dx=z[0]-a[0];dy=z[1]-a[1];ll=dx*dx+dy*dy
  valid=[]
  for p in pts[t.GetLayer()]:
   px=p[0]-a[0];py=p[1]-a[1];dot=px*dx+py*dy
   if 0<=dot<=ll and abs(px*dy-py*dx)<2*max(abs(dx),abs(dy)):valid.append((dot,p))
  valid.sort()
  for (_,p),(_,q)in zip(valid,valid[1:]):edge((t.GetLayer(),p),(t.GetLayer(),q),math.dist(p,q)/1e6,t)
 for v in vias:edge((k.F_Cu,ip(v.GetPosition())),(k.B_Cu,ip(v.GetPosition())),0,v)
 for p in pads:
  pn=('PAD',p.GetParentFootprint().GetReference(),p.GetNumber());adj[pn]
  for l in pts:
   if not p.IsOnLayer(l):continue
   for q in pts[l]:
    if p.HitTest(k.VECTOR2I(*q)):edge(pn,(l,q),math.dist(ip(p.GetPosition()),q)/1e6,None)
 return adj
def path(net,a,z,minwidth=0):
 g=graph(net,minwidth);start=('PAD',a[0],a[1]);target=('PAD',z[0],z[1]);dist={start:0};prev={};heap=[(0,0,start)];seq=0
 while heap:
  d,_,n=heapq.heappop(heap)
  if d!=dist[n]:continue
  if n==target:break
  for q,w,t in g[n]:
   nd=d+w
   if nd<dist.get(q,1e99):dist[q]=nd;prev[q]=(n,t);seq+=1;heapq.heappush(heap,(nd,seq,q))
 if target not in dist:return{'found':False,'net':net,'from':a,'to':z,'min_width_constraint_mm':minwidth}
 items=[];nodes=[];n=target
 while n!=start:
  nodes.append(n);n,t=prev[n]
  if t is not None and t not in items:items.append(t)
 return{'found':True,'net':net,'from':a,'to':z,'min_width_constraint_mm':minwidth,'geometric_length_including_pad_pickups_mm':dist[target],'tracks':sum(not isinstance(t,k.PCB_VIA)for t in items),'vias':sum(isinstance(t,k.PCB_VIA)for t in items),'actual_track_widths_mm':sorted(set(t.GetWidth()/1e6 for t in items if not isinstance(t,k.PCB_VIA))),'track_or_via_uuids':[str(t.m_Uuid.AsString())for t in items],'pad_pickup_node':nodes[-1]if nodes else None}
specs=[('BAT',('J8','1'),('R71','2'),.8),('BAT_SYS',('R71','1'),('C53','1'),.8),('BAT_SYS',('C53','1'),('R1','2'),.8),('CS_P',('L1','2'),('R56','1'),.8),('CHG_CS_M',('R56','2'),('R1','1'),.8),('FILTER_OUT',('L4','2'),('J11','1'),.8),('SYS_3V3',('J11','2'),('NT2','1'),.8),('SYS_3V3',('NT2','1'),('J101','1'),.8),('SYS_3V3',('NT2','1'),('J101','3'),.8),('RADIO_3V3',('NT2','2'),('J101','5'),.8),('RADIO_3V3',('NT2','2'),('J101','7'),.8)]
rows=[path(*s)for s in specs]
kelvin=[path('BAT',('R71','2'),('R73','1'),0),path('BAT_SYS',('R71','1'),('R72','1'),0)]
report={'snapshot_sha256':sha(SNAP),'bulk_routes':rows,'Kelvin_sense_paths':kelvin,'method':'Track centreline graph subdivided at same-layer endpoints and joins through overlapping copper widths. Copper endpoints inside a pad connect through that pad. DRC supplies the authoritative physical connectivity proof. Path numbers include centre-to-endpoint distance within pads; paths are engineering witnesses, not exact DC resistance extraction. Width-filtered bulk witnesses do not include unrelated thin sense branches.'}
(HERE/('handoff_wide_path_proof.json'if len(sys.argv)>1 else'handoff_path_proof.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'bulk_routes':[{k:v for k,v in r.items()if k not in('track_or_via_uuids','pad_pickup_node')}for r in rows],'Kelvin':kelvin},ensure_ascii=False,indent=2))
