# deploy 目录说明

`deploy/` 提供新环境部署和在线环境维护所需脚本。在线服务已经部署完成时，日常验证只需要访问根目录 `README.md` 中列出的三个公网入口。

## 1. 执行顺序

## 1. 脚本索引

| 步骤 | 脚本 | 作用 |
| --- | --- | --- |
| - | [`run_all.sh`](run_all.sh) | **一键串联部署**（自动执行 00-08）。 |
| 1 | [`00_check_prereqs.sh`](00_check_prereqs.sh) | 检查 Docker、Python、配置文件、路径和必要命令。 |
| 2 | [`01_setup_python.sh`](01_setup_python.sh) | 创建 Python 虚拟环境并安装依赖。 |
| 3 | [`02_deploy_operators.sh`](02_deploy_operators.sh) | 将自定义算子同步到 DataMate 算子运行目录。 |
| 4 | [`03_register_operators.sh`](03_register_operators.sh) | 生成并导入 DataMate 算子注册 SQL。 |
| 5 | [`04_build_databases.sh`](04_build_databases.sh) | 构建任务二知识图谱库和任务三分析库。 |
| 6 | [`05_start_mcp.sh`](05_start_mcp.sh) | 启动 MCP 工具服务。 |
| 7 | [`06_register_nexent.sh`](06_register_nexent.sh) | 注册 MCP 服务并发布任务一、任务二、任务三智能体。 |
| 8 | [`07_start_demo.sh`](07_start_demo.sh) | 启动医学数据智能体可视化平台。 |
| 9 | [`08_verify.sh`](08_verify.sh) | 检查服务健康状态和核心接口。 |
| -- | [`docker-compose.ccf-override.yml`](docker-compose.ccf-override.yml) | 端口覆盖配置。 |

## 2. 配置文件

部署前复制模板并填写目标环境参数。字段说明见 [`docs/CONFIGURATION_GUIDE.md`](../docs/CONFIGURATION_GUIDE.md)。

```bash
cp .env.example .env.runtime
cp config.example.yaml config.yaml
```

## 3. 健康检查

```bash
bash deploy/08_verify.sh
```

## 4. 回滚原则

- 部署算子前备份 DataMate 算子目录。
- 重建数据库前备份 `data/task2_medical_kg.db` 和 `data/task3_analytics.db`。
- 发布 Agent 前保留旧版本，必要时在 Nexent 中切回旧版本。

---

[← 返回项目首页](../README.md)
