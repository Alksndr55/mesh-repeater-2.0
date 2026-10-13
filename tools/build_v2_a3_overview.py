"""Publish local A3 navigation only after matching saved-native acceptance proofs."""
from pathlib import Path
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'audit/a3_2026_10_13'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    names = ['schematic/combined_equivalence.json', 'native_board_parity.json',
             'independent/independent_final.json']
    proofs = {}
    for name in names:
        path = AUDIT / name
        doc = read(path)
        assert doc['ok'], name
        hashes = doc.get('inputs', doc.get('inputs_sha256', {}))
        for source, expected in hashes.items():
            assert sha(ROOT / source) == expected, (name, source)
        proofs[name] = {'sha256': sha(path), 'checks': len(doc['checks']),
                        'passed': sum(bool(c['pass']) for c in doc['checks'])}
    boards = {}
    for board in ['POWER', 'LOGIC', 'SHIELD']:
        stem = 'MeshRepeater2_' + board.title()
        project = ROOT / 'design' / stem
        out = ROOT / 'output' / board
        manifest = read(out / (stem + '_exports.json'))
        assert sha(ROOT / manifest['pcb']) == manifest['sha256']
        for row in manifest['artifacts']:
            assert sha(ROOT / row['path']) == row['sha256'], row['path']
        drc = read(out / (stem + '_drc.json'))
        assert all(not drc.get(k, []) for k in
                   ['violations', 'unconnected_items', 'schematic_parity', 'ignored_checks'])
        boards[board] = {'pcb': manifest['pcb'], 'sha256': manifest['sha256'],
                         'native_DRC': {'violations': 0, 'unconnected': 0,
                                        'parity': 0, 'ignored': 0}}
    bom = read(AUDIT / 'v2_a3_component_bom.json')
    assert bom['snapshot_stable'] and bom['baseline_positions_fully_accounted']
    assert all(c['pass'] for c in bom['feature_checks'])
    assert sha(ROOT / 'bom/V2_A3_COMPONENT_BOM.csv') == bom['bom_sha256']
    for source, expected in bom['inputs'].items():
        assert sha(ROOT / source) == expected, source
    assembly = ROOT / 'docs/mechanics/assembly_geometry_report.json'
    assembly_report = read(assembly)
    assert sha(ROOT / 'docs/mechanical_selection.json') == assembly_report['stack_contract_sha256']
    for row in assembly_report['inputs'].values():
        assert sha(ROOT / row['path']) == row['sha256']
        source = row['verified_pcb_source']
        assert sha(ROOT / source['path']) == source['sha256']
    geometry = assembly_report['artifacts']['MeshRepeater2_assembly']
    assert all(c['pass'] for c in geometry['pcb_intersections'])
    assert all(c['pass'] for c in geometry['hardware_to_component_clearances'])
    renders = read(ROOT / 'docs/mechanics/native_render_report.json')
    assert renders['revision'] == 'V2.0-A3' and len(renders['renders']) == 3
    for row in renders['renders']:
        assert sha(ROOT / row['image']) == row['image_sha256']
    transport = read(ROOT / 'docs/step_transport.json')
    for row in transport['files']:
        assert sha(ROOT / row['original_path']) == row['original_sha256']
        assert sha(ROOT / row['transport_path']) == row['gzip_sha256']
        assert row['original_sha256'] == row['verified_decompressed_sha256']
    acceptance = {'revision': 'V2.0-A3', 'date': '2026-10-13', 'ok': True,
                  'boards': boards, 'proofs': proofs, 'component_positions': bom['rows'],
                  'nominal_assembly': {'pcb_pairs': len(geometry['pcb_intersections']),
                                       'hardware_clearances': len(geometry['hardware_to_component_clearances']),
                                       'all_pass': True, 'report_sha256': sha(assembly),
                                       'physical_sample_mating_qualified': False},
                  'STEP_copper_fidelity_qualified': False,
                  'scope': 'Saved native CAD, electrical graph, footprints, marking, nominal assembly. '
                           'No bench EMI/load-step, purchased clone or generic connector mating claim.',
                  'J11': 'One removable POWER jumper, then SYS/RADIO copper star NT2. Remove before USB.'}
    (AUDIT / 'A3_FINAL_CHECKS.json').write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    links = [('../design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro', 'Проект POWER'),
             ('../design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro', 'Проект LOGIC'),
             ('../design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro', 'Проект SHIELD'),
             ('pdf/MeshRepeater2_Power_A3_schematic.pdf', 'Схема POWER A3'),
             ('pdf/MeshRepeater2_Logic_A3_schematic.pdf', 'Схема LOGIC A3'),
             ('../bom/V2_A3_COMPONENT_BOM.csv', 'BOM A3'),
             ('../docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md', 'Инструкция сборки'),
             ('../audit/a3_2026_10_13/A3_FINAL_CHECKS.json', 'Итоговые проверки'),
             ('../audit/a3_2026_10_13/independent/independent_final.json', 'Независимый аудит')]
    views = [('POWER/MeshRepeater2_Power_front.png', 'POWER — медь и маркировка, сторона компонентов'),
             ('POWER/MeshRepeater2_Power_back.png', 'POWER — обратная сторона, проекция маркировки'),
             ('LOGIC/MeshRepeater2_Logic_front.png', 'LOGIC — сторона компонентов'),
             ('LOGIC/MeshRepeater2_Logic_back.png', 'LOGIC — обратная сторона'),
             ('../audit/a3_2026_10_13/logic/views/LOGIC_back_labels_projected.png', 'LOGIC — маркировка под своими компонентами'),
             ('SHIELD/MeshRepeater2_Shield_front.png', 'SHIELD — окно и русская памятка')]
    power_labels = AUDIT / 'power_labels/views/POWER_back_labels_projected.png'
    if power_labels.exists():
        views.insert(2, ('../audit/a3_2026_10_13/power_labels/views/POWER_back_labels_projected.png',
                         'POWER — маркировка под своими компонентами'))
    if assembly.exists():
        report = read(assembly)
        current = all(sha(ROOT / row['verified_pcb_source']['path']) == row['verified_pcb_source']['sha256']
                      for row in report['inputs'].values())
        if current:
            views.extend([('../docs/mechanics/MeshRepeater2_assembly_native_3D.png', 'Сборка A3 — нативная CAD-геометрия'),
                          ('../docs/mechanics/MeshRepeater2_exploded_native_3D.png', 'Разнесённая сборка A3')])
    nav = ''.join(f'<a href="{html.escape(p)}">{html.escape(t)}</a>' for p, t in links)
    figures = ''.join(f'<figure><figcaption>{html.escape(t)}</figcaption><a href="{html.escape(p)}"><img loading="lazy" src="{html.escape(p)}" alt="{html.escape(t)}"></a></figure>' for p, t in views)
    page = f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mesh Repeater 2.0 — A3</title><style>body{{margin:0;background:#f2f4f6;color:#17232f;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1600px;margin:auto;padding:24px}}h1{{margin:0 0 10px;font-size:28px}}nav{{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}}nav a{{background:white;border:1px solid #b7c4cc;border-radius:5px;padding:7px 12px;color:#064c75;text-decoration:none}}.warning{{background:#fff1c7;border-left:5px solid #c17a00;padding:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:18px}}figure{{margin:0;background:white;border:1px solid #cbd4dc;border-radius:5px;overflow:hidden}}figcaption{{padding:12px;font-weight:600}}img{{display:block;width:100%;height:auto}}@media(max-width:550px){{.grid{{grid-template-columns:1fr}}main{{padding:12px}}}}</style><main>
<h1>Mesh Repeater 2.0 · V2.0-A3</h1><p>Designed by @Alksndritm · POWER и LOGIC 90×60 мм · KiCad 10.0.6</p>
<p class="warning"><b>Перед подключением USB снять единственную J11 на POWER.</b> Вернуть после отключения USB. После J11 медная звезда NT2 разделяет SYS_3V3 и RADIO_3V3.</p>
<p>Все компоненты POWER на одной стороне. Шунты 2512; INA219 на POWER. Контакты межплатного разъёма: 1/3 SYS, 5/7 RADIO, 2/4/6 GND, 8 NC, 9 BAT, 10 SDA, 11 MODE, 12 SCL. Экран имеет одно окно 17,2×6,8 мм под пластиковую планку.</p>
<p>DRC трёх плат: 0 нарушений, 0 неразведённых цепей, 0 исключённых проверок. Схемы POWER/LOGIC: ERC 0. Независимый аудит: {proofs['independent/independent_final.json']['passed']}/{proofs['independent/independent_final.json']['checks']}. Геометрия, маркировка и GPIO проверены по сохранённым нативным файлам. EMI и работа реальной сборки требуют испытаний; согласованные ограничения LTO сохранены.</p>
<nav>{nav}</nav><div class="grid">{figures}</div></main></html>'''
    target = ROOT / 'output/V2_OVERVIEW_RU.html'
    target.write_text(page, encoding='utf-8')
    print(json.dumps({'ok': True, 'boards': 3, 'BOM_positions': bom['rows'], 'overview': str(target.relative_to(ROOT)), 'proofs': proofs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
