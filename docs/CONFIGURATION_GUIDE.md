# 配置说明

本项目提供两类配置模板：

| 文件 | 用途 |
| --- | --- |
| `.env.example` | Shell 脚本、Python 脚本和服务运行时读取的环境变量模板。 |
| `config.example.yaml` | 结构化配置示例，说明服务地址、账号、数据库和部署路径的对应关系。 |

在线服务已经部署完成，普通验证无需填写配置文件。只有在新环境部署或接管服务时才需要复制模板并填写。

## 部署前速查清单

复制模板后，按顺序完成以下配置即可部署。每项改完可对照 [`deploy/00_check_prereqs.sh`](../deploy/00_check_prereqs.sh) 验证。

| 序号 | 要做什么 | 文件 | 找哪一行 |
|:---:|---------|------|---------|
| 1 | 填入 DeepSeek API Key | [`.env.example`](../.env.example) | `CCF_LLM_API_KEY=` |
| 2 | 设 Nexent 管理员密码 | [`.env.example`](../.env.example) | `CCF_NEXENT_PASSWORD=` |
| 3 | 换成自己的域名（共 5 个 URL） | [`.env.example`](../.env.example) | 搜索 `mashiro.xin`，全部替换 |
| 4 | 填服务器 IP 和 SSH 用户名 | [`config.example.yaml`](../config.example.yaml) | `server:` 段 |
| 5 | 改项目部署目录 | [`config.example.yaml`](../config.example.yaml) | `server_project_root` |
| 6 | 确认 DataMate 数据卷路径 | [`.env.example`](../.env.example) | `CCF_DATASET_VOLUME` |
| 7 | （如需 sudo）设密码 | [`.env.example`](../.env.example) | `CCF_SUDO_PW=` |

改完后执行 `bash deploy/00_check_prereqs.sh` 验证。

## 1. 在线服务地址

| 服务 | 地址 |
| --- | --- |
| 医学数据智能体可视化平台 | `https://demo.mashiro.xin/` |
| Nexent 智能体平台 | `https://nexent.mashiro.xin/` |
| DataMate 数据处理平台 | `https://datamate.mashiro.xin/` |

演示账号：

```text
账号：suadmin@nexent.com
密码：241002814
```

## 2. 必填配置

新环境部署时，至少需要填写：

| 字段 | 说明 | 默认值 | 消费者 |
| --- | --- | --- | --- |
| `CCF_LLM_API_KEY` | DeepSeek API Key | 空 | [`core/llm_client.py`](../core/llm_client.py) |
| `CCF_LLM_BASE_URL` | LLM 接口地址 | `https://api.deepseek.com/v1/chat/completions` | 同上 |
| `CCF_LLM_MODEL` | 模型名称 | `deepseek-chat` | 同上 |
| `CCF_NEXENT_CONFIG_BASE` | Nexent 配置 API 地址 | `http://127.0.0.1:5010` | [`clients/nexent_client.py`](../clients/nexent_client.py) |
| `CCF_NEXENT_RUNTIME_BASE` | Nexent 运行时 API 地址 | `http://127.0.0.1:5014` | 同上 |
| `CCF_NEXENT_EMAIL` | Nexent 管理员账号 | `suadmin@nexent.com` | [`scripts/register_mcp.py`](../scripts/register_mcp.py) |
| `CCF_NEXENT_PASSWORD` | Nexent 管理员密码 | 空 | 同上 |
| `CCF_MCP_URL` | Nexent 访问 MCP 服务的地址 | `http://127.0.0.1:8900/mcp` | 同上 |
| `CCF_PUBLIC_DOMAIN` | 公网主域名 | `mashiro.xin` | [`mcp_server/shared/frontend_status.py`](../mcp_server/shared/frontend_status.py) |
| `CCF_TASK3_DEMO_URL` | 可视化平台公网入口 | `https://demo.mashiro.xin/` | 同上 |
| `CCF_NEXENT_FRONTEND_URL` | Nexent 前端入口 | `https://nexent.mashiro.xin/` | 同上 |
| `CCF_DATAMATE_FRONTEND_URL` | DataMate 前端入口 | `https://datamate.mashiro.xin/` | 同上 |
| `CCF_MCP_PUBLIC_URL` | MCP 服务公网地址 | `https://mcp.mashiro.xin/mcp` | [`scripts/register_mcp.py`](../scripts/register_mcp.py) |
| `CCF_DATAMATE_BASE` | DataMate API 地址 | `http://127.0.0.1:18000` | [`mcp_server/datamate/client.py`](../mcp_server/datamate/client.py)、[`preserved_pipeline.py`](../mcp_server/task1/runtime_helpers/preserved_pipeline.py) |
| `CCF_DATAMATE_GATEWAY` | DataMate 网关地址 | `http://127.0.0.1:8080` | [`mcp_server/datamate/client.py`](../mcp_server/datamate/client.py) |
| `CCF_DATASET_VOLUME` | DataMate 数据集文件目录 | `/home/share/docker-data/volumes/datamate-dataset-volume/_data` | [`client.py`](../mcp_server/datamate/client.py)、[`preserved_pipeline.py`](../mcp_server/task1/runtime_helpers/preserved_pipeline.py)、[`datamate_ops.py`](../mcp_server/task1/runtime_helpers/datamate_ops.py) |
| `CCF_DATAMATE_OPERATOR_VOLUME` | DataMate 算子运行目录 | `/home/share/docker-data/volumes/datamate-operator-runtime-volume/_data` | [`deploy/02_deploy_operators.sh`](../deploy/02_deploy_operators.sh) |
| `CCF_DATAMATE_RUNTIME_CONTAINER` | DataMate 算子运行容器名 | `datamate-runtime` | 同上 |
| `CCF_DATA_ROOT` | 医学数据源目录 | `data/standard_diabetes_demo/datamate_upload` | [`datamate_ops.py`](../mcp_server/task1/runtime_helpers/datamate_ops.py) |
| `CCF_SUDO_PW` | sudo 密码（读 DataMate 卷需 sudo） | 空 | [`mcp_server/datamate/client.py`](../mcp_server/datamate/client.py) |

## 3. 可选配置

| 字段 | 说明 | 默认值 | 消费者 |
| --- | --- | --- | --- |
| `CCF_LLM_API_KEY_FILE` | 从文件读取 LLM API Key（Docker secrets） | `/run/secrets/ccf_llm_api_key` | [`mcp_server/config.py`](../mcp_server/config.py) |
| `CCF_EMBED_API_KEY` | 向量嵌入 API Key（知识库搜索用） | 空 | Nexent 知识库 |
| `CCF_EMBED_BASE_URL` | 向量嵌入接口地址 | `https://api.siliconflow.cn/v1/embeddings` | 同上 |
| `CCF_EMBED_MODEL` | 向量嵌入模型 | `BAAI/bge-large-zh-v1.5` | 同上 |
| `CCF_TASK1_AGENT_ID` | 任务一 Agent ID（覆盖脚本默认值 3） | `3` | [`update_nexent_agents.py`](../scripts/update_nexent_agents.py) |
| `CCF_TASK2_AGENT_ID` | 任务二 Agent ID | `4` | 同上 |
| `CCF_TASK3_AGENT_ID` | 任务三 Agent ID | `5` | 同上 |
| `CCF_MCP_SERVICE_NAME` | MCP 服务在 Nexent 中的注册名 | `medical-ai` | [`register_mcp.py`](../scripts/register_mcp.py) |
| `CCF_MEDICAL_KG_DB` | 知识图谱库路径 | `data/task2_medical_kg.db` | [`mcp_server/config.py`](../mcp_server/config.py) |
| `CCF_ANALYTICS_DB` | 分析库路径 | `data/task3_analytics.db` | 同上 |
| `CCF_DEMO_DELETE_TOKEN` | 可视化平台数据来源删除令牌 | 空 | [`demo/task3_interactive_demo/source_management.py`](../demo/task3_interactive_demo/source_management.py) |
| `CCF_DATAMATE_SOURCE_ROOT` | DataMate 源码目录（运维用） | `/home/share/modelengine/DataMate` | 部署脚本 |
| `MCP_HOST` / `MCP_PORT` | MCP 服务监听地址和端口 | `0.0.0.0:8900` | [`mcp_server/server.py`](../mcp_server/server.py) |

## 4. 无需修改的路径（容器内标准路径）

以下路径是 DataMate Docker 容器内的标准位置，由 [`deploy/02_deploy_operators.sh`](../deploy/02_deploy_operators.sh) 在部署时自动写入。**通常不需要修改**，仅当 DataMate 容器结构不同时才需调整。

| 路径 | 用途 | 所在文件 |
|------|------|---------|
| `/opt/runtime/datamate/ops/user/*/` | 自定义算子目录 | 8 个算子 `process.py` |
| `/opt/runtime/ccf_medical_ai/core/` | core 模块容器内副本 | 3 个抽取算子 `process.py` |
| `/opt/runtime/ccf_medical_ai/data/` | 数据库容器内副本 | 同上 |
| `/opt/runtime/datamate/task2_fewshot/` | few-shot 示例数据 | [`core/medical_fewshot.py`](../core/medical_fewshot.py) |

这些路径与 [`deploy/02_deploy_operators.sh`](../deploy/02_deploy_operators.sh) 中的 `docker cp` 目标目录一一对应。如需修改，两边要同步改。

## 5. 安全注意

- 不要把真实生产密码写入 Git 历史。
- 在线演示账号只用于当前演示环境。
- 新环境部署时应替换账号、密码、域名和数据库路径。
- 数据来源删除令牌应只提供给维护人员。

---

[← 返回项目首页](../README.md)
