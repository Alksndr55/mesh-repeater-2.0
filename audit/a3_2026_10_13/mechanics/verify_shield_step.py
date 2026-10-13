"""Independent OCP BRep proof: saved STEP has one physical header window.

Run with the existing shared CadQuery runtime. Does not mutate CAD or STEP.
This checks nominal body sweep and declared alignment scenarios; it does not
invent a tolerance specification for the selected generic connector.
"""
from pathlib import Path
import hashlib
import json
import math
import cadquery as cq

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
STEP = ROOT / 'output/SHIELD/MeshRepeater2_Shield.step'
PCB = ROOT / 'design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pcb'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = {str(path.relative_to(ROOT)): sha(path) for path in (STEP, PCB)}
    shape = cq.importers.importStep(str(STEP)).val()
    solids = shape.Solids()
    assert len(solids) == 2, 'Expected one FR4 body and one connected front foil'
    assert all(s.isValid() for s in solids)
    core = max(solids, key=lambda s: s.Volume())
    foil = min(solids, key=lambda s: s.Volume())
    core_box, foil_box = core.BoundingBox(), foil.BoundingBox()
    assert abs(core_box.xlen-90) < 1e-6 and abs(core_box.ylen-60) < 1e-6
    assert abs(core_box.zlen-1.475) < 1e-6
    assert abs(foil_box.zlen-.035) < 1e-6
    window_area = 17.2*6.8-(4-math.pi)*.6**2
    core_expected = (90*60-4*math.pi*1.6**2-window_area)*1.475
    assert abs(core.Volume()-core_expected) < .002, (core.Volume(), core_expected)
    # Eight boundary alignments plus the centred passage. The 0.25mm is a
    # deliberate sensitivity scenario, not a manufacturer-guaranteed tolerance.
    trials = []
    for dx in (-.25, 0., .25):
        for dy in (-.25, 0., .25):
            body = cq.Workplane('XY').box(15.64, 5., 6.).translate((70.5+dx, -50.27+dy, 1.)).val()
            volumes = [s.intersect(body).Volume() for s in (core, foil)]
            assert max(volumes) < 1e-7, (dx, dy, volumes)
            trials.append({'alignment_offset_mm': [dx, dy],
                           'plastic_sweep_intersection_core_mm3': volumes[0],
                           'plastic_sweep_intersection_foil_mm3': volumes[1]})
    assert before == {str(path.relative_to(ROOT)): sha(path) for path in (STEP, PCB)}
    result = {'date': '2026-10-13', 'status': 'NOMINAL_STEP_WINDOW_AND_PLASTIC_SWEEP_PASS',
              'input_sha256': before, 'method': 'OpenCascade native STEP BRep; volume and Boolean intersections',
              'valid_solids': 2, 'core_thickness_mm': core_box.zlen,
              'foil_thickness_mm': foil_box.zlen,
              'physical_window_expected_area_mm2': window_area,
              'core_expected_volume_mm3': core_expected,
              'core_actual_volume_mm3': core.Volume(),
              'core_volume_error_mm3': core.Volume()-core_expected,
              'sweep_body_xy_mm': [15.64, 5.], 'sweep_native_center_mm': [70.5, 50.27],
              'sensitivity_offset_mm': .25, 'sweep_trials': trials,
              'qualifications': 'Existing nominal body model only; actual header maximum body dimensions, contact fit and full stack tolerances require selected sample qualification.'}
    (HERE / 'shield_step_geometry.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'status': result['status'], 'BRep_sweeps': len(trials),
                      'core_volume_error_mm3': result['core_volume_error_mm3']}))


if __name__ == '__main__':
    main()
