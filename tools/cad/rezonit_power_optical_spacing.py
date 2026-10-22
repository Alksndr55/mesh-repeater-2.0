"""Separate two near-touching printed captions after final visual review."""
from pathlib import Path
import hashlib
import json
import re
from rezonit_shield_silk import spans, without_silk

ROOT = Path(__file__).resolve().parents[2]
PCB = ROOT / 'design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb'
AUDIT = ROOT / 'audit/manufacturing_a4_2026_10_14'
PLACEMENTS = {'R16 49k9': (36.5, 18.4), 'TP6': (8.2, 3.3)}

def main():
    raw = PCB.read_bytes()
    source = raw.decode('utf-8')
    result = source
    found = set()
    for start, end, block in reversed(spans(source)):
        match = re.match(r'\(gr_text ("(?:\\.|[^"\\])*")', block)
        if not match:
            continue
        caption = json.loads(match[1])
        if caption not in PLACEMENTS:
            continue
        assert '(layer "B.SilkS")' in block
        x, y = PLACEMENTS[caption]
        updated = re.sub(r'\(at [^)]+\)', f'(at {x} {y} 0)', block, count=1)
        result = result[:start] + updated + result[end:]
        found.add(caption)
    assert found == set(PLACEMENTS)
    assert without_silk(source) == without_silk(result)
    PCB.write_bytes(result.encode('utf-8'))
    proof = {'before_sha256': hashlib.sha256(raw).hexdigest(),
             'after_sha256': hashlib.sha256(PCB.read_bytes()).hexdigest(),
             'changes': PLACEMENTS, 'only_two_B_silk_text_positions_changed': True,
             'purpose': 'Prevent visual concatenation of J7/TP6 and C12/R16'}
    (AUDIT / 'power_optical_spacing.json').write_text(json.dumps(proof, indent=2), 'utf-8')
    print(json.dumps(proof, indent=2))

if __name__ == '__main__':
    main()
