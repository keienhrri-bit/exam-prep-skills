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
    assert cc["name"] == mk["plugins"][0]["name"] == cx["name"] == "kaoyan-study-skills"
    assert cc["version"] == cx["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## {re.escape(cc['version'])}\b", changelog, re.M), "CHANGELOG 没有当前版本"
    assert (ROOT / cx["onboardingSkill"]).exists()
