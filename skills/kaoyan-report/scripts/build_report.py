# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf>=4", "pypdfium2>=4", "pillow>=13"]
# ///
"""Markdown → PDF 报告：pandoc 转 HTML，KaTeX 渲染公式，Chrome（或 Edge、Chromium）无头打印，最后做版面机检。

用法：
  uv run build_report.py <正文.md> <输出.pdf> "<页眉标题>" "<日期>" [图模块.py] [--json] [--strict]

  --json     机检结果按 JSON 打印（默认打印 Python 字典）
  --strict   unrendered_math、blank_pages、overflow、missing_images 任一非空时退出码为 1
  --author   写进 PDF 元数据的作者，默认空
  --chrome   浏览器路径；也可以用环境变量 KAOYAN_CHROME

机检结果：
  pages            页数
  unrendered_math  PDF 文字里残留的 $ 或 \\命令（公式没渲染出来）
  blank_pages      几乎没字也没图的页
  overflow         宽过版心（180 mm）被裁掉的公式、表格、图，给前 40 字
  missing_images   没加载出来的图片（路径写错、文件不在）
  sparse_pages     最后一页以外、内容不到三成的页（通常是大表格或图整块挤到下一页）
  sheet            全部页拼成的一张缩略图，要肉眼看时只看这一张

正文里能用的写法见同目录上一级的 SKILL.md。每次构建在输出 PDF 旁边的 _build/ 中
独占一个子目录，保留 HTML、资源和缩略图。浏览器配置及中间 PDF 在构建结束时清理。
本地图片按 Markdown 源文件所在目录解析，HTML 以相对地址引用构建目录内的副本。只复制常见图片格式（png、jpg、gif、svg、webp 等）；写成图片的其他文件不复制，机检记为缺图。
"""
from __future__ import annotations

import argparse
import html as _html
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import url2pathname

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
CSS_FILES = ("report.css", "extra.css", "cards.css")
PANDOC_FROM = "markdown+pipe_tables+tex_math_dollars+raw_html+fenced_divs"


# ---------- 纯函数（有单测） ----------

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
# 只有这些后缀会被当作图片复制进构建目录。误写成图片的文稿、配置等文件不复制，免得原文落进保留的 _build。
_IMAGE_SUFFIXES = frozenset({".apng", ".avif", ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"})
_SRCSET_SEPARATORS = re.compile(r"[ \t\n\r\f,]*")
_SRCSET_URL = re.compile(r"[^ \t\n\r\f]+")
_SRCSET_DESCRIPTORS = re.compile(r"(?:\([^)]*(?:\)|$)|[^,(])*")


def rebase_srcset(srcset: str, rebase) -> str:
    """只改候选 URL。URL 中间可以有逗号，描述符之间才用逗号分项。"""
    pieces = []
    pos = previous = 0
    while pos < len(srcset):
        pos = _SRCSET_SEPARATORS.match(srcset, pos).end()
        url = _SRCSET_URL.match(srcset, pos)
        if not url:
            break
        value = url.group().rstrip(",")
        pieces.extend((srcset[previous:pos], rebase(value)))
        previous = pos + len(value)
        pos = url.end()
        if previous == pos:
            pos = _SRCSET_DESCRIPTORS.match(srcset, pos).end()
    return "".join(pieces) + srcset[previous:]


class ImageTagParser(HTMLParser):
    CDATA_CONTENT_ELEMENTS = HTMLParser.CDATA_CONTENT_ELEMENTS + ("textarea", "title")

    def __init__(self, html: str, rebase):
        super().__init__()
        self.rebase = rebase
        self.line_offsets = [0, *(m.end() for m in re.finditer("\n", html))]
        self.replacements: list[tuple[int, int, str]] = []

    def handle_starttag(self, tag, attrs):
        self.rewrite(tag, attrs, ">")

    def handle_startendtag(self, tag, attrs):
        self.rewrite(tag, attrs, " />")

    def rewrite(self, tag, attrs, end):
        if tag not in {"img", "source"}:
            return
        updated = []
        for name, value in attrs:
            if value is not None:
                if tag == "img" and name == "src":
                    value = self.rebase(value)
                elif name == "srcset":
                    value = rebase_srcset(value, self.rebase)
            updated.append((name, value))
        if updated == attrs:
            return
        line, col = self.getpos()
        start = self.line_offsets[line - 1] + col
        props = "".join(f" {k}" if v is None else f' {k}="{_html.escape(v)}"' for k, v in updated)
        self.replacements.append((start, start + len(self.get_starttag_text()), f"<{tag}{props}{end}"))


def rebase_images(html: str, base: Path, build: Path) -> tuple[str, dict[str, str]]:
    """复制本地图到构建目录，并保留相对地址到机检标签的映射。"""
    base = base.resolve()
    staged: dict[Path, str] = {}
    labels: dict[str, str] = {}

    def rebase(value: str) -> str:
        address = value.strip(" \t\r\n\f")
        if not address or address.startswith(("#", "//")):
            return value
        is_drive_path = _WINDOWS_DRIVE.match(address)
        parts = urlsplit(address[2:] if is_drive_path else address)
        if parts.scheme == "file":
            authority = f"//{parts.netloc}" if parts.netloc and parts.netloc.lower() != "localhost" else ""
            path = url2pathname(authority + parts.path)
        elif parts.scheme:
            return value
        else:
            path = (address[:2] if is_drive_path else "") + unquote(parts.path)
        if not path:
            return value
        source = (base / path).resolve()
        if source not in staged:
            suffix = source.suffix.lower()
            safe_suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""
            relative = f"images/image-{len(staged) + 1}{safe_suffix}"
            staged[source] = relative
            labels[relative] = (source.relative_to(base).as_posix() if source.is_relative_to(base)
                                else "本地图片（源目录外）")
            if suffix in _IMAGE_SUFFIXES and source.is_file():
                target = build / relative
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(source, target)
        return urlunsplit(("", "", staged[source], parts.query, parts.fragment))

    parser = ImageTagParser(html, rebase)
    parser.feed(html)
    parser.close()
    chunks = []
    pos = 0
    for start, end, tag in parser.replacements:
        chunks.extend((html[pos:start], tag))
        pos = end
    return "".join(chunks) + html[pos:], labels


def inject_figs(html: str, figs: dict) -> str:
    """把 <!--FIG:名字--> 换成 figs[名字]() 返回的 SVG。名字不存在时报错并列出可用的名字。"""
    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in figs:
            raise KeyError(f"正文里有 <!--FIG:{name}-->，图模块的 FIGS 里没有这个名字；现有：{sorted(figs)}")
        return figs[name]()
    return re.sub(r"<!--FIG:(\w+)-->", sub, html)


def css_string(s: str) -> str:
    """转成可以放进 <style> 里 CSS 双引号字符串的内容：引号、反斜杠、尖括号、& 和控制字符
    都写成 CSS 十六进制转义（如 \\3c ），这样标题里的 </style> 关不掉样式块，换行也不会弄坏页眉。"""
    return "".join(f"\\{ord(c):x} " if (c in '"\'\\<>&' or ord(c) < 0x20 or ord(c) == 0x7f) else c for c in s)


def fill_template(tpl: str, title: str, date: str, body: str) -> str:
    slots = {
        "{{TITLE_CSS}}": css_string(title),
        "{{DATE_CSS}}": css_string(date),
        "{{TITLE}}": _html.escape(title),
        "{{DATE}}": _html.escape(date),
        "<!--BODY-->": body,
    }
    return re.sub(r"\{\{(?:TITLE|DATE)(?:_CSS)?\}\}|<!--BODY-->", lambda m: slots[m.group()], tpl)


def leftover_math(text: str) -> list[str]:
    """PDF 文字里残留的 $ 和 \\命令，说明公式没渲染。"""
    return sorted(set(re.findall(r"\$|\\[a-zA-Z]+", text)))[:20]


# ---------- 外部程序 ----------

def find_chrome(explicit: str | None = None) -> str:
    """找一个能无头打印的 Chromium 系浏览器：参数 → 环境变量 → PATH → 各系统默认位置。"""
    cands = [explicit, os.environ.get("KAOYAN_CHROME"), os.environ.get("CHROME_PATH")]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge"):
        cands.append(shutil.which(name))
    system = platform.system()
    if system == "Windows":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                          str(Path(base) / "Microsoft/Edge/Application/msedge.exe")]
    elif system == "Darwin":
        cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for c in cands:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("找不到 Chrome / Edge / Chromium。装一个，或用 --chrome、环境变量 KAOYAN_CHROME 指定路径。")


def chrome_flags(profile: Path) -> list[str]:
    flags = ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             f"--user-data-dir={profile}", "--virtual-time-budget=20000"]
    # GitHub Actions 等 Linux CI 上，Chrome 的沙箱常因用户命名空间受限而起不来
    if platform.system() == "Linux" and os.environ.get("CI"):
        flags.append("--no-sandbox")
    return flags


def remove_profile(profile: Path, tries: int = 5) -> None:
    """删掉无头浏览器的临时配置目录（Cookies、History 等），不留在工作区里。
    Windows 上浏览器的辅助进程可能晚一点才释放文件，删不掉就稍等再试。"""
    for i in range(tries):
        shutil.rmtree(profile, ignore_errors=True)
        if not profile.exists():
            return
        time.sleep(0.5 * (i + 1))


def md_to_html(md: str) -> str:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise FileNotFoundError("找不到 pandoc：https://pandoc.org/installing.html")
    return subprocess.run([pandoc, "-f", PANDOC_FROM, "-t", "html", "--mathjax"], input=md,
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


def load_figs(figmod: Path | None) -> dict:
    if not figmod:
        return {}
    sys.path.insert(0, str(HERE))  # 图模块里 from charts import *
    spec = importlib.util.spec_from_file_location("report_figs", figmod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.FIGS


# ---------- 版面机检 ----------

def scan_pages(pdf: Path, title: str, date: str, build: Path) -> dict:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    texts = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    n = len(doc)
    blank, sparse, sheet = [], [], None
    try:
        from PIL import Image
        thumbs = []
        for i in range(n):
            im = doc[i].render(scale=0.6).to_pil().convert("L")
            w, h = im.size
            px = im.load()
            strip = int(w * 0.045)
            rows = [y for y in range(int(h * 0.08), int(h * 0.94), 4)
                    if any(px[x, y] < 200 for x in range(strip, w - strip, 4))]
            filled = (rows[-1] - rows[0]) / (h * 0.86) if rows else 0
            body = re.sub(r"\d+\s*/\s*\d+", "", texts[i].replace(title, "").replace(date, ""))
            if not rows and len(body.strip()) < 3:
                blank.append(i + 1)
            elif i < n - 1 and filled < 0.3:
                sparse.append(i + 1)
            thumbs.append(im.resize((w // 2, h // 2)))
        cols = 4
        tw, th = thumbs[0].size
        sh = Image.new("L", (cols * tw + (cols + 1) * 6, ((n + cols - 1) // cols) * (th + 6) + 6), 150)
        for k, t in enumerate(thumbs):
            sh.paste(t, (6 + (k % cols) * (tw + 6), 6 + (k // cols) * (th + 6)))
        sheet = build / f"{pdf.stem}_sheet.png"
        sh.save(sheet)
    except ImportError:
        sheet = "没装 Pillow：没有空白页检查和缩略图"
    doc.close()
    return {"pages": n, "unrendered_math": leftover_math("".join(texts)),
            "blank_pages": blank, "sparse_pages": sparse, "sheet": str(sheet)}


PROBE_JS = r"""
<style>html,body{width:180mm!important;max-width:180mm!important;margin:0!important;padding:0!important}</style>
<script>
window.addEventListener('DOMContentLoaded', async () => {
    let timer;
    const deadline = new Promise(resolve => { timer = setTimeout(() => resolve('timeout'), 5000); });
    const images = Array.from(document.images, async (image, index) => {
        const finished = new Promise(resolve => {
            image.addEventListener('load', () => resolve('loaded'), {once: true});
            image.addEventListener('error', () => resolve('failed'), {once: true});
            image.loading = 'eager';
            if (image.complete) resolve(image.naturalWidth ? 'loaded' : 'failed');
        });
        const state = await Promise.race([finished, deadline]);
        if (state === 'loaded') return null;
        return [index + 1, image.currentSrc || image.src, state];
    });
    const missing = (await Promise.all(images)).filter(Boolean);
    clearTimeout(timer);
    await new Promise(resolve => setTimeout(resolve, 300));
    const right = document.body.getBoundingClientRect().right + 1;
    const overflowing = [];
    document.querySelectorAll('.katex-display,table,pre,img,svg,.tiles,.ch,.flow,div').forEach(element => {
        if (element.closest('.katex-display') && !element.classList.contains('katex-display')) return;
        if (element.scrollWidth > element.clientWidth + 2 || element.getBoundingClientRect().right > right) {
            overflowing.push((element.innerText || element.tagName).replace(/\s+/g, ' ').slice(0, 40));
        }
    });
    const result = document.createElement('pre');
    result.id = '__ovf';
    result.textContent = JSON.stringify({o: overflowing.slice(0, 10), g: missing.slice(0, 10)});
    document.body.appendChild(result);
});
</script>
"""


def missing_image_label(index: int, address: str, page: Path, labels: dict[str, str]) -> str:
    parts = urlsplit(address)
    if parts.scheme == "data":
        mime = parts.path.partition(",")[0].partition(";")[0]
        kind = mime if re.fullmatch(r"[\w.+-]+/[\w.+-]+", mime, re.ASCII) else "类型未知"
        return f"第 {index} 张图片（data: {kind}）"
    if parts.scheme in {"https", "http"} or (parts.netloc and not parts.scheme):
        return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
    if parts.scheme == "file":
        path = Path(url2pathname(parts.path))
        if path.is_relative_to(page.parent):
            return labels.get(path.relative_to(page.parent).as_posix(), f"第 {index} 张图片")
    return f"第 {index} 张图片"


def probe_page(chrome: str, page: Path, profile: Path,
               labels: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """在 180 mm 宽的页面里找溢出版心的元素和没加载出来的图片。返回 (overflow, missing_images)。"""
    probe = page.with_name(f"{page.stem}_probe.html")
    probe.write_text(page.read_text(encoding="utf-8").replace("</head>", PROBE_JS + "</head>", 1), encoding="utf-8")
    try:
        dom = subprocess.run([chrome, *chrome_flags(profile), "--window-size=700,1000", "--dump-dom", probe.as_uri()],
                             capture_output=True, text=True, encoding="utf-8", timeout=300, check=True).stdout
        match = re.search(r'<pre id="__ovf">(.*?)</pre>', dom, re.S)
        if not match:
            return ["机检没跑成"], []
        data = json.loads(_html.unescape(match.group(1)))
        missing = []
        for index, address, state in data["g"]:
            label = missing_image_label(index, address, page, labels or {})
            missing.append(f"{label}（加载超时）" if state == "timeout" else label)
        return data["o"], missing
    except subprocess.TimeoutExpired:
        return ["机检超时"], []
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        return ["机检没跑成"], []
    finally:
        probe.unlink(missing_ok=True)


# ---------- 主流程 ----------

def build(src: Path, out: Path, title: str, date: str, figmod: Path | None = None,
          chrome: str | None = None, author: str = "") -> dict:
    from pypdf import PdfReader, PdfWriter

    chrome = find_chrome(chrome)
    body = inject_figs(md_to_html(src.read_text(encoding="utf-8")), load_figs(figmod))
    builds = out.parent / "_build"
    builds.mkdir(parents=True, exist_ok=True)
    bdir = Path(tempfile.mkdtemp(prefix="report-", dir=builds)).resolve()
    body, labels = rebase_images(body, src.parent, bdir)

    shutil.copytree(ASSETS / "katex", bdir / "katex")
    for n in CSS_FILES:
        shutil.copy2(ASSETS / n, bdir / n)
    page = bdir / f"{out.stem}.html"
    page.write_text(fill_template((ASSETS / "template.html").read_text(encoding="utf-8"), title, date, body), encoding="utf-8")

    # 这次构建独占的目录：浏览器配置和中间 PDF 都放这里，结束整个删掉
    run = Path(tempfile.mkdtemp(prefix="run-", dir=bdir))
    profile, raw = run / "chrome-profile", run / "raw.pdf"
    try:
        subprocess.run([chrome, *chrome_flags(profile), "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                        f"--print-to-pdf={raw}", page.as_uri()], check=True, timeout=300, capture_output=True)
        w = PdfWriter(clone_from=PdfReader(str(raw)))
        # Creator 默认是浏览器的 User-Agent（带操作系统和版本），换成固定写法
        w.add_metadata({"/Title": title, "/Author": author, "/Creator": "Chromium (headless)",
                        "/Producer": "kaoyan-report build_report.py"})
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            w.write(f)
        overflow, missing = probe_page(chrome, page, profile, labels)
        result = {"file": out.name, **scan_pages(out, title, date, bdir), "overflow": overflow, "missing_images": missing}
    finally:
        remove_profile(run)
    order = ("file", "pages", "unrendered_math", "blank_pages", "overflow", "missing_images", "sparse_pages", "sheet")
    return {k: result[k] for k in order}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown → PDF 报告，带版面机检")
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("title")
    ap.add_argument("date")
    ap.add_argument("figmod", type=Path, nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--author", default="")
    ap.add_argument("--chrome")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = build(a.src.resolve(), a.out.resolve(), a.title, a.date,
                a.figmod.resolve() if a.figmod else None, a.chrome, a.author)
    print(json.dumps(res, ensure_ascii=False) if a.json else res)
    bad = res["unrendered_math"] or res["blank_pages"] or res["overflow"] or res["missing_images"]
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
