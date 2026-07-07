# 医学数据智能体可视化平台

`task3_interactive_demo/` 是任务三的网页应用，提供数据流向展示、自然语言问答、知识图谱浏览和噪声审计四类交互能力。页面直接读取 `data/task2_medical_kg.db` 和 `data/task3_analytics.db`，不依赖 Nexent 或 MCP 即可独立运行。

## 在线入口

```text
https://demo.mashiro.xin/
```

## 页面结构

页面采用三栏可拖拽布局，从左至右依次为：

| 面板 | 内容 |
| --- | --- |
| **数据流向** | 数据流转节点图、来源登记列表、核心指标卡片 |
| **自然语言问答** | 文本输入框、示例问题、对话历史、Nexent Agent 模式开关 |
| **图谱洞察** | 四个标签页：关系子图、统计图表、证据表、噪声拦截 |

## 交互能力

### 数据流向

- **流转节点图**：以六节点 DAG 展示从原始混合数据到知识图谱和分析库的完整路径（raw → task1 → clean → task2 → kg → task3），每个节点附带说明文字。
- **来源登记列表**：列出知识图谱中已登记的数据来源，含来源名称、类型、记录数和登记时间。每条来源可单独删除。
- **核心指标卡片**：展示疾病数、知识事实数、图谱实体数、图谱关系数、症状事实数、药物事实数、检查事实数、已拦截噪声数和登记来源总数。
- **刷新按钮**：重新读取知识图谱库和分析库的最新状态，同步任务二入库后的新增数据。
- **来源删除**：需要维护口令。删除前自动备份知识图谱库和分析库到 `data/` 目录，基线来源（QASystemOnMedicalKG、CBLUE）需二次确认。

### 自然语言问答

问题经规则引擎分层处理，无需 LLM 即可响应大部分医学查询：

- **疾病事实查询**：识别疾病名称，匹配症状、药物、检查、并发症、科室、治疗方式、病因、预防和易感人群等维度，返回结构化表格和置信度。
- **统计查询**：识别 `TOP N`、`分布`、`频率`、`统计` 等关键词，执行聚合 SQL 并返回图表数据。
- **关系溯源查询**：调用知识图谱三元组查询，展示 `主体 → 关系 → 客体` 结构。
- **Nexent Agent 模式**（默认开启）：问题先转发至 Nexent 任务三智能体，同步生成前端证据和图表。关闭后仅使用本地规则引擎。
- **示例问题**：页面预置常见问题，点击即发送。

### 图谱洞察（四标签页）

**关系子图**：
- 输入疾病名称 → 载入 → 渲染 SVG 力导向图
- 节点为实体（疾病/症状/药物），边为关系（治疗/症状/并发症/检查等），不同关系类型以颜色区分
- 图形可通过鼠标拖拽、缩放交互
- 查询结果联动对话内容：在问答面板中提交疾病查询后，右侧图谱自动更新为该疾病的关系子图

**统计图表**：
- 基于分析库数据渲染柱状图
- 展示症状关联疾病数排名、疾病科室分布等

**证据表**：
- 问答结果的结构化展示，列出匹配的数据库来源字段和原始值

**噪声拦截**：
- 展示任务一清洗过程中识别并过滤的语义噪声记录
- 按噪声类型汇总统计
- 支持展开每条记录的拦截明细，包含被删除的原文片段和匹配的规则

## 核心文件

| 文件 | 职责 |
| --- | --- |
| **[`server.py`](server.py)** | HTTP 服务入口，注册 `/api/overview`、`/api/query`、`/api/disease_graph` 等路由 |
| **[`query_service.py`](query_service.py)** | 规则优先查询引擎，匹配问题模板并执行 SQL |
| **[`dashboard_payloads.py`](dashboard_payloads.py)** | 生成各 API 端点的响应数据（KPI、图谱、图表、证据） |
| **[`quality.py`](quality.py)** | 读取 `kg_quality_issues` 表，按类型聚合噪声记录 |
| **[`source_management.py`](source_management.py)** | 来源删除、数据库备份、基线来源保护 |
| **[`agent_gateway.py`](agent_gateway.py)** | 将问答请求转发至 Nexent Agent，合并 Agent 回复与本地证据 |
| `static/` | 前端页面（`index.html`、`styles.css`）和 JS 模块（见下表） |

### 前端模块

| 文件 | 职责 |
| --- | --- |
| `static/app.js` | 页面主编排：数据流刷新、问答请求、图谱/图表面板联动 |
| `static/app_common.js` | 公共函数：HTTP 请求、HTML 转义、数字格式化 |
| `static/graph_renderer.js` | SVG 力导向关系子图渲染 |
| `static/visualization_renderer.js` | 统计表格和柱状图渲染 |
| `static/markdown_renderer.js` | Markdown 文本转 HTML |
| `static/quality_renderer.js` | 噪声拦截面板渲染和明细展开 |
| `static/workspace_layout.js` | 三栏可拖拽布局 |

## 依赖数据

| 文件 | 作用 |
| --- | --- |
| `data/task2_medical_kg.db` | 知识图谱库（实体、三元组、关系、来源、质量审计） |
| `data/task3_analytics.db` | 分析库（疾病、症状、药物、检查、科室等扁平统计表） |

## 本地启动

```bash
python demo/task3_interactive_demo/server.py --host 0.0.0.0 --port 8765
```

部署脚本入口：`deploy/07_start_demo.sh`

## 数据安全

来源删除功能默认保护基线来源（QASystemOnMedicalKG、CBLUE），仅允许删除演示过程中新增的来源。删除操作需要口令验证，执行前自动备份知识图谱库和分析库。

---

[← 返回项目首页](../../README.md)
