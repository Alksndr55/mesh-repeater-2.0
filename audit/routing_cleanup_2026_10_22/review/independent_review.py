"""Read-only current routing review. Never edits native CAD; no pcbnew/SWIG."""
from pathlib import Path
import sys, json, math, hashlib, collections, importlib.util, argparse
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'.publication_tmp/fab_deps'))
import sexpdata as sx
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('independent_geometry', ROOT/'audit/routing_full_2026_10_16/dfm/independent_geometry.py')
geo=importlib.util.module_from_spec(spec);spec.loader.exec_module(geo)

def inspect(label,path,out):
    path=path.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=True);geo.OUT=out
    facts=geo.audit(label,path)
    tree=sx.loads(path.read_text('utf-8'));tracks=[];zones=collections.defaultdict(list);vias=[];pads=[]
    for s in geo.arr(tree,'segment'):
        a,b=geo.vec(s,'start'),geo.vec(s,'end');w=float(geo.val(s,'width'))
        tracks.append(dict(uuid=geo.uid(s),net=geo.net(s),layer=geo.val(s,'layer'),a=a,b=b,width=w,length=math.dist(a,b),geom=LineString([a,b])))
    for v in geo.arr(tree,'via'):
        vias.append(dict(uuid=geo.uid(v),net=geo.net(v),xy=geo.vec(v,'at'),size=float(geo.val(v,'size'))))
    for f in geo.arr(tree,'footprint'):
        for p in geo.arr(f,'pad'):
            if not geo.layers(p):continue
            g,xy=geo.padshape(f,p);pads.append(dict(net=geo.net(p),layers=geo.layers(p),geom=g))
    for z in geo.arr(tree,'zone'):
        if geo.net(z)!='GND':continue
        for p in geo.arr(z,'filled_polygon'):zones[str(geo.val(p,'layer'))].append(geo.polygon(p))
    zoneunion={l:unary_union(p) for l,p in zones.items()}
    overlap=[]
    for i,a in enumerate(tracks):
        for b in tracks[i+1:]:
            if (a['net'],a['layer'])!=(b['net'],b['layer']):continue
            # Collinear within 10 nm covers KiCad integer rounding of 45-degree
            # vertices; a simple point junction has zero projected overlap.
            common=a['geom'].intersection(b['geom']).length
            if common<=.001 and a['length']>1e-9 and b['length']>1e-9:
                ux=(a['b'][0]-a['a'][0])/a['length'];uy=(a['b'][1]-a['a'][1])/a['length']
                dist=[abs((p[0]-a['a'][0])*uy-(p[1]-a['a'][1])*ux) for p in [b['a'],b['b']]]
                if max(dist)<.00001:
                    pos=sorted((p[0]-a['a'][0])*ux+(p[1]-a['a'][1])*uy for p in [b['a'],b['b']])
                    common=max(0,min(a['length'],pos[1])-max(0,pos[0]))
            if common>0.001:
                overlap.append(dict(net=a['net'],layer=a['layer'],uuids=[a['uuid'],b['uuid']],widths=[a['width'],b['width']],overlap_mm=common,segments=[{k:v for k,v in t.items() if k!='geom'} for t in (a,b)]))
    gnd_covered=[]
    for t in tracks:
        if t['net']!='GND' or t['layer'] not in zoneunion:continue
        full=t['geom'].buffer(t['width']/2,quad_segs=12)
        if full.difference(zoneunion[t['layer']].buffer(.00002)).area>.0001:continue
        ends=[]
        for p in (t['a'],t['b']):
            ends.append([v['uuid'] for v in vias if v['net']=='GND' and math.dist(v['xy'],p)<.0001])
        gnd_covered.append({k:v for k,v in t.items() if k!='geom'}|dict(endpoint_vias=ends,via_to_via=bool(ends[0] and ends[1])))
    pernet=collections.defaultdict(lambda:dict(count=0,length_mm=0.0,min_width_mm=999,max_width_mm=0))
    for t in tracks:
        pernet[t['net']]['count']+=1;pernet[t['net']]['length_mm']+=t['length']
        pernet[t['net']]['min_width_mm']=min(pernet[t['net']]['min_width_mm'],t['width'])
        pernet[t['net']]['max_width_mm']=max(pernet[t['net']]['max_width_mm'],t['width'])
    angles=[];nodes=collections.defaultdict(list)
    for t in tracks:
        for end in ['a','b']:nodes[(t['net'],t['layer'],tuple(t[end]))].append((t,end))
    for key,pair in nodes.items():
        if len(pair)!=2:continue
        # A pad/via is a terminal or branch, not an avoidable route bend.
        pt=Point(key[2])
        if any(p['net']==key[0] and key[1] in p['layers'] and p['geom'].distance(pt)<1e-5 for p in pads):continue
        if any(v['net']==key[0] and math.dist(v['xy'],key[2])<=v['size']/2+1e-5 for v in vias):continue
        t,end=pair[0];u,other=pair[1];p=key[2];q=t['b' if end=='a' else 'a'];r=u['b' if other=='a' else 'a']
        v=(q[0]-p[0],q[1]-p[1]);w=(r[0]-p[0],r[1]-p[1]);ll=math.hypot(*v)*math.hypot(*w)
        if ll<1e-10:continue
        internal=math.degrees(math.acos(max(-1,min(1,(v[0]*w[0]+v[1]*w[1])/ll))))
        # Route deflection: straight=0, a right turn=90; rounded for nanometre artifacts.
        angle=round(180-internal,2)
        if angle>.05:angles.append(dict(net=key[0],layer=key[1],xy=p,deflection_deg=angle,uuids=[t['uuid'],u['uuid']]))
    result=dict(board=label,source=str(path),sha256=facts['sha256'],segments=len(tracks),length_mm=sum(t['length'] for t in tracks),non_gnd_length_mm=sum(t['length'] for t in tracks if t['net']!='GND'),gnd_length_mm=sum(t['length'] for t in tracks if t['net']=='GND'),min_width_mm=min((t['width'] for t in tracks),default=None),vias=len(vias),per_net=dict(pernet),degree_two_bends=angles,bend_histogram=dict(collections.Counter(str(a['deflection_deg']) for a in angles)),non_gnd_bend_histogram=dict(collections.Counter(str(a['deflection_deg']) for a in angles if a['net']!='GND')),collinear_overlap_pairs=overlap,gnd_tracks_fully_covered_by_fill=gnd_covered,ground_connected_components=facts['gnd_combined_connected_components'],off_angle=facts['off_45_90_tracks'],exact_duplicates=facts['duplicate_segments'],dangling_endpoints=facts['dangling_endpoints'])
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:result[k] for k in ['board','sha256','segments','length_mm','min_width_mm','vias']}))
    print('Overlap pairs:',len(overlap),'GND fully pour-covered:',len(gnd_covered),'Via-via:',sum(x['via_to_via'] for x in gnd_covered))
    return tree,result

def norm(n):return sx.dumps(n)
def compare(label,before,after,out):
    a,ra=inspect(label,before,out/'before');b,rb=inspect(label,after,out/'after')
    # Only routing/filled-copper and revision metadata may change. All footprints,
    # component pads/net assignments, board setup, outline and zone definitions fixed.
    def invariant(tree):
        data=[]
        for n in tree[1:]:
            tag=geo.tag(n)
            if tag in ['segment','arc','via','title_block','generator_version']:continue
            if tag=='zone':n=[c for c in n if geo.tag(c) not in ['filled_polygon','fill_segments']]
            data.append(norm(n))
        return sorted(data)
    originalvias={geo.uid(n):norm(n) for n in geo.arr(a,'via')}
    newvias={geo.uid(n):norm(n) for n in geo.arr(b,'via')}
    footprints_a={geo.prop(n,'Reference'):norm(n) for n in geo.arr(a,'footprint')}
    footprints_b={geo.prop(n,'Reference'):norm(n) for n in geo.arr(b,'footprint')}
    result=dict(board=label,before_sha256=ra['sha256'],after_sha256=rb['sha256'],all_nonrouting_invariants_preserved=invariant(a)==invariant(b),all_footprints_and_pad_nets_preserved=footprints_a==footprints_b,via_changes=dict(removed=[u for u in originalvias if u not in newvias],added=[u for u in newvias if u not in originalvias],modified=[u for u in originalvias if u in newvias and originalvias[u]!=newvias[u]]),removed_segments=ra['segments']-rb['segments'],reduced_track_length_mm=ra['length_mm']-rb['length_mm'],reduced_non_gnd_length_mm=ra['non_gnd_length_mm']-rb['non_gnd_length_mm'],removed_gnd_track_length_mm=ra['gnd_length_mm']-rb['gnd_length_mm'],non_gnd_length_before_mm=ra['non_gnd_length_mm'],non_gnd_length_after_mm=rb['non_gnd_length_mm'],min_width_before=ra['min_width_mm'],min_width_after=rb['min_width_mm'],bend_histogram_before=ra['bend_histogram'],bend_histogram_after=rb['bend_histogram'],non_gnd_bend_histogram_before=ra['non_gnd_bend_histogram'],non_gnd_bend_histogram_after=rb['non_gnd_bend_histogram'],nets_with_minimum_width_reduction=[net for net in ra['per_net'] if net in rb['per_net'] and rb['per_net'][net]['min_width_mm']<ra['per_net'][net]['min_width_mm']-1e-6],remaining_collinear_overlap_pairs=len(rb['collinear_overlap_pairs']),remaining_exact_duplicates=len(rb['exact_duplicates']),remaining_off_angle=len(rb['off_angle']),remaining_dangling=len(rb['dangling_endpoints']),ground_components_before=len(ra['ground_connected_components']),ground_components_after=len(rb['ground_connected_components']))
    (out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--before');p.add_argument('--after');p.add_argument('--out');args=p.parse_args()
    label=args.label.upper();before=Path(args.before) if args.before else ROOT/f'design/MeshRepeater2_{label.title()}/MeshRepeater2_{label.title()}.kicad_pcb';out=Path(args.out) if args.out else HERE/label
    if args.after:compare(label,before,Path(args.after),out)
    else:inspect(label,before,out)
