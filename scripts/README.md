# scripts 目录说明

`scripts/` 保存部署流程调用的平台配置和发布脚本。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| [`runtime_env.py`](runtime_env.py) | 从 `.env.runtime` 和环境变量读取部署配置 |
| [`register_mcp.py`](register_mcp.py) | 将 MCP 服务地址注册到 Nexent |
| [`update_nexent_agents.py`](update_nexent_agents.py) | 创建或更新三个智能体的工具、提示词、知识库绑定和导出元数据 |
| [`generate_datamate_registration_sql.py`](generate_datamate_registration_sql.py) | 生成 DataMate 自定义算子注册 SQL |
| [`start_mcp_server.sh`](start_mcp_server.sh) | 启动 MCP 服务 |
| [`rebuild_nexent_knowledge_base.py`](rebuild_nexent_knowledge_base.py) | 将文档清单导入统一 1024 维模型的 Nexent 知识库 |

## 创建 Nexent 知识库

准备文档清单后执行：

```powershell
$env:CCF_NEXENT_CONFIG_BASE = "https://nexent-api.example.com"
$env:CCF_NEXENT_EMAIL = "your-account@example.com"
$env:CCF_NEXENT_PASSWORD = "your-password"

python scripts/rebuild_nexent_knowledge_base.py `
  --manifest "path/to/documents_for_import.json" `
  --create-name "medical_knowledge_base"
```

脚本默认使用 `BAAI/bge-large-zh-v1.5` 的 1024 维向量模型。已有知识库可通过 `--index-name` 传入 Nexent 返回的内部索引标识。

## 发布并绑定智能体

在 `.env.runtime` 中配置目标知识库后，由部署脚本统一执行 Agent 更新：

```dotenv
CCF_NEXENT_KB_INDEX_NAME=目标知识库内部索引标识
CCF_NEXENT_KB_SEARCH_MODE=hybrid
```

`update_nexent_agents.py` 会绑定 MCP 工具和 `knowledge_base_search`，补齐 Nexent 导入导出需要的元数据并发布新版本。完整配置字段见 [`docs/CONFIGURATION_GUIDE.md`](../docs/CONFIGURATION_GUIDE.md)。

---

[← 返回项目首页](../README.md)
