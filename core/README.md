# core 模块说明

`core/` 保存可复用的医学语义处理能力，主要服务任务二和任务三。这里的代码不直接创建 DataMate 清洗任务，也不直接发布 Nexent 智能体；它为 MCP 工具、知识图谱构建脚本和可视化问答提供稳定的领域能力。

## 与三项任务的关系

| 任务 | 主要平台 | core 的作用 | 主要调用方 |
| --- | --- | --- | --- |
| 任务一：数据治理 | DataMate 算子 + Nexent 编排 | 仅提供少量文本预处理和质量判断辅助；正式清洗算子位于 `operators/` | `operators/`、`mcp_server/task1/` |
| 任务二：知识图谱生成 | MCP 知识抽取算子 + Nexent 编排 | 提供实体识别、关系抽取、三元组生成和术语归一化能力 | `mcp_server/task2/`、`mcp_server/kg/` |
| 任务三：分析问答与可视化 | MCP 查询工具 + 可视化平台 | 提供疾病查询、NL2SQL、问答结果组织等能力 | `mcp_server/tools/task3_query.py`、`demo/task3_interactive_demo/` |

## 与 DataMate 算子的分工

| 能力 | 所在位置 | 平台定位 | 说明 |
| --- | --- | --- | --- |
| URL、HTML、Emoji、空白、全角/繁体等格式清理 | `operators/` | DataMate 自定义算子 | 任务一展示重点，负责实际写回 DataMate 数据集。 |
| CSV 字段清洗、JSON 字段清洗 | `operators/table_column_cleaner/`、`operators/json_field_cleaner/` | DataMate 自定义算子 | 保留源文件结构，避免混合数据集被压成纯文本。 |
| 医学术语标准化 | `operators/medical_term_normalizer/` 与 `core/medical_normalize.py` | DataMate 算子 + core 复用能力 | 算子用于任务一清洗；core 用于任务二抽取前后的归一化。 |
| 语义噪声过滤 | `operators/llm_noise_filter/` | DataMate 自定义算子 | 任务一质量治理能力，依赖规则库和可选模型增强。 |
| 实体识别、关系抽取、三元组生成 | `core/medical_extraction_service.py`、`core/medical_offline_extraction.py` | MCP 知识抽取算子 | 任务二展示重点，通过 MCP 工具被 Nexent 智能体编排。 |
| 疾病详情查询与 NL2SQL | `core/medical_query_engine.py`、`core/nl2sql.py` | MCP 查询算子 | 任务三展示重点，读取任务二生成的知识图谱库和分析库。 |

## 文件索引

| 文件 | 职责 | 所属任务 |
| --- | --- | --- |
| [`medical_extraction_service.py`](medical_extraction_service.py) | 任务二知识抽取服务入口，统一执行实体识别、关系抽取和三元组生成。 | T2 |
| [`medical_offline_extraction.py`](medical_offline_extraction.py) | 本地规则与词典增强抽取链，模型不可用时仍可完成基础知识生成。 | T2 |
| [`medical_ner.py`](medical_ner.py) | 医学实体识别，覆盖疾病、症状、药物、检查、科室等类型。 | T2 |
| [`medical_re.py`](medical_re.py) | 医学关系抽取，生成诊断、治疗、检查、并发等关系。 | T2 |
| [`medical_triple.py`](medical_triple.py) | 把实体和关系整理为知识图谱三元组结构。 | T2 |
| [`medical_fewshot.py`](medical_fewshot.py) | CMeEE/CMeIE few-shot 样例检索，供 LLM 抽取路径使用。 | T2 |
| [`medical_extraction_validation.py`](medical_extraction_validation.py) | 实体/关系/三元组去重、校验与置信度过滤。 | T2 |
| [`medical_normalize.py`](medical_normalize.py) | 医学术语、缩写和同义表达标准化。 | T1+T2 |
| [`medical_query_engine.py`](medical_query_engine.py) | 面向任务三的疾病详情查询和 SQL 模板引擎。 | T3 |
| [`nl2sql.py`](nl2sql.py) | 将自然语言统计问题映射为只读 SQL 并执行。 | T3 |
| [`text_preprocessor.py`](text_preprocessor.py) | 通用文本分段与预处理。 | T1+T2 |
| [`text_quality.py`](text_quality.py) | 四维文本质量评分与过滤判断。 | T1+T2 |
| [`schemas.py`](schemas.py) | 实体、关系、三元组等核心数据结构定义。 | T2+T3 |
| [`llm_client.py`](llm_client.py) | 统一 LLM 调用出口，所有 LLM 请求经此模块发出。 | ALL |
| [`__init__.py`](__init__.py) | 包导出，暴露常用模块给外部调用方。 | ALL |

## 调用链

任务二典型调用链：

```text
Nexent 智能体
  -> run_task2_kg_pipeline
  -> mcp_server/task2/pipeline_service.py
  -> core/medical_extraction_service.py
  -> mcp_server/kg/persistence.py
  -> data/task2_medical_kg.db
```

任务三典型调用链：

```text
Nexent 智能体或可视化平台
  -> query_disease_analytics / execute_nl2sql
  -> core/medical_query_engine.py / core/nl2sql.py
  -> data/task3_analytics.db
```

## 设计边界

- `core/` 不直接依赖 DataMate 或 Nexent 的前端页面。
- DataMate 数据集创建、清洗任务创建和状态查询在 `mcp_server/task1/` 与 `mcp_server/datamate/` 中完成。
- 数据库写入、来源登记和分析库刷新在 `mcp_server/kg/` 与 `kg/` 中完成。
- 面向用户的页面展示在 `demo/task3_interactive_demo/` 中完成。

---

[← 返回项目首页](../README.md)
