"""skill 和插件清单的格式：skills.sh、Claude Code 插件、Codex 插件都能认。"""
import json
import re

import pytest

from conftest import ROOT, SKILLS

SKILL_DIRS = sorted(p for p in SKILLS.iterdir() if p.is_dir())


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} 没有 YAML 头"
    fields = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M))
    return fields, text[m.end():]


def test_nine_skills():
    assert [p.name for p in SKILL_DIRS] == sorted([
        "kaoyan-setup", "kaoyan-tutor", "kaoyan-grading", "kaoyan-plan", "kaoyan-archive",
        "kaoyan-daily-pack", "kaoyan-report", "kaoyan-retro", "physics-svg-tutor"])


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_frontmatter(d):
    fields, body = frontmatter(d / "SKILL.md")
    assert fields.get("name") == d.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", d.name) and len(d.name) <= 64
    assert 0 < len(fields.get("description", "")) <= 1024
    assert len(body.strip()) > 200


@pytest.mark.parametrize("d", SKILL_DIRS, ids=lambda p: p.name)
def test_skill_internal_links_exist(d):
    """SKILL.md 里提到的 references/、scripts/、assets/ 下的文件都要真的存在。"""
    _, body = frontmatter(d / "SKILL.md")
    for rel in re.findall(r"`((?:references|scripts|assets)/[^`\s]+?\.(?:md|py|svg|css|html))`", body):
        assert (d / rel).exists(), f"{d.name}: {rel} 不存在"


def test_agents_frontmatter():
    agents = sorted((ROOT / "agents").glob("*.md"))
    assert [a.stem for a in agents] == ["finder", "regrader", "transcriber", "writer"]
    for a in agents:
        fields, _ = frontmatter(a)
        assert fields["name"] == a.stem and fields.get("description") and fields.get("model")


def test_manifests_agree():
    cc = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    mk = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    cx = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert cc["name"] == mk["plugins"][0]["name"] == cx["name"] == "exam-prep-skills"
    assert cc["version"] == mk["plugins"][0].get("version") == cx["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = re.search(r"^## (\d+\.\d+\.\d+)\b", changelog, re.M)
    assert latest and latest.group(1) == cc["version"], "CHANGELOG 最新版本与清单不一致"
    assert (ROOT / cx["onboardingSkill"]).exists()


def _version(text):
    return tuple(int(part) for part in text.split("."))


def test_dependencies_clear_known_advisories():
    """Pillow 13.0.0 修了一批安全问题，同时不再支持 Python 3.10；随附的 KaTeX 要不低于 0.18.2（GHSA-238p-pmpm-9mq7）。"""
    scripts = [*SKILLS.rglob("*.py"), *(ROOT / "examples").rglob("*.py"), *(ROOT / "tools").rglob("*.py")]
    headers = {}
    for script in scripts:
        m = re.search(r"^# /// script\n(.*?)^# ///$", script.read_text(encoding="utf-8"), re.M | re.S)
        if m:
            headers[script.relative_to(ROOT).as_posix()] = m.group(1)
    assert len(headers) == 5
    for rel, header in headers.items():
        assert '# requires-python = ">=3.11"' in header, rel
        for floor in re.findall(r'"pillow>=([\d.]+)"', header, re.I):
            assert _version(floor) >= (13,), rel
    assert re.search(r"^pillow>=13\b", (ROOT / "requirements-dev.txt").read_text(encoding="utf-8"), re.M)
    lock = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    assert "python_full_version < '3.11'" not in lock
    pins = dict(re.findall(r"^([a-z0-9-]+)==([\d.]+)", lock, re.M))
    assert _version(pins["pillow"]) >= (13, 0, 0)
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    matrix = re.search(r"^\s+python: \[(.*)\]$", ci, re.M)
    assert matrix and '"3.11"' in matrix.group(1), "CI 要在最低支持的 Python 上跑"

    katex_js = (SKILLS / "kaoyan-report/assets/katex/katex.min.js").read_text(encoding="utf-8")
    katex = re.search(r'version:"(\d+\.\d+\.\d+)"', katex_js).group(1)
    assert _version(katex) >= (0, 18, 2)
    for doc in ("README.md", "README.en.md", "skills/kaoyan-report/assets/katex/README.txt"):
        assert f"KaTeX {katex}" in (ROOT / doc).read_text(encoding="utf-8"), doc
    for doc in ("README.md", "README.en.md", "skills/kaoyan-report/SKILL.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert "3.10" not in text and "3.11" in text, doc


@pytest.mark.parametrize("path,pattern", [
    ("kaoyan-report/SKILL.md", r"^## 流程\s*\n(1\. [^\n]*)"),
    ("kaoyan-setup/assets/workspace-template/CLAUDE.md", r"^(- \*\*外援的文字不进成稿\*\*[^\n]*)"),
], ids=["skill", "template"])
def test_long_writer_setting_is_honored_in_workflow_and_template(path, pattern):
    text = (SKILLS / path).read_text(encoding="utf-8")
    step = re.search(pattern, text, flags=re.M).group(1)
    assert re.search(r"先读 `kaoyan.yaml` 的 `roles\.long_writer`", step)
    assert re.search(r"`main`[^。]*主会话", step)
    assert re.search(r"`subagent`[^。]*5000 字[^。]*新推导[^。]*`writer`", step)
    config = (SKILLS / "kaoyan-setup/assets/workspace-template/kaoyan.yaml").read_text(encoding="utf-8")
    assert re.search(r"^  long_writer: subagent\b", config, flags=re.M)
