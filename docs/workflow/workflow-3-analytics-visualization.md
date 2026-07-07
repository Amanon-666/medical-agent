# 链路三：任务三 — 数据分析与可视化

> 从自然语言问题/浏览器访问 → SQL 查询/NL2SQL → 图表/图谱/问答

---

## 流程总览

任务三有两条并行的用户路径：

```
路径 A: Nexent 对话                       路径 B: 浏览器访问
"糖尿病有哪些症状"                         https://demo.mashiro.xin
    │                                          │
    ▼                                          ▼
Agent 选工具                              Python HTTP 服务
    │                                   (demo/server.py :8765)
    ▼                                          │
┌──────────────────────────────┐      ┌──────────────────────────────┐
│ 三路查询策略                  │      │ 前端 SPA + REST API           │
│                              │      │                              │
│ 1. query_disease_analytics   │      │ /api/overview     → KPI卡片   │
│    精确查疾病表 (毫秒级)      │      │ /api/evaluation   → NL2SQL    │
│                              │      │ /api/lineage      → 数据链路  │
│ 2. ask_medical_analytics     │      │ /api/disease_graph→ 关系图    │
│    SQL 模板引擎               │      │ /api/quality      → 噪声面板  │
│                              │      │ /api/query        → NL问答    │
│ 3. execute_nl2sql            │      │ /api/agent        → Agent网关 │
│    LLM 灵活查询 (100%准确率)  │      └──────────────────────────────┘
└──────────────────────────────┘
    │
    ▼
        SQLite 数据库
    task2_medical_kg.db (8 表, 213MB)
    task3_analytics.db  (16 表, 211MB)
```

---

## 路径 A: Nexent Agent 对话

### Step 1: 三路查询策略

```
用户问题 "糖尿病有哪些症状"
    │
    ▼
Agent 根据问题类型选择工具:
    │
    ├─ 精确查疾病属性 → query_disease_analytics()
    │   文件: mcp_server/tools/task3_query.py
    │
    ├─ 统计分析类 → ask_medical_analytics()
    │   文件: mcp_server/tools/task3_query.py
    │
    └─ 复杂/灵活查询 → execute_nl2sql()
        文件: mcp_server/tools/task3_nl2sql.py
```

### Step 2a: query_disease_analytics() — 精确查询

```
query_disease_analytics(disease="糖尿病", aspect="symptoms")
    │
    ▼
文件: mcp_server/tools/task3_query.py (函数内 SQL)
    │
    ├─ 解析 disease 名称 → 查别名表 (disease_aliases())
    ├─ 根据 aspect 选择目标表:
    │   symptoms     → disease_symptoms (65,192 条)
    │   drugs        → disease_drugs (235,641 条)
    │   complications→ disease_complications (14,081 条)
    │   departments  → disease_departments (16,781 条)
    │   tests        → disease_tests (43,262 条)
    │   procedures   → disease_procedures (22,250 条)
    │   causes       → disease_causes (11,375 条)
    │   preventions  → disease_preventions (9,171 条)
    │   populations  → disease_populations (9,362 条)
    │
    └─ 执行 SQL: SELECT ... FROM {table} WHERE disease_id IN (...)
       → 毫秒级返回，不调 LLM
```

### Step 2b: ask_medical_analytics() — SQL 模板引擎

```
ask_medical_analytics("统计症状出现频率最高的前5项")
    │
    ▼
文件: core/medical_query_engine.py
    │
    ├─ 模板匹配: 问题文本 → 预定义 SQL 模板
    │   模板示例:
    │   "症状频率" → SELECT symptom, COUNT(*) FROM disease_symptoms GROUP BY symptom ORDER BY COUNT(*) DESC LIMIT ?
    │   "科室分布" → SELECT department, COUNT(*) FROM disease_departments GROUP BY department
    │
    └─ 执行 SQL → 返回结果 (不调 LLM)
```

### Step 2c: execute_nl2sql() — LLM 灵活查询

```
execute_nl2sql("高血压患者同时患有糖尿病时应该优先选择什么药物")
    │
    ▼
文件: mcp_server/tools/task3_nl2sql.py:16
    │
    ▼
文件: core/nl2sql.py → nl2sql()
    │
    ├─ 1. 构建 prompt: 包含数据库 schema + 用户问题
    ├─ 2. 调 LLM (DeepSeek) → 生成 SQL
    ├─ 3. 解析 SQL，安全检查 (只允许 SELECT)
    ├─ 4. 执行 SQL → task3_analytics.db
    └─ 5. 返回: {question, sql, result, row_count}

声明准确率: 42/42 = 100%
评测文件: scripts/evaluate_task3_nl2sql_templates.py (⚠ 提交侧缺失)
```

### Step 3: 其他查询工具

```
get_validation_frontend_status()
    └─ mcp_server/shared/frontend_status.py
    └─ 返回: {demo_url, nexent_url, datamate_url, services_status}

query_knowledge_graph(subject)
    └─ 直接查 task2_medical_kg.db → kg_triples 表
    └─ 返回: [{subject, predicate, object, confidence}, ...]

get_medical_data_sources()
    └─ 查 kg_sources 表
    └─ 返回: 数据来源列表 (名称、记录数、三元组数、创建时间)
```

---

## 路径 B: 浏览器可视化平台

### 架构

```
浏览器 https://demo.mashiro.xin
    │
    ▼
Cloudflare Tunnel → localhost:8765
    │
    ▼
demo/task3_interactive_demo/server.py
Python ThreadingHTTPServer (单文件, 无需 Flask/FastAPI)
    │
    ├─ GET / → static/index.html (SPA 单页应用)
    │
    ├─ REST API 路由:
    │   ├─ /api/health          → 数据库存在性检查
    │   ├─ /api/overview        → KPI 概览数据
    │   ├─ /api/evaluation      → NL2SQL 评估数据
    │   ├─ /api/lineage         → 数据血缘链路
    │   ├─ /api/disease_graph   → 疾病关系子图
    │   ├─ /api/quality         → 噪声拦截面板
    │   ├─ /api/search_diseases → 疾病搜索
    │   ├─ POST /api/query      → 自然语言问答
    │   └─ POST /api/agent      → 转发 Nexent Agent
    │
    └─ 前端 JS 模块 (static/):
        ├─ app.js              → 主应用逻辑
        ├─ app_common.js       → 公共函数
        ├─ graph_renderer.js   → PyVis 关系图渲染
        ├─ markdown_renderer.js→ Markdown 渲染
        ├─ quality_renderer.js → 噪声面板渲染
        ├─ visualization_renderer.js → Plotly 图表渲染
        └─ workspace_layout.js → 页面布局
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
| `/api/query` | `query_service.query_medical()` | 路由到 NL2SQL 或 SQL 模板 | 问答结果 |
| `/api/agent` | `agent_gateway.query_nexent_agent()` | → Nexent Runtime API (:5014) | Agent 回复 |

### 页面结构

```
┌─────────────────────────────────────────────────────┐
│  医学数据智能体可视化平台                              │
├──────────┬──────────┬──────────┬────────────────────┤
│ 79K 实体  │ 467K 三元组│ 14K 疾病  │ 65K 症状记录       │  ← KPI 卡片
├─────────────────────────────────────────────────────┤
│  数据来源  │  NL2SQL 指标  │  关系子图                  │
│  (来源列表) │  (准确率表格)  │  (交互式图谱)              │
├─────────────────────────────────────────────────────┤
│  统计图表                    │  噪声拦截记录            │
│  (Plotly bar/pie)           │  (拦截明细)             │
├─────────────────────────────────────────────────────┤
│  疾病问答                                               │
│  (输入框 → NL2SQL/SQL模板 → 结果)                       │
└─────────────────────────────────────────────────────┘
```

---

## 涉及的提交侧文件

### MCP 工具层
| 文件 | 作用 |
|------|------|
| `mcp_server/tools/task3_query.py` | 5 个查询工具: 前端状态、KG查询、数据来源、疾病分析、SQL模板 |
| `mcp_server/tools/task3_nl2sql.py` | NL2SQL 工具 |

### 核心算法层
| 文件 | 作用 |
|------|------|
| `core/nl2sql.py` | NL2SQL 引擎: LLM 生成 SQL → 安全校验 → 执行 |
| `core/medical_query_engine.py` | SQL 模板引擎: 问题匹配 → 预定义 SQL |
| `core/llm_client.py` | 统一 LLM API 出口 |

### Demo 平台
| 文件 | 作用 |
|------|------|
| `demo/task3_interactive_demo/server.py` | HTTP 服务入口 + 路由 |
| `demo/task3_interactive_demo/dashboard_payloads.py` | 各 API 的数据生成逻辑 |
| `demo/task3_interactive_demo/query_service.py` | 自然语言查询 (detect_stats_query + NL2SQL) |
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
  → Agent → query_disease_analytics("糖尿病", "symptoms")
  → SELECT ... FROM disease_symptoms JOIN diseases ...
  → 返回 [{symptom, frequency}, ...]
  → Agent 用自然语言展示

输入 B: "统计症状频率 Top 5" (Nexent 对话)
  → Agent → ask_medical_analytics(question)
  → core/medical_query_engine.py → SQL 模板匹配
  → SELECT symptom, COUNT(*) FROM disease_symptoms GROUP BY symptom ORDER BY COUNT(*) DESC LIMIT 5
  → 返回结果

输入 C: "高血压合并糖尿病用什么药" (Nexent 对话)
  → Agent → execute_nl2sql(question)
  → core/nl2sql.py → LLM 生成 SQL → 安全校验 → 执行
  → 返回 {question, sql, result}

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
