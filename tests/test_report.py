"""排版流水线：纯函数单测 + 用合成示例做一次端到端构建。"""
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT, load, need_tools

br = load("skills/kaoyan-report/scripts/build_report.py", "build_report")
charts = load("skills/kaoyan-report/scripts/charts.py", "charts")


def test_pandoc_preserves_math_and_literal_code():
    need_tools("pandoc")
    md = r"""
$$\|v\|$$

$$\begin{aligned}x \\ |y|\end{aligned}$$

| 示例 | 内容 |
| --- | --- |
| 正文公式 | $|x| + \|v\|$ |
| 行内代码 | `$|a|$` |

```text
$|b|$
$$\|c\|$$
```

    $|d|$
"""
    html = br.md_to_html(md)
    assert r'<span class="math display">\[\|v\|\]</span>' in html
    assert r"\(|x| + \|v\|\)" in html
    assert r"\begin{aligned}x \\ |y|\end{aligned}" in " ".join(html.split())
    assert "<code>$|a|$</code>" in html
    assert "$|b|$" in html and r"$$\|c\|$$" in html and "$|d|$" in html


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


def test_rebase_images_leaves_remote_and_data_urls(tmp_path):
    html = ('<p><img src="https://e.org/p.png" /><img src="data:image/png;base64,AA" /></p>')
    assert br.rebase_images(html, tmp_path / "notes", tmp_path / "out") == (html, {})


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
    left = [p.name for p in bdir.rglob("*") if p.name.startswith(("run-", "chrome-profile", "_raw"))]
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



def test_template_does_not_reinterpret_placeholders_in_values():
    tpl = '<style>@page { @top-left { content: "{{TITLE_CSS}}"; } }</style><p>{{DATE}}</p><!--BODY-->'
    title = "标题里的 {{DATE}} 和 <!--BODY-->"
    date = "日期\\\n次行"
    out = br.fill_template(tpl, title, date, "<p>{{TITLE_CSS}}</p>")
    assert f'content: "{br.css_string(title)}";' in out
    assert f"<p>{date}</p><p>{{{{TITLE_CSS}}}}</p>" in out


def test_retained_html_uses_copied_relative_images(tmp_path):
    _need_browser()
    from PIL import Image
    notes = tmp_path / "notes"
    notes.mkdir()
    image = notes / "private-source.png"
    Image.new("RGB", (20, 12), "green").save(image)
    md = notes / "report.md"
    md.write_text(f"# 正文\n\n![相对图](private-source.png)\n\n![文件链接](<{image.as_uri()}>)\n", encoding="utf-8")
    pdf = tmp_path / "out" / "report.pdf"
    result = br.build(md, pdf, "标题", "")
    assert result["missing_images"] == []
    page, = (pdf.parent / "_build").rglob("report.html")
    html = page.read_text(encoding="utf-8")
    assert "file:" not in html
    assert image.name not in html
    refs = re.findall(r'<img src="([^"]+)"', html)
    assert len(refs) == 2
    assert all((page.parent / ref).read_bytes() == image.read_bytes() for ref in refs)


def test_probe_redacts_query_and_data_url(tmp_path, monkeypatch):
    from html import escape
    from subprocess import CompletedProcess

    page = tmp_path / "report.html"
    page.write_text("<head></head><body></body>", encoding="utf-8")
    sources = [[1, "https://images.example.org/a.png?test=hidden-value", "failed"],
               [2, "data:image/png;base64,dGVzdA==", "failed"]]
    payload = escape(json.dumps({"o": [], "g": sources}))
    monkeypatch.setattr(br.subprocess, "run",
                        lambda args, **kwargs: CompletedProcess(args, 0, stdout=f'<pre id="__ovf">{payload}</pre>'))
    overflow, missing = br.probe_page("chrome", page, tmp_path / "profile")
    assert overflow == []
    assert len(missing) == 2
    assert "images.example.org/a.png" in missing[0] and "hidden-value" not in missing[0]
    assert "image/png" in missing[1] and "2" in missing[1] and "dGVzdA==" not in missing[1]


def test_report_preserves_image_query_and_svg_fragment(tmp_path):
    _need_browser()
    from html import unescape
    from urllib.parse import urlsplit

    notes = tmp_path / "notes"
    image = notes / "figs" / "a #.svg"
    image.parent.mkdir(parents=True)
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
        '<view id="detail" viewBox="0 0 20 20"/><rect width="40" height="20" fill="red"/></svg>',
        encoding="utf-8",
    )
    md = notes / "report.md"
    absolute = str(image).replace("#", "%23").replace(" ", "%20")
    suffix = "?mode=preview&amp;v=1#detail"
    md.write_text(f'# 图\n\n<img src="figs/a%20%23.svg{suffix}">\n\n<img src="{absolute}{suffix}">\n',
                  encoding="utf-8")
    pdf = tmp_path / "out" / "report.pdf"
    result = br.build(md, pdf, "标题", "")
    page, = (pdf.parent / "_build").rglob("report.html")
    refs = [urlsplit(unescape(ref)) for ref in re.findall(r'<img src="([^"]+)"', page.read_text(encoding="utf-8"))]
    assert [(ref.query, ref.fragment) for ref in refs] == [("mode=preview&v=1", "detail")] * 2
    assert result["missing_images"] == []
    assert all((page.parent / ref.path).read_bytes() == image.read_bytes() for ref in refs)


def test_report_rebases_html_src_and_srcset(tmp_path):
    _need_browser()
    from base64 import b64encode
    from PIL import Image

    notes = tmp_path / "notes"
    image = notes / "figs" / "ok.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (24, 16), "green").save(image)
    data = "data:image/png;base64," + b64encode(image.read_bytes()).decode("ascii")
    md = notes / "report.md"
    md.write_text(
        "# 图\n\n"
        "<img data-src='ignored.png' src = 'figs/ok.png'>\n\n"
        "<img src=figs/ok.png>\n\n"
        "<picture><source srcset = 'figs/ok.png 1x'><img src='figs/fallback.png'></picture>\n\n"
        f"<img src='figs/fallback.png' srcset = '{data} 1x, figs/ok.png 2x'>\n",
        encoding="utf-8",
    )
    pdf = tmp_path / "out" / "report.pdf"
    result = br.build(md, pdf, "标题", "")
    assert result["missing_images"] == []
    page, = (pdf.parent / "_build").rglob("report.html")
    html = page.read_text(encoding="utf-8")
    assert 'data-src="ignored.png"' in html
    single, responsive = re.findall(r'srcset="([^"]+)"', html)
    assert (page.parent / single.split()[0]).read_bytes() == image.read_bytes()
    assert responsive.startswith(f"{data} 1x, ")
    assert (page.parent / responsive.split()[-2]).read_bytes() == image.read_bytes()


def test_probe_loads_lazy_images_below_viewport(tmp_path):
    _need_browser()
    from PIL import Image
    chrome = br.find_chrome()
    Image.new("RGB", (24, 16), "green").save(tmp_path / "lazy.png")
    page = tmp_path / "report.html"
    # 本地 file: 地址可能提前载入。固定探测时的“尚未加载”状态，避免依赖浏览器预取。
    page.write_text(
        '<html><head></head><body><div style="height:6000px"></div>'
        '<img id="lazy" loading="lazy" src="lazy.png">'
        '<script>const img = document.getElementById("lazy");'
        'const complete = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "complete").get;'
        'Object.defineProperty(img, "complete", {get: () => img.loading !== "lazy" && complete.call(img)});'
        '</script></body></html>',
        encoding="utf-8",
    )
    assert br.probe_page(chrome, page, tmp_path / "profile") == ([], [])


def test_probe_distinguishes_load_timeout(tmp_path):
    _need_browser()
    from PIL import Image
    chrome = br.find_chrome()
    Image.new("RGB", (24, 16), "green").save(tmp_path / "slow.png")
    page = tmp_path / "report.html"
    page.write_text(
        '<html><head></head><body><img id="slow" src="slow.png">'
        '<script>const img = document.getElementById("slow");'
        'Object.defineProperty(img, "complete", {get: () => false});'
        'img.addEventListener("load", event => event.stopImmediatePropagation());'
        '</script></body></html>',
        encoding="utf-8",
    )
    overflow, missing = br.probe_page(chrome, page, tmp_path / "profile")
    assert overflow == []
    assert len(missing) == 1 and "超时" in missing[0]


def test_parallel_builds_with_relative_images(tmp_path, monkeypatch):
    """先让另一份正文就位，再探测 a.pdf，稳定触发旧版 a_probe.html 命名冲突。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from PIL import Image
    from pypdf import PdfReader

    _need_browser()
    src = tmp_path / "notes"
    (src / "figs").mkdir(parents=True)
    Image.new("RGB", (40, 20), (200, 60, 60)).save(src / "figs" / "ok.png")
    (src / "a.md").write_text("# FIRSTDOCUMENTONLY\n\n![图](figs/ok.png)\n\n$\\|v\\| = 1$\n", encoding="utf-8")
    (src / "b.md").write_text("# SECONDDOCUMENTONLY\n\n![图](figs/ok.png)\n\n![缺](figs/nope.png)\n", encoding="utf-8")
    out = tmp_path / "out"
    second_ready, first_probed = Event(), Event()
    run, probe = br.subprocess.run, br.probe_page

    def scheduled_run(args, **kwargs):
        if str(args[-1]).endswith("/a_probe.html") and any(str(flag).startswith("--print-to-pdf=") for flag in args):
            second_ready.set()
            assert first_probed.wait(30)
        return run(args, **kwargs)

    def scheduled_probe(chrome, page, profile, *args, **kwargs):
        if page.stem != "a":
            return probe(chrome, page, profile, *args, **kwargs)
        try:
            assert second_ready.wait(30)
            return probe(chrome, page, profile, *args, **kwargs)
        finally:
            first_probed.set()

    monkeypatch.setattr(br.subprocess, "run", scheduled_run)
    monkeypatch.setattr(br, "probe_page", scheduled_probe)
    names = ["a", "a_probe"]
    with ThreadPoolExecutor(2) as ex:
        fa = ex.submit(br.build, src / "a.md", out / "a.pdf", "甲", "测试")
        fb = ex.submit(br.build, src / "b.md", out / "a_probe.pdf", "乙", "测试")
        ra, rb = fa.result(), fb.result()
    marks = ["FIRSTDOCUMENTONLY", "SECONDDOCUMENTONLY"]
    for idx, name in enumerate(names):
        text = "\n".join(page.extract_text() for page in PdfReader(out / f"{name}.pdf").pages)
        assert marks[idx] in text and marks[1 - idx] not in text
    assert ra["missing_images"] == [] and ra["unrendered_math"] == []
    assert rb["missing_images"] == ["figs/nope.png"]
    _no_leftovers(out / "_build")
