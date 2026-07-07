# 部署指南

本文档为项目部署的权威参考。以下流程覆盖从空白环境到全服务可用的完整过程。

---

## 环境要求

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| 操作系统 | Linux（任意发行版） | 用于运行 MCP Server、可视化平台及部署脚本 |
| Python | ≥ 3.10 | 依赖清单见 [`requirements.txt`](requirements.txt) |
| Docker Engine + Compose | 最新稳定版 | 用于运行 DataMate 与 Nexent 容器 |
| SQLite | 系统自带 | 存储知识图谱与分析数据库 |
| DataMate | 官方镜像或源码 | [github.com/ModelEngine-Group/DataMate](https://github.com/ModelEngine-Group/DataMate) |
| Nexent | 官方镜像或源码 | [github.com/ModelEngine-Group/nexent](https://github.com/ModelEngine-Group/nexent) |

> DataMate 与 Nexent 需预先部署并处于运行状态。本工程不包含这两个平台的安装流程。

---

## 部署流程

### 第一步：配置环境

从模板文件创建运行时配置：

```bash
cp .env.example .env.runtime
cp config.example.yaml config.yaml
```

按目标环境修改以下配置项：

| 配置项 | 所在文件 | 修改方式 |
| --- | --- | --- |
| LLM API Key | `.env.runtime` | 填入 `CCF_LLM_API_KEY=` |
| Nexent 管理员凭据 | `.env.runtime` | 填入 `CCF_NEXENT_PASSWORD=` |
| 服务域名（共 5 处） | `.env.runtime` | 搜索 `mashiro.xin` 并替换为目标域名 |
| 服务器连接信息 | `config.yaml` | 修改 `server.host` 与 `server.ssh_user` |
| DataMate 数据卷路径 | `.env.runtime` | 修改 `CCF_DATASET_VOLUME` 以匹配实际挂载点 |

全部 33 个可配置字段的详细说明见 [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md)。

### 第二步：执行部署

```bash
bash deploy/run_all.sh
```

该命令按依赖顺序串行执行以下脚本。任意步骤失败将中断后续步骤，修正后可单独重新执行该步。

| 序号 | 脚本 | 职责 | 常见失败原因 |
|:---:| --- | --- | --- |
| 1 | [`00_check_prereqs.sh`](deploy/00_check_prereqs.sh) | 验证运行时依赖（Docker、Python、配置文件、平台可达性） | `.env.runtime` 未创建或配置项缺失 |
| 2 | [`01_setup_python.sh`](deploy/01_setup_python.sh) | 创建 Python 虚拟环境并安装依赖 | 网络不可达或 pip 源受限 |
| 3 | [`02_deploy_operators.sh`](deploy/02_deploy_operators.sh) | 将自定义算子及依赖文件同步至 DataMate Runtime 容器 | 容器名称与配置不一致 |
| 4 | [`03_register_operators.sh`](deploy/03_register_operators.sh) | 向 DataMate 数据库注册算子元数据 | 注册 SQL 未成功生成 |
| 5 | [`04_build_databases.sh`](deploy/04_build_databases.sh) | 构建知识图谱库与分析库 | 外部数据源路径未正确配置 |
| 6 | [`05_start_mcp.sh`](deploy/05_start_mcp.sh) | 启动 MCP Server（监听 `0.0.0.0:8900`） | GNU Screen 未安装 |
| 7 | [`06_register_nexent.sh`](deploy/06_register_nexent.sh) | 向 Nexent 注册 MCP 服务并发布三个智能体 | Nexent 配置接口不可达 |
| 8 | [`07_start_demo.sh`](deploy/07_start_demo.sh) | 启动可视化平台（监听 `0.0.0.0:8765`） | 数据库文件尚未构建 |
| 9 | [`08_verify.sh`](deploy/08_verify.sh) | 全链路健康检查 | 根据脚本输出定位具体失败项 |

`run_all.sh` 支持部分执行：

```bash
bash deploy/run_all.sh --from 3 --to 6   # 仅重跑第 3-6 步
bash deploy/run_all.sh --dry-run          # 预览而不实际执行
```

### 第三步：验证

```bash
bash deploy/08_verify.sh
```

验证通过后，以下入口应均可访问：

| 服务 | 入口地址（由环境变量决定） |
| --- | --- |
| 医学数据智能体可视化平台 | `CCF_TASK3_DEMO_URL` |
| Nexent 智能体平台 | `CCF_NEXENT_FRONTEND_URL` |
| DataMate 数据处理平台 | `CCF_DATAMATE_FRONTEND_URL` |

### 第四步：发布智能体

首次部署或 MCP 工具集合发生变更后，需执行智能体发布脚本：

```bash
python scripts/update_nexent_agents.py
```

该脚本将三个智能体的 system prompt 与工具绑定写入 Nexent。更多细节见 [`scripts/README.md`](scripts/README.md)。

---

## 附录 A：文件清单

### 部署脚本（`deploy/`）

| 文件 | 职责 |
| --- | --- |
| [`run_all.sh`](deploy/run_all.sh) | 一键部署入口，串行执行 00–08 |
| [`00_check_prereqs.sh`](deploy/00_check_prereqs.sh) – [`08_verify.sh`](deploy/08_verify.sh) | 分步部署脚本（对应上表第 1–9 步） |
| [`docker-compose.ccf-override.yml`](deploy/docker-compose.ccf-override.yml) | 评审环境端口覆盖配置 |
| [`nexent.ccf-clean.env`](deploy/nexent.ccf-clean.env) | Nexent 干净部署环境变量模板 |

### 配置模板（项目根目录）

| 文件 | 职责 |
| --- | --- |
| [`.env.example`](.env.example) | 环境变量模板，复制为 `.env.runtime` 后填写 |
| [`config.example.yaml`](config.example.yaml) | 结构化配置模板，复制为 `config.yaml` 后填写 |
| [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) | 全部 33 个配置字段的说明、默认值与消费者 |

### 注册与维护脚本（`scripts/`）

| 文件 | 职责 | 调用方 |
| --- | --- | --- |
| [`register_mcp.py`](scripts/register_mcp.py) | 将 MCP 服务登记至 Nexent | `deploy/06` |
| [`update_nexent_agents.py`](scripts/update_nexent_agents.py) | 发布/更新三个智能体的 prompt 与工具绑定 | `deploy/06` |
| [`generate_datamate_registration_sql.py`](scripts/generate_datamate_registration_sql.py) | 生成 DataMate 算子注册 SQL | `deploy/03` |
| [`start_mcp_server.sh`](scripts/start_mcp_server.sh) | 启动 MCP Server | `deploy/05` |

### 数据库构建脚本（`kg/`）

| 文件 | 职责 |
| --- | --- |
| [`build_kg_v2.py`](kg/build_kg_v2.py) | 从医学知识源构建知识图谱数据库 |
| [`build_analytics_v2.py`](kg/build_analytics_v2.py) | 从知识图谱数据库派生统计分析库 |

### 相关文档（`docs/`）

| 文件 | 内容 |
| --- | --- |
| [`DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) | 部署流程详解（环境依赖、配置、健康检查、回滚） |
| [`CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) | 配置参考（33 字段表、速查清单、安全注意事项） |
| [`DATA_ARTIFACTS.md`](docs/DATA_ARTIFACTS.md) | 数据库产物、演示数据集与数据来源管理 |
| [`DEMO_USAGE_GUIDE.md`](docs/DEMO_USAGE_GUIDE.md) | 在线服务验证步骤与示例指令 |

---

## 附录 B：回滚操作

部署脚本在执行时不会自动创建备份。以下回滚方式依赖操作者提前手动备份或具备原始代码/数据副本。

| 故障场景 | 前置条件 | 回滚步骤 |
| --- | --- | --- |
| 算子部署异常 | 保留有上一版本的算子代码 | 用上一版本代码重新执行 `bash deploy/02_deploy_operators.sh`，然后 `docker restart datamate-runtime` |
| 数据库构建失败 | 保留有上一版本的数据库文件，或数据源可用 | 用上一版本 `.db` 覆盖 `data/` 目录，或重新执行 `bash deploy/04_build_databases.sh` 从源数据重建 |
| 智能体发布错误 | 发布前版本仍保留在 Nexent 中（`update_nexent_agents.py` 每次发布创建新版本） | 在 Nexent 管理界面选择目标智能体，切换至上一可用版本 |
| MCP 代码缺陷 | 保留有上一版本的 `mcp_server/` 代码 | 用上一版本代码覆盖 `mcp_server/`，执行 `bash deploy/05_start_mcp.sh` 重启 |
