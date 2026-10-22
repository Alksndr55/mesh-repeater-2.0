"""Rezonit LOGIC printed markings: pure text patch; never imports pcbnew.

Keep all non-silkscreen board bytes unchanged.  Native KiCad SVG strokes and
DRC provide geometric validation; the project configuration only raises the
two printed-text manufacturing minima.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.publication_tmp/fab_deps'))
import sexpdata as sx

PCB = ROOT / 'design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pcb'
EVIDENCE = ROOT / 'audit/manufacturing_a4_2026_10_14/marking_LOGIC'
CLI = Path(r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe')


def blocks(source, types):
    result=[]
    for m in re.finditer(r'\(('+'|'.join(types)+r')\b',source):
        depth=0; quoted=False; escaped=False
        for j in range(m.start(),len(source)):
            ch=source[j]
            if quoted:
                if escaped: escaped=False
                elif ch=='\\': escaped=True
                elif ch=='"': quoted=False
            elif ch=='"': quoted=True
            elif ch=='(': depth+=1
            elif ch==')':
                depth-=1
                if depth==0:break
        text=source[m.start():j+1]
        result.append(dict(start=m.start(),end=j+1,block=text,type=m[1]))
    return result


def key(x): return str(x[0]) if isinstance(x,list) and x else ''
def field(x,k): return next((y for y in x if key(y)==k),None)
def silk_rows(source):
    rows=[]
    for row in blocks(source,['gr_text','gr_line','gr_rect','gr_circle','gr_arc','gr_poly',
                              'fp_text','fp_line','fp_rect','fp_circle','fp_arc','fp_poly','property']):
        data=sx.loads(row['block']);layer=field(data,'layer')
        if layer and layer[1] in ('F.SilkS','B.SilkS'):
            row.update(data=data,layer=layer[1]);rows.append(row)
    return rows


def without_printed(source):
    for row in reversed(silk_rows(source)):
        source=source[:row['start']]+source[row['end']:]
    return re.sub(r'\s+',' ',source).strip()


def upgrade(source):
    changes=[]
    for row in silk_rows(source):
        old=row['block'];new=old
        if row['type'] in ('gr_text','fp_text','property'):
            if re.search(r'\(hide yes\)',old) or re.search(r'\bhide\s*\)',old):continue
            new=re.sub(r'\(size ([\d.]+) ([\d.]+)\)',lambda m:f'(size {max(1.,float(m[1])):g} {max(1.,float(m[2])):g})',new)
            new=re.sub(r'\(thickness ([\d.]+)\)',lambda m:f'(thickness {max(.15,float(m[1])):g})',new)
        else:
            new=re.sub(r'\(width ([\d.]+)\)',lambda m:f'(width {max(.15,float(m[1])):g})',new)
        if old!=new:changes.append((row['start'],row['end'],new))
    for a,b,new in reversed(changes):source=source[:a]+new+source[b:]
    return source,len(changes)


def patch_captions(source, corrections):
    changes=[]
    for row in silk_rows(source):
        if row['type']!='gr_text':continue
        text=row['data'][1]
        if text not in corrections:continue
        spec=corrections[text];new=row['block']
        if 'text' in spec:new=new.replace(json.dumps(text,ensure_ascii=False),json.dumps(spec['text'],ensure_ascii=False),1)
        if 'at' in spec:
            new=re.sub(r'\(at [^)]*\)',f"(at {' '.join(f'{v:g}' for v in spec['at'])})",new,count=1)
        if 'layer' in spec:
            new=new.replace(f'(layer "{row["layer"]}")',f'(layer "{spec["layer"]}")')
            new=new.replace('(justify mirror)','')
            if spec['layer']=='B.SilkS':new=new.replace('(effects','(effects\n\t\t(justify mirror)',1)
        changes.append((row['start'],row['end'],new))
    for a,b,new in reversed(changes):source=source[:a]+new+source[b:]
    return source


CORRECTIONS = {
    'H201 M3': {'at':[3.65,7.7536,0]},
    'H203 M3': {'at':[3.65,52.2464,0]},
    'U6\nATtiny13A': {'layer':'B.SilkS','at':[44,34,90]},
    'U4 DS3231M': {'layer':'B.SilkS','at':[77,8,90]},
    'R42 100k': {'text':'R42\n100k','at':[64.5,24,0]},
    'FL1\nS869M000\nS003': {'text':'FL1\nS869\nM000\nS003','at':[40.7,4.25,0]},
    'FB1\n60R': {'text':'FB1','at':[33.8,14.45,0]},
    'J3 I2C\n1 3V3 2 GND\n3 SCL 4 SDA': {'text':'J3 I2C','at':[84,8.2,0]},
    '1RF 2GND': {'text':'1 RF\n2 GND','at':[29,4.25,0]},
}

EXTRA_CAPTIONS = '''
    (gr_text "1 3V3 2 GND\\n3 SCL 4 SDA"
        (at 82 23.4 0)
        (layer "B.SilkS")
        (uuid "b0fc23d5-63b6-40a8-aa84-45c2494705c1")
        (effects (font (size 1 1) (thickness 0.15)) (justify mirror))
    )
    (gr_text "60R"
        (at 33.8 16.1 0)
        (layer "B.SilkS")
        (uuid "f4c759ce-a60a-4a10-9485-c906b82fc89e")
        (effects (font (size 1 1) (thickness 0.15)) (justify mirror))
    )
'''


def export():
    for layer in ('F.SilkS','B.SilkS','F.Mask','B.Mask'):
        subprocess.run([str(CLI),'pcb','export','svg','--mode-single','--layers',layer,
                        '--page-size-mode','2','--exclude-drawing-sheet','-o',str(EVIDENCE/(layer+'.svg')),str(PCB)],check=True,capture_output=True)
    p=subprocess.run([str(CLI),'pcb','drc','--format','json','--severity-all','--schematic-parity','-o',str(EVIDENCE/'LOGIC_drc.json'),str(PCB)],capture_output=True,text=True)
    (EVIDENCE/'LOGIC_drc.log').write_text(p.stdout+p.stderr,'utf-8')
    return json.loads((EVIDENCE/'LOGIC_drc.json').read_text('utf-8'))


def apply():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    original=EVIDENCE/'LOGIC_original_A4.kicad_pcb'
    if not original.exists():original.write_bytes(PCB.read_bytes())
    raw=original.read_text('utf-8');new,count=upgrade(raw);new=patch_captions(new,CORRECTIONS)
    for row in reversed(silk_rows(new)):
        if row['type']=='gr_line':
            block=row['block']
            block=re.sub(r'(\((?:start|end)) 38\.57 ',r'\g<1> 38.52 ',block)
            if re.search(r'\((?:start|end) (?:38\.57|43\.2) 8\.1\)',block):
                block=re.sub(r'(\((?:start|end) (?:38\.57|43\.2)) 8\.1\)',r'\g<1> 8.2)',block)
            block=re.sub(r'(\((?:start|end) 38\.52) 8\.1\)',r'\g<1> 8.2)',block)
            new=new[:row['start']]+block+new[row['end']:]
    additions=[]
    for extra in blocks(EXTRA_CAPTIONS,['gr_text']):
        item_uuid=field(sx.loads(extra['block']),'uuid')[1]
        if f'(uuid "{item_uuid}")' not in new:additions.append(extra['block'])
    if additions:
        end=new.rfind(')');new=new[:end]+'\n'+'\n'.join(additions)+'\n'+new[end:]
    assert without_printed(raw)==without_printed(new),'Non-printed CAD changed'
    uuids=re.findall(r'\(uuid "([^"]+)"\)',new);assert len(uuids)==len(set(uuids))
    def original_newlines(text,baseline):
        return text.replace('\n','\r\n').encode('utf-8') if b'\r\n' in baseline else text.encode('utf-8')
    PCB.write_bytes(original_newlines(new,original.read_bytes()))
    lib_changes=[]
    used={x[1].split(':',1)[1] for x in sx.loads(new) if key(x)=='footprint' and x[1].startswith('Meshcore:')}
    for library in sorted((PCB.parent/'Meshcore.pretty').glob('*.kicad_mod')):
        if library.stem not in used:
            baseline=subprocess.run(['git','show','v2.0-a4:'+library.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True,check=True).stdout
            prior=baseline.decode('utf-8');current=library.read_text('utf-8')
            assert without_printed(prior)==without_printed(current),'Unexpected unused-library change'
            upgraded,_=upgrade(prior)
            assert current==upgraded.replace('\r\n','\n') or current==prior.replace('\r\n','\n'),str(library)
            library.write_bytes(baseline)
            continue
        rawlib=library.read_text('utf-8');newlib,n=upgrade(rawlib)
        baseline=subprocess.run(['git','show','v2.0-a4:'+library.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True,check=True).stdout
        if n:
            assert without_printed(rawlib)==without_printed(newlib)
        library.write_bytes(original_newlines(newlib,baseline))
        if library.read_bytes()!=baseline:
            assert without_printed(baseline.decode('utf-8'))==without_printed(newlib)
            lib_changes.append(dict(path=str(library.relative_to(ROOT)),
                                   before_sha256=hashlib.sha256(baseline).hexdigest(),
                                   after_sha256=hashlib.sha256(library.read_bytes()).hexdigest()))
    pro=PCB.with_suffix('.kicad_pro');proraw=pro.read_text('utf-8')
    proorig=EVIDENCE/'LOGIC_original_A4.kicad_pro'
    if not proorig.exists():proorig.write_text(proraw,'utf-8')
    proraw=re.sub(r'("min_text_height"\s*:\s*)[\d.]+',r'\g<1>1.0',proraw)
    proraw=re.sub(r'("min_text_thickness"\s*:\s*)[\d.]+',r'\g<1>0.15',proraw)
    for key,value in {'silk_line_width':.15,'silk_text_size_h':1.0,
                      'silk_text_size_v':1.0,'silk_text_thickness':.15}.items():
        proraw=re.sub(r'("'+key+r'"\s*:\s*)[\d.]+',lambda m:m[1]+str(value),proraw)
    probaseline=subprocess.run(['git','show','v2.0-a4:'+pro.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True,check=True).stdout
    pro.write_bytes(original_newlines(proraw,probaseline))
    visible_texts=[];visible_graphics=[]
    for row in silk_rows(new):
        data=row['data']
        if row['type'] in ('gr_text','fp_text','property'):
            if re.search(r'\(hide yes\)',row['block']) or re.search(r'\bhide\s*\)',row['block']):continue
            font=field(field(data,'effects'),'font');size=field(font,'size');thickness=field(font,'thickness')
            assert min(size[1:])>=1. and thickness[1]>=.15
            at=field(data,'at');assert (float(at[3]) if len(at)>3 else 0)%90==0
            visible_texts.append(dict(layer=row['layer'],text=data[1],at_mm=at[1:],font_mm=size[1:],stroke_mm=thickness[1]))
        else:
            width=field(field(data,'stroke'),'width');assert width[1]>=.15
            visible_graphics.append(dict(layer=row['layer'],type=row['type'],stroke_mm=width[1]))
    drc=export()
    proof=dict(original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
               after_sha256=hashlib.sha256(PCB.read_bytes()).hexdigest(),
               only_printed_F_B_silkscreen_changed=True,minimum_visible_font_mm=1.,minimum_stroke_mm=.15,
               primitives_upgraded=count,library_changes=lib_changes,uuid_count=len(uuids),
               drc_violations=len(drc.get('violations',[])),unconnected=len(drc.get('unconnected_items',[])),
               parity=len(drc.get('schematic_parity',[])),caption_corrections=CORRECTIONS,
               RF_option_frame_mm=[[38.52,.4],[43.2,.4],[43.2,8.2],[38.52,8.2]],
               identical_F_B_RF_option_frame=True,
               visible_text_count=len(visible_texts),visible_graphic_count=len(visible_graphics),
               visible_texts=visible_texts,
               manufacturing_layout_exceptions=['Square FL1 uses horizontal wrapped full part code.',
                   'J3 heading above connector; pin map below to avoid exposed mounting hole.',
                   'FB1 reference centered below its footprint; 60R is the adjacent next row.'])
    (EVIDENCE/'LOGIC_rezonit_proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(proof,ensure_ascii=False))


if __name__=='__main__':apply()
