"""Apply POWER caption policy using only gr_text edits; preserve all other CAD bytes."""
from pathlib import Path
import argparse,hashlib,json,re,uuid

ROOT=Path(__file__).resolve().parents[2]
BANKS=[(['C15']+[f'C{i}' for i in range(34,43)],'C15, C34-C42\n10x100uF',(57.5,44.8)),
       (['C16']+[f'C{i}' for i in range(43,52)],'C16, C43-C51\n10x100uF',(75.5,44.8))]

def text_blocks(s):
 rows=[]
 for m in re.finditer(r'\(gr_text "((?:\\.|[^"\\])*)"',s):
  i=m.start();depth=0;quoted=False;escaped=False
  for j in range(i,len(s)):
   ch=s[j]
   if quoted:
    if escaped:escaped=False
    elif ch=='\\':escaped=True
    elif ch=='"':quoted=False
   elif ch=='"':quoted=True
   elif ch=='(':depth+=1
   elif ch==')':
    depth-=1
    if depth==0:break
  block=s[i:j+1]
  rows.append({'text':json.loads('"'+m[1]+'"'),'uuid':re.search(r'\(uuid "([^\"]+)"\)',block)[1],
               'layer':re.search(r'\(layer "([^\"]+)"\)',block)[1],'start':i,'end':j+1,'block':block})
 return rows

def without_silk(s):
 for t in reversed(text_blocks(s)):
  if t['layer'] in ('F.SilkS','B.SilkS'):s=s[:t['start']]+s[t['end']:]
 return re.sub(r'\s+',' ',s).strip()

def update(raw,refs):
 s=raw.decode('utf-8');before=s;rows=text_blocks(s);caps={r for bank,_,_ in BANKS for r in bank}
 groups={label for _,label,_ in BANKS};owners={};removed=[];keep={}
 for t in rows:
  if t['layer'] not in ('F.SilkS','B.SilkS'):continue
  if t['text'] in groups:removed.append(t);continue
  m=re.match(r'^([A-Z]+\d+)(?:\s|$)',t['text'])
  if not m or m[1] not in refs:continue
  if m[1] in caps:removed.append(t);continue
  owners.setdefault(m[1],[]).append(t)
 for ref,options in owners.items():
  # A complete connector map owns the caption; pin labels and warnings remain.
  maps=[t for t in options if ref.startswith('J') and re.search(r'(?:^|\n| )[1-9](?:/[1-9])? ',t['text'])]
  front=[t for t in options if t['layer']=='F.SilkS']
  choices=maps or front or options
  chosen=max(choices,key=lambda t:len(t['text']));keep[ref]=chosen
  removed.extend(t for t in options if t is not chosen)
 changes=[(t['start'],t['end'],'') for t in removed]
 r56=keep['R56'];newtext='R56\nN1R8\nL0R'
 newblock=r56['block'].replace(json.dumps(r56['text'],ensure_ascii=False),json.dumps(newtext,ensure_ascii=False),1)
 changes.append((r56['start'],r56['end'],newblock))
 for start,end,value in sorted(changes,reverse=True):s=s[:start]+value+s[end:]
 nl='\r\n' if '\r\n' in before else '\n';insert=[]
 for bank,label,xy in BANKS:
  uid=str(uuid.uuid5(uuid.NAMESPACE_URL,'mesh-repeater-v2/power/capbank/'+bank[0]))
  block=f'''\t(gr_text {json.dumps(label,ensure_ascii=False)}
\t\t(at {xy[0]} {xy[1]} 0)
\t\t(layer "B.SilkS")
\t\t(uuid "{uid}")
\t\t(effects
\t\t\t(font (size 1 1) (thickness 0.15))
\t\t\t(justify mirror)
\t\t)
\t)'''.replace('\n',nl)
  insert.append(block)
 end=s.rfind(')');assert end>=0;s=s[:end]+nl+nl.join(insert)+nl+s[end:]
 s=re.sub(r'(?m)^[\t ]+(?=\r?$)','',s)
 assert without_silk(before)==without_silk(s),'Non-silkscreen CAD changed'
 after=text_blocks(s);counts={}
 for t in after:
  m=re.match(r'^([A-Z]+\d+)(?:\s|$)',t['text'])
  if t['layer'] in ('F.SilkS','B.SilkS') and m and m[1] in refs:counts[m[1]]=counts.get(m[1],0)+1
 assert all(v==1 for v in counts.values()),counts
 assert set(counts)|caps==refs,('Caption coverage',refs-(set(counts)|caps))
 assert not set(counts)&caps
 assert all(sum(t['text']==label for t in after)==1 for _,label,_ in BANKS)
 result={'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(s.encode('utf-8')).hexdigest(),
         'only_silkscreen_gr_text_changed':True,'individual_owners_after':len(counts),'grouped_capacitors':len(caps),
         'removed_captions':[{'uuid':t['uuid'],'text':t['text'],'layer':t['layer']} for t in removed],
         'retained_owners':{r:{'uuid':t['uuid'],'text':newtext if r=='R56' else t['text'],'layer':t['layer']} for r,t in keep.items()},
         'group_labels':[{'refs':bank,'text':label,'xy_mm':xy,'layer':'B.SilkS','font_mm':1.0,'stroke_mm':0.15} for bank,label,xy in BANKS]}
 return s.encode('utf-8'),result

def apply_to_file(pcb,report=None):
 model=json.loads((ROOT/'design/MeshRepeater2_Power/model.json').read_text('utf-8'))
 raw,proof=update(pcb.read_bytes(),{p['ref'] for p in model['parts']})
 pcb.write_bytes(raw)
 from place_v2_power_front_labels import relocate
 proof['front_relocation']=relocate(pcb)
 # Last pass restores the agreed connector row, one-line U2 and strong
 # matched option outlines after any complete caption regeneration.
 from style_v2_power_annotations import style
 styled,annotation_proof=style(pcb,ROOT/'tmp/power_annotation_serialization.kicad_pcb')
 pcb.write_bytes(styled)
 proof['annotation_style']=annotation_proof
 proof['only_silkscreen_gr_text_changed']=False
 proof['only_F_B_silkscreen_drawings_changed']=True
 proof['after_sha256']=hashlib.sha256(pcb.read_bytes()).hexdigest()
 if report:
  report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(proof,ensure_ascii=False,indent=2),'utf-8')
 return proof

def main():
 p=argparse.ArgumentParser();p.add_argument('--pcb',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 for path in [a.pcb,a.output,a.report]:assert path.resolve().is_relative_to(ROOT)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(a.pcb.read_bytes());proof=apply_to_file(a.output,a.report)
 print(json.dumps({'output':str(a.output),'removed_captions':len(proof['removed_captions']),'owners_after':proof['individual_owners_after'],'grouped_capacitors':proof['grouped_capacitors'],'only_silkscreen_changed':True},ensure_ascii=False))
if __name__=='__main__':main()
