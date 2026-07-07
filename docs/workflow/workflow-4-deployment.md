# 链路四：部署流程

> 用户从零复现项目 — 每一步执行什么脚本、依赖什么外部服务

---

## 部署总览

```
用户拿到提交包
    ▼
1. 准备环境: Docker Compose 启动 DataMate + Nexent
2. 填写配置: .env.example → .env.runtime
3. 一键部署: bash deploy/run_all.sh
    00_check_prereqs.sh  检查环境
    01_setup_python.sh   安装 Python 依赖
    02_deploy_operators.sh  部署算子到 DataMate 容器
    03_register_operators.sh  注册算子元数据
    04_build_databases.sh  构建 KG + 分析库
    05_start_mcp.sh  启动 MCP 服务
    06_register_nexent.sh  注册 Agent 到 Nexent
    07_start_demo.sh  启动可视化平台
    08_verify.sh  全链路健康检查
```

---

## 逐步详解

### 00_check_prereqs.sh — 环境检查

```
检查项:
  ✅ .env.runtime 文件存在
  ✅ Python >= 3.10
  ✅ DataMate 容器运行中 (docker ps | grep datamate)
  ✅ Nexent 容器运行中 (docker ps | grep nexent)
  ✅ curl 可用
  ✅ DataMate API 可达: curl http://localhost:18000
  ✅ Nexent API 可达: curl http://localhost:5010

失败处理: 任一项不满足 → exit 1，打印修复建议
```

### 01_setup_python.sh — Python 环境

```
执行:
  1. python3 -m venv .venv (如果 .venv 不存在)
  2. .venv/bin/pip install -r requirements.txt
  3. py_compile 校验 5 个核心模块:
     - mcp_server/server.py
     - core/medical_query_engine.py
     - kg/build_kg_v2.py
     - kg/build_analytics_v2.py
     - demo/task3_interactive_demo/server.py


依赖:
  pip 源可达 (默认 PyPI, 可配置镜像)
```

### 02_deploy_operators.sh — 算子部署

```
执行:
  1. docker cp operators/emoji_cleaner/* → datamate-runtime:/opt/runtime/datamate/ops/user/
  2. docker cp operators/url_remover/* → ... (14个 task1 算子)
  3. docker cp operators/medical_entity_extractor/* → ... (4个 task2 算子)
  4. docker cp core/ → datamate-runtime:/opt/runtime/ccf_medical_ai/core/
  5. docker cp data/task2_medical_kg.db → datamate-runtime:/opt/runtime/ccf_medical_ai/data/
  6. docker restart datamate-runtime (清除 Ray worker 缓存)

部署的算子:
  task1 (14个): emoji_cleaner, url_remover, whitespace_normalizer,
                llm_noise_filter, medical_term_normalizer,
                table_column_cleaner, json_field_cleaner,
                medical_record_splitter, unified_jsonl_exporter,
                + 5个 DataMate 内置算子
  task2 (4个): medical_entity_extractor, medical_relation_extractor,
                medical_triple_generator, medical_text_quality_filter

⚠ runtime_helpers/ 不需要部署到 DataMate 容器
  它们在 MCP 进程中运行，不在 DataMate 容器内

依赖:
  docker 命令可用
  datamate-runtime 容器运行中
```

### 03_register_operators.sh — 算子注册

```
执行方式 A (SQL 直接写入):
  docker exec -i datamate-database psql -U postgres -d datamate < SQL文件

执行方式 B (Python 脚本):
  python scripts/generate_datamate_registration_sql.py
  → 生成 INSERT INTO t_operator + t_operator_category_relation

验证:
  SELECT id, name FROM t_operator WHERE id IN (算子ID列表)

依赖:
  datamate-database 容器运行中
  PostgreSQL 可达
```

### 04_build_databases.sh — 数据库构建

```
执行:
  1. python kg/build_kg_v2.py \
       --db data/task2_medical_kg.db \
       --medical-json $CCF_MEDICAL_KG_DATA \
       [--cmeie-jsonl $CCF_CMEIE_TRAIN] \
       [--cmeee-json $CCF_CMEEE_TRAIN]

  2. python kg/build_analytics_v2.py \
       --kg-db data/task2_medical_kg.db \
       --analytics-db data/task3_analytics.db

验证:
  sqlite3 data/task2_medical_kg.db ".tables" → 8 表
  sqlite3 data/task3_analytics.db ".tables" → 16 表

⚠ 需要 CCF_MEDICAL_KG_DATA 环境变量指向 QASystemOnMedicalKG/medical.json
  如果未设置 → exit 1，提示用户下载数据源

依赖:
  QASystemOnMedicalKG 数据集 (外部, ~110MB)
  可选: CBLUE CMeEE/CMeIE 数据集 (用于评测和 few-shot)
```

### 05_start_mcp.sh — MCP 服务启动

```
执行:
  1. 杀掉旧进程: pkill -f "mcp_server/server.py" (如果存在)
  2. screen -dmS mcpserver bash -c "
       source .env.runtime &&
       .venv/bin/python mcp_server/server.py >> mcp_server.log 2>&1
     "

MCP 服务配置:
  入口: mcp_server/server.py
  框架: FastMCP 3.4.0
  传输: streamable-http
  地址: 0.0.0.0:8900/mcp
  import 链: server.py → tools/__init__.py → task1_data, task2_extract,
             task2_pipeline, task3_query, task3_nl2sql

验证:
  curl http://127.0.0.1:8900/mcp → HTTP 406 (MCP 协议确认)

依赖:
  screen 命令可用
  .env.runtime 含必要的 API key
```

### 06_register_nexent.sh — Nexent 注册

```
执行:

  [1/2] 注册 MCP 服务:
    python scripts/register_mcp.py
    POST /user/signin → JWT token
    GET /mcp/list → 检查是否已注册
    POST /mcp/add?mcp_url=...&service_name=... → 注册
    GET /tool/scan_tool → 扫描工具到 tool 表

  [2/2] 发布 Agent:
    python scripts/update_nexent_agents.py
    获取/创建 3 个 Agent (task1/task2/task3)
    更新 duty_prompt + constraint_prompt
    绑定 enabled_tool_ids (17个 MCP 工具分配给 3 个 Agent)
    POST /agent/{id}/publish → 发布新版本

验证:
  curl Nexent API → 检查 >= 3 个 Agent 状态为 published

⚠ 需要 CCF_NEXENT_PASSWORD 环境变量
⚠ 新环境无预建 Agent (ID 3/4/5)
  → update_nexent_agents.py 需要支持 create-if-missing 逻辑

依赖:
  Nexent Config API (:5010) 可达
  MCP 服务 (:8900) 已启动
```

### 07_start_demo.sh — 可视化平台

```
执行:
  1. 杀掉旧进程: pkill -f "demo/task3_interactive_demo/server.py"
  2. screen -dmS task3demo bash -c "
       source .env.runtime &&
       .venv/bin/python demo/task3_interactive_demo/server.py \
         --host 0.0.0.0 --port 8765 >> task3_demo.log 2>&1
     "

Demo 服务:
  入口: demo/task3_interactive_demo/server.py
  框架: Python ThreadingHTTPServer (无 Flask/FastAPI 依赖)
  端口: 8765
  路由: /, /api/overview, /api/disease_graph, /api/query, ...

验证:
  curl http://127.0.0.1:8765 → HTTP 200 (index.html)

依赖:
  task2_medical_kg.db 和 task3_analytics.db 存在
  screen 命令可用
```

### 08_verify.sh — 全链路验证

```
检查项:
  ✅ DataMate API (:18000) 可达
  ✅ Nexent Config API (:5010) 可达 → 登录成功
  ✅ Nexent Runtime API (:5014) 可达
  ✅ MCP Server (:8900) 可达 → HTTP 406 (正常)
  ✅ 可视化平台 (:8765) 可达 → HTTP 200
  ✅ task2_medical_kg.db 存在 + 表数量 >= 5
  ✅ task3_analytics.db 存在 + 表数量 >= 10
  ✅ Nexent 已发布 Agent 数量 >= 3
  ✅ KG 实体数 > 0
  ✅ KG 三元组数 > 0

输出: deploy/verification_report.txt
```

### 可选脚本

```
09_apply_cloudflare_tunnel.sh
  → 配置 Cloudflare Tunnel (需 cloudflared 已安装)
  → 默认只预览，--apply 实际执行

10_route_cloudflare_dns.sh
  → 注册 Cloudflare DNS 路由 (子域名 → Tunnel)
  → 需 Cloudflare DNS 已托管域名
  → 默认只预览，--apply --overwrite-dns 实际执行
```

---

## 部署依赖图

```
外部依赖 (用户需自行准备):
    Docker + Docker Compose
    DataMate 镜像/源码 (官方)
    Nexent 镜像/源码 (官方)
    QASystemOnMedicalKG 数据集
    DeepSeek API Key
    (可选) Cloudflare 账号 + 域名

提交侧提供:
    全部 Python 代码 (core/, mcp_server/, operators/, demo/, clients/, kg/)
    部署脚本 (deploy/00-10, run_all.sh)
    配置模板 (.env.example, config.example.yaml)
    预构建 SQLite 数据库 (data/*.db) ← 或通过 04 脚本构建
    Demo 数据集 (data/standard_diabetes_demo/)
    文档 (docs/, README.md)

运行时的数据流:
  用户的 API Key → .env.runtime → MCP Server 环境变量
  → core/llm_client.py → DeepSeek API
  → operators/*/process.py → DataMate Runtime 容器内
```

## 常见失败点

| 步骤 | 失败原因 | 修复 |
|------|---------|------|
| 01 | pip install 失败 (pandas 不在 requirements.txt) | 手动 pip install pandas |
| 04 | CCF_MEDICAL_KG_DATA 未设置 | 下载 QASystemOnMedicalKG 并设置环境变量 |
| 04 | medical.json 路径不存在 | 检查数据是否已下载 |
| 05 | screen 未安装 | apt install screen |
| 06 | CCF_NEXENT_PASSWORD 为空 | 填写 .env.runtime |
| 06 | 新环境无预建 Agent | create-if-missing 逻辑 (需确认脚本是否支持) |
| 02 | datamate-runtime 容器名不同 | 检查 docker ps，修改脚本中的容器名 |

---

[← 返回项目首页](../../README.md)
