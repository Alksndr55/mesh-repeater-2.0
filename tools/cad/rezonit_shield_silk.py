"""Lossless SHIELD silkscreen patch for Rezonit's 1.0/0.15 mm minima.

Pure text processing: no pcbnew/SWIG objects or GUI interaction. The complete
PCB outside printed silkscreen drawings is verified byte-for-byte unchanged.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
PCB = ROOT / 'design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pcb'
AUDIT = ROOT / 'audit/manufacturing_a4_2026_10_14/marking_SHIELD'


def spans(source):
    rows = []
    for match in re.finditer(r'\(gr_(?:text|line|rect|poly|arc|circle)\b', source):
        start = match.start()
        depth = 0
        quoted = escaped = False
        for end in range(start, len(source)):
            char = source[end]
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if not depth:
                    break
        block = source[start:end + 1]
        if re.search(r'\(layer "[FB]\.SilkS"\)', block):
            rows.append((start, end + 1, block))
    return rows


def without_silk(source):
    for start, end, _ in reversed(spans(source)):
        source = source[:start] + source[end:]
    return source


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    raw = PCB.read_bytes()
    backup = AUDIT / 'published_A4_before.kicad_pcb'
    if not backup.exists():
        backup.write_bytes(raw)
    source = raw.decode('utf-8')
    result = source
    changes = []
    for start, end, block in reversed(spans(source)):
        changed = re.sub(r'\(size ([\d.]+) ([\d.]+)\)',
            lambda m: f'(size {max(float(m[1]), 1.0):g} {max(float(m[2]), 1.0):g})', block)
        changed = re.sub(r'\(thickness ([\d.]+)\)',
            lambda m: f'(thickness {max(float(m[1]), .15):g})', changed)
        changed = re.sub(r'\(width ([\d.]+)\)',
            lambda m: f'(width {max(float(m[1]), .15):g})', changed)
        # The print states the ordered laminate nominal, excluding mask.
        changed = changed.replace('FR4 1,52 мм', 'FR4 1,5 мм')
        changed = changed.replace('ЭКРАН A3', 'ЭКРАН A4-FAB1')
        if changed != block:
            changes.append({'uuid': re.search(r'\(uuid "([^"]+)"\)', block)[1]})
            result = result[:start] + changed + result[end:]
    assert without_silk(source) == without_silk(result)
    PCB.write_bytes(result.encode('utf-8'))
    pro = PCB.with_suffix('.kicad_pro')
    data = json.loads(pro.read_text('utf-8'))
    defaults = data['board']['design_settings']['defaults']
    rules = data['board']['design_settings']['rules']
    for name, value in {'silk_line_width': .15, 'silk_text_size_h': 1.0,
                        'silk_text_size_v': 1.0, 'silk_text_thickness': .15}.items():
        defaults[name] = value
    rules['min_text_height'] = 1.0
    rules['min_text_thickness'] = .15
    pro.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    proof = {'before_sha256': hashlib.sha256(raw).hexdigest(),
             'after_sha256': hashlib.sha256(PCB.read_bytes()).hexdigest(),
             'PCB_outside_silk_byte_identical': True,
             'changed_objects': changes,
             'font_height_and_width_min_mm': 1.0, 'stroke_min_mm': .15,
             'physical_stack_unchanged': True,
             'manufacturing_revision': 'A4-FAB1',
             'order_laminate_mm': 1.5, 'CAD_total_model_mm': 1.52}
    (AUDIT / 'shield_silk_patch.json').write_text(json.dumps(proof, indent=2), 'utf-8')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
