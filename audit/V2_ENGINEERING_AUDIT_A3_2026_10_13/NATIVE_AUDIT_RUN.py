"""Fresh KiCad checks on isolated copies. This file is an audit attachment."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, stem):
    start = time.monotonic()
    result = subprocess.run([str(CLI), *map(str, args)], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    (OUT / (stem + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    return {'command': [str(CLI), *map(str, args)], 'exit_code': result.returncode,
            'seconds': round(time.monotonic() - start, 3), 'log': stem + '.log'}


def main():
    result = {'KiCad': subprocess.check_output([str(CLI), 'version']).decode().strip(),
              'scope': 'Saved-copy and in-memory-refilled-copy checks; original projects never opened for writing.',
              'boards': {}}
    for name in ['POWER', 'LOGIC', 'SHIELD']:
        project = 'MeshRepeater2_' + name.title()
        source = ROOT / 'design' / project
        copy = OUT / 'CAD_CHECK' / project
        if copy.exists():
            raise RuntimeError('Refusing to overwrite an earlier verification copy: ' + str(copy))
        shutil.copytree(source, copy)
        pcb = copy / (project + '.kicad_pcb')
        settings = json.loads((copy / (project + '.kicad_pro')).read_text(encoding='utf-8'))
        design = settings.get('board', {}).get('design_settings', {})
        state = {'original_pcb': str((source / pcb.name).relative_to(ROOT)),
                 'original_sha256': digest(source / pcb.name),
                 'copy_sha256_before': digest(pcb),
                 'rules': design.get('rules', {}),
                 'rule_severities': design.get('rule_severities', {}),
                 'ignored_rule_types': [k for k, v in design.get('rule_severities', {}).items() if v == 'ignore'],
                 'drc_exclusions': design.get('drc_exclusions', []),
                 'net_settings': settings.get('net_settings', {}),
                 'custom_rules': {p.name: p.read_text(encoding='utf-8') for p in source.glob('*.kicad_dru')}}
        for mode in ['saved', 'refilled']:
            target = OUT / (name + '_DRC_' + mode + '.json')
            args = ['pcb', 'drc', '--format', 'json', '--severity-all', '--all-track-errors',
                    '--exit-code-violations', '-o', target]
            if name != 'SHIELD':
                args.append('--schematic-parity')
            if mode == 'refilled':
                args.append('--refill-zones')
            execution = run([*args, pcb], name + '_DRC_' + mode)
            doc = json.loads(target.read_text(encoding='utf-8'))
            state[mode] = {**execution, 'report': target.name,
                           'counts': {k: len(doc.get(k, [])) for k in
                                      ['violations', 'unconnected_items', 'schematic_parity', 'ignored_checks']}}
        if name != 'SHIELD':
            schema = pcb.with_suffix('.kicad_sch')
            target = OUT / (name + '_ERC.json')
            execution = run(['sch', 'erc', '--format', 'json', '--severity-all',
                             '--exit-code-violations', '-o', target, schema], name + '_ERC')
            doc = json.loads(target.read_text(encoding='utf-8'))
            violations = [v for s in doc.get('sheets', []) for v in s.get('violations', [])]
            state['ERC'] = {**execution, 'report': target.name,
                            'violations': len(violations), 'details': violations}
            target = OUT / (name + '_netlist.xml')
            state['netlist_export'] = run(['sch', 'export', 'netlist', '--format', 'kicadxml',
                                          '-o', target, schema], name + '_netlist')
        state['copy_sha256_after'] = digest(pcb)
        state['original_sha256_after'] = digest(source / pcb.name)
        assert state['original_sha256_after'] == state['original_sha256']
        result['boards'][name] = state
        (OUT / 'NATIVE_CHECKS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'board': name, 'saved': state['saved']['counts'],
                          'refilled': state['refilled']['counts'],
                          'ERC': state.get('ERC', {}).get('violations')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
