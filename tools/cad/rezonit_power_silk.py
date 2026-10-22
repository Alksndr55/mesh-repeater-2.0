"""POWER A4_FAB1 printed silkscreen for Rezonit, without pcbnew/SWIG.

Patches the original byte ranges only. The original A4 PCB/project/library
footprints are backed up under the manufacturing audit directory. Copper,
mask, pads, footprint placement, UUIDs and non-silk objects are invariant.
Run with the KiCad Python runtime. No third party package is required.
"""
from pathlib import Path
import collections
import copy
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
PCB = ROOT / "design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb"
OUT = ROOT / "audit/manufacturing_a4_2026_10_14/marking_POWER"
SILK = {"F.SilkS", "B.SilkS"}
GRAPHICS = {a + b for a in ("fp_", "gr_") for b in ("line", "arc", "rect", "poly", "circle")}
TEXT = {"gr_text", "fp_text", "property"}

# Actual native glyph and mask DRC determine these local text placements.
# Keys are the complete original owner caption, values retain its orientation.
OVERRIDES = {'BAL1': {'at': [30.9, 11.7]},
 'C2\n100n': {'at': [19.0, 18.972422]},
 'C30\nN12p\nL6.8p': {'at': [19.5, 41.25], 'layer': 'B.SilkS', 'text': 'C30 N12p\nL6.8p'},
 'C4\n22u': {'at': [25.5, 42]},
 'C5\n470p': {'at': [13.7, 39.527576]},
 'C54\nDNP': {'at': [45.7, 26.3]},
 'C55\nDNP': {'at': [45.7, 31.3]},
 'C58\n47n': {'at': [11.013095, 15.0]},
 'C59\n47n': {'at': [12.8, 55.927577]},
 'C61 1n': {'at': [49.8, 44.1]},
 'C62\n100n': {'at': [41.7, 54.427577]},
 'COLD A': {'at': [43.5, 28.75]},
 'D4\nGREEN': {'at': [77.047857, 2.1]},
 'Mesh Repeater ver 2.0\nDesigned by @Alksndritm': {'at': [26.0, 57.1]},
 'Q4\nAO34\n01A': {'text': 'Q4'},
 'Q5\nBSS138': {'at': [37.5, 52.3], 'text': 'Q5\nBSS\n138'},
 'Q6\nAO34\n01A': {'text': 'Q6'},
 'Q7\nAO34\n01A': {'text': 'Q7'},
 'R10\n10k': {'at': [63.733095, 5.3]},
 'R13 56k': {'at': [37.5, 21.8], 'layer': 'B.SilkS'},
 'R14\n10k': {'at': [38.0, 24.6]},
 'R15\nN40k2\nL130k': {'at': [37.4, 15.499999]},
 'R16 49k9': {'at': [37.1, 18.4]},
 'R3\nN61k9\nL121k': {'at': [19.0, 37.3]},
 'R4\n100k': {'at': [17.4, 41.397577]},
 'R40\n22mR': {'at': [57.5, 32.5], 'layer': 'B.SilkS'},
 'R41\n22mR': {'at': [75.5, 32.5], 'layer': 'B.SilkS'},
 'R47\n2R': {'at': [18.2, 15], 'layer': 'B.SilkS'},
 'R48\n120k': {'at': [21.8, 15], 'layer': 'B.SilkS'},
 'R49 2k49': {'at': [26, 12], 'text': 'R49\n2k49'},
 'R51\n2R': {'at': [12.8, 45], 'layer': 'B.SilkS'},
 'R52\n120k': {'at': [17.5, 45.002422]},
 'R53\n2k49': {'at': [21.0, 49.897577]},
 'R54\n100k': {'at': [17.5, 52.697577]},
 'R56\nN1R8\nL0R': {'at': [24.7, 32.55]},
 'R57\n47k': {'at': [25.3, 45.5]},
 'R58 100k': {'at': [42.9, 35.6]},
 'R59 100k': {'at': [45.6, 43.9464]},
 'R61\n100k': {'at': [41.4, 45.5]},
 'R66\n1k': {'at': [33.5, 51.4]},
 'R67\n1M': {'at': [33.5, 57.097577]},
 'R7\n105k': {'at': [6.528332, 32.599999]},
 'TH1\n10k NTC': {'at': [46.17, 56.197577]},
 'U1\nCN3722': {'at': [16.9, 28.5], 'layer': 'B.SilkS'},
 'U11\nLM285 2.5': {'at': [27.73, 52.677577]},
 'U12\nINA219': {'at': [57, 10.5], 'layer': 'B.SilkS'},
 'U8\nLMV431A': {'at': [30.7, 16.2]},
 'U9\nLMV431A': {'at': [7.115475, 48.9]}}
EXTRA_GROUPS = [
    {"text": "Q4,Q6,Q7\nAO3401A", "at": [54.0, 28.0], "layer": "B.SilkS",
     "uuid": "e5908304-663f-4ee3-9241-811b18f653e4"}
]
GRAPHIC_ENDPOINT_ADJUSTMENTS = {
    "db576565-c5bb-493e-b336-b5609a08ceeb": {"end": [28.8, 27.020879]},
    "3625cd42-a680-4b19-abc0-cd993c66280a": {"end": [28.8, 27.020879]},
}


class Node:
    def __init__(self, start):
        self.start = start
        self.end = None
        self.items = []

    @property
    def head(self):
        return self.items[0][0]

    def one(self, name):
        return next((a for a in self.items if isinstance(a, Node) and a.head == name), None)

    def atom(self, index=1, default=None):
        if len(self.items) <= index or isinstance(self.items[index], Node):
            return default
        token = self.items[index][0]
        return json.loads(token) if token.startswith('"') else token


def parse(raw):
    stack = []
    root = None
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', raw):
        token = m[0]
        if token == "(":
            node = Node(m.start())
            if stack:
                stack[-1].items.append(node)
            stack.append(node)
        elif token == ")":
            node = stack.pop()
            node.end = m.end()
            if not stack:
                root = node
        else:
            stack[-1].items.append((token, m.start(), m.end()))
    if stack or root is None:
        raise ValueError("Unbalanced S-expression")
    return root


def walk(root):
    yield root
    for a in root.items:
        if isinstance(a, Node):
            yield from walk(a)


def layer(node):
    a = node.one("layer")
    return a.atom() if a else None


def printed(node):
    hide = node.one("hide")
    if hide and hide.atom() == "yes":
        return False
    if any(not isinstance(a, Node) and a[0] == "hide" for a in node.items):
        return False
    effects = node.one("effects")
    hide = effects.one("hide") if effects else None
    return not (hide and hide.atom() == "yes")


def text_value(node):
    return node.atom(2 if node.head in ("fp_text", "property") else 1)


def replace(raw, edits):
    for start, end, value in sorted(edits, reverse=True):
        raw = raw[:start] + value + raw[end:]
    return raw


def without_silk(raw):
    edits = [(n.start, n.end, "") for n in walk(parse(raw))
             if n.head in GRAPHICS | TEXT and layer(n) in SILK]
    return re.sub(r"\s+", " ", replace(raw, edits)).strip()


def patch(raw, use_overrides=False):
    edits = []
    changes = []
    for n in walk(parse(raw)):
        if layer(n) not in SILK:
            continue
        if n.head in TEXT and printed(n):
            effects = n.one("effects")
            font = effects.one("font") if effects else None
            if not font:
                raise ValueError("Printed text has no font: " + str(text_value(n)))
            size = font.one("size")
            thickness = font.one("thickness")
            old_size = [float(size.atom(i)) for i in (1, 2)]
            new_size = [max(1.0, a) for a in old_size]
            old_stroke = float(thickness.atom()) if thickness else 0.0
            new_stroke = max(.15, old_stroke)
            if old_size != new_size:
                edits.append((size.start, size.end, f"(size {new_size[0]:g} {new_size[1]:g})"))
            if thickness and old_stroke != new_stroke:
                edits.append((thickness.start, thickness.end, f"(thickness {new_stroke:g})"))
            elif not thickness:
                edits.append((font.end - 1, font.end - 1, f" (thickness {new_stroke:g})"))
            override = OVERRIDES.get(text_value(n)) if use_overrides else None
            if override:
                if "at" in override:
                    at = n.one("at")
                    angle = float(at.atom(3, 0))
                    x, y = override["at"]
                    edits.append((at.start, at.end, f"(at {x:g} {y:g} {angle:g})"))
                if "text" in override:
                    token = n.items[2 if n.head in ("fp_text", "property") else 1]
                    edits.append((token[1], token[2], json.dumps(override["text"], ensure_ascii=False)))
                if "layer" in override and override["layer"] != layer(n):
                    old_layer = n.one("layer")
                    new_layer = override["layer"]
                    assert new_layer in SILK
                    edits.append((old_layer.start, old_layer.end, f'(layer "{new_layer}")'))
                    justify = effects.one("justify")
                    if new_layer == "B.SilkS":
                        if not justify:
                            edits.append((effects.end - 1, effects.end - 1, " (justify mirror)"))
                        elif not any(not isinstance(a, Node) and a[0] == "mirror" for a in justify.items):
                            edits.append((justify.end - 1, justify.end - 1, " mirror"))
                    elif justify:
                        atoms = [a[0] for a in justify.items if not isinstance(a, Node) and a[0] != "mirror"]
                        edits.append((justify.start, justify.end, "(" + " ".join(atoms) + ")" if len(atoms) > 1 else ""))
            if old_size != new_size or old_stroke != new_stroke or override:
                changes.append({"type": n.head, "text": text_value(n), "layer": layer(n),
                                "size_before": old_size, "size_after": new_size,
                                "stroke_before": old_stroke, "stroke_after": new_stroke,
                                "override": override})
        elif n.head in GRAPHICS:
            identity = n.one("uuid")
            adjustment = GRAPHIC_ENDPOINT_ADJUSTMENTS.get(identity.atom()) if identity else None
            if adjustment and use_overrides:
                for name, xy in adjustment.items():
                    field = n.one(name)
                    edits.append((field.start, field.end, f"({name} {xy[0]:g} {xy[1]:g})"))
                changes.append({"type": n.head, "layer": layer(n), "uuid": identity.atom(),
                                "endpoint_adjustment": adjustment})
            stroke = n.one("stroke")
            width = stroke.one("width") if stroke else n.one("width")
            if width and float(width.atom()) < .15:
                changes.append({"type": n.head, "layer": layer(n), "width_before": float(width.atom()),
                                "width_after": .15})
                edits.append((width.start, width.end, "(width 0.15)"))
    result = replace(raw, edits)
    assert without_silk(raw) == without_silk(result), "Non-silk source changed"
    return result, changes


def backup(path, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(path.read_bytes())
    return destination.read_bytes()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = backup(PCB, OUT / "original.kicad_pcb")
    result, changes = patch(original.decode("utf-8"), True)
    for group in EXTRA_GROUPS:
        value = json.dumps(group["text"], ensure_ascii=False)
        x, y = group["at"]
        block = (f'\n\t(gr_text {value} (at {x:g} {y:g} 0) (layer "{group["layer"]}")'
                 f' (uuid "{group["uuid"]}") (effects (font (size 1 1) (thickness 0.15))'
                 f' (justify mirror)))\n')
        end = result.rfind(")")
        result = result[:end] + block + result[end:]
    assert without_silk(original.decode("utf-8")) == without_silk(result)
    ids = re.findall(r'\(uuid "([^\"]+)"\)', result)
    assert len(ids) == len(set(ids)), "Duplicate UUID"
    original_ids = re.findall(r'\(uuid "([^\"]+)"\)', original.decode("utf-8"))
    assert set(original_ids).issubset(ids), "Original UUID identity changed"
    assert set(ids) - set(original_ids) == {a["uuid"] for a in EXTRA_GROUPS}
    PCB.write_bytes(result.encode("utf-8"))
    pro = PCB.with_suffix(".kicad_pro")
    pro_before = backup(pro, OUT / "original.kicad_pro")
    doc = json.loads(pro_before)
    pro_original = copy.deepcopy(doc)
    defaults = doc["board"]["design_settings"]["defaults"]
    for key in ("silk_text_size_h", "silk_text_size_v"):
        defaults[key] = max(1.0, defaults.get(key, 0.0))
    for key in ("silk_text_thickness", "silk_line_width"):
        defaults[key] = max(.15, defaults.get(key, 0.0))
    rules = doc["board"]["design_settings"]["rules"]
    rules["min_text_height"] = 1.0
    rules["min_text_thickness"] = .15
    pro.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    libraries = []
    for fp in (n for n in walk(parse(original.decode("utf-8"))) if n.head == "footprint"):
        identity = fp.atom().split(":", 1)
        if len(identity) != 2:
            continue
        path = PCB.parent / (identity[0] + ".pretty") / (identity[1] + ".kicad_mod")
        if not path.exists():
            continue
        old = backup(path, OUT / "original_footprints" / path.name)
        new, libchanges = patch(old.decode("utf-8"))
        if libchanges:
            path.write_bytes(new.encode("utf-8"))
            libraries.append({"path": str(path.relative_to(ROOT)), "changes": libchanges,
                              "sha256_before": hashlib.sha256(old).hexdigest(),
                              "sha256_after": hashlib.sha256(new.encode("utf-8")).hexdigest(),
                              "non_silk_source_identical": True})
    report = {"revision": "A4_FAB1", "board": "POWER", "date_Omsk": "2026-10-14",
              "sha256_before": hashlib.sha256(original).hexdigest(),
              "sha256_after": hashlib.sha256(PCB.read_bytes()).hexdigest(),
              "non_silk_source_identical": True, "original_UUIDs_retained_and_all_unique": True,
              "changes": changes, "local_library_silk_changes": libraries,
              "additional_group_captions": EXTRA_GROUPS,
              "project_before": pro_original["board"]["design_settings"]["defaults"],
              "project_after": defaults,
              "project_rule_changes": {key: {"before": pro_original["board"]["design_settings"]["rules"][key],
                                            "after": rules[key]}
                                       for key in ("min_text_height", "min_text_thickness")}}
    (OUT / "patch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"board": "POWER", "changes": len(changes), "libraries": len(libraries),
                      "non_silk_source_identical": True, "sha256": report["sha256_after"]}))


if __name__ == "__main__":
    main()
