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
    assert "$\\vert x\\vert $" in out          # 绝对值：单竖线
    assert "$$\\Vert v\\Vert $$" in out        # 范数：双竖线，不能变成单竖线
    assert "|" not in out.split("$")[1]


def test_fix_math_pipes_keeps_latex_newline():
    # \\ 是换行，后面的 | 是单竖线；不能把第二个反斜杠和 | 拼成 \|
    assert br.fix_math_pipes(r"$$a \\|b|$$") == r"$$a \\\vert b\vert $$"


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
    assert "@A\\3c B \\22 c\\22 @" in out
    assert out.endswith("<p>{{DATE}}</p>2026-01-01")  # 正文里的占位符不被替换


def test_title_cannot_break_out_of_style():
    tpl = (br.ASSETS / "template.html").read_text(encoding="utf-8")
    evil = '</style><script>alert(1)</script><style>\\\n"'
    out = br.fill_template(tpl, evil, evil, "<p>x</p>")
    head = out.split("<body>")[0]
    style = head[head.index("<style>"):head.index("</style>") + len("</style>")]
    assert "<script" not in style and "\n\"" not in style
    assert head.count("</style>") == tpl.split("<body>")[0].count("</style>")
    assert head.count("<script") == tpl.split("<body>")[0].count("<script")


def test_rebase_images_resolves_against_source_dir(tmp_path):
    html = ('<p><img src="figs/a%20b.png" alt="x" /><img src="https://e.org/p.png" />'
            '<img src="data:image/png;base64,AA" /></p>')
    out = br.rebase_images(html, tmp_path / "notes")
    assert f'src="{(tmp_path / "notes" / "figs" / "a b.png").resolve().as_uri()}"' in out
    assert 'src="https://e.org/p.png"' in out and 'src="data:image/png;base64,AA"' in out


def test_chrome_flags_use_given_profile(tmp_path):
    assert f"--user-data-dir={tmp_path / 'p'}" in br.chrome_flags(tmp_path / "p")


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


def _need_browser():
    need_tools("pandoc")
    try:
        br.find_chrome()
    except FileNotFoundError:
        if os.environ.get("KAOYAN_REQUIRE_E2E"):
            raise
        pytest.skip("没有 Chrome / Edge / Chromium")


def _no_leftovers(bdir):
    left = [p.name for p in bdir.iterdir() if p.name.startswith(("run-", "chrome-profile", "_raw"))]
    assert left == [], f"构建目录里留下了浏览器配置或中间文件：{left}"


def test_build_example_end_to_end(tmp_path):
    _need_browser()
    ex = ROOT / "examples" / "synthetic-mechanics"
    res = br.build(ex / "report.md", tmp_path / "report.pdf", "合成示例", "测试", ex / "figs.py")
    print(json.dumps(res, ensure_ascii=False))
    assert res["pages"] >= 1
    assert res["unrendered_math"] == []
    assert res["blank_pages"] == []
    assert res["missing_images"] == []
    assert (tmp_path / "report.pdf").stat().st_size > 10_000
    _no_leftovers(tmp_path / "_build")


def test_parallel_builds_with_relative_images(tmp_path):
    """同一个输出目录里并行构建两份报告；相对路径的图片按源文件目录找，找不到的报到 missing_images。"""
    _need_browser()
    from PIL import Image
    src = tmp_path / "notes"
    (src / "figs").mkdir(parents=True)
    Image.new("RGB", (40, 20), (200, 60, 60)).save(src / "figs" / "ok.png")
    (src / "a.md").write_text("# 甲\n\n![图](figs/ok.png)\n\n$\\|v\\| = 1$\n", encoding="utf-8")
    (src / "b.md").write_text("# 乙\n\n![图](figs/ok.png)\n\n![缺](figs/nope.png)\n", encoding="utf-8")
    out = tmp_path / "out"
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(br.build, src / "a.md", out / "a.pdf", "甲", "测试")
        fb = ex.submit(br.build, src / "b.md", out / "b.pdf", "乙", "测试")
        ra, rb = fa.result(), fb.result()
    assert ra["missing_images"] == [] and ra["unrendered_math"] == []
    assert len(rb["missing_images"]) == 1 and rb["missing_images"][0].endswith("figs/nope.png")
    assert (out / "a.pdf").exists() and (out / "b.pdf").exists()
    _no_leftovers(out / "_build")
