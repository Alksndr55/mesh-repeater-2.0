from pathlib import Path
import hashlib,json,os,subprocess,datetime
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
b=json.loads((OUT/'source_state_before.json').read_text('utf-8'))
env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,env=env)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
changed=[]
for rel,old in b['sources_sha256'].items():
 p=ROOT/rel
 if not p.is_file():changed.append({'file':rel,'before':old,'after':None})
 else:
  new=sha(p)
  if new!=old:changed.append({'file':rel,'before':old,'after':new})
index=Path(b['index_path']);raw_index=sha(index)
entries=git('ls-files','--stage','-z');entries_hash=hashlib.sha256(entries).hexdigest()
status=git('status','--porcelain=v2','-z','--untracked-files=all').decode('utf-8','surrogateescape')
before_set=set(filter(None,b['status_porcelain_v2_z'].split('\0')))
after_set=set(filter(None,status.split('\0')))
removed=sorted(before_set-after_set)
added=sorted(after_set-before_set)
unexpected=[]
for entry in added:
 if not entry.startswith('? '):unexpected.append(entry);continue
 path=entry[2:].replace('\\','/')
 if path!=b['allowed_new_report'] and not path.startswith(b['allowed_new_attachments_prefix']):unexpected.append(entry)
new_design=[p.relative_to(ROOT).as_posix() for p in (ROOT/'design').rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in b['sources_sha256']]
head=git('rev-parse','HEAD').decode().strip();branch=git('branch','--show-current').decode().strip()
checks={'captured_sources_unchanged':not changed,'no_new_design_files':not new_design,'raw_index_unchanged':raw_index==b['index_file_sha256'],'logical_index_unchanged':entries_hash==b['index_entries_sha256'],'HEAD_unchanged':head==b['HEAD'],'branch_unchanged':branch==b['branch'],'existing_git_status_unchanged':not removed,'new_git_entries_only_in_allowed_report_paths':not unexpected}
d={'ok':all(checks.values()),'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files_checked':len(b['sources_sha256']),'checks':checks,'changed_or_missing':changed,'new_design_files':new_design,'raw_index_sha256_before':b['index_file_sha256'],'raw_index_sha256_after':raw_index,'logical_index_sha256_before':b['index_entries_sha256'],'logical_index_sha256_after':entries_hash,'HEAD':head,'branch':branch,'removed_or_changed_existing_status_entries':removed,'new_status_entries_count':len(added),'unexpected_new_status_entries':unexpected,'allowed_report':b['allowed_new_report'],'allowed_attachments_prefix':b['allowed_new_attachments_prefix'],'limit':'Existing captured files and complete Git status/index checked; newly created audit attachments are deliberately not treated as source changes.'}
(OUT/'SOURCE_PRESERVATION_AFTER.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf-8')
(OUT/'git_status_after.z').write_bytes(status.encode('utf-8','surrogateescape'))
print(json.dumps({'ok':d['ok'],'files_checked':d['files_checked'],'checks':checks,'changed':len(changed),'unexpected_new':len(unexpected)},ensure_ascii=False))
if not d['ok']:raise SystemExit(1)
