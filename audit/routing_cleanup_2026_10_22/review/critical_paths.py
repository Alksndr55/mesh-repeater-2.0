"""Physical copper checks for previously corrected supply/INA paths."""
from independent_review import *

def c33(tree):
    fs={geo.prop(f,'Reference'):f for f in geo.arr(tree,'footprint')};c=next(p for p in geo.arr(fs['C33'],'pad') if str(p[1])=='1');cut,cxy=geo.padshape(fs['C33'],c);net=geo.net(c)
    up=next(p for p in geo.arr(fs['U6'],'pad') if str(p[1])=='8');_,load=geo.padshape(fs['U6'],up)
    allcopper={l:[] for l in ['F.Cu','B.Cu']};links=[]
    for s in geo.arr(tree,'segment'):
        if geo.net(s)==net:allcopper[str(geo.val(s,'layer'))].append(LineString([geo.vec(s,'start'),geo.vec(s,'end')]).buffer(float(geo.val(s,'width'))/2,quad_segs=24))
    for f in geo.arr(tree,'footprint'):
        for p in geo.arr(f,'pad'):
            if geo.net(p)!=net:continue
            g,xy=geo.padshape(f,p);ls=geo.layers(p)
            for l in ls:allcopper[l].append(g)
            if len(ls)>1:links.append((g,ls))
    for v in geo.arr(tree,'via'):
        if geo.net(v)!=net:continue
        g=Point(geo.vec(v,'at')).buffer(float(geo.val(v,'size'))/2,quad_segs=24);ls=geo.layers(v)
        for l in ls:allcopper[l].append(g)
        links.append((g,ls))
    def connected(remove_cap_landing):
        comps={}
        for l,gs in allcopper.items():
            g=unary_union(gs)
            if remove_cap_landing and l=='F.Cu':g=g.difference(cut.buffer(.00001))
            comps[l]=list(g.geoms) if hasattr(g,'geoms') else [g]
        keys=[(l,i) for l in comps for i in range(len(comps[l]))];parent={n:n for n in keys}
        def find(n):
            while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
            return n
        def union(a,b):parent[find(a)]=find(b)
        for g,ls in links:
            hits=[(l,i) for l in ls for i,c in enumerate(comps[l]) if g.intersects(c)]
            for n in hits[1:]:union(hits[0],n)
        src=[('F.Cu',i) for i,g in enumerate(comps['F.Cu']) if g.distance(Point(43.1,35.5))<1e-5]
        dst=[('F.Cu',i) for i,g in enumerate(comps['F.Cu']) if g.distance(Point(load))<1e-5]
        return any(find(a)==find(b) for a in src for b in dst)
    normal=connected(False);bypass=connected(True)
    return dict(C33_pin1_xy=cxy,U6_pin8_xy=load,source_xy=[43.1,35.5],source_reaches_U6=normal,source_reaches_U6_with_C33_landing_removed=bypass,pass_=normal and not bypass)

def kelvin(tree):
    fs={geo.prop(f,'Reference'):f for f in geo.arr(tree,'footprint')};ss={geo.uid(n):n for n in geo.arr(tree,'segment')};result={}
    paths={'R72':('1',['6a61b9f1-96a9-49f2-bc9b-5ea380c60f29','08ad68eb-b80f-47d7-add1-006a393ea319','4ce74106-fd35-41e9-b35b-910e1af68b02','e183352a-ee3d-4955-8d5f-6e7894d0396f','d3d48f52-7ea7-4b13-923a-909e11c26e0a','a7b5c815-bef8-4df8-a532-ed8d100a4927']),'R73':('2',['0ba9743e-854b-4b94-96a7-f0e0544d3747','33030863-ae59-414b-a3fd-0af86ce38b2e'])}
    for ref,(pin,ids) in paths.items():
        pad=next(p for p in geo.arr(fs['R71'],'pad') if str(p[1])==pin);shape,_=geo.padshape(fs['R71'],pad);net=geo.net(pad)
        missing=[u for u in ids if u not in ss]
        if missing:result[ref]=dict(pass_=False,missing_path_uuids=missing);continue
        sense=unary_union([LineString([geo.vec(ss[u],'start'),geo.vec(ss[u],'end')]).buffer(float(geo.val(ss[u],'width'))/2,quad_segs=48) for u in ids]);force=[]
        for n in geo.arr(tree,'segment'):
            if geo.net(n)==net and str(geo.val(n,'layer'))=='F.Cu' and float(geo.val(n,'width'))>=.4:force.append(LineString([geo.vec(n,'start'),geo.vec(n,'end')]).buffer(float(geo.val(n,'width'))/2,quad_segs=48))
        for n in geo.arr(tree,'via'):
            if geo.net(n)==net:force.append(Point(geo.vec(n,'at')).buffer(float(geo.val(n,'size'))/2,quad_segs=48))
        outside=sense.intersection(unary_union(force)).difference(shape.buffer(.000001))
        result[ref]=dict(R71_pin=pin,sense_trace_uuids=ids,force_sense_overlap_outside_shunt_pad_mm2=outside.area,pass_=outside.area<1e-8)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('candidate');p.add_argument('out');args=p.parse_args();label=args.label.upper()
    before=ROOT/f'audit/routing_cleanup_2026_10_22/baseline/{label}/MeshRepeater2_{label.title()}.kicad_pcb';after=Path(args.candidate).resolve();fun=c33 if label=='LOGIC' else kelvin
    result=dict(board=label,before_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),after_sha256=hashlib.sha256(after.read_bytes()).hexdigest(),before=fun(sx.loads(before.read_text('utf-8'))),after=fun(sx.loads(after.read_text('utf-8'))))
    Path(args.out).write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result,indent=2))
