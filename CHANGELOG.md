# Changelog

## 0.1.2 (2026-11-19)

- 项目改名为 `exam-prep-skills`（原 `kaoyan-study-skills`），GitHub 旧地址自动跳转。Claude Code 和 Codex 的插件名、marketplace 名一并改为 `exam-prep-skills`：装过旧名的，先移除旧插件和旧 marketplace，再按 README 重新添加。skill 名不变。
- 隐私扫描恢复对原有范围内二进制文件的私有词表检查，识别带 BOM 的 UTF-16 文本，并用完整文件判断未知后缀的空字节。Git 仓库无法读取提交记录时返回错误。
- 报告构建按次隔离 HTML、样式、图片和探测页。保留的 HTML 以相对地址引用图片副本，保留查询串和片段，并处理原生 HTML 的 `src` 和 `srcset`。机检等待图片加载，区分超时，简化远程和 `data:` 图片的失败诊断。
- Markdown 由 Pandoc 直接解析，保留代码示例里的公式写法。页眉模板只替换原有占位符。
- 长稿流程和工作区模板按 `roles.long_writer` 决定由主会话或 `writer` 撰写。
- 句子打标逐份核对讲义，在诊断中记录命中来源，并识别与正文紧连的 `1)` 编号。
- 归档执行复核源文件类型和扫描后缀。初始化拦截指向工作区祖先目录的链接。
- 驻波示意图的 λ/4 尺寸线上端对齐第一层波腹。回归测试校验尺寸、行首负数以及两份并行生成的 PDF 正文。

## 0.1.1 (2026-11-17)

修正第一轮代码审查发现的问题，并为部分改动补充测试。

- `physics-svg-tutor`：维纳驻波示意图把三层波腹画在了 λ/2、λ、3λ/2，这些位置其实是电场波节。镜面是波节、`E ∝ sin(kz)`，第一层波腹应距镜面 λ/4。图已改正，加了 λ/4 标注；案例库里写明节面、腹面的具体位置。
- `kaoyan-report`：
  - 页眉标题和日期按 CSS 字符串完整转义，标题里的 `</style>`、引号、反斜杠、换行不能再跳出样式块或弄坏页眉。
  - 表格公式里的双竖线 `\|`（范数）改成 `\Vert`，以前被错改成单竖线；`\\` 换行后面的 `|` 也不再被误拼。
  - 图片相对路径按 Markdown 源文件所在目录解析，以前会到 `_build/` 下找图而缺图；机检新增 `missing_images`，`--strict` 时缺图算不合格。
  - 每次构建的浏览器配置和中间 PDF 放在 `_build/` 下独立的 `run-*` 子目录，构建完删掉；同一输出目录并行构建不同报告不再互相覆盖。
- `tools/privacy_scan.py`：`.ps1`、`.sh`、`.bat` 等脚本和扩展名不认识但能按 UTF-8 读的文件也按文本查全部规则；扫描目录不存在、一个文件都没扫到、`--extra` 词表不存在、git 仓库里读不出提交作者时退出码 2，不再报“命中 0 处”。
- `kaoyan-archive`：收件夹里的符号链接不进方案，执行时也拒绝移动链接和收件夹以外的文件；日志路径必须在工作区里，否则一个文件都不动。
- `kaoyan-setup`：工作区里已有的目录如果是指向别处的链接（含 Windows 目录联接），初始化脚本不往里写，退出码 2。
- `kaoyan-daily-pack`：句子开头的 `1.5`、`-1` 不再被当成列表符号；多份讲义分开比对，不会把前一份的结尾和后一份的开头拼成一句“讲义原话”。
- 文档：README、工作区模板的 `CLAUDE.md` 和 `kaoyan-report` 写明长讲义可以交 `writer` 子代理写的例外，和 `kaoyan.yaml` 的 `roles.long_writer` 一致。

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
