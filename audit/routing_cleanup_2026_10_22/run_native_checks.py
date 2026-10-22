"""Isolated KiCad CLI checks for the saved v2 boards; never imports SWIG."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, hashlib, json, shutil, subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(name, phase):
    project = ROOT / 'design' / f'MeshRepeater2_{name.title()}'
    board = project / (project.name + '.kicad_pcb')
    files = list(project.glob('*.kicad_*')) + list(project.glob('*lib-table'))
    before = {p.relative_to(ROOT).as_posix():digest(p) for p in files if p.is_file()}
    if phase == 'before':
        for p in files:
            if p.is_file():
                target = HERE/'baseline'/name/p.name
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists(): shutil.copy2(p,target)
        model = project/'model.json'
        if model.is_file() and not (HERE/'baseline'/name/model.name).exists():
            shutil.copy2(model,HERE/'baseline'/name/model.name)
    out = HERE/phase/name
    out.mkdir(parents=True,exist_ok=True)
    commands = [['pcb','drc','--format','json','--units','mm','--severity-all',
        '--all-track-errors','--exit-code-violations','--refill-zones',
        *([] if name=='SHIELD' else ['--schematic-parity']),'-o',str(out/'drc.json'),str(board)]]
    if name != 'SHIELD':
        sch = board.with_suffix('.kicad_sch')
        commands += [['sch','erc','--format','json','--severity-all','--exit-code-violations',
            '-o',str(out/'erc.json'),str(sch)],
            ['sch','export','netlist','--format','kicadxml','-o',str(out/'netlist.xml'),str(sch)]]
    results=[]
    for command in commands:
        proc=subprocess.run([str(CLI),*command],cwd=ROOT,capture_output=True,encoding='utf-8',errors='replace')
        results.append({'command':command,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    after={p.relative_to(ROOT).as_posix():digest(p) for p in files if p.is_file()}
    report={'board':name,'phase':phase,'source_files':before,'sources_preserved':before==after,'commands':results}
    for kind in ('drc','erc'):
        if (out/f'{kind}.json').exists():
            raw=json.loads((out/f'{kind}.json').read_text('utf-8'))
            report[kind]={key:len(raw.get(key,[])) for key in ('violations','unconnected_items','schematic_parity','ignored_checks')}
            if kind == 'erc':
                report[kind]['violations'] += sum(len(s.get('violations',[])) for s in raw.get('sheets',[]))
    (out/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['before','after'],default='before')
    args=ap.parse_args()
    results={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(check,name,args.phase):name for name in ('POWER','LOGIC','SHIELD')}
        for job in as_completed(jobs):
            name=jobs[job];result=job.result();results[name]=result
            print(json.dumps({name:{k:v for k,v in result.items() if k in ('sources_preserved','drc','erc')}}),flush=True)
    (HERE/args.phase/'native_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(r['sources_preserved'] for r in results.values()),'Source changed during CLI checks'

if __name__=='__main__':main()
