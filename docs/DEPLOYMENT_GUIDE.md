# 部署说明

本文说明如何把医学数据智能体工程部署到一套已经具备 DataMate 与 Nexent 基础平台的环境中。在线服务已经部署完成，部署说明用于新环境复现或运维接管。

## 1. 环境依赖

| 依赖 | 用途 |
| --- | --- |
| Linux 服务器 | 运行 MCP 服务、可视化平台、部署脚本和数据库构建任务。 |
| Docker / Docker Compose | 运行 DataMate、Nexent 及其依赖服务。 |
| Python 3.10+ | 运行 MCP、构建脚本和可视化平台。 |
| SQLite | 保存任务二知识图谱库和任务三分析库。 |
| DataMate | 执行任务一数据治理算子。 |
| Nexent | 创建智能体、绑定 MCP 工具并提供对话入口。 |

## 2. 配置文件

复制模板并按环境填写：

```bash
cp .env.example .env.runtime
cp config.example.yaml config.yaml
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `CCF_NEXENT_CONFIG_BASE` | Nexent 配置接口地址。 |
| `CCF_NEXENT_RUNTIME_BASE` | Nexent 运行时接口地址。 |
| `CCF_NEXENT_EMAIL` / `CCF_NEXENT_PASSWORD` | 发布 Agent 的管理员账号。 |
| `CCF_DATAMATE_BASE` | DataMate API 地址。 |
| `CCF_MCP_URL` | Nexent 访问 MCP 服务的地址。 |
| `CCF_TASK3_DEMO_URL` | 可视化平台公网地址。 |
| `CCF_DATAMATE_OPERATOR_VOLUME` | DataMate 算子运行目录。 |
| `CCF_DATAMATE_RUNTIME_CONTAINER` | DataMate 算子运行容器名。 |

在线演示环境使用：

```text
https://demo.mashiro.xin/
https://nexent.mashiro.xin/
https://datamate.mashiro.xin/
```

## 3. 部署顺序

在项目根目录执行：

```bash
bash deploy/00_check_prereqs.sh
bash deploy/01_setup_python.sh
bash deploy/02_deploy_operators.sh
bash deploy/03_register_operators.sh
bash deploy/04_build_databases.sh
bash deploy/05_start_mcp.sh
bash deploy/06_register_nexent.sh
bash deploy/07_start_demo.sh
bash deploy/08_verify.sh
```

也可以串联执行：

```bash
bash deploy/run_all.sh
```

## 4. 部署结果

部署完成后应具备：

- DataMate 中可见自定义算子；
- Nexent 中可见任务一、任务二、任务三智能体；
- Nexent 的 MCP 工具列表可发现本项目工具；
- `data/task2_medical_kg.db` 存在并包含三元组；
- `data/task3_analytics.db` 存在并可支持 NL2SQL 和图表；
- 可视化平台可通过 `CCF_TASK3_DEMO_URL` 访问。

## 5. 健康检查

执行：

```bash
bash deploy/08_verify.sh
```

检查项包括：

- MCP 服务健康状态；
- 可视化平台健康状态；
- DataMate API 可达性；
- Nexent Agent 和 MCP 工具注册状态；
- 数据库文件是否存在。

## 6. 回滚方式

- 算子部署前应备份 DataMate 算子目录；需要回滚时恢复备份并重启 `datamate-runtime`。
- Agent 发布脚本会生成新版本；需要回退时在 Nexent 中切换回旧版本。
- 数据库构建会覆盖 `data/task2_medical_kg.db` 和 `data/task3_analytics.db`；需要回退时恢复部署前备份。
- Cloudflare Tunnel 配置脚本默认 dry-run，使用 `--apply` 前会备份目标配置。
