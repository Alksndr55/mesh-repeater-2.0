"""Synchronize A3 descriptions; never change native CAD, stack or old evidence."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'audit/a3_2026_10_13'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true', help='Bind only fresh final native export manifests.')
    args = parser.parse_args()
    feature_path = ROOT / 'design/feature_a3_single_face_split_power.json'
    feature = read(feature_path)
    for ref in ['R1', 'R40', 'R41', 'R55']:
        p = feature['POWER_reference_updates'][ref]
        p['footprint'] = 'Meshcore:R_Vishay_WSL2512_A3'
        p['land_pattern'] = {'source': 'https://www.vishay.com/docs/30100/wsl.pdf#page=2',
                             'package': 'WSL2512, resistance >= 7 mOhm',
                             'pad_size_mm': [1.65, 3.68], 'pad_pitch_mm': 5.71,
                             'inner_gap_mm': 4.06, 'courtyard_margin_mm': 0.25}
    save(feature_path, feature)
    window = read(AUDIT / 'mechanics/shield_native_checks.json')['window']
    window = dict(window, quantity=1, kind='milled_through_window',
                  continuous_connected_foil_around_window=True)
    mpath = ROOT / 'docs/mechanical_selection.json'
    vpath = ROOT / 'docs/vertical_interconnect_selection.json'
    for path in [mpath, vpath]:
        old = AUDIT / 'mechanics' / ('before_a3_' + path.name)
        if not old.exists():
            old.write_bytes(path.read_bytes())
    m = read(mpath)
    m.update(date='2026-10-13', revision='V2.0-A3',
             status='A3_NATIVE_DESIGN_NOMINAL_STACK_SAMPLE_MATING_UNQUALIFIED')
    m['shield'].pop('pin_apertures', None)
    m['shield']['connector_window'] = window
    m['interboard']['pin_map'] = feature['interboard_pinmap']
    m['interboard']['connection'] = 'Direct vertical 1:1 through one milled plastic-body screen window; no ribbon cable.'
    m['interboard']['route'] = 'Common header plastic passes through the 17.2 x 6.8 mm R0.6 window; copper clearance 0.50 mm.'
    m['interboard'].pop('SYS_3V3_return', None)
    m['interboard']['power_branches'] = 'POWER J11 -> NT2: pins1/3 SYS, pins5/7 RADIO; INA219 supplied locally from SYS, pin8 NC.'
    m['interboard']['assembly_current_limit'] = (
        'Two SYS, two RADIO, three GND contacts; independent routed branches after one POWER J11. '
        'Generic header rating/contact resistance and current sharing require sample qualification. '
        'Parallel pins do not establish a multiplied assembly rating.')
    m['assembly']['J11'] = 'One removable POWER jumper; remove before USB, reinstall after USB disconnect.'
    m['assembly_cad_dimensions'] = {
        'status': 'A3_NATIVE_EXPORT_REFRESH_PENDING',
        'source': 'docs/mechanics/assembly_geometry_report.json',
        'note': 'A2 assembly remains historical until the report binds all three current A3 PCB hashes; '
                'the selected standoffs, washers and L35/H8.5 connector heights are unchanged.'}
    v = read(vpath)
    v.update(date='2026-10-13', revision='V2.0-A3',
             status='A3_NATIVE_DESIGN_SAMPLE_MATING_UNQUALIFIED')
    v['interboard_pinmap'] = feature['interboard_pinmap']
    v['feature_allowlist'] = 'design/feature_a3_single_face_split_power.json'
    v.pop('screen_apertures', None)
    v['screen_window'] = window
    v.pop('native_binding', None)
    v['native_binding'] = {'stage': 'A3_FINAL_FREEZE_PENDING',
                           'note': 'A2 input bindings retained in audit/a3_2026_10_13/mechanics/before_a3_vertical_interconnect_selection.json.'}
    if args.final:
        power_parts = {p['ref']: p for p in read(ROOT / 'design/MeshRepeater2_Power/model.json')['parts']}
        for ref in ['J11', 'NT2']:
            target = feature[ref + '_component']
            for key in ['x', 'y', 'rotation', 'footprint', 'schematic_uuid', 'sheet_path']:
                if key in power_parts[ref]:
                    target[key] = power_parts[ref][key]
        save(feature_path, feature)
        boards = {}
        for board in ['POWER', 'LOGIC', 'SHIELD']:
            stem = 'MeshRepeater2_' + board.title()
            export_path = ROOT / 'output' / board / (stem + '_exports.json')
            export = read(export_path)
            pcb = ROOT / export['pcb']
            assert hashlib.sha256(pcb.read_bytes()).hexdigest() == export['sha256'], board
            drc_path = export_path.with_name(stem + '_drc.json')
            drc = read(drc_path)
            assert all(not drc.get(k, []) for k in ['violations', 'unconnected_items', 'schematic_parity', 'ignored_checks']), board
            boards[board] = {'path': export['pcb'], 'sha256': export['sha256'],
                             'DRC': {'path': str(drc_path.relative_to(ROOT)),
                                     'sha256': hashlib.sha256(drc_path.read_bytes()).hexdigest()}}
        v['native_binding'] = {'stage': 'A3_FINAL_NATIVE_DRC_COMPLETE_SAMPLE_MATING_UNQUALIFIED',
                               'boards': boards,
                               'note': 'Fresh saved CAD/DRC; physical Ali connector qualification remains pending.'}
        m['assembly_cad_dimensions']['status'] = 'USE_NATIVE_REPORT_ONLY_IF_ALL_CURRENT_SOURCE_HASHES_MATCH'
        m['assembly_cad_dimensions']['note'] = 'Current assembly geometry is in the bound native report. Selected standoffs, washers and L35/H8.5 heights are unchanged. '
        m['unresolved'] = [s for s in m['unresolved'] if not s.startswith('Refresh final assembly geometry')]
    save(mpath, m)
    save(vpath, v)
    print('A3 metadata synchronized; stack and nominal selected connector dimensions preserved.')


if __name__ == '__main__':
    main()
