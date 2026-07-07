# 医学数据智能体工程

基于 DataMate 与 Nexent 构建的医学数据智能体系统，形成”数据治理 → 知识图谱生成 → 分析问答与可视化”的端到端闭环。

## 技术栈

| 层级 | 技术 | 用途 |
| --- | --- | --- |
| 运行平台 | DataMate（数据处理）、Nexent（智能体编排） | 算子运行时、Agent 对话与 MCP 工具调度 |
| 后端服务 | Python 3.10+、FastMCP 3.4 | MCP 工具服务、知识抽取、NL2SQL |
| 前端 | Jupyter Notebook (ipywidgets + Plotly)、原生 HTML/JS | 交互式演示、可视化平台 |
| 数据存储 | SQLite（4 个数据库）、PostgreSQL（DataMate 平台） | 知识图谱、分析库、噪声规则、术语词典 |
| 通信协议 | MCP (streamable-http)、REST API、SSE | 智能体工具调用、DataMate API、流式对话 |
| AI 模型 | LLM API（OpenAI 兼容协议，默认 DeepSeek） | 实体识别、关系抽取、NL2SQL（离线规则链可脱离模型运行） |
| 基础设施 | Docker、GNU Screen、Bash | 容器化部署、后台服务管理 |

## 文档导航

| 你要了解什么 | 去看哪个文档 |
| --- | --- |
| 如何部署到新环境 | **[`DEPLOY.md`](DEPLOY.md)** — 部署总指南 |
| 部署前需要改哪些配置 | [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) — 33 个字段速查 |
| 系统架构和模块职责 | [`docs/ARCHITECTURE_AND_IMPLEMENTATION.md`](docs/ARCHITECTURE_AND_IMPLEMENTATION.md) |
| 如何在线验证功能 | [`docs/DEMO_USAGE_GUIDE.md`](docs/DEMO_USAGE_GUIDE.md) |
| 数据库结构和数据资产 | [`data/README.md`](data/README.md) |
| 任务一清洗的编排细节 | [`docs/TASK1_MIXED_ORCHESTRATION.md`](docs/TASK1_MIXED_ORCHESTRATION.md) |
| 代码调用链路追踪 | [`docs/workflow/README.md`](docs/workflow/README.md) — 五条完整链路 |
| 每个代码文件的作用 | [`docs/workflow/code-inventory.md`](docs/workflow/code-inventory.md) — 183 文件清单 |
| 每个目录的子文档 | 见下方[目录结构](#目录结构) |
| 全部文档列表 | [`docs/README.md`](docs/README.md) — 文档索引导读 |

## 在线服务入口

当前维护了一套可直接访问的在线环境，以下服务均已预先配置完毕，可直接验证。

| 服务 | 地址 | 预置内容 |
| --- | --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` | 已预载知识图谱库与分析库。三栏布局：数据流向面板展示来源登记与核心指标；自然语言问答支持疾病事实查询、统计聚合和关系溯源，可切换 Nexent Agent 模式；图谱洞察面板包含可交互力导向关系子图、统计图表、证据表和噪声拦截明细 |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` | 已注册 17 个 MCP 工具，已发布任务一/二/三共 3 个智能体，可直接对话执行全流程 |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` | 已预先注册**糖尿病全流程演示数据集**（`txt/csv/json/jsonl` 混合格式，含 4 个文件）可用于任务演示，已部署 18 个自定义算子 |

演示账号：`suadmin@nexent.com`  
演示密码：`241002814`

## 快速验证

1. 打开 `https://demo.mashiro.xin/`，确认页面标题为“医学数据智能体可视化平台”，页面可加载数据来源、统计指标、关系子图、图表、证据表和噪声拦截记录。
2. 打开 `https://nexent.mashiro.xin/`，使用演示账号登录，选择任务一、任务二或任务三智能体进行对话。
3. 打开 `https://datamate.mashiro.xin/`，使用演示账号登录，在数据管理中查看糖尿病混合格式数据集及其任务一清洗结果。
4. 如需 Notebook 演示，双击 `demo/start_notebook_demo.bat`。Notebook 默认连接已部署服务并使用演示账号，提供固定数据集全流程一键演示。

可直接输入 Nexent 的示例指令：

```text
处理糖尿病全流程演示数据集，执行任务一混合清洗，并返回工具调用过程、输出数据集、质量报告和吞吐量。
```

```text
基于糖尿病任务一清洗后的最终数据集构建知识图谱，展示解析文件、实体数量、关系数量、三元组数量、入库数量、处理耗时和分析库刷新结果。
```

```text
给出医学数据智能体可视化平台入口，并说明本轮新接入数据来源、NL2SQL 指标和图表验证方式。
```

## 目录结构

| 目录 | 作用 | 详细说明 |
| --- | --- | --- |
| `clients/` | DataMate 与 Nexent HTTP 客户端封装 | **[`clients/README.md`](clients/README.md)** |
| `core/` | 医学实体识别、关系抽取、三元组生成、疾病查询、NL2SQL 等领域能力 | **[`core/README.md`](core/README.md)** |
| `operators/` | 注册到 DataMate 的自定义算子，包括医学术语标准化、结构化字段清洗、语义噪声过滤等 | **[`operators/README.md`](operators/README.md)** |
| `mcp_server/` | 暴露给 Nexent 的 MCP 工具服务，负责任务一、二、三的工具入口和流程编排 | **[`mcp_server/README.md`](mcp_server/README.md)** |
| `kg/` | 知识图谱库与分析库的构建脚本 | **[`kg/README.md`](kg/README.md)** |
| `demo/` | Notebook 演示和医学数据智能体可视化平台 | **[`demo/README.md`](demo/README.md)** |
| `data/` | 糖尿病混合格式数据、任务二知识图谱库、任务三分析库 | **[`data/README.md`](data/README.md)** |
| `deploy/` | 环境检查、算子部署、数据库构建、MCP 启动、Agent 发布、可视化平台启动和健康检查 | **[`deploy/README.md`](deploy/README.md)** |
| `docs/` | 架构、任务实现、部署、配置、演示和数据资产说明 | **[`docs/README.md`](docs/README.md)** |
| `scripts/` | 部署流程调用的平台注册脚本 | **[`scripts/README.md`](scripts/README.md)** |

## 三项任务实现方法

### 任务一：混合格式医学数据治理

任务一重点展示 DataMate 算子和 Nexent 智能体编排能力。系统支持 `txt/csv/json/jsonl` 混合数据集：智能体先调用 MCP 工具探查 DataMate 数据集，再按文件格式分派到不同清洗链，最后把清洗结果重新登记为一个最终数据集，并保留源格式、文件数、血缘和质量证据。

主要实现：

- `operators/medical_term_normalizer/`：医学术语和缩写标准化。
- `operators/table_column_cleaner/`：CSV 字段清洗，保留表格结构。
- `operators/json_field_cleaner/`：JSON / JSONL 字段清洗，保留对象结构。
- `operators/llm_noise_filter/`：语义噪声识别、规则库过滤和质量证据记录。
- `mcp_server/task1/`：混合格式清洗编排、输出数据集整理、质量证据汇总。
- `mcp_server/tools/task1_data.py`：Nexent 调用的任务一工具入口。

### 任务二：医学知识图谱生成

任务二重点展示 MCP 知识抽取算子和智能体自动编排能力。系统读取任务一输出数据集，将混合格式文件解析为统一记录流，执行实体识别、关系抽取、三元组生成、质量过滤、三元组入库和分析库刷新。

主要实现：

- `core/medical_extraction_service.py`：医学知识抽取服务入口。
- `core/medical_offline_extraction.py`：本地规则与词典增强抽取链，降低对模型接口的硬依赖。
- `mcp_server/task2/`：任务二流水线编排、记录选择、执行指标和结果报告。
- `mcp_server/kg/`：三元组入库、来源登记、质量审计和分析库刷新。
- `data/task2_medical_kg.db`：任务二知识图谱库。

任务二返回来源文件、格式分布、解析记录数、实体数、关系数、生成三元组数、入库三元组数、平均耗时、吞吐量和分析库刷新状态。

### 任务三：分析问答与可视化

任务三重点展示任务一、二产物复用。系统读取任务二知识图谱库和任务三分析库，提供疾病详情查询、关系子图、统计图表、证据表、噪声拦截记录、自然语言统计查询和 NL2SQL 指标。

主要实现：

- `mcp_server/tools/task3_query.py`：疾病详情、知识图谱、数据来源、前端状态等工具。
- `mcp_server/tools/task3_nl2sql.py`：自然语言统计查询和只读 SQL 执行。
- `demo/task3_interactive_demo/`：医学数据智能体可视化平台。
- `data/task3_analytics.db`：任务三分析库。

## 文档入口（点击跳转）

| 文档 | 内容 |
| --- | --- |
| **[`docs/README.md`](docs/README.md)** | 文档目录索引与阅读顺序 |
| **[`docs/ARCHITECTURE_AND_IMPLEMENTATION.md`](docs/ARCHITECTURE_AND_IMPLEMENTATION.md)** | 总体架构、三项任务数据流、模块职责、算子分工 |
| **[`docs/DEMO_USAGE_GUIDE.md`](docs/DEMO_USAGE_GUIDE.md)** | 在线服务、演示账号、Notebook 和对话式验证 |
| **[`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md)** | 配置总入口：部署前速查清单 + 33 个环境变量表 + 容器路径说明 |
| **[`docs/TASK1_MIXED_ORCHESTRATION.md`](docs/TASK1_MIXED_ORCHESTRATION.md)** | 任务一混合格式清洗编排、格式保留和质量证据 |

## 部署复现

在线服务已部署完成，可直接验证。新环境复现请参阅 **[`DEPLOY.md`](DEPLOY.md)**（部署总指南，含 9 步清单、配置填写、文件索引和回滚方式）。

## 数据资产

在线环境已预载以下知识库。数据库属于数据产物，不进 Git，通过 Release 资产包或脚本构建分发。

| 文件 | 用途 | 使用方 |
| --- | --- | --- |
| `data/task2_medical_kg.db` | 知识图谱库：实体（79,600）、三元组（467,400）、关系、别名、来源、质量审计 | 任务二 MCP 工具、任务三查询、可视化平台 |
| `data/task3_analytics.db` | 分析库：疾病（14,408）、症状、药物、检查、科室、并发症等 16 张表 | 任务三 NL2SQL、统计图表、疾病问答 |
| `operators/llm_noise_filter/noise_kb.db` | 噪声规则库：431 条语义噪声检测规则 | 任务一 LLMNoiseFilter 算子、可视化平台噪声拦截面板 |
| `operators/medical_term_normalizer/term_kb.db` | 术语标准化库：114 条医学缩写/别名映射 | 任务一 MedicalTermNormalizer 算子、字段清洗算子 |
| `data/standard_diabetes_demo/datamate_upload/` | 糖尿病混合格式演示数据（`txt/csv/json/jsonl`，4 文件） | 任务一 DataMate 清洗演示 |

## 设计边界

- 清洗效果以 MCP 工具返回的真实证据为准，不编造未返回的噪声明细或术语替换结果。
- 任务二以数据库写入为成功依据，不把智能体自然语言自述当作成功依据。
- 当前环境未启用 NPU 加速。
- 对上游 DataMate / Nexent 的改动仅通过算子、MCP 工具、数据库产物、部署脚本和文档体现，不直接修改平台源码。

## 相关仓库

| 仓库 | 地址 | 说明 |
| --- | --- | --- |
| 本工程（提交侧） | [github.com/Amanon-666/medical-agent](https://github.com/Amanon-666/medical-agent) | 算子、MCP 工具、Agent 编排、部署脚本与文档 |
| DataMate（运行平台） | [github.com/ModelEngine-Group/DataMate](https://github.com/ModelEngine-Group/DataMate) | 数据处理平台，提供算子运行时与数据集管理 |
| Nexent（运行平台） | [github.com/ModelEngine-Group/nexent](https://github.com/ModelEngine-Group/nexent) | 智能体平台，提供 Agent 编排与 MCP 工具调度 |

