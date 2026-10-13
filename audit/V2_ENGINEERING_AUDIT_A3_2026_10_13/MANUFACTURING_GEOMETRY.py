"""Read-only native extraction for a scoped Rezonit comparison, audit attachment."""
from pathlib import Path
import hashlib
import json
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / 'tools/cad'))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()
HELD = []


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    result = {'source': 'https://www.rezonit.ru/directory/tekhnologicheskie-osobennosti-proizvodstva/',
              'retrieved': '2026-10-13', 'published_silk_min_font_mm': 1.0,
              'published_silk_min_line_mm': 0.15,
              'scope': 'Published capability comparison, not a vendor quotation or DFM approval.', 'boards': {}}
    for name in ['POWER', 'LOGIC', 'SHIELD']:
        path = ROOT / 'design' / ('MeshRepeater2_' + name.title())
        path = path / (path.name + '.kicad_pcb')
        before = sha(path)
        board = k.LoadBoard(str(path)); HELD.append(board)
        silk = []
        items = list(board.GetDrawings())
        for fp in board.GetFootprints():
            items += list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]
        seen = set()
        for item in items:
            uid = item.m_Uuid.AsString()
            if uid in seen: continue
            seen.add(uid)
            if item.GetLayer() not in (k.F_SilkS, k.B_SilkS): continue
            if hasattr(item, 'IsVisible') and not item.IsVisible(): continue
            pos = item.GetPosition()
            if isinstance(item, k.PCB_TEXT):
                size = item.GetTextSize()
                row = {'uuid': uid, 'layer': board.GetLayerName(item.GetLayer()),
                       'text': item.GetText(), 'xy_mm': [k.ToMM(pos.x), k.ToMM(pos.y)],
                       'font_mm': [k.ToMM(size.x), k.ToMM(size.y)],
                       'stroke_mm': k.ToMM(item.GetTextThickness())}
                row['below_published_minimum'] = min(row['font_mm']) < 1.0 - 1e-6 or row['stroke_mm'] < 0.15 - 1e-6
                silk.append(row)
        tracks = [{'uuid': t.m_Uuid.AsString(), 'net': t.GetNetname(), 'width_mm': k.ToMM(t.GetWidth()),
                   'start_mm': [k.ToMM(t.GetStart().x), k.ToMM(t.GetStart().y)],
                   'end_mm': [k.ToMM(t.GetEnd().x), k.ToMM(t.GetEnd().y)]}
                  for t in board.GetTracks() if not isinstance(t, k.PCB_VIA)]
        vias = [{'uuid': t.m_Uuid.AsString(), 'net': t.GetNetname(), 'outer_mm': k.ToMM(t.GetWidth(k.F_Cu)),
                 'drill_mm': k.ToMM(t.GetDrillValue()),
                 'ring_mm': k.ToMM(t.GetWidth(k.F_Cu) - t.GetDrillValue()) / 2}
                for t in board.GetTracks() if isinstance(t, k.PCB_VIA)]
        result['boards'][name] = {'pcb': str(path.relative_to(ROOT)), 'sha256': before,
                                 'visible_silk_text_objects': len(silk),
                                 'silk_text_objects_below_Rezonit': sum(s['below_published_minimum'] for s in silk),
                                 'min_text_height_mm': min((s['font_mm'][1] for s in silk), default=None),
                                 'min_text_stroke_mm': min((s['stroke_mm'] for s in silk), default=None),
                                 'silk': silk, 'tracks': tracks, 'vias': vias,
                                 'min_track_mm': min((t['width_mm'] for t in tracks), default=None),
                                 'min_via_drill_mm': min((v['drill_mm'] for v in vias), default=None),
                                 'min_via_ring_mm': min((v['ring_mm'] for v in vias), default=None)}
        assert sha(path) == before
    (OUT / 'MANUFACTURING_GEOMETRY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({b: {key: v for key, v in r.items() if key not in ['silk', 'tracks', 'vias']}
                      for b, r in result['boards'].items()}, ensure_ascii=True))


if __name__ == '__main__':
    main()
