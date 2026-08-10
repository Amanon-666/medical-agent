# 链路三：任务三 — 统一分析服务与可视化

> 从自然语言问题或浏览器访问 → 同一分析服务 → 证据表、图表、问答和报告

---

## 流程总览

任务三有两个协议入口，但自然语言分析只有一条服务链：

```
Nexent ask_medical_analytics ─┐
Nexent execute_nl2sql（兼容名） ├→ task3/runtime.py → MedicalAnalysisService
Web /api/query ───────────────┘       ↓
                           规划 → 只读校验 → 执行 → 证据/图表/报告
                                      ↓
                           唯一分析库 task3_analytics.db

关系子图、来源清单和仪表盘仍由各自只读工具读取图谱库或登记表，
但任务三智能体的自然语言问题不再拆成疾病直查、模板查询和旧 NL2SQL 三条执行链。
```

---

## 入口 A: Nexent Agent 对话

### Step 1: 统一分析入口

```
用户问题 "糖尿病有哪些症状"
 ▼
任务三 Agent 统一调用 ask_medical_analytics()
文件: mcp_server/tools/task3_query.py
旧配置中的 execute_nl2sql() 也转调同一服务
文件: mcp_server/tools/task3_nl2sql.py
 ▼
task3/runtime.py
 ▼
语义规划 → SQL 白名单/只读连接 → 实际结果 → 分析记录
```

### Step 2: 共享执行与交付

```
ask_medical_analytics("统计症状出现频率最高的前5项")
 ▼
task3/planner.py
 1. 常见问题优先使用确定性语义模板
 2. 复杂问题才请求 Schema 约束的结构化计划
 3. 每条 SQL 经过允许对象、单条语句、只读连接和资源上限检查
 ▼
task3/service.py
 1. 执行实际查询并保存列、行、行数和状态
 2. 生成回答、图表数据、来源范围和 provenance
 3. Web 额外保存分析记录供报告导出
```

`query_disease_analytics` 仍保留为旧调用方的结构化字段投影，但不作为任务三智能体的自然语言主路由。

### Step 3: 其他查询工具

```
get_validation_frontend_status()
 mcp_server/shared/frontend_status.py
 返回: {demo_url, nexent_url, datamate_url, services_status}

query_knowledge_graph(subject)
 直接查 task2_medical_kg.db → kg_triples 表
 返回: [{subject, predicate, object, confidence}, ...]

get_medical_data_sources()
 查 kg_sources 表
 返回: 数据来源列表 (名称、记录数、三元组数、创建时间)
```

---

## 入口 B: 浏览器可视化平台

### 架构

```
浏览器 https://demo.mashiro.xin
 ▼
Cloudflare Tunnel → localhost:8765
 ▼
demo/task3_interactive_demo/server.py
Python ThreadingHTTPServer (单文件, 无需 Flask/FastAPI)
 GET / → static/index.html (SPA 单页应用)
 REST API 路由:
 /api/health → 数据库存在性检查
 /api/overview → KPI 概览数据
 /api/evaluation → NL2SQL 评估数据
 /api/lineage → 数据血缘链路
 /api/disease_graph → 疾病关系子图
 /api/quality → 噪声拦截面板
 /api/search_diseases → 疾病搜索
 POST /api/query → 自然语言问答
 POST /api/agent → 转发 Nexent Agent
 前端 JS 模块 (static/):
 app.js → 主应用逻辑
 app_common.js → 公共函数
 graph_renderer.js → PyVis 关系图渲染
 markdown_renderer.js→ Markdown 渲染
 quality_renderer.js → 噪声面板渲染
 visualization_renderer.js → Plotly 图表渲染
 workspace_layout.js → 页面布局
```

### 各 API 端点详解

| 端点 | 后端函数 | 查询的数据库/表 | 前端展示 |
|------|---------|---------------|---------|
| `/api/overview` | `dashboard_payloads.overview_payload()` | KG: kg_entities, kg_triples; Analytics: diseases, disease_symptoms | 4 个 KPI 卡片 |
| `/api/evaluation` | `dashboard_payloads.evaluation_payload()` | 预计算数据 | NL2SQL 评估表格 |
| `/api/lineage` | `dashboard_payloads.lineage_payload()` | kg_sources, kg_triples | 数据来源列表 |
| `/api/disease_graph` | `dashboard_payloads.disease_graph_payload()` | kg_triples + kg_entities + kg_relations | 关系子图 (graph_renderer.js) |
| `/api/quality` | `dashboard_payloads.quality_payload()` | noise_kb.db | 噪声拦截记录 |
| `/api/search_diseases` | `dashboard_payloads.search_diseases_payload()` | diseases (14,406 条) | 疾病搜索下拉 |
| `/api/query` | `query_service.query_medical()` → `analysis_runtime.analyze_question()` | `task3.runtime` → `task3_analytics.db` | 统一分析结果 |
| `/api/agent_query` | `agent_gateway.query_nexent_agent()` | → Nexent Runtime API (:5014)，无结构化结果时回退同一服务 | Agent 回复 |

### 页面结构

```
 医学数据智能体可视化平台 
 79K 实体 467K 三元组 14K 疾病 65K 症状记录 ← KPI 卡片
 数据来源 NL2SQL 指标 关系子图 
 (来源列表) (准确率表格) (交互式图谱) 
 统计图表 噪声拦截记录 
 (Plotly bar/pie) (拦截明细) 
 疾病问答 
 (输入框 → 统一分析服务 → 结果)
```

---

## 涉及的提交侧文件

### MCP 工具层
| 文件 | 作用 |
|------|------|
| `mcp_server/tools/task3_query.py` | 前端状态、KG查询、数据来源和统一医学分析入口 |
| `mcp_server/tools/task3_nl2sql.py` | 兼容旧名称，转调统一分析服务 |
| `mcp_server/tools/task3_runtime.py` | MCP 侧共享服务装配 |

### 核心算法层
| 文件 | 作用 |
|------|------|
| `task3/runtime.py` | Web 与 MCP 共用的服务装配 |
| `task3/planner.py` | 确定性语义模板与 Schema 约束的复杂问题规划 |
| `task3/service.py` | SQL 安全执行、证据绑定、图表和结果契约 |
| `core/nl2sql.py` | 规划器使用的稳定 NL2SQL 模板和评测辅助逻辑 |
| `core/llm_client.py` | 统一 LLM API 出口 |

### Demo 平台
| 文件 | 作用 |
|------|------|
| `demo/task3_interactive_demo/server.py` | HTTP 服务入口 + 路由 |
| `demo/task3_interactive_demo/dashboard_payloads.py` | 各 API 的数据生成逻辑 |
| `demo/task3_interactive_demo/query_service.py` | 自然语言查询入口和统一服务降级边界 |
| `demo/task3_interactive_demo/analysis_runtime.py` | Web 侧共享服务装配和结果保存 |
| `demo/task3_interactive_demo/agent_gateway.py` | 转发到 Nexent Agent |
| `demo/task3_interactive_demo/db_utils.py` | 数据库连接工具 |
| `demo/task3_interactive_demo/http_utils.py` | HTTP 响应工具 |
| `demo/task3_interactive_demo/paths.py` | 路径配置 |
| `demo/task3_interactive_demo/source_management.py` | KG 来源管理 (增删) |
| `demo/task3_interactive_demo/quality.py` | 质量数据查询 |

### 前端 (static/)
| 文件 | 作用 |
|------|------|
| `static/index.html` | SPA 入口 |
| `static/styles.css` | 样式 |
| `static/app.js` | 主逻辑 |
| `static/app_common.js` | 公共函数 |
| `static/graph_renderer.js` | 关系图渲染 |
| `static/markdown_renderer.js` | Markdown 渲染 |
| `static/quality_renderer.js` | 噪声面板 |
| `static/visualization_renderer.js` | Plotly 图表 |
| `static/workspace_layout.js` | 布局管理 |

---

## 数据库结构

### task2_medical_kg.db (知识图谱, 213MB)

| 表 | 行数 | 说明 |
|----|------|------|
| kg_entities | 79,600 | 实体 (疾病/症状/药物/检查等) |
| kg_triples | 467,400 | 三元组 (subject-predicate-object) |
| kg_relations | 15 | 关系类型定义 |
| kg_aliases | 8,807 | 疾病别名 |
| kg_sources | 4 | 数据来源记录 |
| kg_quality_issues | 1,207 | 质量审计记录 |

### task3_analytics.db (分析库, 211MB)

| 表 | 行数 | 说明 |
|----|------|------|
| diseases | 14,406 | 疾病基础信息 |
| disease_symptoms | 65,192 | 疾病→症状 |
| disease_drugs | 235,641 | 疾病→药物 |
| disease_complications | 14,081 | 疾病→并发症 |
| disease_departments | 16,781 | 疾病→科室 |
| disease_tests | 43,262 | 疾病→检查项 |
| disease_procedures | 22,250 | 疾病→治疗方式 |
| disease_causes | 11,375 | 疾病→病因 |
| disease_preventions | 9,171 | 疾病→预防 |
| disease_populations | 9,362 | 疾病→易感人群 |
| qa_examples | 1,000 | NL2SQL 问答示例 |

---

## 数据流向

```
输入 A: "糖尿病有哪些症状" (Nexent 对话)
 → Agent → ask_medical_analytics(question)
 → task3.runtime → 确定性语义计划 → 只读 SQL
 → 返回统一分析结果
 → Agent 用自然语言展示

输入 B: "统计症状频率 Top 5" (Nexent 对话)
 → Agent → ask_medical_analytics(question)
 → task3.runtime → 结构化查询计划 → 只读 SQL
 → SELECT symptom, COUNT(*) FROM disease_symptoms GROUP BY symptom ORDER BY COUNT(*) DESC LIMIT 5
 → 返回结果

输入 C: "高血压合并糖尿病用什么药" (Nexent 对话)
 → Agent → ask_medical_analytics(question)
 → task3.runtime → 多条件计划 → 安全校验 → 执行
 → 返回 {question, sql, result, provenance}

输入 D: 浏览器访问 demo.mashiro.xin
 → server.py 返回 index.html
 → 前端 JS 调 /api/overview → 渲染 KPI
 → 用户搜索疾病 → /api/disease_graph → 渲染关系图
 → 用户输入问题 → POST /api/query → NL2SQL → 展示答案
```

## 需要的外部服务

| 依赖 | 用途 | 不可用时的后果 |
|------|------|---------------|
| SQLite 数据库 | 所有查询的数据源 | 整个任务三不可用 |
| DeepSeek API | NL2SQL 的 LLM 调用 | NL2SQL 不可用 (模板查询仍可用) |
| Nexent API (:5014) | /api/agent 转发 | Agent 网关不可用 (直查 SQLite 仍可用) |

---

[← 返回项目首页](../../README.md)
