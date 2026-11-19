"""排版流水线：纯函数单测 + 用合成示例做一次端到端构建。"""
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT, link_dir, load, need_tools

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


PNG = b"\x89PNG\r\n\x1a\n"


def _copied(build):
    return sorted(p.read_bytes() for p in build.rglob("*") if p.is_file())


def test_rebase_images_leaves_remote_and_data_urls(tmp_path):
    html = ('<p><img src="https://e.org/p.png" /><img src="data:image/png;base64,AA" /></p>')
    assert br.rebase_images(html, tmp_path / "notes", tmp_path / "out") == (html, {}, [])


def test_rebase_images_copies_only_image_files(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    figure = notes / "fig.png"
    figure.write_bytes(PNG + b"synthetic")
    (tmp_path / "private.txt").write_text("SECRET-BYTES-0042", encoding="utf-8")
    (notes / "config.json").write_text('{"token": "SECRET-BYTES-0043"}', encoding="utf-8")
    build = tmp_path / "out"
    build.mkdir()
    html = ('<p><img src="fig.png" /><img src="../private.txt" />'
            '<img srcset="config.json 1x, fig.png 2x" /></p>')
    out, labels, rejected = br.rebase_images(html, notes, build)
    assert _copied(build) == [figure.read_bytes()]
    assert "private.txt" not in out and "config.json" not in out
    assert len(rejected) == 2 and "config.json：不是图片文件，没复制" in rejected
    assert not any("private" in label for label in labels.values())
    assert sorted(set(labels.values()) - set(rejected)) == ["fig.png"]


def test_rebase_images_copies_only_from_source_and_declared_asset_dirs(tmp_path):
    notes, shared, outside = (tmp_path / name for name in ("notes", "shared", "outside"))
    for folder in (notes, shared, outside):
        folder.mkdir()
    (notes / "fig.png").write_bytes(PNG + b"in-source")
    (shared / "logo.png").write_bytes(PNG + b"declared")
    secret = outside / "private-photo.png"
    secret.write_bytes(PNG + b"OUTSIDE-BYTES-0042")
    # 同一张源目录外的图用三种写法引用，其中一处是不会被浏览器选中的 srcset 候选
    html = ('<img src="fig.png"><img src="../shared/logo.png"><img src="../outside/private-photo.png">'
            f'<img src="{secret.as_uri()}"><img src="fig.png" srcset="fig.png 1x, {secret} 3x">')
    build = tmp_path / "out"
    build.mkdir()
    out, labels, rejected = br.rebase_images(html, notes, build, asset_dirs=[shared])
    assert _copied(build) == sorted([PNG + b"in-source", PNG + b"declared"])
    assert "private-photo" not in out and "outside" not in out
    assert len(rejected) == 1 and "private-photo" not in rejected[0] and "outside" not in rejected[0]
    assert sorted(set(labels.values()) - set(rejected)) == ["fig.png", "shared/logo.png"]
    # 没声明素材目录时，源目录以外的一律不复制
    bare = tmp_path / "bare"
    bare.mkdir()
    _, _, rejected = br.rebase_images(html, notes, bare)
    assert _copied(bare) == [PNG + b"in-source"] and len(rejected) == 2


def test_rebase_images_refuses_links_out_of_source_dir(tmp_path):
    notes, outside = tmp_path / "notes", tmp_path / "outside"
    notes.mkdir()
    outside.mkdir()
    (outside / "photo.png").write_bytes(PNG + b"LINKED-OUTSIDE")
    link_dir(notes / "linked", outside)
    build = tmp_path / "out"
    build.mkdir()
    out, _, rejected = br.rebase_images('<img src="linked/photo.png">', notes, build)
    assert _copied(build) == [] and len(rejected) == 1 and "linked" not in out


def test_rebase_images_checks_content_not_just_suffix(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "notes.png").write_text("SECRET-TEXT-0044 不是图片", encoding="utf-8")
    (notes / "ok.svg").write_text('<?xml version="1.0"?>\n<!-- 注释 -->\n<svg xmlns="http://www.w3.org/2000/svg"/>',
                                  encoding="utf-8")
    build = tmp_path / "out"
    build.mkdir()
    _, _, rejected = br.rebase_images('<img src="notes.png"><img src="ok.svg">', notes, build)
    assert [p.suffix for p in build.rglob("*") if p.is_file()] == [".svg"]
    assert rejected == ["notes.png：不是图片文件，没复制"]


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "GIF", "BMP", "WEBP", "ICO"])
def test_looks_like_image_accepts_common_formats(fmt):
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, fmt)
    assert br.looks_like_image(buffer.getvalue())


@pytest.mark.parametrize("data,expected", [
    (b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1", True),
    (b'\xef\xbb\xbf<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "x.dtd">\n<svg width="1"/>', True),
    (b"<svg>", True),
    (b"%PDF-1.7\n", False),
    (b"PK\x03\x04", False),
    ("姓名：某某\n<svg>".encode("utf-8"), False),
    (b"", False),
])
def test_looks_like_image_signatures(data, expected):
    assert br.looks_like_image(data) is expected


def test_rebase_images_survives_malformed_url(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "fig.png").write_bytes(PNG + b"ok")
    build = tmp_path / "out"
    build.mkdir()
    bad = "https://[broken-host/a.png?token=hidden-value"
    out, _, rejected = br.rebase_images(f'<img src="{bad}"><img src="fig.png"><img srcset="{bad} 2x">', notes, build)
    assert _copied(build) == [PNG + b"ok"]
    assert len(rejected) == 1 and "格式有误" in rejected[0]
    assert "broken-host" not in out + rejected[0] and "hidden-value" not in out + rejected[0]


def test_probe_survives_malformed_reported_address(tmp_path, monkeypatch):
    from html import escape
    from subprocess import CompletedProcess

    page = tmp_path / "report.html"
    page.write_text("<head></head><body></body>", encoding="utf-8")
    payload = escape(json.dumps({"o": [], "g": [[1, "http://[broken-host/a.png", "failed"]]}))
    monkeypatch.setattr(br.subprocess, "run",
                        lambda args, **kwargs: CompletedProcess(args, 0, stdout=f'<pre id="__ovf">{payload}</pre>'))
    overflow, missing = br.probe_page("chrome", page, tmp_path / "profile")
    assert overflow == [] and len(missing) == 1 and "broken-host" not in missing[0]


def test_rebase_images_follows_remote_base_href(tmp_path):
    build = tmp_path / "out"
    build.mkdir()
    html = ('<base href="https://cdn.example.org/a/"><p><img src="fig.png?v=1">'
            '<img srcset="../b.png 2x"><img src="//other.example.org/c.png"></p>')
    out, labels, rejected = br.rebase_images(html, tmp_path, build)
    assert "<base" not in out
    assert 'src="https://cdn.example.org/a/fig.png?v=1"' in out
    assert 'srcset="https://cdn.example.org/b.png 2x"' in out
    assert 'src="https://other.example.org/c.png"' in out
    assert (labels, rejected, _copied(build)) == ({}, [], [])


def test_file_url_path_maps_other_hosts_only_on_windows():
    assert br.file_url_path("fileserver", "/srv/fig.png", windows=False) is None
    assert br.file_url_path("localhost", "/srv/a%20b.png", windows=False) == "/srv/a b.png"
    assert br.file_url_path("", "/srv/fig.png", windows=False) == "/srv/fig.png"
    if os.name == "nt":
        assert br.file_url_path("fileserver", "/share/fig.png", windows=True) == r"\\fileserver\share\fig.png"
        assert br.file_url_path("", "/C:/notes/fig.png", windows=True) == r"C:\notes\fig.png"


@pytest.mark.skipif(os.name == "nt", reason="POSIX 上才会把 file://主机/路径 当成本机路径")
def test_rebase_images_refuses_file_url_with_remote_host_on_posix(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    image = notes / "fig.png"
    image.write_bytes(PNG + b"local")
    build = tmp_path / "out"
    build.mkdir()
    # 路径的第一段成了主机名。旧版把 //主机/其余路径 当成本机路径，碰巧就是这张图。
    _, _, rejected = br.rebase_images(f'<img src="file://{str(image).lstrip("/")}">', notes, build)
    assert _copied(build) == [] and len(rejected) == 1 and "主机" in rejected[0]

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


def test_build_reports_refused_images_and_keeps_going(tmp_path):
    _need_browser()
    from PIL import Image
    notes, outside = tmp_path / "notes", tmp_path / "outside"
    notes.mkdir()
    outside.mkdir()
    Image.new("RGB", (24, 16), "green").save(notes / "ok.png")
    secret = outside / "photo.png"
    Image.new("RGB", (24, 16), "red").save(secret)
    md = notes / "report.md"
    md.write_text("# 图\n\n![好](ok.png)\n\n![外](../outside/photo.png)\n\n"
                  '<img src="https://[broken-host/a.png">\n\n'
                  f'<img src="ok.png" srcset="ok.png 1x, {secret.as_uri()} 3x">\n', encoding="utf-8")
    pdf = tmp_path / "out" / "report.pdf"
    result = br.build(md, pdf, "标题", "")
    assert pdf.stat().st_size > 1000 and result["overflow"] == []
    assert len(result["missing_images"]) == 2, result["missing_images"]
    joined = " ".join(result["missing_images"])
    assert "photo" not in joined and "outside" not in joined and "broken-host" not in joined
    kept = [p.read_bytes() for p in (pdf.parent / "_build").rglob("*") if p.is_file()]
    assert secret.read_bytes() not in kept
    # 显式声明素材目录后，这张图照常复制、加载
    pdf = tmp_path / "declared" / "report.pdf"
    result = br.build(md, pdf, "标题", "", asset_dirs=[outside])
    assert result["overflow"] == [] and len(result["missing_images"]) == 1
    assert "格式有误" in result["missing_images"][0]


def test_build_refuses_missing_asset_dir(tmp_path):
    md = tmp_path / "report.md"
    md.write_text("# 正文\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="--assets"):
        br.build(md, tmp_path / "out" / "report.pdf", "标题", "", chrome=__file__,
                 asset_dirs=[tmp_path / "没有这个目录"])
    assert not (tmp_path / "out").exists()


def test_report_resolves_images_against_local_base_href(tmp_path):
    _need_browser()
    from PIL import Image
    notes = tmp_path / "notes"
    (notes / "sub").mkdir(parents=True)
    Image.new("RGB", (24, 16), "green").save(notes / "sub" / "fig.png")
    Image.new("RGB", (24, 16), "blue").save(notes / "abs.png")
    md = notes / "report.md"
    md.write_text(f'<base href="sub/">\n\n# 图\n\n<img src="fig.png">\n\n<img src="{notes / "abs.png"}">\n',
                  encoding="utf-8")
    pdf = tmp_path / "out" / "report.pdf"
    result = br.build(md, pdf, "标题", "")
    assert result["missing_images"] == [] and result["overflow"] == []
    page, = (pdf.parent / "_build").rglob("report.html")
    html = page.read_text(encoding="utf-8")
    assert "<base" not in html
    refs = re.findall(r'<img src="([^"]+)"', html)
    assert [(page.parent / ref).read_bytes() for ref in refs] == [
        (notes / "sub" / "fig.png").read_bytes(), (notes / "abs.png").read_bytes()]


def test_probe_finds_images_added_after_load(tmp_path):
    _need_browser()
    from PIL import Image
    chrome = br.find_chrome()
    Image.new("RGB", (24, 16), "green").save(tmp_path / "ok.png")
    page = tmp_path / "report.html"
    page.write_text(
        '<html><head></head><body><p>正文</p><script>'
        'const add = src => { const img = new Image(); img.src = src; document.body.appendChild(img); };'
        'window.addEventListener("load", () => {'
        ' add("ok.png"); add("missing-on-load.png"); setTimeout(() => add("missing-later.png"), 150); });'
        '</script></body></html>',
        encoding="utf-8",
    )
    assert br.probe_page(chrome, page, tmp_path / "profile") == ([], ["第 2 张图片", "第 3 张图片"])
