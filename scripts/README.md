# scripts 目录说明

`scripts/` 只保留部署流程需要调用的平台维护脚本，不作为用户交互入口，也不保存一次性测试脚本。

## 文件说明

| 文件 | 作用 | 由谁调用 |
| --- | --- | --- |
| `runtime_env.py` | 读取 `.env.runtime` 中的运行配置，避免在代码中写死部署参数。 | 其他脚本 |
| `register_mcp.py` | 将 MCP 服务地址登记到 Nexent，使智能体能够发现工具。 | `deploy/06_register_nexent.sh` |
| `update_nexent_agents.py` | 创建或更新任务一、任务二、任务三智能体的工具绑定和提示词。 | `deploy/06_register_nexent.sh` |
| `generate_datamate_registration_sql.py` | 生成 DataMate 算子注册 SQL，用于把 `operators/` 中的自定义算子登记到平台。 | `deploy/03_register_operators.sh` |
| `start_mcp_server.sh` | 在服务器上启动 MCP 服务。 | `deploy/05_start_mcp.sh` |

## 配置来源

脚本优先读取环境变量，其次读取项目根目录下的 `.env.runtime`。配置字段说明见 `docs/CONFIGURATION_GUIDE.md`。

关键字段：

| 字段 | 用途 |
| --- | --- |
| `CCF_NEXENT_CONFIG_BASE` | Nexent 配置 API 地址。 |
| `CCF_NEXENT_RUNTIME_BASE` | Nexent 智能体运行 API 地址。 |
| `CCF_NEXENT_EMAIL` / `CCF_NEXENT_PASSWORD` | 用于发布智能体的账号。 |
| `CCF_MCP_URL` | Nexent 注册 MCP 服务时使用的地址。 |
| `CCF_DATAMATE_BASE` / `CCF_DATAMATE_GATEWAY` | DataMate API 地址。 |

## 使用边界

- 在线服务已部署完成时，不需要手动运行本目录脚本。
- 新环境复现时，应通过 `deploy/` 中的脚本统一调用，避免跳过环境检查和健康检查。
- 本目录不保留数据清洗测试脚本、临时探查脚本或本地调试脚本。
