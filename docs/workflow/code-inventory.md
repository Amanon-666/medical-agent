# 代码清单

> 按链路组织的完整文件列表，标注每个文件属于哪条链路、是否被其他链路复用

---

## 图例

| 标记 | 含义 |
|------|------|
| T1 | 任务一专用 |
| T2 | 任务二专用 |
| T3 | 任务三专用 |
| T1+T2 | 任务一和任务二复用 |
| T2+T3 | 任务二和任务三复用 |
| ALL | 三条链路共用 |
| DEPLOY | 部署流程 |
| DEMO | Notebook 演示 |
| CONFIG | 配置模板 |

---

## 根目录

| 文件 | 链路 | 说明 |
|------|------|------|
| `README.md` | ALL | 项目主文档 |
| `.env.example` | CONFIG | 环境变量模板 (21 个变量) |
| `config.example.yaml` | CONFIG | YAML 配置模板 |
| `requirements.txt` | ALL | Python 依赖  |
| `.gitignore` | ALL | Git 排除规则 |

---

## core/ — 核心逻辑层 (平台无关)

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | ALL | 包导出 |
| `llm_client.py` | ALL | **统一 LLM 出口** (DeepSeek Chat API) |
| `schemas.py` | T2+T3 | 数据契约: Entity/Relation/Triple dataclass |
| `medical_ner.py` | T2 | LLM 路径: 9 类实体识别 (含 CMeEE few-shot) |
| `medical_re.py` | T2 | LLM 路径: 16 类关系抽取 (含 CMeIE few-shot) |
| `medical_triple.py` | T2 | 三元组生成 + 置信度计算 |
| `medical_offline_extraction.py` | T2 | 本地路径: 正则+AC自动机+词典匹配 |
| `medical_extraction_service.py` | T2 | 统一抽取入口, backend 路由 (offline/llm/hybrid) |
| `medical_extraction_validation.py` | T2 | 去重、置信度过滤、标准化 |
| `medical_fewshot.py` | T2 | CMeEE/CMeIE few-shot 示例检索 |
| `medical_normalize.py` | T1+T2 | 医学术语标准化 (109 条规则) |
| `text_quality.py` | T1+T2 | 文本质量评分 (4 维度) |
| `text_preprocessor.py` | T1+T2 | 文本分段/预处理 |
| `nl2sql.py` | T3 | NL2SQL 引擎: LLM生成SQL→安全校验→执行 |
| `medical_query_engine.py` | T3 | SQL 模板引擎 (20+ 预定义模板) |
| `README.md` | ALL | core/ 文档 |

---

## mcp_server/ — MCP 工具服务

### 根目录

| 文件 | 链路 | 说明 |
|------|------|------|
| `server.py` | ALL | **MCP 入口** (FastMCP, 17 tools) |
| `config.py` | ALL | 配置读取 (环境变量 + config.yaml) |
| `README.md` | ALL | mcp_server/ 文档 |

### mcp_server/tools/ — MCP 工具定义

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | ALL | mcp 实例共享 (运行时注入) |
| `task1_data.py` | T1 | **7 个任务一工具**: inspect/upload/run_cleaning/status/result/list_ops/run_pipeline |
| `task2_extract.py` | T2 | **3 个任务二工具**: entities/relations/triples |
| `task2_pipeline.py` | T2 | **1 个任务二工具**: run_task2_kg_pipeline |
| `task3_query.py` | T3 | **5 个任务三工具**: frontend_status/kg_query/sources/disease_analytics/sql_template |
| `task3_nl2sql.py` | T3 | **1 个任务三工具**: execute_nl2sql |

### mcp_server/task1/ — 任务一服务层

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | T1 | 包说明 |
| `mixed_cleaning_service.py` | T1 | **核心编排器**: 混合格式清洗主逻辑, import runtime_helpers |
| `pipeline_service.py` | T1 | DataMate 清洗任务创建 + 轮询 (60×5秒) |
| `dataset_service.py` | T1 | DataMate 数据集上传和探查 |
| `chains.py` | T1 | 三条清洗链定义 (text/csv/json/jsonl) |
| `datasets.py` | T1 | 文件分类和路径解析 |
| `evidence.py` | T1 | 清洗前后比对证据汇总 |
| `inspection.py` | T1 | 文件类型识别 + 清洗链推荐 |
| `postprocess.py` | T1 | DataMate 输出后处理 |
| `preserved_cleanup.py` | T1 | 源格式保留文件清理 |
| `status.py` | T1 | 异步任务状态 JSON 读写 |
| `async_worker.py` | T1 | **异步执行 CLI 入口** (subprocess) |

### mcp_server/task1/runtime_helpers/ — 重构辅助层

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | T1 | 包说明 |
| `datamate_ops.py` | T1 | DataMate API 封装: 数据工厂、基准构建、sudo |
| `preserved_pipeline.py` | T1 | **409行**: 流水线编排、输出收集、最终注册 |
| `quality_eval.py` | T1 | 13 条残留噪声正则检测 |
| `governance.py` | T1 | 治理元数据登记 |
| `local_cleaning.py` | T1 | 18 步确定性字段级清洗 |

### mcp_server/task2/ — 任务二服务层

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | T2 | 包说明 |
| `pipeline_service.py` | T2 | KG 批量构建主逻辑 (7 阶段) |
| `selection.py` | T2 | 跨文件均衡抽样 |
| `reporting.py` | T2 | KG 构建统计报告 |

### mcp_server/kg/ — 知识图谱存储

| 文件 | 链路 | 说明 |
|------|------|------|
| `schema.py` | T2+T3 | 表结构 DDL 定义 |
| `persistence.py` | T2 | 实体/关系/三元组入库 |
| `normalization.py` | T2 | 实体类型和关系代码标准化 |
| `analytics.py` | T3 | 疾病分析查询 |
| `analytics_refresh.py` | T2+T3 | 从 KG 刷新分析库 |

### mcp_server/datamate/ — DataMate 通信

| 文件 | 链路 | 说明 |
|------|------|------|
| `client.py` | T1+T2 | HTTP POST/GET 封装 + 临时数据集写入 |
| `resolver.py` | T1+T2 | 数据集名 → UUID 映射 |

### mcp_server/shared/ — 公共工具

| 文件 | 链路 | 说明 |
|------|------|------|
| `sqlite_utils.py` | T2+T3 | SQLite 连接封装 |
| `parsing.py` | T1+T2 | 混合格式文件解析 |
| `frontend_status.py` | T3 | 可视化平台状态查询 |

---

## operators/ — DataMate 算子 (18 个)

### 纯本地算子 (无 LLM 依赖)

| 文件 | 链路 | 说明 |
|------|------|------|
| `operators/emoji_cleaner/` | T1 | Emoji 去除 (⚠ `__init__.py` 空) |
| `operators/url_remover/` | T1 | URL/HTML 清理 |
| `operators/whitespace_normalizer/` | T1 | 空白规范化 |
| `operators/medical_record_splitter/` | T1 | 多段病历拆分 |
| `operators/unified_jsonl_exporter/` | T1 | JSONL 统一输出 |
| `operators/table_column_cleaner/` | T1 | CSV 表格清洗  |
| `operators/json_field_cleaner/` | T1 | JSON/JSONL 字段清洗 |

### 本地规则 + LLM 辅助算子

| 文件 | 链路 | 说明 |
|------|------|------|
| `operators/llm_noise_filter/` | T1 | 语义噪声过滤 (noise_kb.db + DeepSeek) |
| `operators/medical_term_normalizer/` | T1 | 术语标准化 (term_kb.db + DeepSeek) |

### DataMate 内置算子 (不在提交侧, 平台自带)

| 算子名 | 链路 | 说明 |
|--------|------|------|
| GrableCharactersCleaner | T1 | 文档乱码去除 |
| InvisibleCharactersCleaner | T1 | 不可见字符去除 |
| FullWidthCharacterCleaner | T1 | 全角转半角 |
| TraditionalChineseCleaner | T1 | 繁体转简体 |
| HtmlTagCleaner | T1 | HTML 标签去除 |
| FileWithShortOrLongLengthFilter | T1 | 文档字数检查 |
| FileWithHighRepeatPhraseRateFilter | T1 | 文档词重复率检查 |
| FileWithHighSpecialCharRateFilter | T1 | 文档特殊字符率检查 |
| DuplicateFilesFilter | T1 | 相似文档去除 |

### 任务二专用算子 (调 core/ 模块)

| 文件 | 链路 | 说明 |
|------|------|------|
| `operators/medical_entity_extractor/` | T2 | DataMate 内实体抽取 |
| `operators/medical_relation_extractor/` | T2 | DataMate 内关系抽取 |
| `operators/medical_triple_generator/` | T2 | DataMate 内三元组生成 |
| `operators/medical_text_quality_filter/` | T2 | DataMate 内文本质量过滤 |

---

## deploy/ — 部署脚本

| 文件 | 说明 |
|------|------|
| `run_all.sh` | **一键部署主控** (串行 00-08) |
| `README.md` | 部署说明 |
| `00_check_prereqs.sh` | 环境检查 |
| `01_setup_python.sh` | Python 环境 |
| `02_deploy_operators.sh` | 算子部署到 DataMate 容器 |
| `03_register_operators.sh` | 算子注册到 DataMate PostgreSQL |
| `04_build_databases.sh` | KG + 分析库构建 |
| `05_start_mcp.sh` | MCP 服务启动 |
| `06_register_nexent.sh` | MCP 注册 + Agent 发布 |
| `07_start_demo.sh` | 可视化平台启动 |
| `08_verify.sh` | 全链路健康验证 |
| `09_apply_cloudflare_tunnel.sh` | (可选) Cloudflare Tunnel |
| `10_route_cloudflare_dns.sh` | (可选) Cloudflare DNS |
| `docker-compose.ccf-override.yml` | 评审环境端口覆盖 |
| `nexent.ccf-clean.env` | Nexent 干净环境变量 |

---

## demo/ — 演示入口

| 文件 | 链路 | 说明 |
|------|------|------|
| `start_notebook_demo.bat` | DEMO | Windows 启动脚本 |
| `interactive_pipeline_demo.ipynb` | DEMO | 主演示 Notebook |
| `task1_pipeline_demo.ipynb` | DEMO | 任务一专项 Notebook |
| `README.md` | DEMO | demo/ 文档 |

### demo/task3_interactive_demo/ — 可视化平台

| 文件 | 链路 | 说明 |
|------|------|------|
| `server.py` | T3 | **HTTP 服务入口** (ThreadingHTTPServer) |
| `query_service.py` | T3 | 自然语言查询引擎 |
| `dashboard_payloads.py` | T3 | 面板数据生成 |
| `agent_gateway.py` | T3 | Nexent Agent 转发 + 本地降级 |
| `agent_answer.py` | T3 | Agent 回答安全清理 |
| `db_utils.py` | T3 | SQLite 连接工具 |
| `http_utils.py` | T3 | HTTP 响应工具 |
| `paths.py` | T3 | 数据库路径常量 |
| `source_management.py` | T3 | KG 数据源管理 |
| `quality.py` | T3 | 质量审计 |
| `README.md` | T3 | 平台文档 |

### demo/task3_interactive_demo/static/ — 前端

| 文件 | 说明 |
|------|------|
| `index.html` | SPA 骨架 |
| `styles.css` | 全页面样式 |
| `app.js` | 主应用逻辑 |
| `app_common.js` | 公共函数 |
| `graph_renderer.js` | SVG 力导向关系图 |
| `visualization_renderer.js` | 表格+柱状图 |
| `markdown_renderer.js` | Markdown 渲染 |
| `quality_renderer.js` | 噪声审计面板 |
| `workspace_layout.js` | 三栏拖拽布局 |

---

## clients/ — API 客户端

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | ALL | 包导出 |
| `nexent_client.py` | ALL | **Nexent API 客户端** (230行, 登录/Agent/MCP/KB) |
| `datamate_client.py` | ALL | DataMate API 客户端 (部分实现) |
| `README.md` | ALL | clients/ 文档 |

---

## kg/ — 知识图谱构建脚本

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | T2 | 包初始化 |
| `build_kg.py` | T2 | KG 构建 (旧版) |
| `build_kg_v2.py` | T2 | **KG 构建 (新版)**: medical.json + CMeEE/CMeIE |
| `build_sql_db.py` | T3 | 分析库构建 (旧版) |
| `build_analytics_v2.py` | T3 | **分析库构建 (新版)**: KG → 16 表 ETL |
| `README.md` | T2+T3 | kg/ 文档 |

---

## scripts/ — 运维脚本

| 文件 | 链路 | 说明 |
|------|------|------|
| `__init__.py` | ALL | 包初始化 |
| `register_mcp.py` | DEPLOY | 注册 MCP 到 Nexent |
| `update_nexent_agents.py` | DEPLOY | 发布 3 个 Agent |
| `generate_datamate_registration_sql.py` | DEPLOY | 生成算子注册 SQL |
| `runtime_env.py` | ALL | 环境变量加载 (被 runtime_helpers 引用) |
| `start_mcp_server.sh` | DEPLOY | MCP 启动脚本 |
| `README.md` | ALL | scripts/ 文档 |

### ⚠ 提交侧缺失但服务器有的脚本

| 文件 | 用途 | 重要性 |
|------|------|--------|
| `evaluate_task2_cmeee_f1.py` | CMeEE F1 评测 | **必须** |
| `evaluate_task3_nl2sql_templates.py` | NL2SQL 准确率评测 | **必须** |
| `e2e_full_pipeline_test.py` | 端到端自动化测试 | 建议 |
| `judge_reproduce_task2_task3.sh` | 用户复现验证 | 建议 |
| `validate_task2_task3_local.py` | 本地数据库验证 | 建议 |

---

## data/ — 数据资产

| 文件 | 说明 | Git |
|------|------|-----|
| `README.md` | 数据资产文档 | ✓ |
| `task2_medical_kg.db` | 知识图谱 (213MB, 8 表) | ✗ (gitignore) |
| `task3_analytics.db` | 分析库 (211MB, 16 表) | ✗ (gitignore) |
| `standard_diabetes_demo/datamate_upload/` | Demo 数据集 (4 文件) | ✓ |
| `demo_medical_texts/` | 演示用医疗文本 | ✓ |

---

## docs/ — 文档

| 文件 | 说明 |
|------|------|
| `README.md` | 文档索引 |
| `ARCHITECTURE_AND_IMPLEMENTATION.md` | 架构与实现 |
| `DEMO_USAGE_GUIDE.md` | 演示使用指南 |
| `DEPLOYMENT_GUIDE.md` | 部署指南 |
| `CONFIGURATION_GUIDE.md` | 配置指南 |
| `DATA_ARTIFACTS.md` | 数据资产说明 |
| `TASK1_MIXED_ORCHESTRATION.md` | 任务一混合编排 |
| `TASK3_NL2SQL_EVAL_REPORT.md` | NL2SQL 评测报告 |
| `PROJECT_ASSETS.md` | 项目资产清单 |

---

## 复用关系总结

```
llm_client.py           ← ALL (T1的LLMNoiseFilter/TermNormalizer, T2的NER/RE, T3的NL2SQL)
schemas.py              ← T2+T3 (Entity/Relation/Triple 数据结构)
medical_normalize.py    ← T1+T2 (术语标准化)
text_quality.py         ← T1+T2 (文本质量过滤)
text_preprocessor.py    ← T1+T2 (文本分段)
datamate/client.py      ← T1+T2 (DataMate API)
datamate/resolver.py    ← T1+T2 (数据集解析)
shared/sqlite_utils.py  ← T2+T3 (数据库连接)
shared/parsing.py       ← T1+T2 (文件解析)
kg/persistence.py       ← T2 (三元组入库)
kg/analytics_refresh.py ← T2+T3 (KG→分析库 ETL)
nexent_client.py        ← ALL (Nexent API)
```

## 文件总数统计

| 目录 | 文件数 | 主要链路 |
|------|--------|---------|
| core/ | 16 (含 README) | T2, T3 |
| mcp_server/ | 38 (含子目录) | T1, T2, T3 |
| operators/ | ~60 (13×4+内置) | T1, T2 |
| deploy/ | 15 | DEPLOY |
| demo/ | 22 (含静态文件) | DEMO, T3 |
| clients/ | 4 | ALL |
| kg/ | 6 | T2, T3 |
| scripts/ | 7 | DEPLOY |
| data/ | 6+ | ALL |
| docs/ | 10 | ALL |
| 根目录 | 5 | ALL |
| **总计** | **~183** | |

---

[← 返回项目首页](../../README.md)
