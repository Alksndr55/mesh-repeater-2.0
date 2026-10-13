"""Record an agreed native-CAD freeze; this never edits CAD or reports PASS."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = []
    for name in ['Power', 'Logic', 'Shield']:
        project = ROOT / 'design' / ('MeshRepeater2_' + name)
        files.extend(p for p in project.rglob('*') if p.is_file() and
                     (p.suffix in ['.kicad_pcb', '.kicad_pro', '.kicad_dru', '.kicad_sch', '.kicad_mod', '.kicad_sym']
                      or p.name in ['model.json', 'fp-lib-table', 'sym-lib-table']))
    files.extend(ROOT / p for p in ['docs/mechanical_selection.json',
                                   'docs/vertical_interconnect_selection.json',
                                   'design/feature_a3_single_face_split_power.json'])
    value = {'ALL_CAD_FROZEN': True, 'revision': 'V2.0-A3', 'date': '2026-10-13',
             'scope': 'Owner-confirmed CAD freeze for fresh independent read-only checks; not a PASS claim.',
             'inputs_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(set(files))}}
    target = ROOT / 'audit/a3_2026_10_13/ALL_CAD_FROZEN.json'
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'native_files_frozen': len(files), 'manifest': str(target.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
