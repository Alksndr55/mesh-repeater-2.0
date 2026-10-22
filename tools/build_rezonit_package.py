"""Verify and package only current A4-FAB1 bare-board manufacturing data.

No source edits, no old CAD, no schematic/assembly/paste files, no upload.
The full packet and three flat per-board CAM ZIPs are separate deliverables.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.publication_tmp/fab_deps'))
import sexpdata as sx

BASE = '261c9850f0552453948c2c04cb42d1e77ffee5f4'
REVISION = 'A4-FAB1'
PACK = ROOT / 'manufacturing/Rezonit_A4_2026-10-14'
AUDIT = ROOT / 'audit/manufacturing_a4_2026_10_14'
OUTPUT = ROOT / 'manufacturing'
NAMES = ('POWER', 'LOGIC', 'SHIELD')
SILK = {'F.SilkS', 'B.SilkS'}
PRINTED = {'gr_text', 'fp_text', 'property', 'gr_text_box', 'fp_text_box'} | {
    prefix + suffix for prefix in ('gr_', 'fp_')
    for suffix in ('line', 'arc', 'rect', 'poly', 'circle', 'curve')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def children(node, name):
    return [a for a in node if isinstance(a, list) and a and str(a[0]) == name]


def first(node, name):
    return next(iter(children(node, name)), None)


def outside_silk(node):
    if not isinstance(node, list):
        return node
    layer = first(node, 'layer')
    if node and str(node[0]) in PRINTED and layer and str(layer[1]) in SILK:
        return None
    if node and str(node[0]) == 'title_block':
        return [a if not isinstance(a, list) or not a or str(a[0]) not in ('date', 'rev')
                else [a[0], 'REVISION_METADATA'] for a in node]
    result = []
    for child in node:
        kept = outside_silk(child)
        if kept is not None:
            result.append(kept)
    return result


def identity(tree):
    result = {}
    for fp in children(tree, 'footprint'):
        properties = {str(p[1]): str(p[2]) for p in children(fp, 'property')}
        result[properties['Reference']] = properties['Value']
    return result


def board_checks(name):
    source = ROOT / f'design/MeshRepeater2_{name.title()}/MeshRepeater2_{name.title()}.kicad_pcb'
    relative = source.relative_to(ROOT).as_posix()
    old = subprocess.run(['git', 'show', f'{BASE}:{relative}'], cwd=ROOT,
                         check=True, capture_output=True).stdout
    current = source.read_bytes()
    oldtree = sx.loads(old.decode('utf-8'))
    tree = sx.loads(current.decode('utf-8'))
    assert outside_silk(oldtree) == outside_silk(tree), f'{name}: non-silk PCB change'
    title = first(tree, 'title_block')
    assert first(title, 'rev')[1] == 'V2.0-A4-FAB1'
    assert first(title, 'date')[1] == '2026-10-14'
    assert identity(oldtree) == identity(tree), f'{name}: component identity changed'
    uuids = re.findall(rb'\(uuid "([^"]+)"\)', current)
    assert not [a for a, n in Counter(uuids).items() if n > 1], f'{name}: duplicate UUID'
    checked = json.loads((AUDIT / 'exports_checked.json').read_text('utf-8'))['boards'][name]
    assert checked['source_sha256'] == sha(current), f'{name}: stale CAM'
    assert checked['holes_match_saved_CAD']
    assert not any(checked['DRC'].values()), f'{name}: DRC issues'
    measures = json.loads((AUDIT / 'geometry_review.json').read_text('utf-8'))[name]
    assert measures['sha256'] == sha(current), f'{name}: stale geometry'
    assert measures['silk_min_size_mm'] >= 1.0
    assert measures['silk_min_thickness_mm'] >= .15
    assert not measures['silk_objects_below_rezonit_published_1_0_height_or_0_15_stroke']
    assert not measures['silk_graphics_below_0_15_stroke']
    drc = json.loads((AUDIT / f'{name}_fresh_drc.json').read_text('utf-8'))
    assert not drc.get('ignored_checks', []), f'{name}: ignored DRC'
    return {'path': relative, 'source_sha256': sha(current),
            'base_source_sha256': sha(old), 'only_printed_silkscreen_and_revision_metadata_changed': True,
            'component_identities_and_values_unchanged': True, 'UUID_unique': True,
            'DRC': checked['DRC'], 'DRC_ignored_checks': [],
            'holes_match_saved_CAD': True,
            'physical_copper_layers': checked['physical_copper_layers'],
            'PTH_count': checked['drill_counts']['PTH']['holes'],
            'NPTH_count': checked['drill_counts']['NPTH']['holes'],
            'min_silk_text_size_mm': measures['silk_min_size_mm'],
            'min_silk_text_stroke_mm': measures['silk_min_thickness_mm'],
            'min_silk_graphic_stroke_mm': measures['silk_min_graphic_stroke_mm']}


def write_zip(destination, files):
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for member, data in sorted(files.items()):
            item = zipfile.ZipInfo(member, (2026, 10, 14, 12, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for member, data in files.items():
            assert archive.read(member) == data
    digest = sha(destination.read_bytes())
    destination.with_suffix('.zip.sha256.txt').write_text(f'{digest}  {destination.name}\n', 'ascii')
    return {'name': destination.name, 'bytes': destination.stat().st_size,
            'sha256': digest, 'members': len(files), 'CRC_and_member_bytes_verified': True}


def main():
    boards = {name: board_checks(name) for name in NAMES}
    proof = {'revision': REVISION, 'date_local': '2026-10-14', 'timezone': 'Asia/Omsk',
             'base_tag': 'v2.0-a4', 'base_commit': BASE,
             'quantity_per_board': 5, 'sets': 5, 'total_boards': 15,
             'nominal_FR4_with_copper_excluding_mask_mm': 1.5,
             'finish': 'ENIG', 'assembly_included': False,
             'boards': boards, 'order_submitted': False,
             'manufacturer_CAM_acceptance_not_claimed': True}
    (PACK / 'VERIFICATION.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    docs = ('READ_ME.md', 'ORDER_PARAMETERS.csv', 'ORDER_MESSAGE_RU.txt',
            'TECHNICAL_REQUIREMENTS_RU.pdf', 'FABRICATION_DRAWINGS_RU.pdf', 'VERIFICATION.json')
    files = {name: (PACK / name).read_bytes() for name in docs}
    licenses = ('LICENSE', 'LICENSE.md', 'THIRD_PARTY_NOTICES.md',
                'LICENSES/CC-BY-NC-SA-4.0.txt', 'docs/LICENSING_RU_EN.md',
                'LICENSES/CERN-OHL-P-2.0.txt', 'LICENSES/CC-BY-SA-4.0.txt',
                'LICENSES/KiCad-Libraries-LICENSE.md')
    for relative in licenses:
        data = (ROOT / relative).read_bytes()
        target = PACK / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[relative] = data
    attribution = ("# Производственные данные Mesh Repeater 2.0 A4-FAB1\n\n"
        "Designed by @Alksndritm / Alksndr55. Текущая конструкция: POWER, LOGIC и SHIELD, по 90 x 60 мм.\n"
        "Основа совместимости и унаследованных материалов: FakeTec V6 Rev C, shimonomihs / ShimonHoranek; CERN-OHL-P-2.0.\n"
        "Исходный проект: https://github.com/gargomoma/fakeTec_pcb/issues/26\n"
        "Mesh Repeater: https://github.com/Alksndr55/mesh-repeater-2.0\n\n"
        "Для A4-FAB1 переработана маркировка под 1,0 x 1,0 мм / 0,15 мм, обновлены ее настроечные минимумы и дата/ревизия.\n"
        "Медь, маска, номиналы, электрические связи и геометрия компонентов сохранены относительно v2.0-a4.\n"
        "Приложены актуальные LICENSE, LICENSE.md, THIRD_PARTY_NOTICES.md, тексты LICENSES и docs/LICENSING_RU_EN.md.\n"
        "Уведомления сохраняют происхождение предыдущих материалов; упоминания редакции 1.0 относятся к истории.\n"
        "Собственные оригинальные материалы и принадлежащие автору оригинальные дополнения: CC BY-NC-SA 4.0.\n"
        "Изготовление по заказу для личных некоммерческих нужд разрешено на условиях docs/LICENSING_RU_EN.md.\n"
        "Коммерческое использование собственных материалов, коммерческий выпуск и продажа требуют отдельного письменного разрешения Alksndr55 / @Alksndritm.\n"
        "Сторонние материалы сохраняют исходные лицензии; их права не ограничиваются условиями NC собственных материалов.\n")
    files['ATTRIBUTION.md'] = attribution.encode('utf-8')
    (PACK / 'ATTRIBUTION.md').write_bytes(files['ATTRIBUTION.md'])
    for board in NAMES:
        cam_files = {p.name: p.read_bytes() for p in sorted((PACK / board / 'cam').iterdir())
                     if p.suffix in ('.gbr', '.drl', '.gbrjob')}
        expected_gbr = 5 if board == 'SHIELD' else 7
        assert sum(name.endswith('.gbr') for name in cam_files) == expected_gbr
        assert sum(name.endswith('.drl') for name in cam_files) == (2 if board == 'LOGIC' else 1)
        assert sum(name.endswith('.gbrjob') for name in cam_files) == 1
        for name, data in cam_files.items():
            files[f'{board}/cam/{name}'] = data
        for side in ('front', 'back'):
            image = PACK / board / 'reference' / f'{board}_{side}_CAM.png'
            files[f'{board}/reference/{image.name}'] = image.read_bytes()
    manifest = {'revision': REVISION, 'base_commit': BASE,
                'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in sorted(files.items())}}
    files['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (PACK / 'MANIFEST.json').write_bytes(files['MANIFEST.json'])
    output = {}
    for board in NAMES:
        per_board = {Path(name).name: data for name, data in files.items()
                     if name.startswith(f'{board}/cam/')}
        note = (f'Mesh Repeater 2.0 {REVISION}: {board}\nQuantity: 5 bare PCBs, 90x60 mm.\n'
                f'FR4 nominal 1.5 mm including copper, excluding soldermask. ENIG.\n'
                f'Copper: {1 if board == "SHIELD" else 2} physical layer(s), 35 um foil.\n'
                'Green soldermask, white silkscreen both faces. Gerber/drill absolute origin, mm, do not mirror.\n'
                + ('SHIELD: no rear copper or rear mask; rear silkscreen on FR4. Four NPTH3.2 mm; internal routed window17.2x6.8 mm R0.6.\n'
                   if board == 'SHIELD' else 'PTH and NPTH are separate. Vias tented both sides; no resin fill.\n')
                + ('POWER requires advanced 35um process: mintrace/annular PAD ring0.15 mm.\n' if board == 'POWER' else '')
                + 'See TECHNICAL_REQUIREMENTS_RU.pdf and FABRICATION_DRAWINGS_RU.pdf from the full package.\n'
                + f'Source PCB SHA256: {boards[board]["source_sha256"]}\n')
        per_board['ORDER_README.txt'] = note.encode('utf-8')
        for relative in (*licenses, 'ATTRIBUTION.md'):
            per_board[relative] = files[relative]
        output[board] = write_zip(OUTPUT / f'Mesh-Repeater-2.0-{REVISION}-{board}-Rezonit.zip', per_board)
    output['full'] = write_zip(OUTPUT / f'Mesh-Repeater-2.0-{REVISION}-Rezonit-5sets.zip', files)
    (AUDIT / 'package_result.json').write_text(json.dumps({'ok': True, 'archives': output}, indent=2) + '\n', 'utf-8')
    print(json.dumps({'ok': True, 'archives': output}, indent=2))


if __name__ == '__main__':
    main()
