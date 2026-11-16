# 推广清单

这里只列不用登录任何平台就能做的推广：仓库自己的门面（用 `gh` 设置）、明确欢迎投稿的收录列表（提 PR 即可）、靠抓取 GitHub 自动收录的目录。要登录网页才能发的帖子不在这里。

各列表的规则在 2026-11-16 用 `gh` 读过原文；提交前再看一眼链接里的规则，以当时为准。

---

## 一、仓库门面

### 简介（About）

```bash
gh repo edit keienhrri-bit/kaoyan-study-skills \
  --description "考研备考 skill（Claude Code / Codex）：讲题先让你自己做，答卷照片转录、按评分点判分并独立复判，阶段复盘和 PDF 报告。Agent skills for months-long exam prep (kaoyan)."
```

### Topics

GitHub 的 topic 只能用小写字母、数字和连字符，所以中文关键词写在上面的简介里。

```bash
gh repo edit keienhrri-bit/kaoyan-study-skills \
  --add-topic kaoyan,exam-prep,postgraduate-entrance-exam,study,learning,education,tutor,grading \
  --add-topic agent-skills,claude-code,claude-code-plugin,claude-skills,codex,codex-plugin,codex-skills \
  --add-topic chinese,pdf-report,katex
```

`agent-skills` 是 `gh skill` 用来认仓库的 topic。

### README 开头

顺序固定为：一句话用途 → Claude Code 安装命令 → 两张合成示例报告截图 → 其余介绍。英文版 `README.en.md` 同样。

- 中文一句话：给 Claude Code 和 Codex 用的考研备考 skill：讲题先让你自己做，交卷判分有转录、评分点和一次独立复判，计划只给选项。
- 英文一句话：Agent skills for months-long exam prep in Claude Code and Codex: a tutor that makes you try first, and a grading pipeline you can audit.

### Release v0.1.0 说明

```bash
gh release create v0.1.0 --title "v0.1.0" --notes-file <下面这段存成的文件>
```

```markdown
第一个公开版本：给 Claude Code 和 Codex 用的考研备考 skill。讲题先让你自己做；交卷判分有转录稿、评分点和一次独立复判；阶段复盘只给选项；PDF 报告排版固定、构建后自动检查版面。

## 安装

Claude Code（skill 和子代理一起装）：

    /plugin marketplace add keienhrri-bit/kaoyan-study-skills
    /plugin install kaoyan-study-skills@kaoyan-study-skills

Codex：

    codex plugin marketplace add keienhrri-bit/kaoyan-study-skills
    codex plugin add kaoyan-study-skills@kaoyan-study-skills

只装 skill（GitHub CLI 的 `gh skill`，预览功能）：

    gh skill install keienhrri-bit/kaoyan-study-skills --all --agent claude-code --scope user

## 里面有什么

- 9 个 skill：建工作区、讲题、交卷判分、阶段复盘和周计划、学习记录归档、每日资料包、PDF 报告、纠错复盘、物理画图讲解。
- 4 个子代理：照片转录、独立复判、长稿写手、只读找资料。
- 合成示例：一道原创力学题从布置、交卷、转录、判分、复判、报告到订正的完整记录（`examples/synthetic-mechanics/`）。

## 限制

- 没有评测过照片转录的准确率，仓库里只有合成数据。
- 本地只在 Windows 11 上跑过；CI 覆盖 Ubuntu 和 Windows，没有测过 macOS。
- 不含任何讲义或题目，资料用你自己合法拥有的。

---

Agent skills for months-long exam prep in Claude Code and Codex (written for China's postgraduate entrance exam; skills and outputs are in Chinese): a tutor that makes you try first, a photo-to-report grading pipeline with rubric scoring and one independent regrade, checkpoint reviews, and a Markdown-to-PDF report builder with layout checks. Install commands above. See the CHANGELOG for the full list.
```

### 安全设置

仓库里有 `SECURITY.md`。仓库公开后开启私下报告漏洞：

```bash
gh api -X PUT repos/keienhrri-bit/kaoyan-study-skills/private-vulnerability-reporting
```

---

## 二、收录列表

一个列表提一个 PR，按它的格式写一行。不在别人的仓库开 issue 或 discussion 推广。

| 列表 | 维护情况（2026-11-16） | 怎么收 | 对仓库的要求 | 现在能提吗 |
|---|---|---|---|---|
| [BehiSecc/awesome-claude-skills](https://github.com/BehiSecc/awesome-claude-skills) | 约 1 万 star；11 月初有一批合并，开着的 PR 很多 | Fork → 改 README → 提 PR | 没写门槛 | 能 |
| [hashgraph-online/awesome-ai-plugins](https://github.com/hashgraph-online/awesome-ai-plugins) | 约 1 千 star；每天都有合并 | 提 PR，改 README 一行 | README 要写测过的装法和支持的客户端；PR 有统一的格式检查和来源扫描 | 能，等从 GitHub 实装验证过再提 |
| [hashgraph-online/awesome-codex-plugins](https://github.com/hashgraph-online/awesome-codex-plugins) | 约 1.6 千 star；当天有合并 | 提 PR，改 README 一行 | 插件清单、`SECURITY.md`、`LICENSE`、README；不含密钥；Actions 钉 SHA；有锁文件；统一扫描打分 ≥75 | 能，同上；前几项已备齐，扫描打分没在本地跑过，以 PR 上的检查结果为准 |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 约 3.7 万 star；当天有合并 | 提 PR | 刚建的 skill 不收 | 以后 |
| [heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) | 约 6 千 star；每周批量合并 | 只收 PR，issue 不看 | ≥20 star，建仓满 14 天，有 SKILL.md | 以后 |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | 约 5.8 万 star；10 月下旬有合并 | 只收网页上的 issue 表单 | 首个提交满 14 天且之后还有开发，或 ≥100 star | 不适用 |

### BehiSecc/awesome-claude-skills

- 位置：「📘 Learning & Knowledge」末尾。
- 规则原文：<https://github.com/BehiSecc/awesome-claude-skills#-contribution>
- 条目：

```markdown
- [kaoyan-study-skills](https://github.com/keienhrri-bit/kaoyan-study-skills) - Exam-prep skills for Claude Code and Codex: a tutor that has you try first, photo-to-report grading with rubric scoring and an independent regrade, checkpoint reviews and PDF reports.
```

### hashgraph-online/awesome-ai-plugins

- 位置：Community Plugins →「Agent Skills」，按显示名字母序插入。
- 规则原文：<https://github.com/hashgraph-online/awesome-ai-plugins/blob/main/CONTRIBUTING.md>
- 条目：

```markdown
- [kaoyan-study-skills](https://github.com/keienhrri-bit/kaoyan-study-skills) - Nine Agent Skills for months-long exam prep (China's postgraduate entrance exam): a tutor that has you try first, a photo-to-report grading pipeline with rubric scoring and an independent regrade, checkpoint reviews and a Markdown-to-PDF report builder, installable for Claude Code and Codex.
```

### hashgraph-online/awesome-codex-plugins

- 位置：Community Plugins →「Development & Workflow」（同类的 Core Learning 在这一节），按显示名字母序插入。
- 规则原文：<https://github.com/hashgraph-online/awesome-codex-plugins/blob/main/CONTRIBUTING.md>
- 条目：

```markdown
- [kaoyan-study-skills](https://github.com/keienhrri-bit/kaoyan-study-skills) - Exam-prep plugin with nine skills: try-first tutoring, photo-to-report grading with rubric scoring and an independent regrade, checkpoint reviews and Markdown-to-PDF reports.
```

### VoltAgent/awesome-agent-skills（以后）

- 规则原文：<https://github.com/VoltAgent/awesome-agent-skills/blob/main/CONTRIBUTING.md>（“Brand new skills that were just created are not accepted”）
- PR 标题格式 `Add skill: author/skill-name`，一条只收一个 skill，描述不超过 10 个词。等仓库有人用了再提最有代表性的 `kaoyan-grading`：

```markdown
- **[keienhrri-bit/kaoyan-grading](https://github.com/keienhrri-bit/kaoyan-study-skills/tree/main/skills/kaoyan-grading)** - Grade handwritten answers with transcripts and independent regrade
```

### heilcheng/awesome-agent-skills（以后）

- 规则原文：<https://github.com/heilcheng/awesome-agent-skills/blob/main/AGENTS.md>
- 满 14 天（2026-11-16 公开的话，最早 11-30）并且到 20 star 再提，放 Community Skills 下最贴近的类别末尾：

```markdown
- [keienhrri-bit/kaoyan-study-skills](https://github.com/keienhrri-bit/kaoyan-study-skills) - Exam-prep skills: try-first tutoring, auditable grading with independent regrade
```

### hesreallyhim/awesome-claude-code（不适用）

规则写明不收 PR、不能用 gh 命令行提交、推荐必须由人本人填写网页表单（<https://github.com/hesreallyhim/awesome-claude-code/blob/main/CONTRIBUTING.md>）。要登录网页，不在本清单的范围里。

### 查过、没有列的

- ComposioHQ/awesome-claude-skills、composio-community/awesome-codex-skills、travisvn/awesome-claude-skills、Prat011/awesome-llm-skills：最近半年左右没有合并或推送。
- libukai/awesome-agent-skills：作者自己挑，没有投稿流程。
- 中文的 skill 列表（如 awesome-claude-skills-zh 几个同名仓库）：都在 30 star 以下，多数从 5、6 月起没有更新。没有找到明确欢迎投稿、还在维护的中文学习工具列表。

---

## 三、自动收录的目录

仓库公开后不用提交，下面这些会自己抓取。

| 目录 | 怎么收录 | 需要什么 | 本仓库 |
|---|---|---|---|
| [skills.sh](https://skills.sh) | 原文：“The skills leaderboard ranks skills based on anonymous telemetry data collected from the `skills` CLI.” 没有投稿入口，按原文理解是有人用 `npx skills add` 装过才会上榜 | 公开仓库，`skills/*/SKILL.md` | 已有 |
| [claude-plugins.dev](https://claude-plugins.dev) | 原文：“automatically discovers and indexes all public Claude Code plugins and agent skills on GitHub”（[Kamalnrf/claude-plugins](https://github.com/Kamalnrf/claude-plugins)） | `.claude-plugin/marketplace.json` 和 `skills/` 下的 SKILL.md；已归档的仓库不收 | 已有 |
| `gh skill search` | 用 GitHub 的代码搜索找 SKILL.md，仓库公开并被索引后就能搜到 | `skills/*/SKILL.md`；topic `agent-skills` | 已有 |
| [claudemarketplaces.com](https://claudemarketplaces.com) | 原文：“Crawlers discover listings”，另有人工审核；手动提交要用 GitHub 登录，不用 | 没写明看哪个文件 | 未核实 |
| SkillsMP | 网页返回 403，没有核实到收录规则 | — | 未核实 |

上榜后可以在 README 加 skills.sh 的徽章（`https://skills.sh/b/keienhrri-bit/kaoyan-study-skills`）；没上榜之前不加。
