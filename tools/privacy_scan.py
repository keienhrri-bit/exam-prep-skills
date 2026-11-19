"""发布前的隐私扫描：邮箱、手机号、身份证号、本机用户路径、token、cookie 名、考试分数写法，以及 git 提交作者。

用法：
  python tools/privacy_scan.py [--root .] [--extra 私有词表.txt]

- 仓库里只放通用规则。个人的词（真实姓名、用户名、院校、科目代码等）写在一个**不提交**的文件里，
  每行一个正则，用 --extra 传入；默认会读 .work/privacy-extra.txt（.work/ 已在 .gitignore 里）。
- 文本文件逐行查全部规则，支持 UTF-8 和带 BOM 的 UTF-16。未知扩展名的 UTF-8 文件只有不含 NUL 字节才按文本查。
  PDF、PNG 等二进制文件查原始字节里的路径和邮箱，PDF 另外抽文字和元数据再查一遍。
  未知扩展名、以 UTF-16 BOM 开头的文件既按 UTF-16 文本查，也查原始字节。
- 输出只有文件、位置（文本是行号:列号，二进制是字节偏移）、规则名和计数，不打印命中的内容：
  私有词表只说第几条，提交作者只给提交号。这样在公开 CI 的日志里跑也不会多出一份明文。
- 有命中时退出码 1。扫描目录不存在、一个文件都没扫到、--extra 指定的词表不存在、
  git 仓库里读不出提交作者时退出码 2：没查完不算通过。
"""
from __future__ import annotations

import argparse
import codecs
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", ".work", "_build", "node_modules", ".venv", "__pycache__", ".pytest_cache"}
TEXT_EXT = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".css", ".html", ".js", ".csv", ".svg", ".toml", ".cfg", ".ini", "",
            ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd", ".ts", ".tsx", ".mjs", ".cjs", ".xml", ".env",
            ".tex", ".bib", ".r", ".sql", ".rb", ".go", ".rs", ".java", ".c", ".h", ".cpp", ".lua", ".php", ".ipynb"}
BINARY_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".woff2", ".woff", ".ttf", ".otf",
              ".zip", ".gz", ".7z", ".tar", ".exe", ".dll", ".so", ".dylib", ".pyc"}
SKIP_BINARY_EXTRA_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".woff2", ".woff", ".ttf", ".zip"}
VENDORED = ("skills/kaoyan-report/assets/katex/",)
ALLOWED_EMAIL = re.compile(r"@(users\.noreply\.github\.com|example\.(com|org))$", re.I)

RULES: list[tuple[str, re.Pattern]] = [
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("手机号", re.compile(r"(?<![\d.])1[3-9]\d{9}(?![\d.])")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("QQ 号", re.compile(r"(?i)qq\s*[:：号]?\s*\d{5,11}")),
    ("Windows 用户路径", re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+(?![<{%*$])[^\\/\s\"'`]+")),
    ("Git Bash 用户路径", re.compile(r"(?i)/[a-z]/users/(?![<{%*$])[^/\s\"'`]+")),
    ("macOS / Linux 用户路径", re.compile(r"(?<![\w.~])/(?:Users|home)/(?![<{%*$])[A-Za-z0-9._-]+/")),
    ("OpenAI / Anthropic key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{16,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("cookie", re.compile(r"(?i)(?:__Secure-[0-9A-Z]+PSID\w*|\bSAPISID\b|\bsessionKey=|\bcookie\s*[:=]\s*\S{20,})")),
    ("考试满分写法（像真实成绩）", re.compile(r"(?<![\d.])\d{1,3}\s*/\s*(?:150|100|300|500)(?![\d.])")),
]
BINARY_RULES = [
    ("二进制里的用户路径", re.compile(rb"(?i)[a-z]:[\\/]{1,2}users[\\/]{1,2}[^\\/\x00\s]+|/(?:Users|home)/[A-Za-z0-9._-]+/")),
    ("二进制里的 file:// 链接", re.compile(rb"file:///[^\x00\s)>]+")),
    ("二进制里的邮箱", re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]{2,}")),
]


def load_extra(paths: list[Path]) -> list[tuple[str, re.Pattern]]:
    """私有词表的规则名只写第几条：词本身就是要保密的内容，不能出现在输出里。"""
    rules = []
    for p in paths:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    rules.append((f"私有词表第 {len(rules) + 1} 条", re.compile(line.strip(), re.I)))
    return rules


UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)


def decode_text(p: Path, data: bytes) -> str | None:
    """按文本查就返回解码后的字符串，按二进制查返回 None。"""
    suf = p.suffix.lower()
    if suf in BINARY_EXT:
        return None
    if data.startswith(UTF16_BOMS):
        return data.decode("utf-16", errors="replace")
    if suf in TEXT_EXT:
        return data.decode("utf-8", errors="replace")
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            yield p


def scan_text(rel: str, text: str, rules) -> list[str]:
    """命中写成“文件:行:列  规则名”，不带命中的内容。"""
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        for name, rx in rules:
            for m in rx.finditer(line):
                if name == "邮箱" and ALLOWED_EMAIL.search(m.group(0)):
                    continue
                hits.append(f"{rel}:{no}:{m.start() + 1}  {name}")
    return hits


def scan_binary(rel: str, data: bytes, extra) -> list[str]:
    """命中写成“文件  规则名  偏移 N”，不带命中的内容。"""
    hits = []
    for name, rx in BINARY_RULES:
        for m in rx.finditer(data):
            if name == "二进制里的邮箱" and ALLOWED_EMAIL.search(m.group(0).decode("latin-1")):
                continue
            hits.append(f"{rel}  {name}  偏移 {m.start()}")
    if rel.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            r = PdfReader(str(rel_root / rel))
            meta = " ".join(str(v) for v in (r.metadata or {}).values())
            text = meta + "\n" + "\n".join((pg.extract_text() or "") for pg in r.pages)
            hits += [h.replace(f"{rel}:", f"{rel}（PDF 文字）:") for h in scan_text(rel, text, RULES + extra)]
        except ImportError:
            hits.append(f"{rel}  没装 pypdf，PDF 文字没查")
    return hits


def find_git_marker(root: Path) -> Path | None:
    """识别普通仓库、工作树的 .git 文件和裸仓库，即使 Git 无法打开它们。"""
    for directory in (root, *root.parents):
        if os.path.lexists(directory / ".git"):
            return directory / ".git"
        if (os.path.lexists(directory / "HEAD") and (directory / "objects").is_dir()
                and (directory / "refs").is_dir()):
            return directory
    return None


def git_authors(root: Path) -> tuple[list[str], str | None, bool]:
    """返回 (可疑的提交作者, 说明, 是否没查成)。"""
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env={**os.environ, "LC_ALL": "C"})

    not_repo = "不是 git 仓库，没查提交作者"
    marker = find_git_marker(root)
    try:
        discovery = git("rev-parse", "--absolute-git-dir")
        if discovery.returncode != 0:
            if not marker and discovery.stderr.startswith("fatal: not a git repository"):
                return [], not_repo, False
            return [], "Git 无法读取仓库，没查提交作者，不算通过。", True
        if marker:
            # 损坏的内层仓库可能被 Git 跳过，误读上级仓库的提交。
            expected = git("rev-parse", "--resolve-git-dir", str(marker))
            if (expected.returncode != 0
                    or Path(expected.stdout.strip()).resolve() != Path(discovery.stdout.strip()).resolve()):
                return [], "Git 无法读取扫描目录对应的仓库，没查提交作者，不算通过。", True
        if git("rev-parse", "--verify", "-q", "HEAD^{commit}").returncode != 0:
            head = git("symbolic-ref", "--quiet", "HEAD")
            if head.returncode == 0 and head.stdout.startswith("refs/heads/"):
                refs = git("for-each-ref", "--format=%(refname)")
                if refs.returncode == 0 and not refs.stdout.strip() and not refs.stderr.strip():
                    return [], "还没有提交，没查提交作者", False
            return [], "Git 无法读取 HEAD，没查提交作者，不算通过。", True
        r = git("log", "--encoding=UTF-8", "--format=%h%x1f%ae%x1f%ce")
    except FileNotFoundError:
        if not marker:
            return [], not_repo, False
        return [], "没找到 Git，没查提交作者，不算通过。", True
    except OSError:
        return [], "无法运行 Git，没查提交作者，不算通过。", True
    if r.returncode != 0 or not r.stdout.strip():
        return [], "git log 没跑成，提交作者未查完，不算通过。", True
    # 只报提交号和次数，不打印名字和邮箱
    bad: dict[tuple[str, str], list] = {}
    for line in r.stdout.splitlines():
        commit, *emails = line.split("\x1f")
        for role, email in zip(("提交作者", "提交者"), emails):
            if email and not ALLOWED_EMAIL.search(email) and email != "noreply@github.com":
                bad.setdefault((role, email), [commit, 0])[1] += 1
    return ([f"git {role}邮箱不是 noreply  最近一次是提交 {commit}，共 {count} 个提交"
             for (role, _), (commit, count) in bad.items()], None, False)


rel_root = Path(".")


def main(argv: list[str] | None = None) -> int:
    global rel_root
    ap = argparse.ArgumentParser(description="发布前隐私扫描")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--extra", type=Path, action="append", default=[])
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    root = rel_root = a.root.resolve()
    if not root.is_dir():
        print(f"扫描目录不存在或不是目录：{a.root}。没有扫描，不算通过。")
        return 2
    missing = [p for p in a.extra if not p.is_file()]
    if missing:
        print(f"--extra 指定的词表不存在：{', '.join(map(str, missing))}。没有扫描，不算通过。")
        return 2
    extra = load_extra(a.extra + [root / ".work" / "privacy-extra.txt"])
    me = Path(__file__).resolve()
    hits, n = [], 0
    for p in files(root):
        if p.resolve() == me:
            continue
        n += 1
        rel = p.relative_to(root).as_posix()
        data = p.read_bytes()
        text = decode_text(p, data)
        if text is not None:
            # 第三方原样打包的文件（KaTeX）只查通用规则；私有词表里的数字会在压缩代码里误报
            rules = RULES if rel.startswith(VENDORED) else RULES + extra
            hits += scan_text(rel, text, rules)
        # 未知后缀的文件以 UTF-16 BOM 开头也可能是二进制：错位的 ASCII 解码后会变成乱码，所以原始字节也查
        if text is None or (p.suffix.lower() not in TEXT_EXT and data.startswith(UTF16_BOMS)):
            hits += scan_binary(rel, data, extra)
            # 压缩过的 PDF、图片、字体里按私有词表搜原始字节只会误报；PDF 已在上面抽文字查过
            if extra and p.suffix.lower() not in SKIP_BINARY_EXTRA_EXT:
                raw_text = data.decode("latin-1")
                for name, rx in extra:
                    m = rx.search(raw_text)
                    if m:
                        hits.append(f"{rel}  {name}（二进制）  偏移 {m.start()}")
    authors, note, git_failed = git_authors(root)
    hits += authors
    print(f"扫描 {n} 个文件，私有词表 {len(extra)} 条，命中 {len(hits)} 处")
    for h, count in Counter(hits).items():
        print("  " + h + (f"  ×{count}" if count > 1 else ""))
    if note:
        print(f"  说明：{note}")
    if n == 0:
        print("一个文件都没扫到，不算通过。")
        return 2
    if git_failed:
        return 2
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
