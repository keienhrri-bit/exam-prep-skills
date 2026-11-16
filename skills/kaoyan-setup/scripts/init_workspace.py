# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""把备考工作区模板复制到目标目录，并按科目建文件夹。已有的文件一律不覆盖。

用法：
  uv run init_workspace.py <目标目录> --subject 10_数学 --subject 20_英语 --subject 30_政治 --subject 40_专业课
  python init_workspace.py <目标目录> --subject ... [--dry-run]

打印一张清单：每个路径是“新建”还是“已存在，跳过”。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "workspace-template"
SUBJECT_DIR = "_subject"


def plan(dest: Path, subjects: list[str]) -> list[tuple[Path, Path]]:
    """返回 (源, 目标) 列表；源是模板里的文件，目录用 .gitkeep 占位。"""
    pairs = []
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(TEMPLATE)
        if rel.parts[0] == SUBJECT_DIR:
            for s in subjects:
                pairs.append((src, dest / s / Path(*rel.parts[1:])))
        else:
            pairs.append((src, dest / rel))
    return pairs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="建备考工作区")
    ap.add_argument("dest", type=Path)
    ap.add_argument("--subject", action="append", default=[], help="科目文件夹名，可重复，如 10_数学")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bad = [s for s in a.subject if not s or any(c in s for c in '/\\:*?"<>|') or s.startswith(".")]
    if bad:
        print(f"科目文件夹名不合法：{bad}")
        return 2
    dest = a.dest.expanduser().resolve()
    made = skipped = 0
    for src, dst in plan(dest, a.subject):
        if dst.exists():
            print(f"已存在，跳过  {dst.relative_to(dest)}")
            skipped += 1
            continue
        print(f"{'将新建' if a.dry_run else '新建'}        {dst.relative_to(dest)}")
        made += 1
        if not a.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    print(f"合计：新建 {made}，跳过 {skipped}{'（演练，未写入）' if a.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
