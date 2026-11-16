"""排版流水线：纯函数单测 + 用合成示例做一次端到端构建。"""
import json
import os
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT, load, need_tools

br = load("skills/kaoyan-report/scripts/build_report.py", "build_report")
charts = load("skills/kaoyan-report/scripts/charts.py", "charts")


def test_fix_math_pipes_inside_table_math():
    md = "| a | $|x|$ |\n|---|---|\n| b | $$\\|v\\|$$ |"
    out = br.fix_math_pipes(md)
    assert "$\\vert x\\vert $" in out
    assert "\\vert v\\vert" in out
    assert "|" not in out.split("$")[1]


def test_fix_math_pipes_leaves_plain_text():
    md = "a | b，单价 5 元"
    assert br.fix_math_pipes(md) == md


def test_inject_figs_replaces_and_reports_unknown():
    html = "<p>x</p><!--FIG:score--><p>y</p>"
    assert br.inject_figs(html, {"score": lambda: "<svg/>"}) == "<p>x</p><svg/><p>y</p>"
    with pytest.raises(KeyError, match="score"):
        br.inject_figs(html, {"other": lambda: ""})


def test_fill_template_escapes_title_and_keeps_body():
    tpl = "<title>{{TITLE}}</title>@{{TITLE_CSS}}@{{DATE_CSS}}<!--BODY-->{{DATE}}"
    out = br.fill_template(tpl, 'A<B "c"', "2026-01-01", "<p>{{DATE}}</p>")
    assert "<title>A&lt;B &quot;c&quot;</title>" in out
    assert '@A<B \\"c\\"@' in out
    assert out.endswith("<p>{{DATE}}</p>2026-01-01")  # 正文里的占位符不被替换


def test_leftover_math():
    assert br.leftover_math("能量 E = mc2，没有残留") == []
    assert br.leftover_math("残留 $x$ 和 \\frac") == ["$", "\\frac"]


@pytest.mark.parametrize("fig", [
    lambda: charts.bars([("甲", 3, charts.ACC, " / 5"), ("乙<丙", 1, charts.BAD, "", (0.5, 2))], 5, [0, 5], refs=[(4, "线")]),
    lambda: charts.segments([(0, 60, "选择", charts.ACC), (60, 180, "大题", charts.PART)], 180, unit=" 分钟"),
], ids=["bars", "segments"])
def test_charts_are_valid_svg(fig):
    root = ET.fromstring(fig())
    assert root.tag.endswith("svg")


def test_find_chrome_respects_env(tmp_path, monkeypatch):
    fake = tmp_path / "chrome"
    fake.write_text("")
    monkeypatch.setenv("KAOYAN_CHROME", str(fake))
    assert br.find_chrome() == str(fake)


def test_build_example_end_to_end(tmp_path):
    need_tools("pandoc")
    try:
        br.find_chrome()
    except FileNotFoundError:
        if os.environ.get("KAOYAN_REQUIRE_E2E"):
            raise
        pytest.skip("没有 Chrome / Edge / Chromium")
    ex = ROOT / "examples" / "synthetic-mechanics"
    res = br.build(ex / "report.md", tmp_path / "report.pdf", "合成示例", "测试", ex / "figs.py")
    print(json.dumps(res, ensure_ascii=False))
    assert res["pages"] >= 1
    assert res["unrendered_math"] == []
    assert res["blank_pages"] == []
    assert (tmp_path / "report.pdf").stat().st_size > 10_000
    assert not (tmp_path / "_build" / "chrome-profile").exists(), "浏览器配置目录应在构建后删掉"
