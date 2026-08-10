# MediFlow 技术报告

本目录保存技术报告的 LaTeX 源文件。正式 PDF 输出到：

`../../output/pdf/MediFlow-Technical-Report.pdf`

## 版式来源

报告以 CTeX 官方 `ctexrep` 文档类为中文排版基础，
单栏版心、字号层级、三线表和图表说明参考公开的
[中文技术报告 LaTeX 模板（单栏）](https://www.overleaf.com/latex/templates/zhong-wen-ji-zhu-bao-gao-latexmo-ban-dan-lan-cjc-xelatex/tcnttxfsqykx)。
正式稿采用纯黑白版式，标题、正文、表格、图注和链接均不设置颜色。

## 编译

在本目录执行：

```powershell
.\build.ps1
```

脚本依次运行 XeLaTeX、Biber 和两轮 XeLaTeX，
并把最终文件复制到 `output/pdf/`。
本地环境需要提供 `xelatex`、`biber`、`ctex`、`tikz`
和 `biblatex-gb7714-2015`。

## 目录

- `main.tex`：报告入口、封面和章节顺序；
- `preamble.tex`：版心、表格、图形和参考文献设置；
- `chapters/`：摘要与正文；
- `figures/`：TikZ 流程图、统计图生成脚本和矢量图文件；
- `references.bib`：正文实际引用的开源项目、论文和协议；
- `build/`：本地编译中间文件。

正式报告只引用源码、可重复测试和当前运行实例中能够核对的事实。
新增测试结果时，应同时保存测试脚本、输入数据和原始输出。
