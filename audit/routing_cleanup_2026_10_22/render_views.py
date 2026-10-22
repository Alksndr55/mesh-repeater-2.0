"""Native KiCad route views; source boards remain untouched.

The routes-only views are exported from explicitly labelled audit copies with
zone records removed. They illustrate routing, and are not manufacturing CAM.
Full copper views are exported from the exact saved source board.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, json, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
sys.path.insert(0, str(ROOT/'tools/cad'))
from rezonit_logic_silk import blocks

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def render(name, phase):
    stem = f'MeshRepeater2_{name.title()}'
    source = (HERE/'baseline'/name if phase == 'before' else ROOT/'design'/stem)/(stem+'.kicad_pcb')
    original = sha(source)
    dest = HERE/'views'/phase/name
    dest.mkdir(parents=True, exist_ok=True)
    raw = source.read_text('utf-8')
    records = blocks(raw, ['zone'])
    for r in reversed(records):
        raw = raw[:r['start']]+raw[r['end']:]
    diagnostic = dest/(stem+'_ROUTES_ONLY_NOT_FOR_FAB.kicad_pcb')
    diagnostic.write_text(raw, 'utf-8', newline='\n')
    logs=[]
    for side, copper, silk in [('front','F.Cu','F.SilkS'),('back','B.Cu','B.SilkS')]:
        for mode, pcb in [('routes',diagnostic),('copper',source)]:
            target = dest/f'{name}_{mode}_{side}.svg'
            args = [str(CLI),'pcb','export','svg','--output',str(target),
                    '--layers',f'{copper},{silk},Edge.Cuts','--mode-single',
                    '--fit-page-to-board','--exclude-drawing-sheet']
            if side=='back': args.append('--mirror')
            args.append(str(pcb))
            r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
            logs.append(dict(command=args,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
            assert r.returncode==0,logs[-1]
    assert sha(source)==original,'Source mutated during rendering'
    result=dict(board=name,phase=phase,source=str(source.relative_to(ROOT)),
                source_sha256=original,source_preserved=True,
                diagnostic_note='ROUTES_ONLY: actual tracks/pads/vias/silk; zone records omitted in an audit-only copy. Not fabrication CAM.',
                zone_records_omitted=len(records),commands=logs)
    (dest/'render_proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(name,phase,'native views ready',flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['before','after'],required=True)
    ap.add_argument('--boards',nargs='+',choices=['POWER','LOGIC','SHIELD'],default=['POWER','LOGIC'])
    a=ap.parse_args()
    with ThreadPoolExecutor(max_workers=2) as p:
        results=list(p.map(lambda name:render(name,a.phase),a.boards))
    suffix='' if a.boards==['POWER','LOGIC'] else '_'+'_'.join(a.boards)
    (HERE/f'{a.phase}_views{suffix}.json').write_text(json.dumps(results,indent=2),'utf-8')
