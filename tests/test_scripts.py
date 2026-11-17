"""归档、建工作区、句子打标、示例答案核对、隐私扫描。"""
import os
import re
import subprocess
import sys
import time

import pytest

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


def _link_dir(link, target):
    """建目录链接：Windows 用目录联接（不要管理员权限），其他系统用符号链接。建不了就跳过。"""
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except (OSError, AttributeError, NotImplementedError) as e:
        pytest.skip(f"建不了目录链接：{e}")


def _link_file(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"建不了文件符号链接：{e}")


def test_archive_refuses_log_outside_workspace(tmp_path):
    inbox, ws = _ws(tmp_path)
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    next(it for it in plan["items"] if it["name"] == "new.md").update(action="move", dest="10_数学")
    for bad in ("../outside.md", str(tmp_path / "abs.md")):
        with pytest.raises(ValueError, match="日志路径"):
            arch.apply(plan, bad)
    assert (inbox / "new.md").exists(), "日志路径不合法时一个文件都不能动"
    assert not (tmp_path / "outside.md").exists() and not (tmp_path / "abs.md").exists()


def test_archive_ignores_symlinks_in_inbox(tmp_path):
    inbox, ws = _ws(tmp_path)
    secret = tmp_path / "elsewhere.md"
    secret.write_text("收件夹外的文件\n", encoding="utf-8")
    _link_file(inbox / "link.md", secret)
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    assert "link.md" not in {it["name"] for it in plan["items"]}
    # 即使有人手工把链接写进方案，执行时也不移动
    plan["items"].append({"src": str(inbox.resolve() / "link.md"), "name": "link.md", "sha256": arch.sha256(secret),
                          "action": "move", "dest": "10_数学", "dup_of": None, "note": ""})
    res = arch.apply(plan, None)
    assert ("源文件是符号链接，不移动" in [why for _, why in res["skipped"]])
    assert secret.exists() and not (ws / "10_数学" / "link.md").exists()


def test_init_workspace_does_not_write_through_links(tmp_path):
    dest, outside = tmp_path / "备考", tmp_path / "外面"
    dest.mkdir()
    outside.mkdir()
    _link_dir(dest / "10_数学", outside)
    assert init.main([str(dest), "--subject", "10_数学"]) == 2
    assert list(outside.iterdir()) == [], "不能沿链接把文件写到工作区外"
    assert (dest / "kaoyan.yaml").exists()  # 其余正常的文件照常新建


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


def test_tag_quotes_does_not_split_decimals_or_negatives():
    corpus = tq.build_corpus(["电压变为原来的 1.5 倍。温度降到 -1 度。"])
    assert tq.tag_line("1.5 倍", tq.build_corpus(["只有 5 倍"])) == ("【转述】1.5 倍", False)
    assert tq.tag_line("电压变为原来的 1.5 倍。", corpus) == ("【讲义原话】电压变为原来的 1.5 倍。", True)
    assert tq.tag_line("- -1 度", corpus) == ("- 【讲义原话】-1 度", True)
    assert tq.tag_line("1、电压变为原来的 1.5 倍", corpus)[0].startswith("1、【讲义原话】")


def test_tag_quotes_does_not_match_across_lecture_files():
    corpus = tq.build_corpus(["……摩擦力总是", "阻碍运动。……"])
    assert tq.tag_line("摩擦力总是阻碍运动。", corpus) == ("【转述】摩擦力总是阻碍运动。", False)
    assert tq.tag_line("阻碍运动。", corpus)[1] is True


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


def test_privacy_scan_reads_scripts_and_unknown_text_files(tmp_path, capsys):
    key = "sk-" + "a1B2" * 6
    tok = "ghp_" + "Z" * 30
    (tmp_path / "deploy.ps1").write_text(f'$k = "{key}"\n', encoding="utf-8")
    (tmp_path / "notes.weird").write_text(f"token {tok}\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01" + key.encode())  # 真二进制：不按文本查
    assert scan.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "deploy.ps1:1" in out and "notes.weird:1" in out


def test_privacy_scan_fails_when_nothing_was_checked(tmp_path, capsys):
    assert scan.main(["--root", str(tmp_path / "不存在的目录")]) == 2
    assert scan.main(["--root", str(tmp_path)]) == 2  # 空目录：一个文件都没扫到
    (tmp_path / "a.md").write_text("干净\n", encoding="utf-8")
    assert scan.main(["--root", str(tmp_path)]) == 0
    assert scan.main(["--root", str(tmp_path), "--extra", str(tmp_path / "没有的词表.txt")]) == 2
    assert "不算通过" in capsys.readouterr().out


def test_repo_passes_privacy_scan():
    r = subprocess.run([sys.executable, str(ROOT / "tools/privacy_scan.py"), "--root", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert r.returncode == 0, r.stdout
