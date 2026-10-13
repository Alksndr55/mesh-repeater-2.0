"""A3 screen: one milled connector window and concise Russian silkscreen.

Only the standalone SHIELD PCB, its mechanical footprint and its own outputs
are changed. The POWER/LOGIC circuitry and engineering contracts are not read
as mutable inputs. Their final pad map must be independently checked by root.
"""
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DIR = ROOT / "design/MeshRepeater2_Shield"
NAME = "MeshRepeater2_Shield"
WINDOW = "Shield_Interconnect_Window17p2x6p8_R0p6"
WINDOW_BOX = (61.9, 46.87, 79.1, 53.67)
WINDOW_RADIUS = .6
SHIELD_ORIGIN = (64.15, 49.)
PINMAP = {"1": "SYS_3V3", "2": "GND", "3": "SYS_3V3", "4": "GND",
          "5": "RADIO_3V3", "6": "GND", "7": "RADIO_3V3", "8": "NC",
          "9": "BAT", "10": "SDA", "11": "MODE", "12": "SCL"}
sys.path.insert(0, str(ROOT / "tools/cad"))
from kicad_headless import configure_headless
configure_headless()
import pcbnew as k
configure_headless()


def vec(x, y):
    return k.VECTOR2I(k.FromMM(x), k.FromMM(y))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded_window_shapes(box, radius):
    x0, y0, x1, y1 = box
    d = radius / math.sqrt(2)
    return [
        ("line", (x0+radius, y0), (x1-radius, y0)),
        ("arc", (x1-radius, y0), (x1-radius+d, y0+radius-d), (x1, y0+radius)),
        ("line", (x1, y0+radius), (x1, y1-radius)),
        ("arc", (x1, y1-radius), (x1-radius+d, y1-radius+d), (x1-radius, y1)),
        ("line", (x1-radius, y1), (x0+radius, y1)),
        ("arc", (x0+radius, y1), (x0+radius-d, y1-radius+d), (x0, y1-radius)),
        ("line", (x0, y1-radius), (x0, y0+radius)),
        ("arc", (x0, y0+radius), (x0+radius-d, y0+radius-d), (x0+radius, y0)),
    ]


def footprint_text():
    relative = tuple(v-SHIELD_ORIGIN[i % 2] for i, v in enumerate(WINDOW_BOX))
    body = []
    for kind, *points in rounded_window_shapes(relative, WINDOW_RADIUS):
        if kind == "line":
            (x0, y0), (x1, y1) = points
            body.append(f'(fp_line (start {x0:.9f} {y0:.9f}) (end {x1:.9f} {y1:.9f}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts"))')
        else:
            (x0, y0), (xm, ym), (x1, y1) = points
            body.append(f'(fp_arc (start {x0:.9f} {y0:.9f}) (mid {xm:.9f} {ym:.9f}) (end {x1:.9f} {y1:.9f}) (stroke (width 0.05) (type default)) (layer "Edge.Cuts"))')
    return f'''(footprint "{WINDOW}" (version 20260206) (generator "pcbnew")
 (layer "F.Cu")
 (descr "A3 physical milled opening 17.2x6.8mm R0.6 for the connected upper insulator of the 2x6 long-pin header. Minimum foil clearance 0.5mm. Existing connector model is nominal; qualify the actual male body and assembly alignment on a sample.")
 (attr board_only exclude_from_pos_files exclude_from_bom)
 (fp_text reference "HS1" (at 6.35 1.27) (layer "F.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.1))))
 (fp_text value "ОКНО МЕЖПЛАТНОГО РАЗЪЁМА" (at 6.35 1.27) (layer "F.Fab") hide (effects (font (size 0.8 0.8) (thickness 0.1))))
 (fp_rect (start {relative[0]-.15:.9f} {relative[1]-.15:.9f}) (end {relative[2]+.15:.9f} {relative[3]+.15:.9f}) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
 {chr(10).join(body)}
)\n'''


def label(board, value, x, face_y, layer, size=1., bold=False):
    # B.SilkS faces the observer from above after the assembly's X180 flip.
    # The native bottom view intentionally rotates this physically readable
    # assembly guide, just as for A2; its exported assembly-top view resolves it.
    y = 60-face_y if layer == k.B_SilkS else face_y
    item = k.PCB_TEXT(board)
    item.SetText(value)
    item.SetPosition(vec(x, y))
    item.SetLayer(layer)
    item.SetMirrored(layer == k.B_SilkS)
    item.SetTextAngle(k.EDA_ANGLE(180 if layer == k.B_SilkS else 0, k.DEGREES_T))
    item.SetTextSize(vec(size, size))
    item.SetTextThickness(k.FromMM(.17 if bold else .13))
    item.SetBold(bold)
    item.SetHorizJustify(k.GR_TEXT_H_ALIGN_CENTER)
    item.SetVertJustify(k.GR_TEXT_V_ALIGN_CENTER)
    board.Add(item)
    return item


def artwork(board):
    rows = [
        ("Mesh Repeater 2.0 — ЭКРАН A3", 8., 35., 1.2, True),
        ("POWER: CN3722, TPS63802, LC, INA219", 15., 45., 1.05, False),
        ("LOGIC: Nice!Nano, HT-RA62, часы CR2032, ватчдог", 18., 45., 1., False),
        ("90 × 60 мм; FR4 1,52 мм; медь 35 мкм", 21., 45., 1., False),
        ("Панель 12 В; заряд до 0,8 А", 24., 45., 1., False),
        ("J7: 1 SOLAR+; 2 GND", 27., 45., 1., False),
        ("J8 Na-ion 1S: 1 BAT+; 2 GND", 30., 45., 1., False),
        ("J12 LTO 2S: 1 BAT+; 2 MID; 3 GND; 4 NC", 33., 45., 1., False),
        ("J101/J201: 1,3 SYS_3V3; 5,7 RADIO_3V3", 36., 45., 1., True),
        ("2,4,6 GND; 8 NC; 9 BAT; 10 SDA; 11 MODE; 12 SCL", 39., 45., .95, False),
        ("Опции: Na-ion — COLD; LTO — BAL1/BAL2", 42., 45., 1., False),
        ("J8 и J12 вместе не подключать!", 45., 35., 1., True),
        ("Экран устанавливать медью к POWER", 49., 31., .85, False),
        ("СНЯТЬ J11 ДО USB! Вернуть после отключения USB.", 56., 45., 1.1, True),
    ]
    return [label(board, value, x, y, layer, size, bold)
            for layer in (k.F_SilkS, k.B_SilkS)
            for value, y, x, size, bold in rows]


def check(board, path, text_items):
    zone = next(z for z in board.Zones() if not z.GetIsRuleArea())
    foil = k.SHAPE_POLY_SET(zone.GetFilledPolysList(k.F_Cu))
    foil.Unfracture()
    assert foil.OutlineCount() == 1, "Foil must remain one connected region"
    assert sum(foil.HoleCount(i) for i in range(foil.OutlineCount())) == 5
    footprints = {f.GetReference(): f for f in board.GetFootprints()}
    assert len(footprints) == 6
    window = footprints['HS1']
    assert not list(window.Pads()), "The twelve individual NPTH must be absent"
    edge_shapes = [g for g in window.GraphicalItems()
                   if isinstance(g, k.PCB_SHAPE) and g.GetLayer() == k.Edge_Cuts]
    assert len(edge_shapes) == 8
    assert sum(g.GetShape() == k.SHAPE_T_ARC for g in edge_shapes) == 4
    contacts = []
    for reference in ('H301', 'H302', 'H303', 'H304'):
        f = footprints[reference]
        x, y = k.ToMM(f.GetPosition().x), k.ToMM(f.GetPosition().y)
        ring = [foil.Contains(vec(x+2.5*math.cos(i*math.tau/144),
                                  y+2.5*math.sin(i*math.tau/144)))
                for i in range(144)]
        assert all(ring), "Each complete exposed M3 contact annulus must remain joined"
        contacts.append({'reference': reference, 'xy_mm': [x, y],
                         'all_144_contact_ring_points_connected': True})
    assert not list(board.GetTracks())
    assert not any(p.IsOnLayer(k.B_Cu) and p.GetAttribute() != k.PAD_ATTRIB_NPTH
                   for f in board.GetFootprints() for p in f.Pads())
    text_records = []
    for t in text_items:
        box = t.GetBoundingBox()
        bounds = [k.ToMM(box.GetLeft()), k.ToMM(box.GetTop()),
                  k.ToMM(box.GetRight()), k.ToMM(box.GetBottom())]
        assert bounds[0] > .3 and bounds[1] > .3 and bounds[2] < 89.7 and bounds[3] < 59.7, (t.GetText(), bounds)
        x0, y0, x1, y1 = WINDOW_BOX
        intersects = not (bounds[2] < x0-.15 or bounds[0] > x1+.15
                          or bounds[3] < y0-.15 or bounds[1] > y1+.15)
        assert not intersects, ('text over window', t.GetText(), bounds)
        text_records.append({'text': t.GetText(), 'layer': k.LayerName(t.GetLayer()),
                             'height_mm': k.ToMM(t.GetTextHeight()),
                             'bounds_mm': bounds, 'bold': t.IsBold()})
    assert not any(g.GetLayer() in (k.F_Cu, k.B_Cu) for g in board.GetDrawings())
    return {'date': '2026-10-13', 'revision': 'V2.0-A3',
            'pcb_sha256': digest(path), 'foil_connected_regions': 1,
            'foil_voids': 5, 'manufacturing_copper_layers': ['F.Cu'],
            'window': {'native_bounds_mm': WINDOW_BOX,
                       'width_height_mm': [17.2, 6.8], 'corner_radius_mm': .6,
                       'foil_clearance_mm': .5, 'individual_pin_drills_removed': 12,
                       'footprint': str(window.GetFPID().GetLibItemName()),
                       'passage_qualification': 'Nominal existing body envelope only; verify actual selected header body and alignment on sample before fabrication.'},
            'interboard_pinmap': PINMAP, 'contacts': contacts,
            'labels': text_records, 'J11_warning_both_faces': True,
            'native_total_thickness_mm': k.ToMM(board.GetDesignSettings().GetBoardThickness()),
            'sample_mating_unqualified': True}


def main():
    path = DIR / (NAME + '.kicad_pcb')
    before = HERE / 'before'
    if before.exists():
        assert digest(before/(NAME+'.kicad_pcb')) == digest(path), 'Saved PCB already changed; inspect before rerunning'
    else:
        before.mkdir()
        for name in (NAME+'.kicad_pcb', NAME+'.kicad_pro', 'README_RU.md'):
            shutil.copy2(DIR / name, before / name)
    board = k.LoadBoard(str(path))
    # Removed SWIG wrappers must stay alive through native mutation: several
    # KiCad bindings transfer ownership on Remove(), and early collection of
    # the returned Python proxy can terminate the process on Windows.
    removed = []
    for g in list(board.GetDrawings()):
        if isinstance(g, k.PCB_TEXT) and g.GetLayer() in (k.F_SilkS, k.B_SilkS):
            removed.append(g)
            board.Remove(g)
    for f in list(board.GetFootprints()):
        if f.GetReference() == 'HS1':
            removed.append(f)
            board.Remove(f)
    library = DIR / 'Shield.pretty'
    library_path = library / (WINDOW + '.kicad_mod')
    library_path.write_text(footprint_text(), encoding='utf8')
    f = k.FootprintLoad(str(library), WINDOW)
    f.SetReference('HS1')
    f.SetFPID(k.LIB_ID('Shield', WINDOW))
    f.SetPosition(vec(*SHIELD_ORIGIN))
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    board.Add(f)
    zone = next(z for z in board.Zones() if not z.GetIsRuleArea())
    outline = zone.Outline()
    assert outline.OutlineCount() == 1 and outline.HoleCount(0) == 1
    # The physical cutout is rounded. Its conservative rectangular foil void
    # leaves >=0.5mm clearance everywhere, including the rounded corners.
    outline.RemoveContour(1, 0)
    hole = outline.NewHole(0)
    x0, y0, x1, y1 = WINDOW_BOX
    for x, y in [(x0-.5, y0-.5), (x1+.5, y0-.5),
                 (x1+.5, y1+.5), (x0-.5, y1+.5)]:
        outline.Append(vec(x, y), 0, hole)
    items = artwork(board)
    title = board.GetTitleBlock()
    title.SetTitle('Mesh Repeater 2.0 / средний экран')
    title.SetRevision('V2.0-A3')
    title.SetDate('2026-10-13')
    k.ZONE_FILLER(board).Fill(board.Zones())
    k.SaveBoard(str(path), board)
    # Native SaveBoard can reset project defaults; the existing strict DRC
    # project file belongs to this screen and must remain byte-identical.
    shutil.copy2(before / (NAME+'.kicad_pro'), DIR / (NAME+'.kicad_pro'))
    from set_v2_shield_stackup import ensure
    ensure(path)
    reloaded = k.LoadBoard(str(path))
    assert reloaded.GetTitleBlock().GetRevision() == 'V2.0-A3'
    # Texts used for validation are reloaded objects, binding checks to saved CAD.
    saved_texts = [g for g in reloaded.GetDrawings() if isinstance(g, k.PCB_TEXT)
                   and g.GetLayer() in (k.F_SilkS, k.B_SilkS)]
    proof = check(reloaded, path, saved_texts)
    proof['library_sha256'] = digest(library_path)
    proof['strict_project_sha256_unchanged'] = digest(DIR/(NAME+'.kicad_pro')) == digest(before/(NAME+'.kicad_pro'))
    assert proof['strict_project_sha256_unchanged']
    (HERE / 'shield_native_checks.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf8')
    finish_saved(reloaded, path, library_path, before)


def finish_saved(board, path, library_path, before):
    saved_texts = [g for g in board.GetDrawings() if isinstance(g, k.PCB_TEXT)
                   and g.GetLayer() in (k.F_SilkS, k.B_SilkS)]
    proof = check(board, path, saved_texts)
    proof['library_sha256'] = digest(library_path)
    proof['strict_project_sha256_unchanged'] = digest(DIR/(NAME+'.kicad_pro')) == digest(before/(NAME+'.kicad_pro'))
    assert proof['strict_project_sha256_unchanged']
    cli = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
    subprocess.run([sys.executable, str(ROOT/'tools/cad/export_v2_board.py'),
                    '--pcb', str(path), '--out', str(ROOT/'output/SHIELD'),
                    '--drc', '--mechanical', '--step', '--cli', str(cli)], check=True)
    drc = json.loads((ROOT/'output/SHIELD'/(NAME+'_drc.json')).read_text(encoding='utf8'))
    counts = {key: len(drc.get(key, [])) for key in ('violations', 'unconnected_items', 'schematic_parity')}
    proof['drc_counts'] = counts
    proof['drc_ignored_checks'] = drc.get('ignored_checks', [])
    assert not any(counts.values()) and not proof['drc_ignored_checks']
    (HERE / 'shield_native_checks.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'pcb_sha256': digest(path), 'window_mm': [17.2, 6.8],
                      'native_DRC': counts, 'foil_regions': 1}, ensure_ascii=True))


if __name__ == '__main__':
    main()
