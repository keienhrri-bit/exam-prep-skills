import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def load(rel: str, name: str):
    """按路径导入 skill 里的脚本（它们不是包）。"""
    path = ROOT / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def link_dir(link, target):
    """建目录链接：Windows 用目录联接（不要管理员权限），其他系统用符号链接。建不了就跳过。"""
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except (OSError, AttributeError, NotImplementedError) as e:
        pytest.skip(f"建不了目录链接：{e}")


def need_tools(*names):
    """缺外部程序时跳过；CI 里设 KAOYAN_REQUIRE_E2E=1 时改成失败。"""
    missing = [n for n in names if not shutil.which(n)]
    if missing:
        if os.environ.get("KAOYAN_REQUIRE_E2E"):
            pytest.fail(f"CI 要求跑端到端测试，但缺：{missing}")
        pytest.skip(f"缺：{missing}")
