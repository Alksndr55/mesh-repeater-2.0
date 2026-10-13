"""Package an exact A3 commit and verified lossless STEP exports; no network writes."""
from pathlib import Path
import argparse,gzip,hashlib,json,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='Mesh-Repeater-2.0-A3-project.zip'
PREFIX='Mesh-Repeater-2.0-A3/'
def git(*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 commit=git('rev-parse',a.commit+'^{commit}').decode().strip();a.out.mkdir(parents=True,exist_ok=True)
 package=a.out/NAME
 if package.exists():raise FileExistsError('Preserve existing release archive: '+str(package))
 tracked=[n for n in git('ls-tree','-rz','--name-only',commit).decode('utf-8').split('\0') if n]
 assert not any('/CAD_CHECK/' in n or ('/SOFTWARE_BOM_BUILD_TMP/' in n and not n.endswith('.log')) or n.endswith('/git_diff_before.patch') for n in tracked)
 for record in git('ls-tree','-rlz',commit).decode('utf-8').split('\0'):
  if not record:continue
  fields,n=record.split('\t',1);size=int(fields.split()[-1])
  assert size<100*1024*1024,('GitHub blob too large',n)
 subprocess.run(['git','archive','--format=zip','--prefix='+PREFIX,'--output='+str(package.resolve()),commit],cwd=ROOT,check=True)
 transport=json.loads(git('show',commit+':docs/step_transport.json'))
 manifest={'release':'Mesh Repeater 2.0 A3','tag':'v2.0-a3','commit':commit,'tree':git('rev-parse',commit+'^{tree}').decode().strip(),'scope':'Exact tracked commit plus four losslessly restored STEP exports; standard KiCad 10 libraries required. Prototype limitations retained.','tracked_files':len(tracked),'restored_STEP_files':[],'files':{}}
 with zipfile.ZipFile(package,'a',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  assert {i.filename for i in z.infolist() if not i.is_dir()}=={PREFIX+n for n in tracked}
  for record in transport['files']:
   rawgz=z.read(PREFIX+record['transport_path']);assert len(rawgz)==record['gzip_size_bytes'];assert digest(rawgz)==record['gzip_sha256']
   raw=gzip.decompress(rawgz);assert len(raw)==record['original_size_bytes'];assert digest(raw)==record['original_sha256']
   assert PREFIX+record['original_path'] not in z.namelist(),('Duplicate STEP',record['original_path'])
   z.writestr(PREFIX+record['original_path'],raw);manifest['restored_STEP_files'].append(record['original_path'])
  for i in z.infolist():
   if i.is_dir():continue
   with z.open(i) as f:h=hashlib.file_digest(f,'sha256').hexdigest()
   manifest['files'][i.filename[len(PREFIX):]]={'size':i.file_size,'sha256':h}
  z.writestr(PREFIX+'RELEASE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
 with zipfile.ZipFile(package) as z:
  assert z.testzip() is None
  required=['README.md','docs/V2_A3_RELEASE_RU.md','bom/V2_A3_COMPONENT_BOM.csv','output/pdf/MeshRepeater2_Power_A3_schematic.pdf','output/pdf/MeshRepeater2_Logic_A3_schematic.pdf']
  required += [f'design/MeshRepeater2_{n}/MeshRepeater2_{n}.kicad_pro' for n in ['Power','Logic','Shield']]
  required += [f'design/MeshRepeater2_{n}/MeshRepeater2_{n}.kicad_pcb' for n in ['Power','Logic','Shield']]
  assert all(PREFIX+n in z.namelist() for n in required)
 with package.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 checksum=a.out/(NAME+'.sha256.txt');checksum.write_text(h+'  '+NAME+'\n','ascii')
 result={'ok':True,'commit':commit,'package':str(package.resolve()),'sha256':h,'size_bytes':package.stat().st_size,'tracked_files':len(tracked),'restored_STEP_files':manifest['restored_STEP_files'],'manifest_files':len(manifest['files']),'CRC_check':'PASS'}
 (a.out/'build_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
