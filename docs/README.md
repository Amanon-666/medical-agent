# docs 文档索引

`docs/` 保存工程说明、任务实现说明、部署说明、数据资产说明和演示说明。根目录 `README.md` 提供最快入口；本目录用于进一步了解实现细节、部署方式和数据资产边界。

## 阅读顺序

1. `ARCHITECTURE_AND_IMPLEMENTATION.md`：理解系统架构、三项任务的数据流、DataMate 算子与 MCP 算子的分工。
2. `DEMO_USAGE_GUIDE.md`：按照在线服务入口进行功能验证。
3. `TASK1_MIXED_ORCHESTRATION.md`：查看任务一混合格式清洗如何保留 `txt/csv/json/jsonl` 源格式和质量证据。
4. `DATA_ARTIFACTS.md`：确认演示数据、知识图谱库、分析库和数据来源管理方式。
5. `DEPLOYMENT_GUIDE.md` 与 `CONFIGURATION_GUIDE.md`：在新环境中复现服务。
6. `PERFORMANCE_AND_EVALUATION.md`：查看任务一、任务二、任务三的指标口径和复现脚本。
7. `TASK3_NL2SQL_EVAL_REPORT.md`：查看任务三 NL2SQL 指标口径和限制。

---

[← 返回项目首页](../README.md)

## 文档清单

| 文件 | 中文标题 | 内容 |
| --- | --- | --- |
| `ARCHITECTURE_AND_IMPLEMENTATION.md` | 架构与实现说明 | 总体架构、任务一/二/三实现流程、模块职责、算子分工、部署关系。 |
| `CONFIGURATION_GUIDE.md` | 配置说明 | `.env.example` 与 `config.example.yaml` 的字段含义和填写方式。 |
| `DATA_ARTIFACTS.md` | 数据资产说明 | 糖尿病混合数据集、知识图谱库、分析库、术语库、噪声库和来源管理。 |
| `DEMO_USAGE_GUIDE.md` | 演示操作说明 | 在线入口、演示账号、Notebook、Nexent 对话、DataMate 数据查看和可视化平台操作。 |
| `DEPLOYMENT_GUIDE.md` | 部署复现说明 | 环境依赖、脚本顺序、健康检查、域名配置和回滚边界。 |
| `PROJECT_ASSETS.md` | 工程资产说明 | 各目录和关键文件的作用、对应任务和交付边界。 |
| `PERFORMANCE_AND_EVALUATION.md` | 性能与评测说明 | 图谱规模、任务一/二性能口径、任务三 NL2SQL 准确率和复现脚本。 |
| `TASK1_MIXED_ORCHESTRATION.md` | 任务一混合清洗说明 | 混合格式识别、分链清洗、格式保留、血缘和质量证据。 |
| `TASK3_NL2SQL_EVAL_REPORT.md` | 任务三 NL2SQL 指标说明 | NL2SQL 准确率、通过数、阈值和展示口径。 |

