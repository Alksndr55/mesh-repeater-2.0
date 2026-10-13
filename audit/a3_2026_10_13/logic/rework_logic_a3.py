"""A3 LOGIC-only changes: move jumper off board and separate supply ingress.

The netlist is the contract. All footprint poses, ISP pads and RF copper remain
fixed. This script does not edit schematics, model.json, POWER or SHIELD.
"""
from pathlib import Path
import argparse, collections, hashlib, json, math, re, shutil, subprocess, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
import complete_v2_routes as router

OUT = Path(__file__).resolve().parent
PCB = ROOT / 'design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pcb'
XML = ROOT / 'audit/a3_2026_10_13/schematic/LOGIC/netlist.xml'
CLI = 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
HELD = []

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def uid(o): return o.m_Uuid.AsString()
def xy(p): return (round(k.ToMM(p.x), 6), round(k.ToMM(p.y), 6))
def vec(p): return k.VECTOR2I(k.FromMM(p[0]), k.FromMM(p[1]))
def mm_box(o):
    bb = o.GetBoundingBox()
    return [k.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]

def contract():
    root = ET.parse(XML).getroot()
    names = {(n.attrib['ref'],n.attrib['pin']): net.attrib['name']
             for net in root.findall('./nets/net') for n in net.findall('node')}
    values = {c.attrib['ref']:c.findtext('value') for c in root.findall('./components/comp')}
    return names, values

def ensure_net(b, name):
    result = next((n for n in b.GetNetInfo().NetsByNetcode().values()
                   if n.GetNetname() == name), None)
    if result is None:
        result = k.NETINFO_ITEM(b, name); HELD.append(result); b.Add(result)
    return result

def copper_row(b, t):
    return dict(uuid=uid(t), net=t.GetNetname(), start=xy(t.GetStart()),
                end=xy(t.GetEnd()), layer=b.GetLayerName(t.GetLayer()),
                kind='via' if isinstance(t,k.PCB_VIA) else 'track')

def prepare():
    backup = OUT/'before_A3.kicad_pcb'
    if backup.exists(): raise RuntimeError('Initial preparation already done; do not replay')
    if not XML.exists(): raise RuntimeError('Waiting for schematic netlist contract')
    shutil.copy2(PCB, backup)
    names, values = contract()
    b = k.LoadBoard(str(PCB)); HELD.append(b)
    before_poses = {f.GetReference():[xy(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()]
                    for f in b.GetFootprints()}
    log = dict(before_sha256=sha(backup), removed=[], renamed=[], pad_changes=[])
    old_fb_input = {
        '61bbdb00-3f14-48a4-b89e-fd12abcb5454',
        'eb44df61-28b6-4501-a110-f15c1aaf7d96',
        '5ff3237a-79c4-4433-b62a-773cb1bce39f',
        'c0648521-606a-4b89-8967-ecc094e8a0ed',
    }
    old_jumper_launch = {
        '39f71730-1279-458f-bc74-293c44c571a9',
        '5a86970e-3abf-45b2-870b-db87197bd789',
        '62539dcf-31c1-4fb4-b27c-b8e81590ecd3',
        '779716bb-8fc5-4fc2-91e5-ccbdf0c63737',
        '95a0728c-08c6-43d3-afa3-dc9e434f5903',
    }
    old_pin7_return = {
        '3a5b3694-bc9e-4c22-9579-1f476e2c62e0',
        '465cca0a-bf0e-4187-a790-3fcf4671c631',
        '4f9c1a93-4fcc-4084-9991-1ecddb1b8287',
        '55882e23-50ff-46fc-b469-81299a29774b',
        '59531109-fc94-4ff8-a04a-a4a3f32292f2',
        'd1f152a5-69de-4251-84bd-7efa4aa870a1',
    }
    radio_in = ensure_net(b, names[('FB1','1')])
    radio_local = ensure_net(b, names[('FB1','2')])
    for t in list(b.GetTracks()):
        if t.GetNetname() == 'FILTER_OUT' or uid(t) in old_jumper_launch | old_pin7_return:
            log['removed'].append(copper_row(b,t)); b.Remove(t); HELD.append(t)
        elif uid(t) in old_fb_input:
            log['renamed'].append(dict(copper_row(b,t), new_net=radio_in.GetNetname()))
            t.SetNet(radio_in)
        elif t.GetNetname().lstrip('/') == 'RADIO_3V3':
            log['renamed'].append(dict(copper_row(b,t), new_net=radio_local.GetNetname()))
            t.SetNet(radio_local)
    for f in list(b.GetFootprints()):
        ref = f.GetReference()
        if ref == 'J11':
            log['removed'].append(dict(footprint=ref, position=xy(f.GetPosition())))
            b.Remove(f); HELD.append(f); continue
        if ref in values: f.SetValue(values[ref])
        for p in f.Pads():
            number=p.GetNumber(); name=names.get((ref,number))
            # Pin MP and repeated thermal pads are part of the same physical node.
            if name is None and number == 'MP': name = 'GND'
            if name is None: continue
            if p.GetNetname() != name:
                log['pad_changes'].append(dict(ref=ref,pin=number,old=p.GetNetname(),new=name))
                p.SetNet(ensure_net(b,name))
    assert {f.GetReference():[xy(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()]
            for f in b.GetFootprints()} == {r:p for r,p in before_poses.items() if r!='J11'}
    # Remove obsolete front/back text, including every displaced group legend.
    # Rebuild connected operators and component labels after copper routing.
    for g in list(b.GetDrawings()):
        if isinstance(g,k.PCB_TEXT) and g.GetLayer() in (k.F_SilkS,k.B_SilkS):
            log['removed'].append(dict(text=g.GetText(), uuid=uid(g),layer=b.GetLayerName(g.GetLayer())))
            b.Remove(g); HELD.append(g)
    for f in b.GetFootprints(): f.Reference().SetVisible(False); f.Value().SetVisible(False)
    k.SaveBoard(str(PCB),b)
    log.update(after_sha256=sha(PCB), footprint_poses_preserved=True,
               jumper_removed=True, isp_unchanged=before_poses['J10'])
    (OUT/'prepare_changes.json').write_text(json.dumps(log,indent=2),encoding='utf8')
    print(json.dumps({k:log[k] for k in ('before_sha256','after_sha256','footprint_poses_preserved')},indent=2))

def check(label, parity=True):
    output = OUT/('drc_'+label+'.json')
    args=[CLI,'pcb','drc','--format','json','--severity-all','--all-track-errors',
          '--refill-zones','--save-board','-o',str(output),str(PCB)]
    if parity: args.insert(3,'--schematic-parity')
    cp=subprocess.run(args,capture_output=True,text=True)
    (OUT/('drc_'+label+'.log')).write_text(cp.stdout+cp.stderr,encoding='utf8')
    if not output.exists(): raise RuntimeError(cp.stdout+cp.stderr)
    d=json.loads(output.read_text(encoding='utf8'))
    print(json.dumps({'check':label, 'counts':{n:len(d.get(n,[])) for n in
        ('violations','unconnected_items','schematic_parity','ignored_checks')},
        'types':dict(collections.Counter(v['type'] for v in d['violations']))}),flush=True)
    return d

def route(rounds=5):
    log=[]
    for i in range(rounds):
        drc=check('route_before_'+str(i),False)
        b=k.LoadBoard(str(PCB)); HELD.append(b)
        lookup={uid(t):t for t in b.GetTracks()}
        lookup.update({uid(p):p for f in b.GetFootprints() for p in f.Pads()})
        removed=[]
        # Only obsolete unconnected tracks may disappear; protected RF untouched.
        for error in drc['violations']:
            if error['type'] not in ('track_dangling','via_dangling'): continue
            for item in error['items']:
                t=lookup.get(item['uuid'])
                if t is not None and isinstance(t,k.PCB_TRACK) and t.GetNetname().lstrip('/') not in ('ANT_RF','ANT_SMA','RADIO_3V3'):
                    removed.append(copper_row(b,t)); b.Remove(t); HELD.append(t)
        if removed:
            log.append(dict(round=i, removed_orphan=removed)); k.SaveBoard(str(PCB),b)
            drc=check('route_clean_'+str(i),False)
            b=k.LoadBoard(str(PCB)); HELD.append(b)
            lookup={uid(t):t for t in b.GetTracks()}
            lookup.update({uid(p):p for f in b.GetFootprints() for p in f.Pads()})
        if not drc['unconnected_items']: break
        pairs=sorted(drc['unconnected_items'],key=lambda e:
                     0 if any(s in e['description'] for s in ('RADIO','SYS_3V3')) else 1)
        for pair in pairs:
            a,z=pair['items']; ai,zi=lookup.get(a['uuid']),lookup.get(z['uuid'])
            if ai is None or zi is None: continue
            net=ai.GetNetname(); assert net==zi.GetNetname(),pair
            if net.startswith('unconnected-'): continue
            width=.8 if net.lstrip('/') in ('SYS_3V3','RADIO_3V3') else .5 if net=='GND' else .25
            start=tuple(a['pos'][p] for p in ('x','y')); end=tuple(z['pos'][p] for p in ('x','y'))
            sp=router.component_points(b,ai); tp=router.component_points(b,zi)
            # Resolved earlier pair in this same round needs no additional copper.
            if {p for p,l in sp} & {p for p,l in tp}: continue
            info=router.route(b,net,start,end,width,router.item_layers(a['description']),
                              router.item_layers(z['description']),True,sp,tp)
            log.append(dict(round=i,route=info))
        k.ZONE_FILLER(b).Fill(b.Zones()); k.SaveBoard(str(PCB),b)
    (OUT/'route_changes.json').write_text(json.dumps(log,indent=2),encoding='utf8')
    check('routes_final',False)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=('prepare','route','check'))
    ap.add_argument('--rounds',type=int,default=5); args=ap.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='route': route(args.rounds)
    else: check('current')
