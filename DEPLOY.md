# 部署指南

本文是项目部署的**唯一总入口**。按顺序完成以下步骤即可在新环境复现全部服务。

---

## 前提

| 依赖 | 版本要求 | 说明 |
| --- | --- | --- |
| Linux 服务器 | — | 运行 MCP、可视化平台和部署脚本 |
| Python | ≥ 3.10 | 见 [`requirements.txt`](requirements.txt) |
| Docker + Docker Compose | — | 运行 DataMate 和 Nexent 容器 |
| SQLite | — | 已预装在大多数 Linux 发行版中 |
| DataMate | 官方镜像/源码 | [github.com/ModelEngine-Group/DataMate](https://github.com/ModelEngine-Group/DataMate) |
| Nexent | 官方镜像/源码 | [github.com/ModelEngine-Group/nexent](https://github.com/ModelEngine-Group/nexent) |

---

## 部署步骤

### 0. 复制并填写配置

```bash
cp .env.example .env.runtime
cp config.example.yaml config.yaml
```

| 你要改什么 | 去哪个文件 | 找什么 |
|-----------|-----------|--------|
| DeepSeek API Key | [`.env.example`](.env.example) → `.env.runtime` | `CCF_LLM_API_KEY=` |
| Nexent 管理员密码 | 同上 | `CCF_NEXENT_PASSWORD=` |
| 替换为自己的域名（5 个 URL） | 同上 | 搜索 `mashiro.xin`，全部替换 |
| 填服务器地址 | [`config.example.yaml`](config.example.yaml) → `config.yaml` | `server:` 段 |
| 确认 Docker 路径 | [`.env.example`](.env.example) → `.env.runtime` | `CCF_DATASET_VOLUME` |

全部字段说明见 [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md)。

### 1. 一键部署

```bash
bash deploy/run_all.sh
```

这串行执行以下 9 个脚本。如某步失败可单独重跑。

| 步骤 | 脚本 | 做什么 | 失败时检查 |
|:---:| --- | --- | --- |
| 1 | [`00_check_prereqs.sh`](deploy/00_check_prereqs.sh) | 检查 Docker、Python、配置文件、DataMate/Nexent 可达性 | `.env.runtime` 是否已创建 |
| 2 | [`01_setup_python.sh`](deploy/01_setup_python.sh) | 创建 `.venv` + `pip install` | 网络 / pip 源 |
| 3 | [`02_deploy_operators.sh`](deploy/02_deploy_operators.sh) | `docker cp` 算子代码到 DataMate Runtime 容器 | 容器名是否匹配 |
| 4 | [`03_register_operators.sh`](deploy/03_register_operators.sh) | 在 DataMate PostgreSQL 中注册算子元数据 | SQL 文件是否生成 |
| 5 | [`04_build_databases.sh`](deploy/04_build_databases.sh) | 构建 `task2_medical_kg.db` 和 `task3_analytics.db` | `CCF_MEDICAL_KG_DATA` 是否指向源数据 |
| 6 | [`05_start_mcp.sh`](deploy/05_start_mcp.sh) | 启动 MCP 服务（screen 后台，端口 8900） | `screen` 是否安装 |
| 7 | [`06_register_nexent.sh`](deploy/06_register_nexent.sh) | 注册 MCP 工具 + 发布 3 个智能体 | Nexent API 是否可达 |
| 8 | [`07_start_demo.sh`](deploy/07_start_demo.sh) | 启动可视化平台（screen 后台，端口 8765） | `.db` 文件是否存在 |
| 9 | [`08_verify.sh`](deploy/08_verify.sh) | 健康检查：API、数据库、智能体 | 查看输出定位失败项 |

### 2. 验证部署

```bash
bash deploy/08_verify.sh
```

通过后访问：

| 服务 | 默认入口 |
| --- | --- |
| 可视化平台 | `CCF_TASK3_DEMO_URL`（默认 `https://demo.mashiro.xin/`） |
| Nexent | `CCF_NEXENT_FRONTEND_URL`（默认 `https://nexent.mashiro.xin/`） |
| DataMate | `CCF_DATAMATE_FRONTEND_URL`（默认 `https://datamate.mashiro.xin/`） |

### 3. 发布智能体（首次部署或工具变更后）

```bash
python scripts/update_nexent_agents.py
```

该脚本将三个智能体的 system prompt 和工具绑定推送到 Nexent。首次部署或 MCP 工具集合变化后必须执行。详见 [`scripts/README.md`](scripts/README.md)。

---

## 可选：公网访问

如果评委需要通过公网访问服务（而非仅本机），可配置 Cloudflare Tunnel：

| 脚本 | 作用 | 备注 |
| --- | --- | --- |
| [`09_apply_cloudflare_tunnel.sh`](deploy/09_apply_cloudflare_tunnel.sh) | 应用 Cloudflare Tunnel 配置 | 默认只预览，加 `--apply` 执行 |
| [`10_route_cloudflare_dns.sh`](deploy/10_route_cloudflare_dns.sh) | 注册 Cloudflare DNS 路由 | 默认只预览，加 `--apply --overwrite-dns` 执行 |

---

## 文件索引

### 部署脚本

| 文件 | 作用 |
| --- | --- |
| [`deploy/run_all.sh`](deploy/run_all.sh) | 一键串联执行 00-08 |
| [`deploy/00_check_prereqs.sh`](deploy/00_check_prereqs.sh) | 环境检查 |
| [`deploy/01_setup_python.sh`](deploy/01_setup_python.sh) | Python 环境 |
| [`deploy/02_deploy_operators.sh`](deploy/02_deploy_operators.sh) | 算子部署 |
| [`deploy/03_register_operators.sh`](deploy/03_register_operators.sh) | 算子注册 |
| [`deploy/04_build_databases.sh`](deploy/04_build_databases.sh) | 数据库构建 |
| [`deploy/05_start_mcp.sh`](deploy/05_start_mcp.sh) | MCP 启动 |
| [`deploy/06_register_nexent.sh`](deploy/06_register_nexent.sh) | Nexent 注册 |
| [`deploy/07_start_demo.sh`](deploy/07_start_demo.sh) | 可视化平台启动 |
| [`deploy/08_verify.sh`](deploy/08_verify.sh) | 健康检查 |
| [`deploy/09_apply_cloudflare_tunnel.sh`](deploy/09_apply_cloudflare_tunnel.sh) | Cloudflare Tunnel（可选） |
| [`deploy/10_route_cloudflare_dns.sh`](deploy/10_route_cloudflare_dns.sh) | Cloudflare DNS（可选） |
| [`deploy/docker-compose.ccf-override.yml`](deploy/docker-compose.ccf-override.yml) | 评审环境端口覆盖 |
| [`deploy/nexent.ccf-clean.env`](deploy/nexent.ccf-clean.env) | Nexent 干净部署环境变量 |

### 配置模板

| 文件 | 作用 |
| --- | --- |
| [`.env.example`](.env.example) | 环境变量模板 → 复制为 `.env.runtime` |
| [`config.example.yaml`](config.example.yaml) | YAML 配置模板 → 复制为 `config.yaml` |
| [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) | 全部 33 个字段说明 + 速查清单 |

### 注册脚本

| 文件 | 作用 | 何时运行 |
| --- | --- | --- |
| [`scripts/register_mcp.py`](scripts/register_mcp.py) | 将 MCP 服务登记到 Nexent | `deploy/06` 调用 |
| [`scripts/update_nexent_agents.py`](scripts/update_nexent_agents.py) | 发布/更新三个智能体 | `deploy/06` 调用 |
| [`scripts/generate_datamate_registration_sql.py`](scripts/generate_datamate_registration_sql.py) | 生成算子注册 SQL | `deploy/03` 调用 |
| [`scripts/start_mcp_server.sh`](scripts/start_mcp_server.sh) | 启动 MCP 服务 | `deploy/05` 调用 |

### 构建脚本

| 文件 | 作用 |
| --- | --- |
| [`kg/build_kg_v2.py`](kg/build_kg_v2.py) | 构建知识图谱库 |
| [`kg/build_analytics_v2.py`](kg/build_analytics_v2.py) | 构建分析库 |

### 文档

| 文件 | 内容 |
| --- | --- |
| [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) | 部署流程详解（环境依赖 / 配置 / 回滚） |
| [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) | 配置总入口（33 个字段表 + 速查清单） |
| [`docs/DATA_ARTIFACTS.md`](docs/DATA_ARTIFACTS.md) | 数据资产与数据库说明 |
| [`docs/DEMO_USAGE_GUIDE.md`](docs/DEMO_USAGE_GUIDE.md) | 在线验证步骤 |

---

## 回滚

| 场景 | 操作 |
| --- | --- |
| 算子部署出错 | 恢复 DataMate 算子目录备份 → `docker restart datamate-runtime` |
| 数据库构建出错 | 恢复 `data/task2_medical_kg.db` 和 `data/task3_analytics.db` 备份 |
| Agent 发布出错 | 在 Nexent 中切回旧版本 |
| MCP 代码问题 | 恢复 `mcp_server/` 备份 → 重启 MCP |
