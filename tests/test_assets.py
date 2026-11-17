"""示意图的物理几何：图上的位置要和图里标的关系一致。"""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT

SVG = ROOT / "skills/physics-svg-tutor/assets/wiener-standing-wave.svg"
NS = {"s": "http://www.w3.org/2000/svg"}


def test_wiener_first_antinode_is_quarter_wavelength_above_mirror():
    """镜面是电场波节，E ∝ sin(kz)：波腹在 z = λ/4, 3λ/4, …，相邻波腹相隔 λ/2。
    所以镜面到第一层波腹应是相邻波腹间距的一半。"""
    root = ET.parse(SVG).getroot()
    mirror_y = min(float(r.get("y")) for r in root.findall("s:rect", NS) if r.get("y"))  # 镜面上表面
    dashed = next(g for g in root.findall("s:g", NS) if g.get("stroke-dasharray"))
    ys = sorted((float(re.match(r"M\S+ (\S+) H", p.get("d")).group(1)) for p in dashed.findall("s:path", NS)),
                reverse=True)
    gaps = [a - b for a, b in zip(ys, ys[1:])]
    assert len(ys) == 3 and max(gaps) - min(gaps) < 1e-9, ys
    half = gaps[0]                       # λ/2 对应的坐标长度
    assert abs((mirror_y - ys[0]) - half / 2) < 1e-9, f"镜面 y={mirror_y}，第一层波腹 y={ys[0]}，应相距 {half / 2}"


def test_wiener_intersections_lie_on_plate_and_antinodes():
    root = ET.parse(SVG).getroot()
    x0, y0, x1, y1 = map(float, re.findall(r"[\d.]+", root.find("s:path", NS).get("d")))
    dashed = next(g for g in root.findall("s:g", NS) if g.get("stroke-dasharray"))
    ys = {float(re.match(r"M\S+ (\S+) H", p.get("d")).group(1)) for p in dashed.findall("s:path", NS)}
    pts = [(float(c.get("cx")), float(c.get("cy"))) for c in root.findall("s:circle", NS)]
    assert len(pts) == 3
    for cx, cy in pts:
        assert cy in ys
        on_line = y0 + (y1 - y0) * (cx - x0) / (x1 - x0)
        assert abs(on_line - cy) < 0.6, (cx, cy, on_line)
