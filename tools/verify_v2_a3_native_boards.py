"""Read-only A3 saved PCB/model/XML parity and requested interface geometry.

Run with KiCad's Python. This gate checks the actual native files, not a
generator's placement declaration. Native DRC, shield mechanical sampling,
load-step/RF bench tests and assembly qualification remain separate proofs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
from v2_a3_feature_contract import load_feature,feature_checks,PINMAP,SHUNT_MPN,SHUNT_FOOTPRINT
KEEP=[]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def fpid(footprint):
    ident=footprint.GetFPID()
    return str(ident.GetLibNickname())+':'+str(ident.GetLibItemName())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,default=ROOT/'audit/a3_2026_10_13/native_board_parity.json')
    args=ap.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('A3 proof must stay inside v2')
    contract=ROOT/'design/v2_electrical_contract.json'
    feature=load_feature(contract)
    checks=[];inputs=[contract,ROOT/'design/feature_a3_single_face_split_power.json',
        ROOT/'design/feature_ina219_vertical.json',ROOT/'tools/v2_a3_feature_contract.py',
        ROOT/'tools/v2_feature_contract.py',ROOT/'tools/cad/kicad_headless.py',Path(__file__)]
    models={};boards={};fps={};details={};before={str(p):sha(p) for p in inputs}
    def check(name,ok,detail=None):checks.append({'name':name,'pass':bool(ok),'detail':detail})
    for board in ['POWER','LOGIC']:
        project=ROOT/'design'/('MeshRepeater2_'+board.title())
        mp=project/'model.json';pp=project/(project.name+'.kicad_pcb')
        xp=ROOT/'audit/a3_2026_10_13/schematic'/board/'netlist.xml'
        inputs.extend([mp,pp,xp])
        before.update({str(p):sha(p) for p in [mp,pp,xp]})
        models[board]=json.loads(mp.read_text('utf-8'))
        b=k.LoadBoard(str(pp));KEEP.append(b);boards[board]=b
        fp={f.GetReference():f for f in b.GetFootprints()};fps[board]=fp
        parts={p['ref']:p for p in models[board]['parts']}
        check(board+' exact model/PCB reference set',set(fp)==set(parts),{'model_only':sorted(set(parts)-set(fp)),'pcb_only':sorted(set(fp)-set(parts))})
        check(board+' no duplicate PCB references',len(fp)==len(list(b.GetFootprints())))
        missing=[];pose=[];footprint=[];value=[];native_groups={};pcb_groups={}
        xml=ET.parse(xp).getroot()
        for net in xml.findall('nets/net'):
            nodes={(n.get('ref'),n.get('pin')) for n in net.findall('node') if n.get('ref') in parts}
            if nodes:native_groups[net.get('name')]=nodes
        for ref,p in parts.items():
            if ref not in fp:continue
            f=fp[ref];point=f.GetPosition()
            if math.dist((k.ToMM(point.x),k.ToMM(point.y)),(p['x'],p['y']))>0.001 or abs((f.GetOrientationDegrees()-p['rotation']+180)%360-180)>0.001:pose.append(ref)
            if fpid(f)!=p['footprint']:footprint.append((ref,fpid(f),p['footprint']))
            if f.GetValue()!=p['value']:value.append((ref,f.GetValue(),p['value']))
            pad_by_number={}
            for pad in f.Pads():pad_by_number.setdefault(pad.GetNumber(),[]).append(pad)
            for pin,logical in p['nets'].items():
                pads=pad_by_number.get(str(pin),[])
                if not pads:missing.append((ref,str(pin)));continue
                codes={pad.GetNetCode() for pad in pads}
                if len(codes)!=1:missing.append((ref,str(pin),'duplicate-pad-net-disagreement'));continue
                code=next(iter(codes))
                key=('NC',ref,str(pin)) if logical is None else ('NET',code)
                pcb_groups.setdefault(key,set()).add((ref,str(pin)))
        ng={frozenset(v) for v in native_groups.values()};pg={frozenset(v) for v in pcb_groups.values()}
        check(board+' all native endpoint groups match saved copper net assignment',not missing and ng==pg,{'missing_pins':missing,'native_only':[sorted(x) for x in ng-pg],'pcb_only':[sorted(x) for x in pg-ng]})
        check(board+' exact model/PCB position and angle',not pose,pose)
        check(board+' exact current footprint IDs',not footprint,footprint)
        check(board+' exact component values',not value,value)
        bad_angles=[];tracks=0
        for t in b.GetTracks():
            if isinstance(t,k.PCB_VIA):continue
            tracks+=1;start,end=t.GetStart(),t.GetEnd();dx=abs(end.x-start.x);dy=abs(end.y-start.y)
            if not(dx<=1 or dy<=1 or abs(dx-dy)<=10):bad_angles.append({'net':t.GetNetname(),'start_mm':[k.ToMM(start.x),k.ToMM(start.y)],'end_mm':[k.ToMM(end.x),k.ToMM(end.y)]})
        check(board+' track segments only 0/45/90 degrees',not bad_angles,bad_angles)
        callouts=[]
        for item in b.GetDrawings():
            if isinstance(item,k.PCB_TEXT) and re.search(r'\bG\d+\s*[xX]\s*\d',item.GetText()):callouts.append(item.GetText())
        check(board+' no old enlarged-group Gxx x1.5 callouts',not callouts,callouts)
        details[board]={'parts':len(parts),'track_segments':tracks,'graph_groups':len(ng)}
    checks.extend(feature_checks(models,feature))
    check('POWER all components have one F.Cu mounting face',all(f.GetLayer()==k.F_Cu for f in fps['POWER'].values()),[f.GetReference() for f in fps['POWER'].values() if f.GetLayer()!=k.F_Cu])
    for ref in SHUNT_MPN:
        f=fps['POWER'].get(ref)
        expected=SHUNT_FOOTPRINT[ref]
        source=next((p.get('source_footprint_before_v2_graphic_variant',p.get('footprint')) for p in models['POWER']['parts'] if p['ref']==ref),None)
        check('POWER 2512 physical-package library ID '+ref,f is not None and source==expected and fpid(f).split('__')[0]==expected,{'actual':fpid(f) if f else None,'expected_physical':expected,'model_source':source})
    points={ref:[k.ToMM(fps['POWER'][ref].GetPosition().x),k.ToMM(fps['POWER'][ref].GetPosition().y)] for ref in ['TP1','TP6','TP9'] if ref in fps['POWER']}
    row=len(points)==3 and (max(p[0] for p in points.values())-min(p[0] for p in points.values())<=0.01 or max(p[1] for p in points.values())-min(p[1] for p in points.values())<=0.01)
    check('POWER TP1/TP6/TP9 form one straight row',row,points)
    after={str(p):sha(p) for p in inputs}
    check('Read-only input files unchanged during proof',before==after)
    report={'ok':all(c['pass'] for c in checks),'scope':'Actual A3 PCB/model/native XML connectivity assignments, unchanged component poses and user-authorized interface; DRC and physical assembly/EMI validation separate','checks':checks,'boards':details,'inputs':{str(Path(p).relative_to(ROOT)):digest for p,digest in after.items()}}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'ok':report['ok'],'checks':len(checks),'failed':[c for c in checks if not c['pass']],'report':str(out.relative_to(ROOT))},ensure_ascii=True))
    if not report['ok']:raise SystemExit(1)


if __name__=='__main__':main()
