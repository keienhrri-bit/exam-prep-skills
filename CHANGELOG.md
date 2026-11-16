# Changelog

## 0.1.0 (2026-11-16)

第一个公开版本。

- 9 个 skill：`kaoyan-setup`、`kaoyan-tutor`、`kaoyan-grading`、`kaoyan-plan`、`kaoyan-archive`、`kaoyan-daily-pack`、`kaoyan-report`、`kaoyan-retro`、`physics-svg-tutor`。
- 4 个子代理：`transcriber`（照片转录）、`regrader`（独立复判）、`writer`（长稿）、`finder`（只读找资料）。
- 备考工作区模板和配置文件 `kaoyan.yaml`。
- Markdown → PDF 排版流水线，带版面机检；KaTeX 0.16.22 随仓库打包。
- 合成示例：一道力学计算题从布置、交卷、转录、判分、复判、报告到订正的完整记录。
- Claude Code 插件清单、Codex 插件清单；`skills/*/SKILL.md` 目录结构，可用 `gh skill install` 或 skills.sh 的命令行只装 skill。每个 SKILL.md 带 `license: MIT`。
- 发布前隐私扫描脚本 `tools/privacy_scan.py`。
- `SECURITY.md`（私下报告漏洞的方式和范围）；CI 的 GitHub Actions 钉到提交 SHA，只读权限，依赖从 `requirements-lock.txt` 安装。
