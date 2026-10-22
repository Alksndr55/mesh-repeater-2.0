"""Build the current A5 project ZIP from an exact Git commit.

Only the three current native projects and their dependency closure are copied.
Current checks/views are selected by PCB SHA256. Historical CAD, obsolete CAM,
board STEP exports, backups, build environments and nested archives are excluded.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import quote, unquote, urlsplit

import build_v2_a4_release as base

base.NAME = 'Mesh-Repeater-2.0-A5-project.zip'
base.PREFIX = 'Mesh-Repeater-2.0-A5/'
ROOT = base.ROOT
TAG = 'v2.0-a5'
CHECK_ROOT = 'audit/routing_cleanup_2026_10_22/'
EXPECTED_PCB = {
    'POWER': '458a411eb25d42cc0b6395fb01c80aefa79b1fcdedcfea174da56f8f893665a2',
    'LOGIC': 'c3cea91efff79b5f737a00ea3b0976ceff944b20178516770259ff7276353d8a',
    'SHIELD': '15820652da1d3b979402e062fbb74fb98a4f2d1d6de9235085a2d4532d9c435c',
}


class Package(base.Package):
    def __init__(self, commit: str, extra_documents: list[str] | None = None):
        super().__init__(commit)
        self.extra_documents = extra_documents or []
        self.current_proofs: dict[str, dict] = {}
        self.view_records: dict[str, dict] = {}

    def json(self, path: str):
        return json.loads(self.text(path))

    def add_portable_json(self, source: str, destination: str):
        """Keep proof values/hash binding; replace machine paths for portability."""
        raw = self.read(source)
        value = json.loads(raw.decode('utf-8-sig'))
        source_root = str(ROOT).replace('\\', '/')

        def portable(x):
            if isinstance(x, dict):
                return {str(portable(k)): portable(v) for k, v in x.items()}
            if isinstance(x, list):
                return [portable(v) for v in x]
            if not isinstance(x, str):
                return x
            x = x.replace('\\', '/')
            x = re.sub(re.escape(source_root), '<PROJECT>', x, flags=re.I)
            x = re.sub(r'[A-Za-z]:/Program Files/KiCad/[^/]+/bin/kicad-cli\.exe',
                       'kicad-cli', x, flags=re.I)
            return x

        destination = base.clean_path(destination)
        base.require(destination not in self.members, 'Duplicate proof: ' + destination)
        encoded = (json.dumps(portable(value), ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        self.members[destination] = base.Member(
            encoded, source, 'exact JSON values; machine path prefixes normalized to <PROJECT>',
            base.digest(raw))
        self.aliases[source] = destination

    def current_checks(self):
        native_path = CHECK_ROOT+'after/native_summary.json'
        native = self.json(native_path)
        for title in base.PROJECTS:
            name = title.upper()
            pcb = f'design/MeshRepeater2_{title}/MeshRepeater2_{title}.kicad_pcb'
            expected = self.cad_hashes[name]
            base.require(expected == EXPECTED_PCB[name], 'Unexpected current PCB: ' + name)
            proof = native[name]
            base.require(proof['sources_preserved'] is True, 'Source mutation during native check: ' + name)
            base.require(proof['source_files'][pcb] == expected, 'Native check SHA mismatch: ' + name)
            base.require(all(x['exit_code'] == 0 for x in proof['commands']), 'Native check command failed: ' + name)
            base.require(all(v == 0 for v in proof['drc'].values()), 'DRC not clear: ' + name)
            if name != 'SHIELD':
                base.require(all(v == 0 for v in proof['erc'].values()), 'ERC not clear: ' + name)
            for path, digest in proof['source_files'].items():
                if path.endswith('.kicad_prl'):
                    continue
                base.require(path in self.tracked, 'Native checked source is not committed: ' + path)
                base.require(base.digest(self.read(path)) == digest,
                             'Native checked source changed since check: ' + path)
            folder = CHECK_ROOT+'after/'+name+'/'
            for kind in ['drc']+([] if name == 'SHIELD' else ['erc']):
                self.add_portable_json(folder+kind+'.json', f'docs/checks/{name}_{kind}.json')
            self.current_proofs[name] = {
                'PCB_SHA256': expected, 'DRC': proof['drc'],
                'ERC': proof.get('erc'), 'sources_preserved_during_native_checks': True,
            }
        self.add_portable_json(native_path, 'docs/checks/A5_NATIVE_CHECKS.json')
        for name in ('POWER', 'LOGIC'):
            source = CHECK_ROOT+f'review/final/{name}/ACCEPTANCE.json'
            acceptance = self.json(source)
            base.require(acceptance['status'] == 'PASS', 'No independent acceptance: ' + name)
            base.require(acceptance['accepted_candidate_sha256'] == self.cad_hashes[name],
                         'Independent accepted SHA mismatch: ' + name)
            base.require(all(acceptance['conditions'].values()), 'Failed independent condition: ' + name)
            self.add_portable_json(source, f'docs/checks/{name}_INDEPENDENT_ACCEPTANCE.json')
        for name in ('LOGIC_C33.json', 'POWER_Kelvin.json'):
            self.add_portable_json(CHECK_ROOT+'review/'+name, 'docs/checks/'+name)
        visual = self.json(CHECK_ROOT+'review/VISUAL_QA.json')
        base.require(visual['status'] == 'PASS', 'Visual review did not pass')
        for name in ('POWER', 'LOGIC'):
            binding = visual['source_hash_bindings'][name]
            base.require(binding['canonical_sha256'] == binding['native_view_source_sha256']
                         == self.cad_hashes[name], 'Visual review SHA mismatch: ' + name)
        for image in visual['images']:
            path = base.clean_path(image['path'])
            if '/views/after/' in path:
                base.require(base.digest(self.read(path)) == image['sha256'], 'Inspected image changed: ' + path)
        # The full numerical history is linked at the immutable commit, not bundled as old source snapshots.
        final = self.json(CHECK_ROOT+'FINAL_AUDIT.json')
        comparison = {name: final['independent_review'][name]['comparison'] for name in ('POWER', 'LOGIC')}
        current = {
            'release': 'A5', 'tag': TAG, 'source_commit': self.commit,
            'native_PCB_SHA256': self.cad_hashes,
            'native_checks': self.current_proofs,
            'routing_comparison': comparison,
            'visual_review_status': 'PASS',
            'source_proof': base.REPOSITORY+'/blob/'+self.commit+'/'+CHECK_ROOT+'FINAL_AUDIT.json',
            'scope': 'Saved CAD geometry/connectivity only; no bench EMI, RF, thermal or startup qualification.',
        }
        self.generated('docs/checks/A5_CURRENT_CHECKS.json', json.dumps(current, ensure_ascii=False, indent=2)+'\n',
                       'summary derived from current hash-bound native and independent checks')
        self.aliases[CHECK_ROOT+'FINAL_AUDIT.json'] = 'docs/checks/A5_CURRENT_CHECKS.json'

    def add_current_views(self):
        for name in ('POWER', 'LOGIC'):
            folder = CHECK_ROOT+'views/after/'+name+'/'
            proof = self.json(folder+'render_proof.json')
            base.require(proof['source_sha256'] == self.cad_hashes[name], 'Stale native view: ' + name)
            base.require(proof['source_preserved'] is True, 'Native view changed source: ' + name)
            selected = []
            for mode in ('routes', 'copper'):
                for side in ('front', 'back'):
                    for ext in ('png', 'svg'):
                        path = folder+f'{name}_{mode}_{side}.{ext}'
                        target = f'output/{name}/{name}_{mode}_{side}.{ext}'
                        self.add(path, target)
                        selected.append({'path': target, 'sha256': base.digest(self.read(path))})
            self.view_records[name] = {'source_PCB_SHA256': self.cad_hashes[name], 'artifacts': selected,
                                      'route_view_note': 'Route-only views omit zone records in a diagnostic copy; full-copper views show actual filled copper.'}
        # Fresh SHIELD export is intentionally required; old A4-labelled export manifests are rejected.
        folder = CHECK_ROOT+'views/after/SHIELD/'
        proof = self.json(folder+'render_proof.json')
        base.require(proof['source_sha256'] == self.cad_hashes['SHIELD'], 'Stale SHIELD view')
        base.require(proof['source_preserved'] is True, 'SHIELD view changed source')
        selected = []
        for side in ('front', 'back'):
            for ext in ('png', 'svg'):
                path = folder+f'SHIELD_copper_{side}.{ext}'
                if path not in self.tracked:
                    path = folder+f'SHIELD_{side}.{ext}'
                target = f'output/SHIELD/SHIELD_{side}.{ext}'
                self.add(path, target)
                selected.append({'path': target, 'sha256': base.digest(self.read(path))})
        self.view_records['SHIELD'] = {'source_PCB_SHA256': self.cad_hashes['SHIELD'], 'artifacts': selected}
        self.generated('output/CURRENT_VIEW_MANIFEST.json', json.dumps(self.view_records, indent=2)+'\n',
                       'current native views selected by hash-bound export proof; exact committed image bytes')

    def select(self):
        for title in base.PROJECTS:
            self.project(title)
        for path in ('LICENSE', 'LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'docs/LICENSING_RU_EN.md'):
            self.add(path)
        for path in sorted(self.tracked):
            if path.startswith('LICENSES/') and path.count('/') == 1:
                self.add(path)
        for name in ('main.c', 'Makefile', 'watchdog.hex', 'source_hashes.json', 'INTEGRATION_RU.txt'):
            self.add('design/watchdog_reference/'+name)
        self.add('design/interboard_cable.json')
        required_docs = ('docs/V2_A5_RELEASE_RU.md', 'docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md',
                         'docs/V2_LIMITATIONS_RU.md', 'docs/interboard_connections.csv',
                         'docs/mechanical_selection.json', 'docs/vertical_interconnect_selection.json',
                         'bom/DAN_NEW_PARTS.csv')
        for path in required_docs:
            self.add(path)
        for path in self.extra_documents:
            base.require(path.startswith(('docs/', 'design/')) and PurePosixPath(path).suffix in ('.md', '.txt', '.json', '.csv'),
                         'Extra document must be a small current provenance document: '+path)
            if path not in self.members:
                self.add(path)
        for path in sorted(self.tracked):
            if path.startswith('docs/licensing/') and PurePosixPath(path).suffix in ('.md', '.txt', '.json', '.csv'):
                if path not in self.members:
                    self.add(path)
        bom = 'bom/V2_A5_COMPONENT_BOM.csv' if 'bom/V2_A5_COMPONENT_BOM.csv' in self.tracked else 'bom/V2_A3_COMPONENT_BOM.csv'
        self.add(bom, 'bom/V2_A5_COMPONENT_BOM.csv')
        for title in ('Power', 'Logic'):
            source = f'output/pdf/MeshRepeater2_{title}_A3_schematic.pdf'
            self.add(source, f'output/pdf/MeshRepeater2_{title}_A5_schematic.pdf')
        self.current_checks()
        self.add_current_views()
        self.make_presentations()

    def presentation_link(self, original, source_path, output_path):
        split = urlsplit(html.unescape(original))
        if split.scheme or split.netloc or not split.path or split.path.startswith('#'):
            return original
        target = base.clean_path(posixpath.join(posixpath.dirname(source_path), unquote(split.path)))
        target = self.aliases.get(target, target)
        suffix = ('?'+split.query if split.query else '')+('#'+split.fragment if split.fragment else '')
        if target in self.members:
            return posixpath.relpath(target, posixpath.dirname(output_path))+suffix
        # Do not bundle historical sources just to satisfy a documentation reference.
        if target in self.tracked:
            result = base.REPOSITORY+'/blob/'+self.commit+'/'+quote(target)+suffix
        elif any(x.startswith(target.rstrip('/')+'/') for x in self.tracked):
            result = base.REPOSITORY+'/tree/'+self.commit+'/'+quote(target)+suffix
        else:
            lookup = base.subprocess.run(['git', 'cat-file', '-t', 'v2.0-a3:'+target], cwd=ROOT, capture_output=True)
            base.require(lookup.returncode == 0, 'Broken documentation reference: '+source_path+' -> '+original)
            kind = '/tree/' if lookup.stdout.strip() == b'tree' else '/blob/'
            result = base.REPOSITORY+kind+'v2.0-a3/'+quote(target)+suffix
        self.presentation_links.append({'document': output_path, 'old_link': original, 'new_link': result,
                                        'reason': 'reference retained at immutable Git commit; excluded from current project ZIP'})
        return result

    def make_presentations(self):
        for output, member in list(self.members.items()):
            if not member.source or PurePosixPath(output).suffix != '.md' or output.startswith('LICENSES/'):
                continue
            original = member.raw.decode('utf-8-sig')
            updated = re.sub(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)',
                             lambda m: m.group(0).replace(m.group(1), self.presentation_link(
                                 m.group(1).strip('<>'), member.source, output)), original)
            if updated != original:
                member.raw = updated.encode('utf-8')
                member.method = 'exact source prose; package-relative Markdown links adapted'
        readme = f'''# Mesh Repeater 2.0 — A5

Designed by @Alksndritm / Alksndr55. Тег `{TAG}`, коммит `{self.commit}`.

Текущие проекты POWER, LOGIC и SHIELD, локальные библиотеки и модели,
watchdog, электрические схемы, BOM, инструкция сборки, лицензии и проверки.
Архив не содержит прежних схем/плат, резервных копий, старых производственных
ZIP, промежуточных CAD и STEP с прежней трассировкой.

Откройте [текущие виды плат](output/V2_OVERVIEW_RU.html).
Требуется KiCad 10 со стандартными библиотеками. Распакуйте весь архив,
сохраняя дерево папок; локальные зависимости ${{KIPRJMOD}} включены.

| Проект | KiCad | Схема PDF |
|---|---|---|
| POWER | [Проект](design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro) | [PDF](output/pdf/MeshRepeater2_Power_A5_schematic.pdf) |
| LOGIC | [Проект](design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro) | [PDF](output/pdf/MeshRepeater2_Logic_A5_schematic.pdf) |
| SHIELD | [Проект](design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro) | [Описание](design/MeshRepeater2_Shield/README_RU.md) |

- [Выпуск A5](docs/V2_A5_RELEASE_RU.md), [сборка](docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md), [BOM](bom/V2_A5_COMPONENT_BOM.csv).
- [Текущие проверки](docs/checks/A5_CURRENT_CHECKS.json), [ограничения](docs/V2_LIMITATIONS_RU.md).
- [Условия лицензирования](LICENSE.md), [пояснения RU/EN](docs/LICENSING_RU_EN.md), [сторонние материалы](THIRD_PARTY_NOTICES.md).

Собственные материалы: CC BY-NC-SA 4.0 в указанной в LICENSE.md области.
Личный некоммерческий заказ плат разрешён; коммерческий выпуск и продажа
требуют письменного разрешения правообладателя. Сторонние лицензии сохранены.

Перед подключением USB снять J11 на POWER. Аппаратные ограничения LTO и
необходимость проверки собранного образца сохраняются. Это инженерный прототип.
Этот архив исходников не является актуальным производственным CAM-пакетом.
PDF схем и BOM электрически не менялись с A3; в архиве они представлены
один раз с именем A5, а исходные пути/хеши записаны в RELEASE_MANIFEST.json.
'''
        self.generated('README.md', readme, 'standalone current A5 project entry points')
        figures = []
        for name in ('POWER', 'LOGIC'):
            for mode, description in [('routes', 'дорожки без заливки'), ('copper', 'фактическая медь с заливкой')]:
                for side, label in [('front', 'лицевая сторона'), ('back', 'обратная сторона')]:
                    path = f'{name}/{name}_{mode}_{side}.png'
                    figures.append(f'<figure><figcaption>{name} — {label}, {description}</figcaption><a href="{path}"><img loading="lazy" src="{path}" alt="{name} {side} {mode}"></a></figure>')
        for side, label in [('front', 'лицевая сторона'), ('back', 'обратная сторона')]:
            path = f'SHIELD/SHIELD_{side}.png'
            figures.append(f'<figure><figcaption>SHIELD — {label}</figcaption><a href="{path}"><img loading="lazy" src="{path}" alt="SHIELD {side}"></a></figure>')
        overview = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mesh Repeater 2.0 — A5</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#f3f5f7;color:#18303e;margin:0}main{max-width:1500px;margin:auto;padding:24px}nav{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}.note{padding:12px;background:#fff0cc;border-left:5px solid #ac790b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:18px}figure{background:white;margin:0;border:1px solid #ccd6dc}figcaption{padding:12px;font-weight:600}img{display:block;width:100%;height:auto}@media(max-width:600px){main{padding:12px}.grid{grid-template-columns:1fr}}</style><main>
<h1>Mesh Repeater 2.0 · A5</h1><p>Designed by @Alksndritm · текущая трассировка от 22.10.2026 · 90×60 мм</p>
<p class="note"><b>Перед USB снять J11 на POWER.</b> Архив содержит исходники инженерного прототипа; актуальный производственный CAM-пакет в него не включён.</p>
<p>Native DRC всех трёх плат: 0 нарушений и неподключённых цепей; POWER/LOGIC — 0 расхождений со схемой и ERC 0. Проверки относятся к точным SHA256 в манифесте. Стендовые EMI/RF/тепловые испытания не заявляются.</p>
<nav><a href="../README.md">Состав архива</a><a href="../LICENSE.md">Лицензия и область применения</a><a href="../docs/V2_ASSEMBLY_INSTRUCTIONS_RU.md">Сборка</a><a href="../docs/checks/A5_CURRENT_CHECKS.json">Проверки</a></nav>
<p>Видами без заливки показаны реальные дорожки/переходы из диагностических копий; это иллюстрации, не CAM. Виды меди показывают сохранённую заливку.</p><div class="grid">'''+''.join(figures)+'</div></main></html>\n'
        self.generated('output/V2_OVERVIEW_RU.html', overview, 'standalone overview of exact current native images')

    def manifest(self):
        result = super().manifest()
        result.update({
            'release': 'Mesh Repeater 2.0 A5', 'tag': TAG,
            'scope': 'Three current native KiCad projects and actual dependency closure; current licensing, documents, views and checks only.',
            'excluded': ['historical CAD/schematics', 'RAR/backups', 'obsolete manufacturing ZIP/CAM',
                         'board STEP with former copper', 'old assembly exports', 'local build dependencies',
                         'unused footprints/models', 'nested archives', 'temporary CAD/route diagnostic copies'],
            'restored_STEP_files': [],
            'retained_STEP_scope': 'No old complete-board STEP exports included. Local component STEP models referenced by current footprints are included.',
            'current_native_checks': self.current_proofs,
            'current_views': self.view_records,
            'own_materials_license': 'CC-BY-NC-SA-4.0; scope/exceptions in LICENSE.md; third-party licenses unchanged',
        })
        return result

    def validate(self):
        super().validate()
        for path, member in self.members.items():
            base.require(not path.lower().endswith(('.rar', '.step.gz')), 'Obsolete transport/archive: '+path)
            base.require(not path.startswith(('manufacturing/', 'docs/mechanics/', 'output/POWER_MARKING/', 'output/LOGIC_MARKING/')),
                         'Historical exported geometry/production package: '+path)
            if path.startswith('LICENSES/'):
                base.require(member.raw == self.read(path), 'Third-party/full license text changed in archive: '+path)
        native = [p for p in self.members if p.endswith('.kicad_pcb')]
        base.require(len(native) == 3, 'Exactly three current native PCB files required')
        base.require(self.cad_hashes == EXPECTED_PCB, 'Current PCB set differs from accepted routing revision')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--extra-document', action='append', default=[])
    args = parser.parse_args()
    package = Package(args.commit, args.extra_document)
    package.select()
    print(json.dumps(package.write(args.out), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
