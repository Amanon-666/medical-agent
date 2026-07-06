# deploy 目录说明

`deploy/` 提供新环境部署和在线环境维护所需脚本。在线服务已经部署完成时，日常验证只需要访问根目录 `README.md` 中列出的三个公网入口。

## 1. 执行顺序

| 步骤 | 脚本 | 作用 |
| --- | --- | --- |
| 1 | `00_check_prereqs.sh` | 检查 Docker、Python、配置文件、路径和必要命令。 |
| 2 | `01_setup_python.sh` | 创建 Python 虚拟环境并安装依赖。 |
| 3 | `02_deploy_operators.sh` | 将自定义算子同步到 DataMate 算子运行目录。 |
| 4 | `03_register_operators.sh` | 生成并导入 DataMate 算子注册 SQL。 |
| 5 | `04_build_databases.sh` | 构建任务二知识图谱库和任务三分析库。 |
| 6 | `05_start_mcp.sh` | 启动 MCP 工具服务。 |
| 7 | `06_register_nexent.sh` | 注册 MCP 服务并发布任务一、任务二、任务三智能体。 |
| 8 | `07_start_demo.sh` | 启动医学数据智能体可视化平台。 |
| 9 | `08_verify.sh` | 检查服务健康状态和核心接口。 |

串联执行入口：

```bash
bash deploy/run_all.sh
```

## 2. 配置文件

部署前准备：

```bash
cp .env.example .env.runtime
cp config.example.yaml config.yaml
```

按目标环境填写 Nexent、DataMate、MCP、数据库路径和公网域名。字段说明见 `../docs/CONFIGURATION_GUIDE.md`。

## 3. 公网域名

可视化平台、Nexent 和 DataMate 的在线域名分别为：

```text
https://demo.mashiro.xin/
https://nexent.mashiro.xin/
https://datamate.mashiro.xin/
```

Cloudflare Tunnel 配置脚本位于：

```text
09_apply_cloudflare_tunnel.sh
10_route_cloudflare_dns.sh
```

这两个脚本默认只预览变更，使用 `--apply` 参数才会写入配置。

## 4. 回滚原则

- 部署算子前备份 DataMate 算子目录。
- 重建数据库前备份 `data/task2_medical_kg.db` 和 `data/task3_analytics.db`。
- 发布 Agent 前保留旧版本，必要时在 Nexent 中切回旧版本。
- 修改公网隧道配置前保留原配置文件。
