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

## 可选 PDF 解析能力

PDF 清洗链默认连接 MinerU 官方 Agent 轻量解析接口，不需要部署本地解析容器，也不需要 Token。`.env.runtime` 中保持 `CCF_MINERU_API=https://mineru.net/api/v1/agent` 即可；如使用兼容代理服务，可覆盖该地址和请求超时参数。

任务一在发现 PDF 后先验证远程接口，再执行签名上传、状态轮询、Markdown 下载和 TXT 规范化，随后把 TXT 交给 DataMate 文本清洗链。远程服务不可达、触发限频或文件超过 10 MB / 20 页时会停止该任务并返回明确原因，原有 TXT、CSV、JSON 和 JSONL 链不受影响。

## 1.5 任务二级联抽取运行态更新

```bash
bash deploy/apply_task2_cascade.sh
```

该脚本会先在目标运行态备份任务二抽取文件，再同步级联模块、MCP 入口和三个任务二算子，完成语法检查并重启 MCP。目标主机和项目路径可分别通过 `CCF_REMOTE_HOST`、`CCF_REMOTE_ROOT` 覆盖；纯离线回退仍使用显式 `backend=offline`。

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
