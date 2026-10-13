"""Read-only final proof for the POWER annotation handoff."""
from pathlib import Path
import collections, hashlib, json, re
import label_power_a3 as p

p.setup();c=p.c;e=p.e
before=p.OUT/'before_legends_after_wide_pickups.kicad_pcb'
b=c.k.LoadBoard(str(p.PCB));c.HELD.append(b)

def children(path):
    src=path.read_text(encoding='utf8');depth=0;quoted=False;escape=False;start=None;out=[]
    for i,ch in enumerate(src):
        if quoted:
            if escape:escape=False
            elif ch=='\\':escape=True
            elif ch=='"':quoted=False
            continue
        if ch=='"':quoted=True
        elif ch=='(':
            if depth==1:start=i
            depth+=1
        elif ch==')':
            depth-=1
            if depth==1 and start is not None:
                out.append(src[start:i+1]);start=None
    return out

def forms(path):
    out=collections.defaultdict(list)
    for s in children(path):
        tag=re.match(r'\(([^\s()]+)',s)[1]
        # Board annotation is the one authorised mutation class. This excludes
        # neither footprint graphics nor edge cuts or any copper object.
        if tag.startswith('gr_') and re.search(r'\(layer "[FB]\.SilkS"\)',s):continue
        tokens=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^()\s]+',s)
        out[tag].append(hashlib.sha256('\x00'.join(tokens).encode()).hexdigest())
    return {tag:sorted(rows) for tag,rows in out.items()}

fa,fb=forms(before),forms(p.PCB)
changed={tag:[len(fa.get(tag,[])),len(fb.get(tag,[]))] for tag in fa.keys()|fb.keys() if fa.get(tag)!=fb.get(tag)}
assert not changed,changed
texts={c.uid(t):t for t in b.GetDrawings() if isinstance(t,c.k.PCB_TEXT)}
labels=json.loads((p.OUT/'label_changes.json').read_text(encoding='utf8'))['labels']
actual=[]
for row in labels:
    out=dict(row)
    for side,layer in (('front',c.k.F_SilkS),('back',c.k.B_SilkS)):
        item=row.get(side)
        if item and item['uuid'] not in texts:out[side]=None;continue
        if not item:continue
        t=texts[item['uuid']]
        assert t.GetLayer()==layer
        assert abs(t.GetTextAngle().AsDegrees()%180-row['axis_deg'])<.001
        assert min(c.xy(t.GetTextSize()))>=.8
        if side=='back':
            assert max(abs(x-y) for x,y in zip(c.xy(t.GetPosition()),row['body_center']))<.000003
            assert t.IsMirrored()
        else:assert not t.IsMirrored()
        assert row['ref'] in t.GetText()
    assert out.get('front') or out.get('back'),row['ref']
    actual.append(out)
assert len(actual)==len(list(b.GetFootprints()))==123
for t in texts.values():assert not re.search(r'\bG\d+\s*[x×]',t.GetText(),re.I)

segments={c.k.F_SilkS:[],c.k.B_SilkS:[]}
for s in b.GetDrawings():
    if isinstance(s,c.k.PCB_SHAPE) and s.GetLayer() in segments:
        segments[s.GetLayer()].append([c.xy(s.GetStart()),c.xy(s.GetEnd()),c.k.ToMM(s.GetWidth())])
assert sorted(segments[c.k.F_SilkS])==sorted(segments[c.k.B_SilkS])
outline=json.loads((p.OUT/'option_outline_changes.json').read_text(encoding='utf8'))
for g in outline['groups']:
    if g['option'].startswith('COLD'):assert 'R56' not in g['refs']
    pair=[t for t in texts.values() if t.GetText()==g['caption']]
    assert len(pair)==2
    assert c.xy(pair[0].GetPosition())==c.xy(pair[1].GetPosition())
    assert all(t.IsBold() for t in pair)
legend=json.loads((p.OUT/'power_connector_legends.json').read_text(encoding='utf8'))
assert all(r['uuid'] in texts for r in legend)
assert {r['owner'] for r in legend} >= {'J7','J8','J12','J101','J11','USB warning','branding'}
drc=p.OUT/'drc_POWER_labels_final.json'
d=json.loads(drc.read_text(encoding='utf8'))
counts={key:len(d.get(key,[])) for key in ('violations','unconnected_items','schematic_parity','ignored_checks')}
assert all(n==0 for n in counts.values()),counts
proof=dict(board_sha256=c.sha(p.PCB),strict_native_drc=counts,final_drc=str(drc.relative_to(p.ROOT)).replace('\\','/'),
    final_drc_sha256=c.sha(drc),annotation_baseline_sha256=c.sha(before),
    all_non_board_silkscreen_s_expressions_preserved=True,
    all_footprint_poses_pads_nets_library_models_preserved=True,
    all_copper_tracks_vias_zones_board_settings_edgecuts_preserved=True,
    component_label_coverage=len(actual),front_labels=sum(bool(r.get('front')) for r in actual),
    back_labels=sum(bool(r.get('back')) for r in actual),silk_font_min_mm=.8,
    component_labels_follow_actual_body_axis=True,back_labels_projected_body_centres=True,
    no_group_callouts=True,front_back_option_segments_equal=True,
    option_segments_per_side=len(segments[c.k.F_SilkS]),option_groups=[g['option'] for g in outline['groups']],
    R56_excluded_from_optional_frames=True,connector_back_pinouts=['J7','J8','J12','J101','J11'],
    branding_restored=True,single_jumper_USB_warning=True,
    final_views=['audit/a3_2026_10_13/power_labels/views/POWER_front_labels.png',
                 'audit/a3_2026_10_13/power_labels/views/POWER_back_labels_projected.png'])
views=p.OUT/'views'
if views.exists():proof['PNG_sha256']={f.name:c.sha(f) for f in views.glob('*.png')}
(p.OUT/'label_coverage_final.json').write_text(json.dumps(actual,indent=2,ensure_ascii=False),encoding='utf8')
(p.OUT/'POWER_A3_FREEZE.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps(proof,indent=2,ensure_ascii=False))
