# CCF 医疗 AI 比赛工作流说明

> 基于提交侧 `D:\ccf-medical-ai-final-submission` 的代码实际追踪结果
> 生成日期: 2026-07-06

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [workflow-1-data-cleaning.md](workflow-1-data-cleaning.md) | 任务一：数据处理 — 从用户文本到清洗结果 |
| [workflow-2-knowledge-graph.md](workflow-2-knowledge-graph.md) | 任务二：知识图谱 — 实体、关系、三元组生成 |
| [workflow-3-analytics-visualization.md](workflow-3-analytics-visualization.md) | 任务三：数据分析 — NL2SQL + 可视化平台 |
| [workflow-4-deployment.md](workflow-4-deployment.md) | 部署流程 — 评委从零复现的每一步 |
| [workflow-5-notebook-demo.md](workflow-5-notebook-demo.md) | Notebook 演示 — 交互式全链路展示 |
| [code-inventory.md](code-inventory.md) | 代码清单 — 每个文件属于哪条链路 |

---

## 总体架构（一张图）

```
┌─────────────────────────────────────────────────────────────────────┐
│                         评委/用户交互层                              │
│                                                                     │
│   Nexent 对话界面           浏览器                  Jupyter Notebook │
│   (nexent.mashiro.xin)     (demo.mashiro.xin)    (start_notebook)   │
└──────┬──────────────────────┬──────────────────────┬────────────────┘
       │                      │                      │
       │  "清洗这段文本"       │  看图表/关系图        │  全链路演示
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐
│   任务一      │    │   任务二      │    │      任务三               │
│  数据清洗     │───▶│  知识图谱     │───▶│  分析查询 + BI 可视化      │
│              │    │              │    │                          │
│  12 算子链    │    │  NER 9类实体  │    │  三路查询策略              │
│  3 条格式链   │    │  RE 16类关系  │    │  NL2SQL + 模板 + SQL      │
│  混合编排     │    │  Triple+置信度 │    │  图谱 + 图表 + 噪声面板    │
└──────┬───────┘    └──────┬───────┘    └────────────┬─────────────┘
       │                   │                        │
       ▼                   ▼                        ▼
  DataMate REST        core/ 模块              SQLite 数据库
  API (:18000)         LLM API (DeepSeek)      task2_medical_kg.db
  算子容器内执行        离线规则 + 在线模型       task3_analytics.db
                                              noise_kb.db
                                              term_kb.db
```

## 两条验证路径

项目提供了两套并行的验证路径，评委可以任选：

| | Agent 路径（在线） | 直接路径（离线） |
|---|---|---|
| **任务一** | Nexent → MCP → DataMate API → 算子链 | 无（清洗必须走 DataMate） |
| **任务二** | Nexent → MCP → core/ → LLM API | `kg/build_kg_v2.py` 直接调 core/ |
| **任务三** | Nexent → MCP → core/nl2sql.py | `demo/server.py` 直接查 SQLite |
| **优势** | 证明 Agent 编排能力 | 稳定可复现，无网络依赖 |
| **入口** | `nexent.mashiro.xin` 对话 | `python kg/build_kg_v2.py` 等 |

## 关键外部依赖

| 依赖 | 用途 | 不可用时的后果 |
|------|------|---------------|
| DataMate 平台 (:18000) | 任务一清洗执行 | 任务一完全无法工作 |
| Nexent 平台 (:5010, :5014) | Agent 对话和编排 | Agent 路径不可用（离线路径仍可用） |
| DeepSeek API | LLM 调用（NER/RE/NL2SQL） | 回退到本地规则（精度降低） |
| QASystemOnMedicalKG 数据 | KG 构建源数据 | 无法构建 task2_medical_kg.db |
| Docker + sudo | 读取 DataMate 清洗结果 | 无法收集清洗输出 |

---

[← 返回项目首页](../../README.md)
