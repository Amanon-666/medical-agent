# 工程资产说明

本文说明工程目录中各类资产的用途、对应任务和运行边界。

## 1. 根目录文件

| 文件 | 作用 |
| --- | --- |
| `README.md` | 项目总入口，包含在线服务地址、账号、任务流程、目录结构和部署入口。 |
| `.env.example` | 环境变量模板，用于新环境部署。 |
| `config.example.yaml` | YAML 配置模板，用于统一说明服务地址、账号、数据库和部署路径。 |
| `requirements.txt` | Python 依赖列表。 |

## 2. 任务相关资产

| 任务 | 目录或文件 | 说明 |
| --- | --- | --- |
| 任务一 | `operators/` | DataMate 自定义算子。 |
| 任务一 | `mcp_server/task1/` | 混合格式数据集探查、清洗编排和质量证据整理。 |
| 任务二 | `core/` | 医学实体识别、关系抽取和三元组生成。 |
| 任务二 | `mcp_server/task2/` | 知识图谱流水线编排和报告生成。 |
| 任务二 | `mcp_server/kg/` | 三元组入库、来源登记和分析库刷新。 |
| 任务三 | `mcp_server/tools/task3_*.py` | 疾病查询、NL2SQL、数据来源和前端状态工具。 |
| 任务三 | `demo/task3_interactive_demo/` | 医学数据智能体可视化平台。 |

## 3. 数据资产

| 文件或目录 | 说明 |
| --- | --- |
| `data/standard_diabetes_demo/datamate_upload/` | 糖尿病混合格式输入数据，覆盖 `txt/csv/json/jsonl`。 |
| `data/task2_medical_kg.db` | 任务二知识图谱库。 |
| `data/task3_analytics.db` | 任务三分析库。 |

## 4. 部署资产

| 目录或文件 | 说明 |
| --- | --- |
| `deploy/run_all.sh` | 串联环境检查、算子部署、数据库构建、MCP 启动、Agent 发布和健康检查。 |
| `deploy/00_check_prereqs.sh` | 检查 Docker、Python、配置文件和路径。 |
| `deploy/02_deploy_operators.sh` | 同步 DataMate 自定义算子。 |
| `deploy/03_register_operators.sh` | 注册 DataMate 算子元数据。 |
| `deploy/04_build_databases.sh` | 构建任务二和任务三数据库。 |
| `deploy/05_start_mcp.sh` | 启动 MCP 服务。 |
| `deploy/06_register_nexent.sh` | 注册 MCP 服务并发布 Nexent 智能体。 |
| `deploy/07_start_demo.sh` | 启动可视化平台。 |
| `deploy/08_verify.sh` | 执行健康检查。 |

## 5. 不包含的内容

工程目录不保留本地调试脚本、一次性测试脚本、历史运行截图、临时探针和 `__pycache__`。这些内容不属于系统运行或部署所需资产。
