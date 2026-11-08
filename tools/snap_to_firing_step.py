"""Move soldiers' hold positions that lie inside a trench onto the trench's firing step.

    .venv\\Scripts\\python.exe tools\\snap_to_firing_step.py data\\missions\\m02_line_breaks.json

A soldier standing on the trench floor cannot see over the parapet (so he never shoots).
The firing step runs along the front wall, 0.82 m forward of the trench centre line
(see build_trench in environments/props.py).
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP_OFFSET = 0.82          # local +Y of the step centre (hw - 0.28 with width 2.2)
HALF_WIDTH = 1.1


def trenches(map_name):
    data = json.loads((ROOT / "data" / "maps" / f"{map_name}.json").read_text(encoding="utf-8"))
    out = []
    for p in data["props"]:
        if p["type"] != "trench":
            continue
        params = p.get("params", {})
        if params.get("front", True) is False:
            continue
        out.append((p["pos"][0], p["pos"][1], math.radians(p.get("heading", 0.0)), params.get("length", 20.0)))
    return out


def snap(x, y, ts):
    for tx, ty, h, length in ts:
        c, s = math.cos(h), math.sin(h)
        lx = (x - tx) * c + (y - ty) * s                 # into the trench's local frame
        ly = -(x - tx) * s + (y - ty) * c
        if abs(lx) <= length / 2 - 0.3 and abs(ly) <= HALF_WIDTH:
            ly = STEP_OFFSET
            return round(tx + lx * c - ly * s, 2), round(ty + lx * s + ly * c, 2), True
    return x, y, False


def walk(node, ts, counter):
    if isinstance(node, dict):
        hold = node.get("hold")
        if isinstance(hold, list) and len(hold) >= 2 and all(isinstance(v, (int, float)) for v in hold[:2]):
            x, y, moved = snap(hold[0], hold[1], ts)
            if moved:
                hold[0], hold[1] = x, y
                pos = node.get("pos")
                if isinstance(pos, list) and len(pos) >= 2:
                    pos[0], pos[1] = x, y
                counter[0] += 1
        if node.get("action") == "spawn_friendly":
            for unit in node.get("units", []):
                pos = unit.get("pos")
                if "hold" not in unit and isinstance(pos, list):
                    x, y, moved = snap(pos[0], pos[1], ts)
                    if moved:
                        pos[0], pos[1] = x, y
                        counter[0] += 1
        if node.get("action") == "squad_hold":
            for pos in node.get("positions", {}).values():
                x, y, moved = snap(pos[0], pos[1], ts)
                if moved:
                    pos[0], pos[1] = x, y
                    counter[0] += 1
        for v in node.values():
            walk(v, ts, counter)
    elif isinstance(node, list):
        for v in node:
            walk(v, ts, counter)


def main(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = trenches(data["map"])
    counter = [0]
    walk(data, ts, counter)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{path.name}: {counter[0]} hold positions moved onto firing steps ({len(ts)} trenches)")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
