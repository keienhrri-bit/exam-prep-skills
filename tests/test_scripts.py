"""归档、建工作区、句子打标、示例答案核对、隐私扫描。"""
import os
import re
import subprocess
import sys
import time

from conftest import ROOT, load

arch = load("skills/kaoyan-archive/scripts/archive.py", "archive")
init = load("skills/kaoyan-setup/scripts/init_workspace.py", "init_workspace")
tq = load("skills/kaoyan-daily-pack/scripts/tag_quotes.py", "tag_quotes")
scan = load("tools/privacy_scan.py", "privacy_scan")
UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _ws(tmp_path):
    inbox, ws = tmp_path / "inbox", tmp_path / "ws"
    (ws / "10_数学" / "B_学习记录").mkdir(parents=True)
    inbox.mkdir()
    (ws / "10_数学" / "B_学习记录" / "old.md").write_text("同一份内容\n", encoding="utf-8")
    (inbox / "dup.md").write_text("同一份内容\n", encoding="utf-8")
    (inbox / "new.md").write_text("# 极限的定义\n", encoding="utf-8")
    (inbox / "photo.jpg").write_bytes(b"\xff\xd8")
    stale = inbox / "stale.md"
    stale.write_text("很久以前", encoding="utf-8")
    os.utime(stale, (time.time() - 10 * 86400,) * 2)
    return inbox, ws


def test_archive_scan_marks_duplicates_and_skips_old(tmp_path):
    inbox, ws = _ws(tmp_path)
    plan = arch.scan(inbox, ws, days=3, exts=(".md", ".txt"))
    by = {it["name"]: it for it in plan["items"]}
    assert set(by) == {"dup.md", "new.md"}
    assert by["dup.md"]["action"] == "duplicate"
    assert by["dup.md"]["dup_of"] == "10_数学/B_学习记录/old.md"
    assert by["new.md"]["action"] == "classify"


def test_archive_apply_moves_only_approved_and_logs(tmp_path):
    inbox, ws = _ws(tmp_path)
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    for it in plan["items"]:
        if it["name"] == "new.md":
            it.update(action="move", subject="数学", stage="一轮", dest="10_数学/B_学习记录/一轮")
    res = arch.apply(plan, "99_整理记录/归档日志.md")
    assert [d for _, d in res["moved"]] == ["10_数学/B_学习记录/一轮/new.md"]
    assert (inbox / "dup.md").exists() and not (inbox / "new.md").exists()
    log = (ws / "99_整理记录" / "归档日志.md").read_text(encoding="utf-8")
    assert "new.md" in log and "dup.md" in log


def test_archive_apply_refuses_escape_and_changed_source(tmp_path):
    inbox, ws = _ws(tmp_path)
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    new = next(it for it in plan["items"] if it["name"] == "new.md")
    new.update(action="move", dest="../outside")
    assert arch.apply(plan, None)["skipped"][0][1] == "目标不在工作区里"
    new.update(dest="10_数学")
    (inbox / "new.md").write_text("改过了", encoding="utf-8")
    assert "被改过" in arch.apply(plan, None)["skipped"][0][1]
    assert (inbox / "new.md").exists()


def test_init_workspace_creates_and_never_overwrites(tmp_path):
    dest = tmp_path / "备考"
    assert init.main([str(dest), "--subject", "10_数学", "--subject", "40_专业课"]) == 0
    assert (dest / "kaoyan.yaml").exists()
    assert (dest / "10_数学" / "C_试卷与批改").is_dir()
    assert (dest / "40_专业课" / "学习日志.md").exists()
    assert not (dest / "_subject").exists()
    (dest / "AGENTS.md").write_text("我自己的", encoding="utf-8")
    init.main([str(dest), "--subject", "10_数学"])
    assert (dest / "AGENTS.md").read_text(encoding="utf-8") == "我自己的"
    assert init.main([str(dest), "--subject", "../逃逸"]) == 2


def test_tag_quotes_normalizes_punctuation_and_retags():
    corpus = tq.norm("奥斯特发现通电导线能使附近的小磁针偏转，第一次揭示了电流的磁效应。")
    line = "1. 奥斯特发现通电导线能使附近的小磁针偏转, 第一次揭示了电流的磁效应."
    assert tq.tag_line(line, corpus) == ("1. 【讲义原话】" + line[3:], True)
    assert tq.tag_line("- 【讲义原话】法拉第发现了电磁感应", corpus) == ("- 【转述】法拉第发现了电磁感应", False)


def test_example_pack_tags_are_honest():
    """合成资料包里标的【讲义原话】必须真在它自己的“讲义原文”一节里。"""
    text = (ROOT / "skills/kaoyan-daily-pack/references/example-pack.md").read_text(encoding="utf-8")
    corpus = tq.norm(text.split("## 五、讲义原文", 1)[1])
    tagged = [ln for ln in text.splitlines() if re.match(r"^\d+\. 【(讲义原话|转述)】", ln)]
    assert len(tagged) == 4
    for line in tagged:
        _, found = tq.tag_line(line, corpus)
        assert found == ("【讲义原话】" in line), line


def test_example_answers_check_out():
    r = subprocess.run([sys.executable, str(ROOT / "examples/synthetic-mechanics/check_answers.py")],
                       capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert r.returncode == 0, r.stdout + r.stderr


def test_privacy_scan_catches_planted_leaks(tmp_path):
    # 拼接写法：让这个测试文件本身不被全仓扫描命中
    leak = ("联系 someone" + "@mail.test.cn，路径 C:" + "\\Users\\alice\\Desktop，令牌 ghp_" + "x" * 30
            + "，总分 88 " + "/ 150，手机 139" + "12345678")
    hits = scan.scan_text("a.md", leak, scan.RULES)
    kinds = {h.split("  ")[1] for h in hits}
    assert {"邮箱", "手机号", "Windows 用户路径", "GitHub token", "考试满分写法（像真实成绩）"} <= kinds
    ok = "路径写成 ~/Downloads 或 C:\\Users\\<你的用户名>\\Downloads；作者 1+bot@users.noreply.github.com"
    assert scan.scan_text("ok.md", ok, scan.RULES) == []


def test_repo_passes_privacy_scan():
    r = subprocess.run([sys.executable, str(ROOT / "tools/privacy_scan.py"), "--root", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert r.returncode == 0, r.stdout
