"""Read-only independent review of the saved A3 native files.

Does not import any author's A3 placement, connectivity, or labelling gate.
Requires the root agent's ALL_CAD_FROZEN handoff. Never saves a board.
"""
from pathlib import Path
import argparse
import collections
from decimal import Decimal
import hashlib
import heapq
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
sys.path.insert(0, str(ROOT / 'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
HELD = []
PINMAP = {'1':'SYS_3V3','2':'GND','3':'SYS_3V3','4':'GND',
          '5':'RADIO_3V3','6':'GND','7':'RADIO_3V3','8':None,
          '9':'BAT','10':'SDA','11':'MODE','12':'SCL'}
SHUNTS = {'R1':'0.28R', 'R40':'22mR', 'R41':'22mR',
          'R55':'47mR', 'R56':'1.8R', 'R71':'0.1R'}
OVERRIDES = {'U1':{'14':'BAT_SYS'},'R1':{'2':'BAT_SYS'},
             'C4':{'1':'BAT_SYS'},'R3':{'1':'BAT_SYS'},
             'U2':{'10':'BAT_SYS'},'C12':{'1':'BAT_SYS'},
             'C13':{'1':'BAT_SYS'},'C52':{'1':'BAT_SYS'},
             'C53':{'1':'BAT_SYS'},'C30':{'1':'BAT_SYS'},
             'FB1':{'1':'RADIO_3V3','2':'RADIO_LOCAL_3V3'},
             'M2':{'3':'RADIO_LOCAL_3V3'},
             'C23':{'1':'RADIO_LOCAL_3V3'},'C24':{'1':'RADIO_LOCAL_3V3'}}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def xy(point):
    return (k.ToMM(point.x), k.ToMM(point.y))

def uid(obj):
    return str(obj.m_Uuid.AsString())

def bounds(obj):
    bb = obj.GetBoundingBox()
    return (k.ToMM(bb.GetX()), k.ToMM(bb.GetY()),
            k.ToMM(bb.GetRight()), k.ToMM(bb.GetBottom()))

def body_bounds(f):
    graphics = [bounds(g) for g in f.GraphicalItems()
                if g.GetLayer() in (k.F_CrtYd,k.B_CrtYd)]
    if not graphics:
        graphics = [bounds(p) for p in f.Pads()]
    return (min(g[0] for g in graphics), min(g[1] for g in graphics),
            max(g[2] for g in graphics), max(g[3] for g in graphics))

def centre(box):
    return ((box[0]+box[2])/2,(box[1]+box[3])/2)

def axis(f):
    box = body_bounds(f)
    w,h = box[2]-box[0],box[3]-box[1]
    if w > 1.15*h:
        return 0
    if h > 1.15*w:
        return 90
    return f.GetOrientationDegrees()%180

def angle_distance(a,b):
    return abs((a-b+90)%180-90)

def fp_id(f):
    ident = f.GetFPID()
    return str(ident.GetLibNickname())+':'+str(ident.GetLibItemName())

def shape_geometry(g):
    # Compare identical native coordinates, including arcs and stroke widths.
    data = [int(g.GetShape()), tuple(g.GetStart()), tuple(g.GetEnd()), g.GetWidth()]
    if g.GetShape() == k.SHAPE_T_ARC:
        data += [tuple(g.GetArcMid())]
    return json.dumps(data)

def run_cli(args, stem):
    result = subprocess.run([str(CLI),*args],capture_output=True,text=True,
                            encoding='utf8',errors='replace',timeout=600)
    (OUT/(stem+'.log')).write_text(result.stdout+result.stderr,encoding='utf8')
    return result.returncode

def sexpr(text):
    """Small independent reader; keeps atoms as text for exact native fields."""
    stack=[];result=[]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if token=='(':
            value=[]
            if stack:stack[-1].append(value)
            else:result.append(value)
            stack.append(value)
        elif token==')':
            stack.pop()
        else:
            value=token[1:-1].replace('\\"','"').replace('\\\\','\\') if token.startswith('"') else token
            stack[-1].append(value)
    if stack:raise ValueError('Unbalanced native S-expression')
    return result[0]

def nearest_copper_route(board,footprints,ref):
    """Shortest saved track route from TP to another pad on its physical net.

    Splits same-net segments at branch endpoint crossings, crosses actual
    via barrels, and joins endpoints contained in the same component pad.
    Zone-connected GND gets no invented path length.
    """
    source_pad=next(iter(footprints[ref].Pads()))
    net=source_pad.GetNetCode()
    graph=collections.defaultdict(list)
    points=set()
    tracks=[t for t in board.GetTracks() if t.GetNetCode()==net]
    def node(point,layer):return (point.x,point.y,layer)
    def edge(a,b,length):
        graph[a].append((b,length));graph[b].append((a,length))
    for t in tracks:
        if isinstance(t,k.PCB_VIA):
            a=node(t.GetPosition(),k.F_Cu);b=node(t.GetPosition(),k.B_Cu)
            points.update([a,b]);edge(a,b,0)
        else:points.update([node(t.GetStart(),t.GetLayer()),node(t.GetEnd(),t.GetLayer())])
    for t in tracks:
        if isinstance(t,k.PCB_VIA):continue
        a,b=t.GetStart(),t.GetEnd();dx,dy=b.x-a.x,b.y-a.y;ll=dx*dx+dy*dy
        if not ll:continue
        values=[]
        for nn in points:
            if nn[2]!=t.GetLayer():continue
            ratio=((nn[0]-a.x)*dx+(nn[1]-a.y)*dy)/ll
            distance=math.hypot(nn[0]-a.x-ratio*dx,nn[1]-a.y-ratio*dy)
            if -1e-9<=ratio<=1+1e-9 and distance<=10:values.append((ratio,nn))
        values.sort()
        for (_,n1),(_,n2) in zip(values,values[1:]):
            edge(n1,n2,math.hypot(n1[0]-n2[0],n1[1]-n2[1])/1e6)
    target_pads={}
    start=('PAD',ref,'1')
    for owner,f in footprints.items():
        for pad in f.Pads():
            if pad.GetNetCode()!=net:continue
            padnode=('PAD',owner,pad.GetNumber())
            for nn in points:
                if pad.IsOnLayer(nn[2]) and pad.HitTest(k.VECTOR2I(nn[0],nn[1])):
                    edge(padnode,nn,0)
            if owner!=ref and not owner.startswith('TP'):target_pads[padnode]=pad
    pending=[(0,repr(start),start)];best={start:0}
    while pending:
        dist,_,current=heapq.heappop(pending)
        if dist!=best[current]:continue
        if current in target_pads:
            pad=target_pads[current]
            direct=math.dist(xy(source_pad.GetPosition()),xy(pad.GetPosition()))
            return {'route_mm':dist,'nearest_pad':current[1:],'pad_centre_distance_mm':direct}
        for neighbour,length in graph[current]:
            new=dist+length
            if new<best.get(neighbour,float('inf')):
                best[neighbour]=new;heapq.heappush(pending,(new,repr(neighbour),neighbour))
    if source_pad.GetNetname()=='GND':
        return {'route_mm':0,'nearest_pad':'direct GND pour','zone_connection_verified_by_DRC':True}
    return {'route_mm':None,'reason':'No continuous endpoint-track route found'}

def wide_copper_path(board,footprints,source,target,minimum_width=.8):
    """A continuous broad centreline route; thin sense copper cannot help.

    Pad projections split through-passing tracks, as well as tracks ending
    inside the pad. A centreline passing beside a pad is not a broad pickup.
    Full physical pad copper joins different contacts of that same pad;
    different pins of a component are never assumed internally shorted.
    """
    pp={(ref,q.GetNumber()):q for ref,f in footprints.items() for q in f.Pads()}
    net=pp[source].GetNetCode()
    if net!=pp[target].GetNetCode():return {'continuous_wide_path':False,'reason':'Different physical nets'}
    points=set();graph=collections.defaultdict(list)
    all_tracks=[t for t in board.GetTracks() if t.GetNetCode()==net]
    tracks=[t for t in all_tracks if isinstance(t,k.PCB_VIA) or k.ToMM(t.GetWidth())>=minimum_width-1e-6]
    pads={key:pad for key,pad in pp.items() if pad.GetNetCode()==net}
    def node(point,layer):return (point.x,point.y,layer)
    def edge(a,b,length,meta):
        graph[a].append((b,length,meta));graph[b].append((a,length,meta))
    for t in tracks:
        if isinstance(t,k.PCB_VIA):
            a=node(t.GetPosition(),k.F_Cu);b=node(t.GetPosition(),k.B_Cu)
            points.update([a,b])
            edge(a,b,0,{'type':'via','uuid':uid(t),'diameter_mm':k.ToMM(t.GetWidth(k.F_Cu)),
                        'drill_mm':k.ToMM(t.GetDrillValue())})
        else:
            points.update([node(t.GetStart(),t.GetLayer()),node(t.GetEnd(),t.GetLayer())])
            a,b=t.GetStart(),t.GetEnd();dx,dy=b.x-a.x,b.y-a.y;ll=dx*dx+dy*dy
            if not ll:continue
            for pad in pads.values():
                if not pad.IsOnLayer(t.GetLayer()):continue
                centre=pad.GetPosition()
                ratio=((centre.x-a.x)*dx+(centre.y-a.y)*dy)/ll
                ratio=min(max(ratio,0),1)
                projected=k.VECTOR2I(round(a.x+ratio*dx),round(a.y+ratio*dy))
                if pad.HitTest(projected):points.add(node(projected,t.GetLayer()))
    for t in tracks:
        if isinstance(t,k.PCB_VIA):continue
        a,b=t.GetStart(),t.GetEnd();dx,dy=b.x-a.x,b.y-a.y;ll=dx*dx+dy*dy
        if not ll:continue
        nn=[]
        for point in points:
            if point[2]!=t.GetLayer():continue
            ratio=((point[0]-a.x)*dx+(point[1]-a.y)*dy)/ll
            distance=math.hypot(point[0]-a.x-ratio*dx,point[1]-a.y-ratio*dy)
            if -1e-9<=ratio<=1+1e-9 and distance<=10:nn.append((ratio,point))
        nn.sort()
        for (_,n1),(_,n2) in zip(nn,nn[1:]):
            edge(n1,n2,math.hypot(n1[0]-n2[0],n1[1]-n2[1])/1e6,
                 {'type':'track','uuid':uid(t),'width_mm':k.ToMM(t.GetWidth())})
    for key,pad in pads.items():
        for point in points:
            if pad.IsOnLayer(point[2]) and pad.HitTest(k.VECTOR2I(point[0],point[1])):
                edge(('PAD',*key),point,0,{'type':'pad','endpoint':key})
    start,end=('PAD',*source),('PAD',*target)
    heap=[(0,repr(start),start)];best={start:0};parents={}
    while heap:
        dist,_,current=heapq.heappop(heap)
        if dist!=best[current]:continue
        if current==end:
            path=[]
            while current!=start:
                previous,meta=parents[current];path.append(meta);current=previous
            metal=[p for p in path if p['type']=='track']
            vias={p['uuid']:p for p in path if p['type']=='via'}
            return {'continuous_wide_path':bool(metal),'route_mm':dist,
                    'minimum_track_width_mm':min(p['width_mm'] for p in metal) if metal else None,
                    'track_uuids':sorted({p['uuid'] for p in metal}),
                    'vias':list(vias.values())}
        for neighbour,length,meta in graph[current]:
            candidate=dist+length
            if candidate<best.get(neighbour,float('inf')):
                best[neighbour]=candidate;parents[neighbour]=(current,meta)
                heapq.heappush(heap,(candidate,repr(neighbour),neighbour))
    return {'continuous_wide_path':False,'reason':'No continuous >=%.2fmm route from source pad to target pad'%minimum_width}

def native_broad_copper_path(board,footprints,source,target,minimum_width=.8):
    """Direct physical adjacency with all thin tracks removed from the graph.

    KiCad's direct-neighbour API handles copper intersections and barrel
    contacts, including genuine off-centre joins. It is not a whole-net or
    transitive-neighbour query. Checking width only at endpoints, or obtaining
    the connected whole net before filtering, would miss the thin-pickup bug.
    """
    pads={(ref,p.GetNumber()):p for ref,f in footprints.items() for p in f.Pads()}
    source_item,target_item=pads[source],pads[target]
    net=source_item.GetNetCode()
    if net!=target_item.GetNetCode():return {'continuous_wide_path':False,'reason':'Different physical nets'}
    allowed={uid(p):p for p in pads.values() if p.GetNetCode()==net}
    for t in board.GetTracks():
        if t.GetNetCode()==net and (isinstance(t,k.PCB_VIA) or k.ToMM(t.GetWidth())>=minimum_width-1e-6):
            allowed[uid(t)]=t
    connectivity=board.GetConnectivity()
    start,end=uid(source_item),uid(target_item)
    heap=[(0,start)];best={start:0};parents={}
    while heap:
        distance,current=heapq.heappop(heap)
        if distance!=best[current]:continue
        if current==end:
            selected=[]
            while current!=start:
                selected.append(allowed[current]);current=parents[current]
            metal=[item for item in selected if isinstance(item,k.PCB_TRACK) and not isinstance(item,k.PCB_VIA)]
            vias=[item for item in selected if isinstance(item,k.PCB_VIA)]
            return {'continuous_wide_path':bool(metal),
                    'selected_segment_length_sum_mm':sum(item.GetLength()/1e6 for item in metal),
                    'minimum_track_width_mm':min(k.ToMM(item.GetWidth()) for item in metal) if metal else None,
                    'track_uuids':sorted(uid(item) for item in metal),
                    'vias':[{'uuid':uid(item),'diameter_mm':k.ToMM(item.GetWidth(k.F_Cu)),
                             'drill_mm':k.ToMM(item.GetDrillValue())} for item in vias],
                    'method':'Direct native copper neighbours after excluding all narrow tracks; no whole-net collapse'}
        item=allowed[current]
        neighbours=list(connectivity.GetConnectedTracks(item))+list(connectivity.GetConnectedPads(item))
        for adjacent in neighbours:
            identifier=uid(adjacent)
            if identifier not in allowed:continue
            length=adjacent.GetLength()/1e6 if isinstance(adjacent,k.PCB_TRACK) and not isinstance(adjacent,k.PCB_VIA) else 0
            candidate=distance+length
            if candidate<best.get(identifier,float('inf')):
                best[identifier]=candidate;parents[identifier]=current
                heapq.heappush(heap,(candidate,identifier))
    return {'continuous_wide_path':False,'reason':'Narrow tracks removed: no physical broad-copper adjacency path'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frozen', required=True,
                        help='ALL_CAD_FROZEN handoff JSON supplied by root')
    args = parser.parse_args()
    freeze = Path(args.frozen).resolve()
    if not freeze.is_relative_to(ROOT) or not freeze.is_file():
        raise ValueError('Root freeze handoff must be a real file inside v2')
    handoff = json.loads(freeze.read_text('utf8'))
    if not (handoff.get('ALL_CAD_FROZEN') is True or
            handoff.get('status') == 'ALL_CAD_FROZEN'):
        raise ValueError('Explicit ALL_CAD_FROZEN handoff required')
    checks = []
    details = {}
    def check(name, passed, detail=None):
        checks.append({'name':name,'pass':bool(passed),'detail':detail})
    projects = {n:ROOT/'design'/('MeshRepeater2_'+n.title())
                for n in ('POWER','LOGIC','SHIELD')}
    inputs = [freeze,Path(__file__),ROOT/'tools/cad/kicad_headless.py',
              ROOT/'design/v2_electrical_contract.json']
    for project in projects.values():
        for p in project.rglob('*'):
            if p.is_file() and (p.suffix in ('.kicad_pcb','.kicad_pro','.kicad_dru',
                '.kicad_sch','.kicad_mod','.kicad_sym') or p.name in
                ('model.json','fp-lib-table','sym-lib-table')):
                inputs.append(p)
    for relative in ['docs/vertical_interconnect_selection.json',
                     'docs/mechanical_selection.json',
                     'audit/a3_2026_10_13/logic/before_A3.kicad_pcb',
                     'audit/a3_2026_10_13/power/before_power.kicad_pcb',
                     'audit/a3_2026_10_13/independent/before_A3_POWER_model_from_d1206d1.json']:
        p = ROOT/relative
        if p.is_file(): inputs.append(p)
    before = {str(p.relative_to(ROOT)):sha(p) for p in inputs}
    boards, fps, models, logical_codes = {},{},{},{}
    for name, project in projects.items():
        pcb = project/(project.name+'.kicad_pcb')
        board = k.LoadBoard(str(pcb));HELD.append(board)
        boards[name]=board
        fps[name]={f.GetReference():f for f in board.GetFootprints()}
        check(name+' native reference uniqueness',
              len(fps[name])==len(list(board.GetFootprints())))
        project_json=json.loads(pcb.with_suffix('.kicad_pro').read_text('utf8'))
        rules=project_json.get('board',{}).get('design_settings',{})
        check(name+' no project DRC exclusions',not rules.get('drc_exclusions'),rules.get('drc_exclusions'))
        check(name+' no ignored design-rule severities',
              not [key for key,value in rules.get('rule_severities',{}).items()
                   if value=='ignore'])
        drc_path=OUT/(name+'_drc.json')
        drc_args=['pcb','drc','--format','json','--severity-all','--all-track-errors',
                  '--refill-zones','--exit-code-violations','-o',str(drc_path)]
        if name!='SHIELD':drc_args.append('--schematic-parity')
        rc=run_cli([*drc_args,str(pcb)],name+'_drc')
        drc=json.loads(drc_path.read_text('utf8'))
        failure={field:drc.get(field,[]) for field in
                 ('violations','unconnected_items','schematic_parity','ignored_checks')}
        check(name+' fresh native all-severity DRC and parity',
              rc==0 and all(not v for v in failure.values()),failure)
        details[name]={'pcb_sha256':before[str(pcb.relative_to(ROOT))],
                       'fresh_drc_sha256':sha(drc_path)}
        if name=='SHIELD':continue
        models[name]=json.loads((project/'model.json').read_text('utf8'))
        parts={p['ref']:p for p in models[name]['parts']}
        check(name+' actual reference set matches current model',
              set(parts)==set(fps[name]),
              {'model_only':sorted(set(parts)-set(fps[name])),
               'pcb_only':sorted(set(fps[name])-set(parts))})
        xml_path=OUT/(name+'_netlist.xml')
        rc=run_cli(['sch','export','netlist','--format','kicadxml','-o',str(xml_path),
                    str(pcb.with_suffix('.kicad_sch'))],name+'_netlist')
        check(name+' fresh native schematic netlist export',rc==0)
        native=ET.parse(xml_path).getroot()
        xml_groups={frozenset((n.get('ref'),n.get('pin')) for n in net.findall('node')
                    if n.get('ref') in parts) for net in native.findall('nets/net')}
        xml_groups.discard(frozenset())
        actual=collections.defaultdict(set)
        mismatch=[];codes=collections.defaultdict(set)
        for ref,p in parts.items():
            f=fps[name].get(ref)
            if not f:continue
            if math.dist(xy(f.GetPosition()),(p['x'],p['y']))>.001 or \
               angle_distance(f.GetOrientationDegrees(),p['rotation'])>.001:
                mismatch.append([ref,'pose'])
            if f.GetValue()!=p['value'] or fp_id(f)!=p['footprint']:
                mismatch.append([ref,'value or footprint'])
            pads=collections.defaultdict(list)
            for pad in f.Pads():pads[pad.GetNumber()].append(pad)
            for pin,logical in p['nets'].items():
                pp=pads[str(pin)]
                nn={pad.GetNetCode() for pad in pp}
                if len(nn)!=1:mismatch.append([ref,pin,'missing/unequal pads']);continue
                code=next(iter(nn))
                key=('NET',code) if logical is not None else ('NC',ref,str(pin))
                actual[key].add((ref,str(pin)))
                if logical is not None:codes[logical].add(code)
        check(name+' model pose, value and physical package parity',not mismatch,mismatch)
        actual_groups={frozenset(x) for x in actual.values()}
        check(name+' fresh XML endpoint groups equal actual PCB assignment',
              xml_groups==actual_groups,
              {'xml_only':[sorted(x) for x in xml_groups-actual_groups],
               'pcb_only':[sorted(x) for x in actual_groups-xml_groups]})
        code_error={n:sorted(x) for n,x in codes.items() if len(x)!=1}
        # One code for each logical net, and one logical net for each code.
        reverse=collections.defaultdict(set)
        for n,cc in codes.items():
            for code in cc:reverse[code].add(n)
        aliases={c:sorted(n) for c,n in reverse.items() if len(n)>1}
        check(name+' logical net names neither split nor alias',not code_error and not aliases,
              {'split':code_error,'aliases':aliases})
        logical_codes[name]={n:next(iter(x)) for n,x in codes.items() if len(x)==1}
        erc_path=OUT/(name+'_erc.json')
        rc=run_cli(['sch','erc','--format','json','--severity-all','--exit-code-violations',
                    '-o',str(erc_path),str(pcb.with_suffix('.kicad_sch'))],name+'_erc')
        erc=json.loads(erc_path.read_text('utf8'))
        erc_errors=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
        check(name+' fresh native all-severity ERC',rc==0 and not erc_errors,erc_errors)
        check(name+' no project ERC exclusions',
              not project_json.get('erc',{}).get('erc_exclusions'))
        check(name+' no ignored ERC rule severities',
              not [key for key,value in project_json.get('erc',{}).get('rule_severities',{}).items()
                   if value=='ignore'])
        bad_angles=[];widths={}
        for track in board.GetTracks():
            if isinstance(track,k.PCB_VIA):continue
            d=track.GetEnd()-track.GetStart()
            if not (abs(d.x)<=1 or abs(d.y)<=1 or abs(abs(d.x)-abs(d.y))<=10):
                bad_angles.append({'start':xy(track.GetStart()),'end':xy(track.GetEnd())})
        check(name+' track directions are strictly orthogonal or 45 degrees',not bad_angles,bad_angles)
        for net,code in logical_codes[name].items():
            tracks=[t for t in board.GetTracks() if not isinstance(t,k.PCB_VIA) and t.GetNetCode()==code]
            widths[net]={'length_mm':sum(t.GetLength()/1e6 for t in tracks),
                        'width_count':dict(collections.Counter(k.ToMM(t.GetWidth()) for t in tracks))}
        details[name]['actual_net_trace_inventory']=widths
    parts={name:{p['ref']:p for p in m['parts']} for name,m in models.items()}
    p,l=parts['POWER'],parts['LOGIC']
    for name,ref in [('POWER','J101'),('LOGIC','J201')]:
        check(name+' exact two SYS, two RADIO, three GND and NC8',parts[name][ref]['nets']==PINMAP)
        pad8=next(x for x in fps[name][ref].Pads() if x.GetNumber()=='8')
        actual_code=pad8.GetNetCode()
        connected=[t for t in boards[name].GetTracks() if actual_code and t.GetNetCode()==actual_code]
        otherpads=[x for f in fps[name].values() for x in f.Pads()
                   if actual_code and x.GetNetCode()==actual_code and f.GetReference()!=ref]
        check(name+' pin8 physically isolated and unrouted',not connected and not otherpads)
    power_pins={q.GetNumber():xy(q.GetPosition()) for q in fps['POWER']['J101'].Pads()}
    logic_pins={q.GetNumber():xy(q.GetPosition()) for q in fps['LOGIC']['J201'].Pads()}
    mating_errors={pin:{'POWER':power_pins.get(pin),'LOGIC_transformed':
                  (logic_pins[pin][0],60-logic_pins[pin][1]) if pin in logic_pins else None}
                  for pin in power_pins if pin not in logic_pins or
                  math.dist(power_pins[pin],(logic_pins[pin][0],60-logic_pins[pin][1]))>.001}
    check('All twelve physical mating pin centres and numbers align after LOGIC inversion',
          len(power_pins)==12 and len(logic_pins)==12 and not mating_errors,mating_errors)
    check('All POWER parts mount on F.Cu',all(f.GetLayer()==k.F_Cu for f in fps['POWER'].values()),
          [r for r,f in fps['POWER'].items() if f.GetLayer()!=k.F_Cu])
    check('J11 only on POWER and single removable bridge',
          'J11' not in l and p['J11']['nets']=={'1':'FILTER_OUT','2':'SYS_3V3'}
          and len(list(fps['POWER']['J11'].Pads()))==2)
    native_power=sexpr((projects['POWER']/'MeshRepeater2_Power.kicad_pcb').read_text('utf8'))
    native_star=next(node for node in native_power if isinstance(node,list) and node[0]=='footprint'
        and any(isinstance(item,list) and item[:3]==['property','Reference','NT2'] for item in node))
    native_tie_groups=[item[1:] for item in native_star if isinstance(item,list) and item[0]=='net_tie_pad_groups']
    check('NT2 copper star has sole permitted SYS/RADIO tie',
          fps['POWER']['NT2'].IsNetTie()
          and native_tie_groups==[['1,2']]
          and p['NT2']['nets']=={'1':'SYS_3V3','2':'RADIO_3V3'})
    radio_power={(ref,pin) for ref,a in p.items() for pin,net in a['nets'].items() if net=='RADIO_3V3'}
    radio_logic={(ref,pin) for ref,a in l.items() for pin,net in a['nets'].items() if net=='RADIO_3V3'}
    local={(ref,pin) for ref,a in l.items() for pin,net in a['nets'].items() if net=='RADIO_LOCAL_3V3'}
    check('Separate RADIO branch runs from NT2 to two connector pins only',
          radio_power=={('NT2','2'),('J101','5'),('J101','7')},sorted(radio_power))
    check('RADIO on LOGIC feeds only FB1 input',radio_logic=={('J201','5'),('J201','7'),('FB1','1')},sorted(radio_logic))
    check('After FB1 only modem and C23/C24 receive RADIO_LOCAL',
          local=={('FB1','2'),('M2','3'),('C23','1'),('C24','1')},sorted(local))
    check('J11 disconnects converter from all SYS/RADIO load groups',
          logical_codes['POWER']['FILTER_OUT']!=logical_codes['POWER']['SYS_3V3']
          and logical_codes['POWER']['FILTER_OUT']!=logical_codes['POWER']['RADIO_3V3'])
    power_paths=[(('L1','2'),('R56','1')),(('L1','2'),('Q4','2')),
                 (('R56','2'),('R1','1')),(('Q4','3'),('R1','1')),
                 (('R1','2'),('R71','1')),(('R55','2'),('L3','1')),
                 (('L3','2'),('L4','1')),(('L4','2'),('J11','1')),
                 (('J11','2'),('NT2','1')),(('NT2','1'),('J101','1')),
                 (('NT2','1'),('J101','3')),(('NT2','2'),('J101','5')),
                 (('NT2','2'),('J101','7'))]
    wide_routes=[]
    for source_pad,target_pad in power_paths:
        result=native_broad_copper_path(boards['POWER'],fps['POWER'],source_pad,target_pad,.8)
        wide_routes.append({'source_pad':source_pad,'target_pad':target_pad,**result})
        check('POWER broad load route '+'.'.join(source_pad)+' to '+'.'.join(target_pad),
              result['continuous_wide_path'],result)
    details['POWER']['continuous_broad_load_routes']=wide_routes
    check('J8 and J12 have correct chemistry values',p['J8']['value']=='Na-ion' and p['J12']['value']=='LTO')
    for ref,nominal in SHUNTS.items():
        f=fps['POWER'][ref]
        pads=list(f.Pads())
        pitch=math.dist(xy(pads[0].GetPosition()),xy(pads[1].GetPosition())) if len(pads)==2 else None
        expected_pitch,expected_size=(5.71,(1.65,3.68)) if ref in ['R1','R40','R41','R55'] else (5.925,(1.225,3.35))
        pad_sizes=[tuple(sorted(xy(q.GetSize()))) for q in pads]
        check(ref+' physical 2512 and unchanged nominal',
              ('2512' in fp_id(f)) and f.GetValue().split()[0]==nominal,
              {'footprint':fp_id(f),'value':f.GetValue()})
        check(ref+' correct saved manufacturer-specific 2512 lands',
              pitch is not None and abs(pitch-expected_pitch)<.001
              and all(max(abs(a-b) for a,b in zip(size,expected_size))<.001 for size in pad_sizes),
              {'pitch_mm':pitch,'pad_sizes_mm':pad_sizes,'expected_pitch_mm':expected_pitch,
               'expected_pad_size_mm':expected_size,
               'source':'https://www.vishay.com/docs/30100/wsl.pdf page 2' if ref in ['R1','R40','R41','R55'] else 'KiCad IPC-derived generic 2512 lands'})
    for ref in ['R47','R51']:
        check(ref+' accepted 2 ohm balancer unchanged',p[ref]['value']=='2R 1%')
    contract=ROOT/'design/v2_electrical_contract.json'
    check('Original S4.16 contract immutable',sha(contract)=='478b416c5fa28fbe4cebbc594eb1b519e90cb6c393aba6f58130b6fecffdac08')
    source=json.loads(contract.read_text('utf8'))
    old_power_path=ROOT/'audit/a3_2026_10_13/power/before_power.kicad_pcb'
    old_power=k.LoadBoard(str(old_power_path));HELD.append(old_power)
    old_power_fp={f.GetReference():f for f in old_power.GetFootprints()}
    a2_model_path=OUT/'before_A3_POWER_model_from_d1206d1.json'
    a2_parts={p['ref']:p for p in json.loads(a2_model_path.read_text('utf8'))['parts']}
    check('Saved A2 board/model source for earlier mechanical allowance is exact',
          sha(old_power_path)=='24e7f986b5367bad9b9b7b468f39a2237bb83569585871b9a056a6da6072e729'
          and sha(a2_model_path)=='8047db72825784315a9204b069fcbf96249d16ccbbe3642f6936bea83b4631c0')
    a2_grounded=all(a2_parts[ref]['nets']=={'1':'GND'} and
                   {q.GetNumber():q.GetNetname() for q in old_power_fp[ref].Pads()}=={'1':'GND'}
                   for ref in ['H1','H2','H3','H4'])
    a2_pin4=next((q for q in old_power_fp['J12'].Pads() if q.GetNumber()=='4'),None)
    a2_nc4='4' in a2_parts['J12']['nets'] and a2_parts['J12']['nets']['4'] is None and a2_pin4 is not None
    a2_nc4 &= a2_pin4 is not None and (a2_pin4.GetNetCode()==0 or a2_pin4.GetNetname().startswith('unconnected-'))
    check('H1-H4 grounding is already present in both saved A2 PCB and model',a2_grounded)
    check('J12 NC4 is already present in both saved A2 PCB and model',a2_nc4)
    net_errors=[];value_errors=[]
    for original in source['parts']:
        ref=original['reference'];board='POWER' if ref=='J11' else original['board']
        if ref not in parts[board]:continue
        expected=dict(original['original_model_part']['nets'])
        expected.update(OVERRIDES.get(ref,{}))
        # Preserved earlier V2 mechanical authorization: grounded M3 rings
        # and the real four-pole XH LTO part with an unused fourth contact.
        if ref in ['H1','H2','H3','H4'] and original['original_model_part'].get('kind')=='MountingHole' and a2_grounded:
            expected=dict(a2_parts[ref]['nets'])
        if ref=='J12' and a2_nc4:expected['4']=a2_parts['J12']['nets']['4']
        if expected!=parts[board][ref]['nets']:
            net_errors.append({'ref':ref,'expected':expected,'actual':parts[board][ref]['nets']})
        old_part=original['original_model_part']
        kind=old_part.get('kind','')
        if not kind.startswith('Connector') and kind not in ['MountingHole','NetTie','TestPoint']:
            expected_value='1.8R 1% 1W' if ref=='R56' else old_part['value']
            if parts[board][ref]['value']!=expected_value:
                value_errors.append({'ref':ref,'expected':expected_value,'actual':parts[board][ref]['value']})
    check('Every original component endpoint preserves source or narrow authorized override',not net_errors,net_errors)
    check('Original electrical values remain unchanged except authorized R56 package rating',not value_errors,value_errors)
    for ref in ['M1','U6','U7','J10']:
        old=next(x['original_model_part'] for x in source['parts'] if x['reference']==ref)
        check(ref+' original firmware/ISP logical pin mapping',l[ref]['nets']==old['nets'])
    old_board=k.LoadBoard(str(ROOT/'audit/a3_2026_10_13/logic/before_A3.kicad_pcb'));HELD.append(old_board)
    old_fp={f.GetReference():f for f in old_board.GetFootprints()}
    check('POWER reference set changes only by relocated J11 and copper NT2',
          set(fps['POWER'])==set(old_power_fp)|{'J11','NT2'})
    check('LOGIC reference set changes only by removing relocated J11',
          set(fps['LOGIC'])==set(old_fp)-{'J11'})
    def pad_signature(f):
        return [(q.GetNumber(),xy(q.GetPosition()),xy(q.GetSize()),q.GetDrillSize().x,q.GetDrillSize().y)
                for q in f.Pads()]
    check('ISP J10 never moved, rotated or reworked',
          xy(old_fp['J10'].GetPosition())==xy(fps['LOGIC']['J10'].GetPosition())
          and old_fp['J10'].GetOrientationDegrees()==fps['LOGIC']['J10'].GetOrientationDegrees()
          and pad_signature(old_fp['J10'])==pad_signature(fps['LOGIC']['J10']))
    pose_changes=[]
    for ref,f in fps['LOGIC'].items():
        prior=old_fp[ref]
        if xy(f.GetPosition())!=xy(prior.GetPosition()) or f.GetOrientationDegrees()!=prior.GetOrientationDegrees():
            pose_changes.append(ref)
    check('All retained LOGIC component positions/orientations are preserved',not pose_changes,pose_changes)
    def ground_vias(board):
        return sorted((xy(t.GetPosition()),k.ToMM(t.GetWidth(k.F_Cu)),k.ToMM(t.GetDrillValue()))
                      for t in board.GetTracks() if isinstance(t,k.PCB_VIA) and t.GetNetname()=='GND')
    check('LOGIC ground stitching geometry preserved',ground_vias(old_board)==ground_vias(boards['LOGIC']))
    rf_names={q.GetNetname() for ref in ['M2','J13','FL1','NT1'] for q in old_fp[ref].Pads()
              if q.GetNetname() in ('/ANT_RF','/ANT_SMA')}
    def radio_copper(board):
        return sorted((t.GetNetname(),t.GetLayer(),xy(t.GetStart()),xy(t.GetEnd()),
                       k.ToMM(t.GetWidth(k.F_Cu)) if isinstance(t,k.PCB_VIA) else k.ToMM(t.GetWidth()))
                      for t in board.GetTracks() if t.GetNetname() in rf_names)
    check('Modem/SMA RF trace geometry unchanged',len(rf_names)==2 and radio_copper(old_board)==radio_copper(boards['LOGIC']))
    tp={ref:xy(fps['POWER'][ref].GetPosition()) for ref in ['TP1','TP6','TP9']}
    row=(max(x[0] for x in tp.values())-min(x[0] for x in tp.values())<.001
         or max(x[1] for x in tp.values())-min(x[1] for x in tp.values())<.001)
    check('TP1/TP6/TP9 form one exact row within 4mm of edge',row and all(min(x,y,90-x,60-y)<=4 for x,y in tp.values()),tp)
    dimension=0 if max(x[1] for x in tp.values())-min(x[1] for x in tp.values())<.001 else 1
    sequence=sorted(point[dimension] for point in tp.values())
    check('Edge testpoint row has equal spacing',abs(sequence[2]-2*sequence[1]+sequence[0])<.001,sequence)
    tp_access=[]
    header_bodies={}
    for ref in ['J7','J8','J12']:
        shapes=[g for g in fps['POWER'][ref].GraphicalItems()
                if g.GetLayer()==k.F_Fab and isinstance(g,k.PCB_SHAPE) and g.GetShape()==k.SHAPE_T_RECT]
        header_bodies[ref]=min([bounds(g) for g in shapes],key=lambda bb:(bb[2]-bb[0])*(bb[3]-bb[1]))
    for ref,point in tp.items():
        pad=next(iter(fps['POWER'][ref].Pads()));radius=max(xy(pad.GetSize()))/2
        gaps={rr:math.hypot(max(bb[0]-point[0],point[0]-bb[2],0),
                           max(bb[1]-point[1],point[1]-bb[3],0))-radius
              for rr,bb in header_bodies.items()}
        mount_gaps={rr:math.dist(point,xy(f.GetPosition()))-radius-3.25
                    for rr,f in fps['POWER'].items() if rr.startswith('H')}
        tp_access.append({'ref':ref,'native_mm':point,'pad_to_header_body_mm':gaps,
                          'pad_to_washer_R3p25_mm':mount_gaps})
    check('Actual test pads remain accessible outside plastic bodies and M3 washers',
          all(min(r['pad_to_header_body_mm'].values())>=0 and
              min(r['pad_to_washer_R3p25_mm'].values())>=0 for r in tp_access),tp_access)
    tp_routes={ref:nearest_copper_route(boards['POWER'],fps['POWER'],ref) for ref in tp}
    check('Testpoint copper routes are short at nearby source/ground',
          all(item['route_mm'] is not None and item['route_mm']<=12 for item in tp_routes.values()),tp_routes)
    details['POWER']['edge_testpoint_routes']=tp_routes
    header=body_bounds(fps['POWER']['J101'])
    check('D3/D4 are behind J101 toward top board edge',
          all(body_bounds(fps['POWER'][ref])[3]<header[1] for ref in ['D3','D4']))
    j=centre(body_bounds(fps['POWER']['J11']));ind=centre(body_bounds(fps['POWER']['L4']))
    check('J11 is at right edge opposite final L4',j[0]>84 and abs(j[1]-ind[1])<5,{'J11_centre':j,'L4_centre':ind})
    for name in ['POWER','LOGIC']:
        texts=[t for t in boards[name].GetDrawings() if isinstance(t,k.PCB_TEXT)
               and t.GetLayer() in (k.F_SilkS,k.B_SilkS)]
        old_calls=[t.GetText() for t in texts if re.search(r'\bG\d+\s*[xX]\s*\d',t.GetText())]
        check(name+' no Gxx enlarged-group callouts',not old_calls,old_calls)
        errors=[];coverage=[]
        for ref,f in fps[name].items():
            if ref.startswith('NT'):continue  # Copper-only features are not assembly components.
            own=[t for t in texts if re.match(r'^'+re.escape(ref)+r'(?:\s|$)',t.GetText())]
            bb=body_bounds(f);cc=centre(bb);good=[];invalid_tags=[]
            def normalized_nominal(value):
                value=value.replace('Ω','R')
                if value.endswith(('F','H')):value=value[:-1]
                if value.endswith('R') and len(value)>1:value=value[:-1]
                factors={'':Decimal(1),'R':Decimal(1),'k':Decimal('1e3'),'K':Decimal('1e3'),
                         'M':Decimal('1e6'),'m':Decimal('1e-3'),'u':Decimal('1e-6'),
                         'n':Decimal('1e-9'),'p':Decimal('1e-12')}
                embedded=re.fullmatch(r'(\d*)([RkKMmunp])(\d+)',value)
                if embedded:
                    coefficient=Decimal((embedded[1] or '0')+'.'+embedded[3])
                    return str((coefficient*factors[embedded[2]]).normalize())
                standard=re.fullmatch(r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))([RkKMmunp]?)',value)
                if standard:return str((Decimal(standard[1])*factors[standard[2]]).normalize())
                return value
            required_nominal=normalized_nominal(f.GetValue().split()[0]) if ref.startswith(('R','C','L')) and not ref.startswith('LED') else None
            part=parts[name][ref]
            nominal_variants={tag:normalized_nominal(part.get(field,f.GetValue()).split()[0])
                 for tag,field in [('N','value'),('L','value_lto2s'),('NC','value_naion_no_cold')]}
            for t in own:
                angle_ok=angle_distance(t.GetTextAngle().AsDegrees(),axis(f))<.01
                if t.GetLayer()==k.B_SilkS:
                    where=math.dist(xy(t.GetPosition()),cc)<.01 and t.IsMirrored()
                else:
                    tb=bounds(t)
                    dx=max(bb[0]-tb[2],tb[0]-bb[2],0)
                    dy=max(bb[1]-tb[3],tb[1]-bb[3],0)
                    where=math.hypot(dx,dy)<=1.8
                words=t.GetText().split()
                printed=[];nominal_ok=True
                if required_nominal is not None:
                    for token in words[1:]:
                        for alternative in token.split('/'):
                            tag=None
                            if alternative[:1] in ('N','L') and len(alternative)>1 and alternative[1].isdigit():
                                tag,alternative=alternative[0],alternative[1:]
                            number=normalized_nominal(alternative);printed.append(number)
                            nominal_ok &= number==nominal_variants[tag] if tag else number in set(nominal_variants.values())
                    nominal_ok &= required_nominal in printed
                is_pinout=('\n1 ' in t.GetText() or ('/' in t.GetText().split('\n')[0]
                           and ref.startswith('J')))
                if is_pinout:continue
                if angle_ok and where and nominal_ok:good.append(t)
                else:invalid_tags.append(t.GetText())
            if not good or invalid_tags:errors.append({'ref':ref,'axis':axis(f),'body_centre':cc,
                           'invalid_component_tags':invalid_tags,
                           'labels':[{'text':t.GetText(),'at':xy(t.GetPosition()),
                                      'angle':t.GetTextAngle().AsDegrees(),
                                      'layer':boards[name].GetLayerName(t.GetLayer())} for t in own]})
            coverage.append({'ref':ref,'qualified_labels':len(good)})
        check(name+' each component has owner-axis adjacent or exact under-body label',not errors,errors)
        check(name+' all back silk labels are mirrored',all(t.IsMirrored() for t in texts if t.GetLayer()==k.B_SilkS))
        details[name]['component_label_coverage']=coverage
    shapes={layer:collections.Counter(shape_geometry(g) for g in boards['POWER'].GetDrawings()
                if isinstance(g,k.PCB_SHAPE) and g.GetLayer()==layer)
            for layer in [k.F_SilkS,k.B_SilkS]}
    check('Optional POWER frame segments are exact identical F/B coordinates',
          bool(shapes[k.F_SilkS]) and shapes[k.F_SilkS]==shapes[k.B_SilkS],
          {'front_count':sum(shapes[k.F_SilkS].values()),'back_count':sum(shapes[k.B_SilkS].values())})
    for layer,label in [(k.F_SilkS,'front'),(k.B_SilkS,'back')]:
        option_text='\n'.join(t.GetText() for t in boards['POWER'].GetDrawings()
            if isinstance(t,k.PCB_TEXT) and t.GetLayer()==layer)
        check('POWER '+label+' names both balancers and cold option',
              all(term in option_text for term in ['BAL1','BAL2','COLD']))
    shield=boards['SHIELD']
    windows=[f for f in shield.GetFootprints() if 'Window17p2x6p8' in fp_id(f)]
    check('SHIELD has one continuous plastic passage footprint',len(windows)==1)
    holes=[q for f in shield.GetFootprints() for q in f.Pads() if q.GetDrillSize().x>0]
    check('SHIELD contains only four M3 drills, no individual pin drills',len(holes)==4,len(holes))
    if windows:
        edges=[g for g in windows[0].GraphicalItems() if g.GetLayer()==k.Edge_Cuts]
        bb=[bounds(g) for g in edges]
        window=(min(q[0] for q in bb),min(q[1] for q in bb),max(q[2] for q in bb),max(q[3] for q in bb))
        # Bounding boxes include stroke, so use exact endpoints for dimensions.
        points=[xy(g.GetStart()) for g in edges]+[xy(g.GetEnd()) for g in edges]
        extent=(min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points))
        window_center=centre(extent)
        pad_centres=[xy(q.GetPosition()) for q in fps['POWER']['J101'].Pads()]
        hc=(sum(q[0] for q in pad_centres)/12,60-sum(q[1] for q in pad_centres)/12)
        check('SHIELD window is 17.2 x 6.8 centered at real header',
              abs(extent[2]-extent[0]-17.2)<.001 and abs(extent[3]-extent[1]-6.8)<.001
              and math.dist(window_center,hc)<.001,{'bounds':extent,'centre':window_center,'header':hc})
        arcs=[g for g in edges if g.GetShape()==k.SHAPE_T_ARC]
        check('SHIELD passage has four R0.6 milling corners',len(arcs)==4 and all(abs(k.ToMM(g.GetRadius())-.6)<.001 for g in arcs))
        body_graphics=[g for g in fps['POWER']['J101'].GraphicalItems()
            if g.GetLayer()==k.F_Fab and hasattr(g,'GetShape') and g.GetShape()==k.SHAPE_T_RECT]
        body=body_bounds(fps['POWER']['J101'])
        if body_graphics:
            body=max((bounds(g) for g in body_graphics),key=lambda bb:(bb[2]-bb[0])*(bb[3]-bb[1]))
        # Physical transform of the real F.Fab plastic envelope into SHIELD.
        plastic=(body[0],60-body[3],body[2],60-body[1])
        def within_rounded(x,y):
            xx=min(max(x,extent[0]+.6),extent[2]-.6)
            yy=min(max(y,extent[1]+.6),extent[3]-.6)
            return math.hypot(x-xx,y-yy)<=.6+1e-6
        check('Native modeled header plastic passes rounded SHIELD window',
              all(within_rounded(x,y) for x in [plastic[0],plastic[2]]
                  for y in [plastic[1],plastic[3]]),{'plastic_native_envelope':plastic,'window':extent})
    regions=[]
    for zone in shield.Zones():
        for layer in [k.F_Cu,k.B_Cu]:
            if zone.HasFilledPolysForLayer(layer):
                poly=zone.GetFilledPolysList(layer)
                regions.append({'layer':shield.GetLayerName(layer),'regions':poly.OutlineCount(),
                                'holes':[poly.HoleCount(i) for i in range(poly.OutlineCount())]})
    check('SHIELD saved foil is one connected F.Cu region',
          len(regions)==1 and regions[0]['layer']=='F.Cu' and regions[0]['regions']==1,regions)
    silk=[t.GetText() for t in shield.GetDrawings() if isinstance(t,k.PCB_TEXT)
          and t.GetLayer() in (k.F_SilkS,k.B_SilkS)]
    joined='\n'.join(silk)
    check('SHIELD Russian essential legends and J11 USB warning',
          all(term in joined for term in ['POWER','LOGIC','Na-ion','LTO','J11','USB'])
          and bool(re.search(r'[А-Яа-яЁё]',joined)) and ('снять' in joined.lower() or 'сним' in joined.lower()),silk)
    check('SHIELD silk preserves exact A3 interface and battery port cautions',
          all(term in joined for term in ['1,3 SYS_3V3','5,7 RADIO_3V3','2,4,6 GND',
              '8 NC','9 BAT','10 SDA','11 MODE','12 SCL','J12 LTO','2 MID','4 NC'])
          and 'вместе не подключать' in joined.lower())
    after={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    check('All native files, local libraries and project rules unchanged by audit',before==after,
          {p:[before[p],after.get(p)] for p in before if before[p]!=after.get(p)})
    report={'ok':all(c['pass'] for c in checks),'scope':'Independent saved-native A3 CAD audit; nominal connector passage only; bench EMI/load-step and accepted LTO limits remain separate',
            'checks':checks,'details':details,'inputs_sha256':after,
            'derived_reports_sha256':{p.name:sha(p) for p in OUT.iterdir()
                if p.is_file() and (p.name.endswith('_drc.json') or p.name.endswith('_erc.json') or p.name.endswith('_netlist.xml'))}}
    target=OUT/'independent_final.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'ok':report['ok'],'checks':len(checks),'failures':[c for c in checks if not c['pass']],
                      'report':str(target.relative_to(ROOT))},ensure_ascii=True))
    if not report['ok']:raise SystemExit(1)

if __name__=='__main__':
    main()
