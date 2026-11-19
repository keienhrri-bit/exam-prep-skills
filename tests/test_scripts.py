"""归档、建工作区、句子打标、示例答案核对、隐私扫描。"""
import os
import re
import subprocess
import sys
import time

import pytest

from conftest import ROOT, link_dir, load

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


_link_dir = link_dir


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
    assert tq.tag_line("-1 度", corpus) == ("【讲义原话】-1 度", True)
    assert tq.tag_line("- -1 度", corpus) == ("- 【讲义原话】-1 度", True)
    assert tq.tag_line("1、电压变为原来的 1.5 倍", corpus)[0].startswith("1、【讲义原话】")


def test_tag_quotes_does_not_match_across_lecture_files():
    corpus = tq.build_corpus(["……摩擦力总是", "阻碍运动。……"])
    assert tq.tag_line("摩擦力总是阻碍运动。", corpus) == ("【转述】摩擦力总是阻碍运动。", False)
    assert tq.tag_line("阻碍运动。", corpus)[1] is True


def test_tag_quotes_does_not_match_across_nul_boundary():
    line = "前半\x00后半"
    assert tq.tag_line(line, tq.build_corpus(["前半", "后半"])) == ("【转述】" + line, False)
    assert tq.tag_line(line, tq.build_corpus(["前半\x00后半"])) == ("【讲义原话】" + line, True)


def test_tag_quotes_accepts_numbered_parenthesis_without_space():
    corpus = tq.build_corpus(["惯性与物体的质量有关。"])
    assert tq.tag_line("1)惯性与物体的质量有关。", corpus) == ("1)【讲义原话】惯性与物体的质量有关。", True)


def test_tag_quotes_cli_reports_matching_lecture_file(tmp_path):
    first, second, sentences = (tmp_path / name for name in ("first.md", "second.md", "sentences.md"))
    first.write_text("位移是矢量。\n", encoding="utf-8")
    second.write_text("速率是标量。\n", encoding="utf-8")
    sentences.write_text("\n速率是标量。\n", encoding="utf-8")
    result = subprocess.run([sys.executable, tq.__file__, "--lecture", str(first), str(second),
                             "--sentences", str(sentences)],
                            capture_output=True, text=True, encoding="utf-8", env=UTF8, check=True)
    assert result.stdout == "\n【讲义原话】速率是标量。\n"
    assert "第 2 行" in result.stderr and "second.md" in result.stderr and "first.md" not in result.stderr


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


def test_privacy_scan_checks_unknown_suffix_past_first_chunk(tmp_path):
    path = tmp_path / "data.unknown"
    text = ("a" * 8193 + "段落").encode("utf-8")
    assert scan.decode_text(path, text) == text.decode("utf-8")
    assert scan.decode_text(path, text + b"\x00") is None


def test_privacy_scan_fails_when_nothing_was_checked(tmp_path, capsys):
    assert scan.main(["--root", str(tmp_path / "不存在的目录")]) == 2
    assert scan.main(["--root", str(tmp_path)]) == 2  # 空目录：一个文件都没扫到
    (tmp_path / "a.md").write_text("干净\n", encoding="utf-8")
    assert scan.main(["--root", str(tmp_path)]) == 0
    assert scan.main(["--root", str(tmp_path), "--extra", str(tmp_path / "没有的词表.txt")]) == 2
    assert "不算通过" in capsys.readouterr().out



def test_archive_apply_rechecks_source_type_and_extensions(tmp_path):
    inbox, ws = _ws(tmp_path)
    csv = inbox / "table.csv"
    csv.write_text("x,y", encoding="utf-8")
    plan = arch.scan(inbox, ws, days=3, exts=(".csv",))
    plan["items"][0].update(action="move", dest="10_数学")
    other = inbox / "new.md"
    folder = inbox / "directory.csv"
    folder.mkdir()
    for path in (other, folder):
        plan["items"].append({
            "src": str(path), "name": path.name, "action": "move", "dest": "10_数学",
            "sha256": arch.sha256(other),
        })
    result = arch.apply(plan, None)
    assert [it["name"] for it, _ in result["moved"]] == ["table.csv"]
    assert [it["name"] for it, _ in result["skipped"]] == ["new.md", "directory.csv"]
    assert other.is_file() and folder.is_dir()


def test_archive_apply_refuses_non_list_extensions(tmp_path):
    inbox, ws = _ws(tmp_path)
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    approved = next(item for item in plan["items"] if item["name"] == "new.md")
    approved.update(action="move", dest="10_数学")
    plan["extensions"] = ".md.other"
    with pytest.raises(ValueError, match="extensions"):
        arch.apply(plan, None)
    assert (inbox / "new.md").is_file()


def test_archive_apply_uses_default_extensions_for_legacy_plan(tmp_path):
    inbox, ws = _ws(tmp_path)
    path = inbox / "photo.jpg"
    plan = arch.scan(inbox, ws, days=3, exts=(".md",))
    plan.pop("extensions", None)
    plan["items"].append({
        "src": str(path), "name": path.name, "sha256": arch.sha256(path),
        "action": "move", "dest": "10_数学",
    })
    result = arch.apply(plan, None)
    assert not result["moved"] and len(result["skipped"]) == 1
    assert path.is_file()


def test_init_workspace_refuses_link_to_workspace_ancestor(tmp_path):
    workspace = tmp_path / "outer" / "ws"
    workspace.mkdir(parents=True)
    _link_dir(workspace / "10_数学", workspace.parent)
    assert init.main([str(workspace), "--subject", "10_数学"]) == 2
    assert list(workspace.parent.iterdir()) == [workspace]


def test_privacy_scan_checks_extra_rules_in_executable_bytes(tmp_path, capsys):
    rules = tmp_path / ".work" / "privacy-extra.txt"
    rules.parent.mkdir()
    rules.write_text("FixtureOnlyMarker\n", encoding="utf-8")
    for name in ("sample.exe", "sample.dll"):
        (tmp_path / name).write_bytes(b"\x00\xffFixtureOnlyMarker\x00")
    assert scan.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    for name in ("sample.exe", "sample.dll"):
        assert f"{name}  私有词表第 1 条（二进制）" in out


@pytest.mark.parametrize("discovery_error", ["missing", "ownership"])
def test_privacy_scan_refuses_git_discovery_failure_in_repository(tmp_path, monkeypatch, discovery_error):
    # linked worktree 的 .git 是文件。
    (tmp_path / ".git").write_text("gitdir: metadata\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("clean", encoding="utf-8")

    def git_unavailable(args, **kwargs):
        if discovery_error == "missing":
            raise FileNotFoundError("git")
        return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: detected dubious ownership")

    monkeypatch.setattr(scan.subprocess, "run", git_unavailable)
    assert scan.main(["--root", str(tmp_path)]) == 2


def test_privacy_scan_allows_non_repository_without_git(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("clean", encoding="utf-8")

    def git_unavailable(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(scan.subprocess, "run", git_unavailable)
    # CI 的临时目录也可以放在仓库内；这里隔离“无仓库标记”的分支。
    monkeypatch.setattr(scan, "find_git_marker", lambda root: None)
    assert scan.main(["--root", str(tmp_path)]) == 0


def _init_scan_repo(path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, capture_output=True)
    (path / "a.md").write_text("clean", encoding="utf-8")


def test_privacy_scan_allows_unborn_repository(tmp_path, capsys):
    _init_scan_repo(tmp_path)
    assert scan.main(["--root", str(tmp_path)]) == 0
    assert "还没有提交" in capsys.readouterr().out


@pytest.mark.parametrize("corruption", ["head", "branch"])
def test_privacy_scan_refuses_broken_head(tmp_path, corruption):
    _init_scan_repo(tmp_path)
    ref = ".git/HEAD" if corruption == "head" else ".git/refs/heads/main"
    (tmp_path / ref).write_text("invalid reference\n", encoding="ascii")
    assert scan.main(["--root", str(tmp_path)]) == 2


@pytest.mark.parametrize("byte_order", [b"\xff\xfe", b"\xfe\xff"])
def test_privacy_scan_reads_bom_utf16_powershell(tmp_path, capsys, byte_order):
    key = "sk-" + "a1B2" * 6
    encoding = "utf-16-le" if byte_order == b"\xff\xfe" else "utf-16-be"
    (tmp_path / "deploy.ps1").write_bytes(byte_order + f'$k = "{key}"\r\n'.encode(encoding))
    assert scan.main(["--root", str(tmp_path)]) == 1
    assert "deploy.ps1:1" in capsys.readouterr().out


def test_privacy_scan_output_never_contains_matched_values(tmp_path, capsys):
    """命中只报文件、位置、规则和计数：公开 CI 的日志里不能多一份明文。"""
    # 拼接写法：让这个测试文件本身不被全仓扫描命中
    email = "leaky.person" + "@mail.test.cn"
    token = "ghp_" + "Q" * 30
    marker = "FixtureOnly" + "PrivateWord"
    rules = tmp_path / ".work" / "privacy-extra.txt"
    rules.parent.mkdir()
    rules.write_text(marker + "\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text(f"联系 {email}\n令牌 {token} 和 {token}\n{marker}\n", encoding="utf-8")
    (tmp_path / "blob.exe").write_bytes(b"\x00\xff" + email.encode() + b"\x00" + marker.encode())
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Leaky Person", "-c", f"user.email={email}",
                    "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "x"],
                   check=True, capture_output=True)
    assert scan.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    for secret in (email, token, marker, "Leaky Person", "leaky.person", "mail.test"):
        assert secret not in out
    for expected in ("notes.md:1:", "notes.md:2:", "notes.md:3:", "邮箱", "GitHub token", "私有词表第 1 条",
                     "blob.exe  二进制里的邮箱", "blob.exe  私有词表第 1 条（二进制）", "git 提交作者", "git 提交者"):
        assert expected in out


def test_privacy_scan_checks_raw_bytes_of_unknown_bom_files(tmp_path):
    """未知后缀的文件即使以 UTF-16 BOM 开头，也要查原始字节：错位的 ASCII 在 UTF-16 解码后会变成乱码。"""
    path = "C:" + "\\Users\\alice\\Desktop"
    (tmp_path / "mixed.unknown").write_bytes(
        b"\xff\xfe" + "表头".encode("utf-16-le") + b"\x00" + path.encode("ascii") + b"\x00")
    assert scan.main(["--root", str(tmp_path)]) == 1


def test_privacy_scan_still_reads_unknown_bom_files_as_utf16_text(tmp_path, capsys):
    token = "ghp_" + "Z" * 30
    (tmp_path / "notes.weird").write_bytes(b"\xff\xfe" + f"第一行\r\ntoken {token}\r\n".encode("utf-16-le"))
    assert scan.main(["--root", str(tmp_path)]) == 1
    assert "notes.weird:2:7  GitHub token" in capsys.readouterr().out


def test_privacy_scan_prunes_skipped_dirs_and_directory_links(tmp_path):
    """跳过的目录不进去；目录链接（含 Windows 目录联接）不跟进，免得扫到仓库外、绕成环。"""
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "a.md").write_text("干净\n", encoding="utf-8")
    (outside / "leak.md").write_text("token ghp_" + "L" * 30 + "\n", encoding="utf-8")
    link_dir(root / "linked", outside)
    (root / ".work").mkdir()
    link_dir(root / ".work" / "loop", root)
    assert scan.main(["--root", str(root)]) == 0
    assert [p.name for p in scan.files(root)] == ["a.md"]


def test_repo_passes_privacy_scan():
    r = subprocess.run([sys.executable, str(ROOT / "tools/privacy_scan.py"), "--root", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert r.returncode == 0, r.stdout
