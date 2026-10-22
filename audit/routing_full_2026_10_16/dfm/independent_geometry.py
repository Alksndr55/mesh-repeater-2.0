"""Read-only independent native PCB geometry audit, no pcbnew/SWIG."""
from pathlib import Path
import sys, json, math, hashlib, collections
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'.publication_tmp/fab_deps'))
import sexpdata
from shapely.geometry import Point, LineString, Polygon, box
from shapely.affinity import rotate, translate
from shapely import make_valid
from shapely.ops import unary_union

OUT=Path(__file__).resolve().parent
def tag(n): return str(n[0]) if isinstance(n,list) and n else ''
def arr(n,k): return [x for x in n if tag(x)==k]
def one(n,k): return next((x for x in n if tag(x)==k),None)
def val(n,k,default=None):
    a=one(n,k); return a[1] if a and len(a)>1 else default
def vec(n,k): return list(map(float,one(n,k)[1:3]))
def uid(n): return str(val(n,'uuid',''))
def net(n):
    a=one(n,'net'); return str(a[-1]) if a else ''
def prop(n,k): return next((x[2] for x in arr(n,'property') if x[1]==k),'')
def xy(n,p):
    a=one(n,'at'); x,y=map(float,a[1:3]); ang=math.radians(float(a[3]) if len(a)>3 else 0)
    return [x+math.cos(ang)*p[0]+math.sin(ang)*p[1],y-math.sin(ang)*p[0]+math.cos(ang)*p[1]]
def layers(n):
    a=one(n,'layers')
    ls=[str(x) for x in a[1:]] if a else [str(val(n,'layer',''))]
    return ['F.Cu','B.Cu'] if '*.Cu' in ls else [x for x in ls if x.endswith('.Cu')]
def polygon(n):
    pts=one(n,'pts'); return make_valid(Polygon([tuple(x[1:3]) for x in arr(pts,'xy')]))
def padshape(f,p):
    w,h=vec(p,'size'); shp=str(p[3]); a=one(p,'at'); pos=xy(f,[float(a[1]),float(a[2])]); ang=float(a[3]) if len(a)>3 else 0
    if shp=='circle': g=Point(0,0).buffer(w/2,quad_segs=24)
    elif shp=='oval':
        if w>=h: g=LineString([(-(w-h)/2,0),((w-h)/2,0)]).buffer(h/2,quad_segs=24)
        else: g=LineString([(0,-(h-w)/2),(0,(h-w)/2)]).buffer(w/2,quad_segs=24)
    elif shp=='roundrect':
        r=float(val(p,'roundrect_rratio',0))*min(w,h);g=box(-w/2+r,-h/2+r,w/2-r,h/2-r).buffer(r,quad_segs=12) if r else box(-w/2,-h/2,w/2,h/2)
    else: g=box(-w/2,-h/2,w/2,h/2)
    return translate(rotate(g,-ang,origin=(0,0)),*pos),pos

def audit(label, source_override=None):
    source=Path(source_override) if source_override else ROOT/f'design/MeshRepeater2_{label.title()}/MeshRepeater2_{label.title()}.kicad_pcb'
    raw=source.read_bytes(); tree=sexpdata.loads(raw.decode('utf-8'))
    tracks=[]; vias=[]; pads=[]; holes=[]; gd={l:[] for l in ('F.Cu','B.Cu')}; zone_stats=[]; zones=[]
    for t in arr(tree,'segment'):
        a,b=vec(t,'start'),vec(t,'end'); w=float(val(t,'width'));dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        d={'uuid':uid(t),'net':net(t),'a':a,'b':b,'width':w,'layer':str(val(t,'layer')),'length':length,'angle':math.degrees(math.atan2(dy,dx))%180}
        d['geom']=LineString([a,b]).buffer(w/2,quad_segs=12);tracks.append(d)
        if d['net']=='GND':gd[d['layer']].append(d['geom'])
    for v in arr(tree,'via'):
        a=vec(v,'at');w=float(val(v,'size'));drill=float(val(v,'drill')); d={'uuid':uid(v),'net':net(v),'xy':a,'size':w,'drill':drill,'layers':layers(v),'geom':Point(a).buffer(w/2,quad_segs=24)};vias.append(d)
        holes.append({'uuid':uid(v),'xy':a,'drill':drill,'kind':'via','annular':(w-drill)/2})
        if d['net']=='GND':
            for l in d['layers']: gd[l].append(d['geom'])
    footprints={}
    for f in arr(tree,'footprint'):
        ref=prop(f,'Reference');fp={'ref':ref,'value':prop(f,'Value'),'at':one(f,'at')[1:],'layer':str(val(f,'layer')),'pads':[],'uuid':uid(f),'library':str(f[1])}
        for p in arr(f,'pad'):
            ls=layers(p)
            if not ls:continue
            g,pos=padshape(f,p);size=vec(p,'size');dr=one(p,'drill');drill=float(dr[1]) if dr and isinstance(dr[1],(float,int)) else None
            d={'ref':ref,'pin':str(p[1]),'net':net(p),'xy':pos,'size':size,'kind':str(p[2]),'shape':str(p[3]),'layers':ls,'uuid':uid(p),'geom':g,'drill':drill};pads.append(d);fp['pads'].append({k:v for k,v in d.items() if k!='geom'})
            if drill:holes.append({'uuid':uid(p),'ref':ref,'pin':str(p[1]),'xy':pos,'drill':drill,'kind':str(p[2]),'annular':(min(size)-drill)/2 if str(p[2])=='thru_hole' else None})
            if d['net']=='GND':
                for l in ls:gd[l].append(g)
        footprints[ref]=fp
    for z in arr(tree,'zone'):
        if net(z)!='GND':continue
        for p in arr(z,'filled_polygon'):
            layer=str(val(p,'layer'));g=polygon(p);gd[layer].append(g);zones.append((layer,g))
            zone_stats.append({'name':val(z,'name'),'layer':layer,'area':g.area,'bounds':g.bounds,'valid':g.is_valid,'island':bool(one(p,'island'))})
    # Check routing shape and truly duplicate segment records.
    off=[t for t in tracks if min(abs(t['angle']%45),45-abs(t['angle']%45))>0.05 and t['length']>.001]
    groups=collections.defaultdict(list)
    for t in tracks:groups[(t['net'],t['layer'],t['width'],tuple(sorted((tuple(t['a']),tuple(t['b'])))))].append(t['uuid'])
    duplicate=[v for v in groups.values() if len(v)>1]
    # Endpoint geometry: attach to any same-net object, including full filled GND zones.
    dangles=[]
    for t in tracks:
        for which in ('a','b'):
            pt=Point(t[which]);touch=[]
            for u in tracks:
                if u['uuid']==t['uuid'] or u['net']!=t['net'] or u['layer']!=t['layer']:continue
                if pt.distance(u['geom'])<1e-5:touch.append(u['uuid'])
            for u in pads+vias:
                if u['net']==t['net'] and t['layer'] in u['layers'] and pt.distance(u['geom'])<1e-5:touch.append(u['uuid'])
            if t['net']=='GND' and any(l==t['layer'] and pt.distance(g)<1e-5 for l,g in zones):touch.append('GND_zone')
            if not touch:dangles.append({k:v for k,v in t.items() if k!='geom'}|{'endpoint':which})
    # Filled GND: combine plane, pads and segments on each face; join faces only at GND plated holes.
    comps={}
    for l,gs in gd.items():
        merged=unary_union(gs);comps[l]=list(merged.geoms) if hasattr(merged,'geoms') else ([merged] if not merged.is_empty else [])
    nodekeys=[(l,i) for l in comps for i in range(len(comps[l]))]; parent={n:n for n in nodekeys}
    def find(n):
        while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
        return n
    def union(a,b):parent[find(a)]=find(b)
    links=[]
    for h in pads+vias:
        if h['net']!='GND' or len(h['layers'])<2 or not h.get('drill'):continue
        hits=[(l,i) for l in h['layers'] for i,g in enumerate(comps[l]) if g.intersects(h['geom'])]
        for n in hits[1:]:union(hits[0],n)
        links.append({'uuid':h['uuid'],'xy':h['xy'],'component_hits':hits})
    groups=collections.defaultdict(list)
    for n in nodekeys:groups[str(find(n))].append({'layer':n[0],'index':n[1],'area':comps[n[0]][n[1]].area,'bounds':comps[n[0]][n[1]].bounds})
    # Exact centerline-to-outline distance for tracks and circular vias, boards have rectangular outer boundary.
    edge=[]
    for t in tracks:edge.append({'uuid':t['uuid'],'clearance':min(*t['a'],90-t['a'][0],60-t['a'][1],*t['b'],90-t['b'][0],60-t['b'][1])-t['width']/2})
    for v in vias:edge.append({'uuid':v['uuid'],'clearance':min(*v['xy'],90-v['xy'][0],60-v['xy'][1])-v['size']/2})
    holes_gap=[]
    for i,h in enumerate(holes):
        for j in range(i+1,len(holes)):
            q=holes[j];dist=math.dist(h['xy'],q['xy'])-(h['drill']+q['drill'])/2
            if dist<.5:holes_gap.append({'a':h,'b':q,'edge_gap':dist})
    vg=[v for v in vias if v['net']=='GND']; spacing=[]
    for v in vg:
        ns=sorted((math.dist(v['xy'],u['xy']),u['uuid']) for u in vg if u['uuid']!=v['uuid'])
        if ns:spacing.append({'uuid':v['uuid'],'xy':v['xy'],'nearest_distance':ns[0][0],'nearest_uuid':ns[0][1]})
    clean=lambda d:{k:v for k,v in d.items() if k!='geom'}
    result={'source':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(raw).hexdigest(),'track_count':len(tracks),'via_count':len(vias),'pad_count':len(pads),'hole_count':len(holes),'width_hist':dict(collections.Counter(str(t['width']) for t in tracks)),'off_45_90_tracks':[clean(t) for t in off],'zero_tracks':[clean(t) for t in tracks if t['length']<.001],'duplicate_segments':duplicate,'dangling_endpoints':dangles,'gnd_zone_polygons':zone_stats,'gnd_layer_component_counts':{l:len(c) for l,c in comps.items()},'gnd_combined_connected_components':list(groups.values()),'gnd_vias':len(vg),'gnd_closest_pairs':sorted(spacing,key=lambda x:x['nearest_distance'])[:40],'gnd_via_coords':[clean(v) for v in vg],'min_track_via_outer_edge':min(edge,key=lambda x:x['clearance']) if edge else None,'minimum_hole_edge_gap':min(holes_gap,key=lambda x:x['edge_gap']) if holes_gap else None,'minimum_pad_annular':min((h for h in holes if h['kind']=='thru_hole'),key=lambda x:x['annular']) if any(h['kind']=='thru_hole' for h in holes) else None,'footprints':footprints}
    (OUT/f'{label}_geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(label,json.dumps({k:result[k] for k in ('sha256','track_count','via_count','pad_count','hole_count','gnd_layer_component_counts')},ensure_ascii=False), 'off-angle',len(off),'duplicates',len(duplicate),'dangles',len(dangles),'gndnets',len(groups))
    return result
if __name__=='__main__':
    for b in sys.argv[1:] or ['POWER','LOGIC','SHIELD']:audit(b)
