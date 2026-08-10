# 任务三统一分析链

## 这次改动解决什么问题

任务三原来存在两个容易混淆的自然语言入口：Web 工作台走 `MedicalAnalysisService`，MCP 的旧 `execute_nl2sql` 直接调用另一套 NL2SQL 执行器。两条路径可能使用不同数据库、不同安全边界和不同返回结构。

现在的主链只有一条：

```text
Web /api/query
Nexent ask_medical_analytics
Nexent execute_nl2sql（兼容名称）
              ↓
task3/runtime.py
              ↓
问题理解 → 查询规划 → 只读校验 → SQLite 执行
              ↓
证据表 + 回答 + 图表 + 来源范围 + 分析追溯
```

`data/task3_analytics.db` 是唯一权威分析库。`SQL_DB` 仍然导出，但只是指向 `ANALYTICS_DB` 的旧名称兼容别名；旧配置字段 `sql_db_path` 和 `analytics_sqlite_path` 仍可读取，新配置统一使用 `analytics_db_path`。

## 代码入口

| 位置 | 实际作用 |
| --- | --- |
| `task3/runtime.py` | 统一装配 `MedicalAnalysisService`，并接入来源范围说明 |
| `mcp_server/tools/task3_runtime.py` | 为 Nexent MCP 缓存共享服务实例 |
| `mcp_server/tools/task3_query.py` | `ask_medical_analytics` 正式自然语言入口 |
| `mcp_server/tools/task3_nl2sql.py` | `execute_nl2sql` 兼容入口，转调同一服务 |
| `demo/task3_interactive_demo/analysis_runtime.py` | Web 工作台装配同一服务 |
| `mcp_server/config.py` | 解析唯一分析库路径，并兼容旧环境变量 |

`query_disease_analytics` 仍保留为旧调用方需要的结构化字段投影。它不是任务三智能体的自然语言主路由；任务三 Agent 的发布提示词已改为所有疾病详情、统计、排名和解释问题优先调用 `ask_medical_analytics`。

## 统一结果契约

成功分析至少包含：

- `analysis_id`：本轮分析的唯一标识；
- `plan`、`planner`：问题识别和查询规划信息；
- `analyses`：每项 SQL、执行状态、列、行、行数和图表；
- `answer`、`charts`：回答和可视化数据；
- `analysis_scope`、`provenance`：来源范围、数据库文件、查询数量、耗时和结果行数。

所有 SQL 仍经过单条 `SELECT/WITH`、允许对象、只读连接、5 秒中止和 200 行上限检查。

## 验证方式

本地：

```bash
python -m pytest tests -q
```

运行态：

```bash
bash deploy/05_start_mcp.sh
bash deploy/07_start_demo.sh --restart
```

验收时使用同一个问题分别调用 `ask_medical_analytics`、`execute_nl2sql` 和 `/api/query`，核对 `planner`、`row_count`、首条 SQL、`analysis_scope` 和 `provenance`。本轮真实核验中，MCP 传输层列出 19 个工具；两个 MCP 入口均返回确定性规划、20 行结果和相同 SQL，Web `/api/query` 返回成功和 20 行证据。

Nexent Agent 已实际调用 `ask_medical_analytics`。当前 Nexent 事件流只返回最终文本，未返回可验证的结构化分析对象，因此 Web 网关会使用同一分析服务回退并标记 `degraded=true`。该标记表示 Agent 事件结构尚未闭合，不表示分析库查询失败。

## 能力边界

任务三回答的是疾病知识条目、关系事实及其聚合统计，不是患者级临床统计；当前分析库没有患者唯一标识和可用时间字段。133 道 NL2SQL 题的回归复核用于检验分析库上的 SQL 执行一致性，不代表 Nexent 完整对话质量，也不代表复杂问题的泛化能力。
