"""Build a curated A4 release from Git blobs, never from the working directory.

Only current projects and their actually referenced local libraries are included.
No repository-wide git archive, historical CAD, build generators or nested gzip
transports are copied. Presentation links are adapted for the standalone package;
all editable CAD, firmware and other binary source bytes remain unchanged.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import quote, unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Mesh-Repeater-2.0-A4-project.zip'
PREFIX = 'Mesh-Repeater-2.0-A4/'
REPOSITORY = 'https://github.com/Alksndr55/mesh-repeater-2.0'
MAX_BLOB = 100 * 1024 * 1024
PROJECTS = ('Power', 'Logic', 'Shield')
TEXT_SUFFIXES = {'.md', '.txt', '.json', '.csv', '.kicad_pro', '.kicad_pcb',
                 '.kicad_sch', '.kicad_dru', '.kicad_mod', '.kicad_sym', '.html'}


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=ROOT)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def clean_path(path: str) -> str:
    path = path.replace('\\', '/')
    require(not path.startswith('/') and ':' not in path,
            'Non-portable package path: ' + path)
    result = posixpath.normpath(path)
    require(result not in ('', '.', '..') and not result.startswith('../'),
            'Path escapes package: ' + path)
    return result


@dataclass
class Member:
    raw: bytes
    source: str | None
    method: str = 'exact Git blob'
    source_sha256: str | None = None


class Package:
    def __init__(self, commit: str):
        self.commit = git('rev-parse', commit + '^{commit}').decode().strip()
        self.tree = git('rev-parse', self.commit + '^{tree}').decode().strip()
        self.timestamp = int(git('show', '-s', '--format=%ct', self.commit).strip())
        self.tracked: dict[str, tuple[str, int]] = {}
        for record in git('ls-tree', '-rlz', self.commit).decode('utf-8').split('\0'):
            if not record:
                continue
            fields, path = record.split('\t', 1)
            mode, kind, oid, size = fields.split()
            require(kind == 'blob' and mode != '120000', 'Unsupported tree entry: ' + path)
            self.tracked[path] = (oid, int(size))
        self.cache: dict[str, bytes] = {}
        self.members: dict[str, Member] = {}
        self.standard_models: set[str] = set()
        self.dependencies: dict[str, dict] = {}
        self.restored_steps: list[dict] = []
        self.presentation_links: list[dict] = []
        self.aliases: dict[str, str] = {}
        self.cad_hashes: dict[str, str] = {}

    def read(self, path: str) -> bytes:
        path = clean_path(path)
        require(path in self.tracked, 'Required file not tracked at commit: ' + path)
        require(self.tracked[path][1] < MAX_BLOB, 'Oversized Git source blob: ' + path)
        if path not in self.cache:
            self.cache[path] = git('cat-file', 'blob', self.tracked[path][0])
        return self.cache[path]

    def text(self, path: str) -> str:
        return self.read(path).decode('utf-8-sig')

    def add(self, path: str, destination: str | None = None) -> None:
        path = clean_path(path)
        destination = clean_path(destination or path)
        require(destination not in self.members, 'Duplicate package member: ' + destination)
        raw = self.read(path)
        self.members[destination] = Member(raw, path, source_sha256=digest(raw))
        if path != destination:
            self.aliases[path] = destination

    def generated(self, path: str, text: str, method: str) -> None:
        path = clean_path(path)
        require(path not in self.members, 'Duplicate generated member: ' + path)
        self.members[path] = Member(text.encode('utf-8'), None, method)

    def project(self, title: str) -> None:
        base = 'design/MeshRepeater2_' + title
        stem = 'MeshRepeater2_' + title
        for extension in ('kicad_pro', 'kicad_pcb', 'kicad_dru'):
            self.add(f'{base}/{stem}.{extension}')
        board_path = f'{base}/{stem}.kicad_pcb'
        self.cad_hashes[title.upper()] = digest(self.read(board_path))
        required_sheets: set[str] = set()
        pending = [f'{base}/{stem}.kicad_sch'] if title != 'Shield' else []
        while pending:
            sheet = pending.pop()
            if sheet in required_sheets:
                continue
            require(sheet.startswith(base + '/'), 'Schematic outside current project: ' + sheet)
            required_sheets.add(sheet)
            self.add(sheet)
            for child in re.findall(r'\(property\s+"Sheetfile"\s+"([^"\n]+)"', self.text(sheet)):
                pending.append(clean_path(posixpath.join(posixpath.dirname(sheet), child)))

        tables = {}
        for table in ('fp-lib-table', 'sym-lib-table'):
            path = f'{base}/{table}'
            if path not in self.tracked:
                continue
            self.add(path)
            for name, uri in re.findall(r'\(lib\s+\(name\s+"([^"\n]+)"\).*?\(uri\s+"([^"\n]+)"\)',
                                        self.text(path), flags=re.S):
                require(uri.startswith('${KIPRJMOD}/'), 'Non-local library table URI: ' + uri)
                location = clean_path(base + '/' + uri[len('${KIPRJMOD}/'):])
                tables[(table, name)] = location
                if table == 'sym-lib-table':
                    self.add(location)

        footprint_names = set(re.findall(r'\(footprint\s+"([^"\n]+)"', self.text(board_path)))
        for sheet in required_sheets:
            footprint_names.update(x for x in re.findall(r'\(property\s+"Footprint"\s+"([^"\n]+)"',
                                                         self.text(sheet)) if x)
        footprint_paths: set[str] = set()
        for name in sorted(footprint_names):
            require(':' in name, 'Footprint has no library identity: ' + name)
            library, footprint = name.split(':', 1)
            require(('fp-lib-table', library) in tables, 'Unresolved local footprint: ' + name)
            path = clean_path(tables[('fp-lib-table', library)] + '/' + footprint + '.kicad_mod')
            require(path.startswith(base + '/'), 'Footprint outside current project: ' + path)
            if path not in footprint_paths:
                self.add(path)
                footprint_paths.add(path)

        local_models: set[str] = set()
        for source in [board_path, *sorted(footprint_paths)]:
            for model in re.findall(r'\(model\s+"([^"\n]+)"', self.text(source)):
                if model.startswith('${KIPRJMOD}/'):
                    path = clean_path(base + '/' + model[len('${KIPRJMOD}/'):])
                    require(path.startswith(base + '/'), '3D model outside current project: ' + path)
                    local_models.add(path)
                else:
                    require(model.startswith('${KICAD10_3DMODEL_DIR}/'),
                            'Unexpected external 3D model path: ' + model)
                    self.standard_models.add(model)
        for path in sorted(local_models):
            self.add(path)
        # These are current custom COLD-part source documents, not old schematic copies.
        if title == 'Power':
            self.add(base + '/datasheets/LM393XK-Runic-datasheet.pdf')
        if title == 'Shield':
            self.add(base + '/README_RU.md')
        self.dependencies[title.upper()] = {
            'schematics': sorted(required_sheets),
            'used_footprints': sorted(footprint_paths),
            'local_models': sorted(local_models),
            'standard_model_library': '${KICAD10_3DMODEL_DIR}',
        }

    def add_current_views(self) -> None:
        for title in ('Power', 'Logic'):
            base = 'output/' + title.upper() + '_MARKING/'
            manifest_path = base + 'MeshRepeater2_' + title + '_exports.json'
            manifest = json.loads(self.read(manifest_path))
            require(manifest['sha256'] == self.cad_hashes[title.upper()],
                    'Current views do not match current PCB: ' + title)
            self.add(manifest_path)
            for artifact in manifest['artifacts']:
                path = clean_path(artifact['path'])
                require(path.startswith(base) and PurePosixPath(path).suffix in ('.svg', '.png', '.json'),
                        'Unexpected current view artifact: ' + path)
                require(digest(self.read(path)) == artifact['sha256'], 'Stale view artifact: ' + path)
                self.add(path)
            for name in ('label_view_method.json', 'MeshRepeater2_Logic_operator_top_view.json'):
                path = base + name
                if path in self.tracked and path not in self.members:
                    self.add(path)
            # The operator projection is generated from the same current PCB.
            if title == 'Logic':
                for extension in ('png', 'svg'):
                    path = base + 'MeshRepeater2_Logic_operator_top.' + extension
                    if path not in self.members:
                        self.add(path)
        shield_manifest = 'output/SHIELD/MeshRepeater2_Shield_exports.json'
        manifest = json.loads(self.read(shield_manifest))
        require(manifest['sha256'] == self.cad_hashes['SHIELD'], 'Stale SHIELD exports')
        self.add(shield_manifest)
        for artifact in manifest['artifacts']:
            path = clean_path(artifact['path'])
            if PurePosixPath(path).suffix not in ('.svg', '.png', '.step'):
                continue
            require(path.startswith('output/SHIELD/'), 'Unexpected SHIELD artifact: ' + path)
            require(digest(self.read(path)) == artifact['sha256'], 'Stale SHIELD artifact: ' + path)
            self.add(path)

    def current_checks(self) -> None:
        old_root = 'audit/a3_2026_10_13/marking_cleanup/'
        for name in ('POWER_marking_cleanup.json', 'LOGIC_marking_cleanup.json',
                     'POWER_connector_option_style.json', 'final_validation.json',
                     'LOGIC_final_validation.json'):
            self.add(old_root + name, 'docs/checks/' + name)
        for title in ('POWER', 'LOGIC'):
            proof = json.loads(self.read(old_root + title + '_marking_cleanup.json'))
            require(proof['after_sha256'] == self.cad_hashes[title], 'Stale marking proof: ' + title)
        # A4 publication preflight reruns the native CLI for every current board.
        # Require these four files; older DRC exports are not copied into the package.
        a4_root = 'audit/a4_2026_10_14/'
        self.add(a4_root + 'A4_RELEASE_CHECKS.json', 'docs/checks/A4/A4_RELEASE_CHECKS.json')
        for title in ('POWER', 'LOGIC', 'SHIELD'):
            path = a4_root + title + '_drc.json'
            drc = json.loads(self.read(path))
            require(not any(drc.get(k) for k in ('violations', 'unconnected_items',
                                               'schematic_parity', 'ignored_checks')),
                    'Fresh A4 DRC not clean: ' + title)
            expected_source = 'MeshRepeater2_' + title.title() + '.kicad_pcb'
            require(drc.get('source') == expected_source, 'Fresh A4 DRC source mismatch: ' + title)
            self.add(path, 'docs/checks/A4/' + title + '_drc.json')

    def restore_steps(self) -> None:
        transport = json.loads(self.read('docs/step_transport.json'))
        expected = {'docs/mechanics/MeshRepeater2_assembly.step',
                    'docs/mechanics/MeshRepeater2_exploded.step',
                    'output/LOGIC/MeshRepeater2_Logic.step',
                    'output/POWER/MeshRepeater2_Power.step'}
        require({r['original_path'] for r in transport['files']} == expected,
                'Unexpected STEP transport membership')
        for record in transport['files']:
            path = clean_path(record['original_path'])
            compressed = self.read(record['transport_path'])
            require(len(compressed) == record['gzip_size_bytes']
                    and digest(compressed) == record['gzip_sha256'], 'Bad STEP gzip: ' + path)
            raw = gzip.decompress(compressed)
            require(len(raw) == record['original_size_bytes']
                    and digest(raw) == record['original_sha256'], 'Bad restored STEP: ' + path)
            require(path not in self.members, 'Duplicate restored STEP: ' + path)
            self.members[path] = Member(raw, record['transport_path'],
                                       'verified lossless gzip decompression; retained A3 geometry',
                                       record['gzip_sha256'])
            self.restored_steps.append(record)

    def select(self) -> None:
        for title in PROJECTS:
            self.project(title)
        for path in ('LICENSE.md', 'THIRD_PARTY_NOTICES.md'):
            self.add(path)
        for path in sorted(self.tracked):
            if path.startswith('LICENSES/') and path.count('/') == 1:
                self.add(path)
        for name in ('main.c', 'Makefile', 'watchdog.hex', 'source_hashes.json', 'INTEGRATION_RU.txt'):
            self.add('design/watchdog_reference/' + name)
        self.add('design/interboard_cable.json')
        for path in ('docs/V2_A4_RELEASE_RU.md', 'docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md',
                     'docs/V2_LIMITATIONS_RU.md', 'docs/interboard_connections.csv',
                     'docs/mechanical_selection.json', 'docs/vertical_interconnect_selection.json',
                     'bom/DAN_NEW_PARTS.csv'):
            self.add(path)
        bom_source = ('bom/V2_A4_COMPONENT_BOM.csv' if 'bom/V2_A4_COMPONENT_BOM.csv' in self.tracked
                      else 'bom/V2_A3_COMPONENT_BOM.csv')
        self.add(bom_source, 'bom/V2_A4_COMPONENT_BOM.csv')
        for title in ('Power', 'Logic'):
            old = f'output/pdf/MeshRepeater2_{title}_A3_schematic.pdf'
            new = f'output/pdf/MeshRepeater2_{title}_A4_schematic.pdf'
            self.add(new if new in self.tracked else old, new)
        for name in ('MeshRepeater2_assembly.FCStd', 'MeshRepeater2_exploded.FCStd',
                     'Connfly_DS1071_SCB01x4_Mated_Envelope.step',
                     'MeshRepeater2_assembly_native_3D.png', 'MeshRepeater2_exploded_native_3D.png',
                     'MeshRepeater2_exploded_below_native_3D.png',
                     'MeshRepeater2_stack_dimensions.svg', 'MeshRepeater2_stack_dimensions.png',
                     'MeshRepeater2_harness_routing_plan.svg', 'MeshRepeater2_harness_routing_plan.png',
                     'assembly_geometry_report.json'):
            self.add('docs/mechanics/' + name)
        self.add_current_views()
        self.current_checks()
        self.restore_steps()
        self.make_presentations()

    def presentation_link(self, original: str, source_path: str, output_path: str) -> str:
        split = urlsplit(html.unescape(original))
        if split.scheme or split.netloc or not split.path or split.path.startswith('#'):
            return original
        target = clean_path(posixpath.join(posixpath.dirname(source_path), unquote(split.path)))
        target = self.aliases.get(target, target)
        suffix = ('?' + split.query if split.query else '') + ('#' + split.fragment if split.fragment else '')
        if target in self.members:
            return posixpath.relpath(target, posixpath.dirname(output_path)) + suffix
        exists_current = target in self.tracked or any(n.startswith(target.rstrip('/') + '/') for n in self.tracked)
        reference = self.commit
        is_directory = target not in self.tracked
        if not exists_current:
            # Older snapshots may be removed from the A4 tree, while the immutable
            # A3 tag retains them. Never silently create a link to a missing path.
            lookup = subprocess.run(['git', 'cat-file', '-t', 'v2.0-a3:' + target],
                                    cwd=ROOT, capture_output=True, check=False)
            require(lookup.returncode == 0, 'Broken local documentation link: ' + source_path + ' -> ' + original)
            reference = 'v2.0-a3'
            is_directory = lookup.stdout.strip() == b'tree'
        result = REPOSITORY + ('/tree/' if is_directory else '/blob/') + reference + '/' + quote(target) + suffix
        self.presentation_links.append({'document': output_path, 'old_link': original,
                                        'new_link': result, 'reason': 'historical/reference file excluded from archive'})
        return result

    def make_presentations(self) -> None:
        # Adapt Markdown links only; original prose and all non-presentation files are retained.
        for output_path, member in list(self.members.items()):
            if PurePosixPath(output_path).suffix != '.md' or not member.source:
                continue
            source_path = member.source
            original = member.raw.decode('utf-8-sig')
            updated = re.sub(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)',
                             lambda m: m.group(0).replace(m.group(1), self.presentation_link(
                                 m.group(1).strip('<>'), source_path, output_path)), original)
            if updated != original:
                member.raw = updated.encode('utf-8')
                member.method = 'exact source prose; package-relative Markdown links adapted'
        readme = f'''# Mesh Repeater 2.0 — A4

Designed by @Alksndritm. Снимок коммита `{self.commit}`; тег `v2.0-a4`.

Архив содержит только актуальные проекты POWER, LOGIC и SHIELD, используемые
локальные библиотеки и модели, watchdog, BOM и текущую инструкцию сборки.
Старые исходники 1.0, схемы A1/A2, резервные копии и прежние платы не включены.

Откройте [обзор обеих сторон](output/V2_OVERVIEW_RU.html).
Требуется **KiCad 10 со стандартными библиотеками символов, посадок и 3D-моделей**.
Встроенные ссылки `${{KICAD10_3DMODEL_DIR}}` разрешаются установленной библиотекой.
Локальные зависимости `${{KIPRJMOD}}` включены полностью; распакуйте весь архив
в одну папку, сохранив дерево, и откройте нужный `.kicad_pro`.

| Проект | Редактируемые файлы | Текущая схема PDF |
|---|---|---|
| POWER | [KiCad](design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro) | [PDF](output/pdf/MeshRepeater2_Power_A4_schematic.pdf) |
| LOGIC | [KiCad](design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro) | [PDF](output/pdf/MeshRepeater2_Logic_A4_schematic.pdf) |
| SHIELD | [KiCad](design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro) | [Описание](design/MeshRepeater2_Shield/README_RU.md) |

- [Состав A4](docs/V2_A4_RELEASE_RU.md), [инструкция сборки](docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md).
- [BOM A4 с вариантами](bom/V2_A4_COMPONENT_BOM.csv), [разъёмы и крепёж](bom/DAN_NEW_PARTS.csv).
- [Распиновка](docs/interboard_connections.csv), [ограничения](docs/V2_LIMITATIONS_RU.md).
- [Свежие проверки A4](docs/checks/A4/A4_RELEASE_CHECKS.json), [проверки маркировки](docs/checks/), [полный манифест](RELEASE_MANIFEST.json).

**Перед USB снять единственную J11 на POWER; вернуть после отключения USB.**
Этот выпуск остаётся инженерным прототипом; стендовая квалификация не завершена.
POWER и LOGIC — 90×60 мм, два слоя. Экран изготавливается только с F.Cu.

В A4 изменены подписи и рамки опций. Схемотехника, медь и размещение компонентов
сохранились. PDF схем и BOM, ранее названные A3, являются текущими и в этом
архиве названы A4; их исходные пути и контрольные суммы указаны в манифесте.

STEP и редактируемые FreeCAD-сборки сохраняют геометрию A3, которая соответствует
A4: геометрия компонентов и меди не менялась. Актуальный шелк A4 смотрите в SVG/PNG
и KiCad, а не в сохранённых сборочных STEP. STEP уже распакованы; gzip и вложенные
пакеты выпуска в архив не включены. `.FCStd` — редактируемый формат FreeCAD.
Исторические отчёты доступны по ссылкам на точный коммит GitHub и не копируются
в этот архив. Лицензии и уведомления о происхождении сохранены. Упомянутый
в унаследованных уведомлениях [manifest источников библиотек]({REPOSITORY}/blob/v2.0-a3/archive/v1_S4_16/design/Meshcore_NaIon/asset_manifest.json)
доступен в отдельной истории; текущие используемые посадки и модели, их пути
и SHA256 перечислены в `RELEASE_MANIFEST.json` этого архива.
'''
        self.generated('README.md', readme, 'generated standalone A4 package guide')
        self.generated('bom/NOTES_RU.txt',
                       'Mesh Repeater 2.0 A4: V2_A4_COMPONENT_BOM.csv — текущие варианты; '
                       'DAN_NEW_PARTS.csv — разъёмы и крепёж. Наличие и цены относятся к датам '
                       'проверки в документах. Nice!Nano и HT-RA62 приобретаются отдельно.\n',
                       'generated current BOM index')
        # Copy current overview images exactly, but build a clean navigation without old reports.
        figures = []
        for title in ('Power', 'Logic'):
            for side, caption in (('front_labels', 'маркировка спереди'),
                                  ('back_labels', 'маркировка сзади'),
                                  ('front', 'медь со стороны компонентов'), ('back', 'обратная сторона')):
                path = f'{title.upper()}_MARKING/MeshRepeater2_{title}_{side}.png'
                figures.append(f'<figure><figcaption>{title.upper()} — {caption}</figcaption>'
                               f'<a href="{path}"><img loading="lazy" src="{path}" alt="{title} {side}"></a></figure>')
        for path, caption in [('SHIELD/MeshRepeater2_Shield_front.png', 'SHIELD — окно и памятка'),
                              ('../docs/mechanics/MeshRepeater2_assembly_native_3D.png', 'Сборка — сохранённая геометрия'),
                              ('../docs/mechanics/MeshRepeater2_exploded_native_3D.png', 'Разнесённая сборка')]:
            figures.append(f'<figure><figcaption>{caption}</figcaption><a href="{path}">'
                           f'<img loading="lazy" src="{path}" alt="{caption}"></a></figure>')
        overview = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mesh Repeater 2.0 — A4</title>
<style>body{background:#f2f4f6;color:#17232f;font:16px/1.5 system-ui,sans-serif;margin:0}
main{max-width:1600px;margin:auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:18px}
figure{background:white;margin:0;border:1px solid #cbd4dc}figcaption{padding:12px;font-weight:600}
img{display:block;width:100%;height:auto}.warning{background:#fff1c7;padding:14px;border-left:5px solid #c17a00}
nav{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}nav a{padding:6px;background:white}
@media(max-width:520px){.grid{grid-template-columns:1fr}main{padding:12px}}</style><main>
<h1>Mesh Repeater 2.0 · A4</h1><p>Designed by @Alksndritm · 90×60 мм · KiCad 10</p>
<p class="warning"><b>До подключения USB снять J11 на POWER.</b> Вернуть только после отключения USB.</p>
<p>Текущая маркировка POWER/LOGIC и рамки опций. Медь, маска, положения компонентов и схемотехника сохранены.
Сборочные 3D-виды показывают сохранённую механическую геометрию A3; актуальный шелк A4 приведён на видах плат.
Аппаратные ограничения и необходимость проверки образца сохраняются.</p><nav>'''
        for title in PROJECTS:
            overview += (f'<a href="../design/MeshRepeater2_{title}/MeshRepeater2_{title}.kicad_pro">'
                         f'Проект {title.upper()}</a>')
        overview += '''<a href="pdf/MeshRepeater2_Power_A4_schematic.pdf">Схема POWER</a>
<a href="pdf/MeshRepeater2_Logic_A4_schematic.pdf">Схема LOGIC</a>
<a href="../bom/V2_A4_COMPONENT_BOM.csv">BOM</a><a href="../docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md">Сборка</a>
<a href="../docs/V2_A4_RELEASE_RU.md">Состав A4</a>
<a href="../docs/checks/A4/A4_RELEASE_CHECKS.json">Проверки A4</a></nav><div class="grid">'''
        overview += ''.join(figures) + '</div></main></html>\n'
        self.generated('output/V2_OVERVIEW_RU.html', overview, 'generated standalone overview using exact current images')

    def validate(self) -> None:
        require(len(self.members) > 100, 'Unexpectedly incomplete release')
        forbidden = ('archive/', 'baseline/', 'audit/', 'tmp/', '.git/', '.publication_tmp/', 'tools/')
        cad_projects: set[str] = set()
        for path, member in self.members.items():
            require(not path.startswith(forbidden), 'Historical/build directory in package: ' + path)
            lower = path.lower()
            require(not any(x in lower for x in ('/before/', '/backup/', '/snapshot/',
                                               '_a1_', '_a2_', '_s4_', 'meshcore_naion')),
                    'Obsolete CAD/version in package: ' + path)
            require(not lower.endswith(('.zip', '.gz', '.7z', '.fcbak', '.bak', '.kicad_prl', '.lck')),
                    'Nested archive or backup in package: ' + path)
            require(len(member.raw) < MAX_BLOB, 'Oversized release member: ' + path)
            if lower.endswith(('.kicad_pcb', '.kicad_pro')):
                require(path.startswith('design/MeshRepeater2_'), 'Unexpected CAD project: ' + path)
                cad_projects.add(path)
                require(member.source and member.raw == self.read(member.source), 'Modified editable CAD: ' + path)
            if PurePosixPath(path).suffix in TEXT_SUFFIXES:
                text = member.raw.decode('utf-8-sig')
                require(not re.search(r'(?i)(?:file:/+|[A-Z]:[/\\](?:Users|Windows|Temp)[/\\]|\.publication_tmp)', text),
                        'Machine-local/temp path in package text: ' + path)
                if path.endswith('.html'):
                    for value in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', text):
                        split = urlsplit(html.unescape(value))
                        if split.scheme or split.netloc or not split.path:
                            continue
                        target = clean_path(posixpath.join(posixpath.dirname(path), unquote(split.path)))
                        require(target in self.members, 'Broken standalone overview link: ' + target)
        require(len(cad_projects) == 6, 'Release must have exactly three native PCB/project pairs')
        for title, expected in self.cad_hashes.items():
            path = f'design/MeshRepeater2_{title.title()}/MeshRepeater2_{title.title()}.kicad_pcb'
            require(digest(self.members[path].raw) == expected, 'CAD hash differs from exact commit: ' + title)

    def manifest(self) -> dict:
        return {
            'release': 'Mesh Repeater 2.0 A4', 'tag': 'v2.0-a4', 'commit': self.commit, 'tree': self.tree,
            'scope': 'Current design dependency closure only; no historical source snapshots or earlier schemes/boards.',
            'source_policy': 'All native CAD and firmware bytes taken from exact commit. Presentation links/README adapted.',
            'standard_libraries_required': 'KiCad 10 standard symbol/footprint/3D libraries',
            'excluded': ['archive', 'baseline', 'historical audit CAD snapshots', 'earlier A1/A2 PDF schematics',
                         'older single-board projects', 'unused local footprints/models', 'backups', 'build generators',
                         'nested ZIP/gzip transport archives', 'obsolete assembly PDFs'],
            'native_PCB_SHA256': self.cad_hashes, 'local_dependencies': self.dependencies,
            'external_standard_models': sorted(self.standard_models),
            'restored_STEP_files': self.restored_steps,
            'retained_STEP_scope': 'A3 component/copper mechanical geometry unchanged in A4; current silk is in PCB/SVG/PNG.',
            'presentation_link_adaptations': self.presentation_links,
            'files': {path: {'size': len(member.raw), 'sha256': digest(member.raw),
                              'source_path': member.source, 'source_sha256': member.source_sha256,
                              'method': member.method} for path, member in sorted(self.members.items())},
            'self_manifest_note': 'Manifest does not include its own recursive checksum; ZIP checksum is separate.',
        }

    def write(self, out: Path) -> dict:
        self.validate()
        out.mkdir(parents=True, exist_ok=True)
        archive = out / NAME
        require(not archive.exists(), 'Preserve existing release archive: ' + str(archive))
        date = datetime.fromtimestamp(max(self.timestamp, 315532800), timezone.utc)
        zip_date = (date.year, date.month, date.day, date.hour, date.minute, date.second // 2 * 2)
        manifest = self.manifest()
        manifest_raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for path, member in sorted(self.members.items()):
                entry = zipfile.ZipInfo(PREFIX + path, date_time=zip_date)
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                z.writestr(entry, member.raw, compresslevel=6)
            entry = zipfile.ZipInfo(PREFIX + 'RELEASE_MANIFEST.json', date_time=zip_date)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, manifest_raw, compresslevel=6)
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            require(len(names) == len(set(names)), 'Duplicate ZIP entries')
            require(set(names) == {PREFIX + p for p in self.members} | {PREFIX + 'RELEASE_MANIFEST.json'},
                    'ZIP membership differs from curated manifest')
            require(z.testzip() is None, 'ZIP CRC failure')
            for path, record in manifest['files'].items():
                require(digest(z.read(PREFIX + path)) == record['sha256'], 'ZIP member hash failure: ' + path)
        with archive.open('rb') as f:
            archive_hash = hashlib.file_digest(f, 'sha256').hexdigest()
        (out / (NAME + '.sha256.txt')).write_text(archive_hash + '  ' + NAME + '\n', encoding='ascii')
        result = {'ok': True, 'commit': self.commit, 'package': str(archive.resolve()),
                  'sha256': archive_hash, 'size_bytes': archive.stat().st_size,
                  'manifest_files': len(self.members), 'native_PCB_SHA256': self.cad_hashes,
                  'retained_current_project_count': 3, 'historical_CAD_files': 0,
                  'nested_release_archives': 0, 'CRC_check': 'PASS',
                  'manifest_member_SHA256_check': 'PASS', 'local_dependency_closure': 'PASS'}
        (out / 'build_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (out / 'release_manifest.json').write_bytes(manifest_raw)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True, help='Exact committed source revision')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    package = Package(args.commit)
    package.select()
    print(json.dumps(package.write(args.out), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
