# 链路五：Notebook 演示

> 双击 `demo/start_notebook_demo.bat` → Jupyter Notebook 交互式全链路展示

---

## 启动流程

```
用户双击 demo/start_notebook_demo.bat
    ▼
    start_notebook_demo.bat                                   │
    1. 设置环境变量:                                          │
    CCF_NEXENT_CONFIG_BASE  = https://nexent-api.mashiro.xin │
    CCF_NEXENT_RUNTIME_BASE = https://nexent-runtime.mashiro.xin │
    CCF_NEXENT_EMAIL        = suadmin@nexent.com           │
    CCF_NEXENT_PASSWORD     = 241002814                    │
    CCF_TASK3_DEMO_URL      = https://demo.mashiro.xin/    │
    2. cd 到项目根目录                                        │
    3. jupyter notebook demo/interactive_pipeline_demo.ipynb │
    ▼
Jupyter Notebook 启动 → 浏览器打开
    Cell 0: 环境初始化
    Cell 1: 样式加载
    Cell 2: 交互界面 (ipywidgets)
    Cell 3: 数据分析看板 (SQLite 直连)
    Cell 4: 全链路演示 (依次调 3 个 Agent)
```

---

## Cell 0: 环境初始化

```
执行的代码 (简化):

1. SSL 兼容性修复
    自定义 TLS12Adapter (minimum_version = TLSv1_2)
    猴子补丁 requests.post / requests.get
    解决 Anaconda OpenSSL 1.1.1u 与 Cloudflare TLS 兼容问题

2. 连接 Nexent
    from clients.nexent_client import NexentClient
    client = NexentClient(
    config_base  = "https://nexent-api.mashiro.xin",
    runtime_base = "https://nexent-runtime.mashiro.xin",
    email        = "suadmin@nexent.com",
    password     = "241002814"
    )
    client.login()  →  POST /user/signin → JWT token

3. 获取 Agent 列表
    agents = client.list_agents()
    按名称匹配:
       "medical_data_cleaner" → AGENT_IDS[1]  (任务一)
       "medical_kg_qa"        → AGENT_IDS[2]  (任务二)
       "medical_nl2sql"       → AGENT_IDS[3]  (任务三)

4. 数据库路径
    KG_DB      = data/task2_medical_kg.db
    ANALYTICS_DB = data/task3_analytics.db
    EXAMPLE_DIR  = data/demo_medical_texts/

输出: "Nexent 服务器已连接 | Agent 已就绪: 3 个"
```

## Cell 1: 样式加载

```
纯前端: CSS 样式定义
  - .ccf-chat  : 对话气泡容器
  - .ccf-user  : 用户消息 (蓝色气泡, 右对齐)
  - .ccf-agent : Agent 回复 (灰色气泡, 左对齐)
  - .ccf-tool  : 工具调用标签 (蓝色小标签)
  - .ccf-kpi   : KPI 卡片 (白色, 阴影)
  - .ccf-h2    : 标题样式

预设示例文本:
  任务一: "患者T2DM病史8年...主诉胸闷3天..."
  任务二: "患者男65岁，胸痛2小时入院..."
  任务三: "糖尿病有哪些症状" / "统计症状频率 Top 5" / "高血压用什么药"
```

## Cell 2: 交互界面 (ipywidgets)

```
界面组件:
  ┌─ 任务选择 ──────────────────────────────────────┐
    Dropdown: [任务一: 数据清洗 | 任务二 | 任务三]    │
    示例问题 ──────────────────────────────────────┤
    Dropdown: [预设问题列表]  [使用此示例] 按钮       │
    输入区 ────────────────────────────────────────┤
    Tab 1: 文字输入  → Textarea + [发送] 按钮        │
    Tab 2: 上传文件  → FileUpload (.txt/.csv/.json)  │
    Tab 3: 示例文件  → 从 data/demo_medical_texts/   │
  ┌─ 对话区 ────────────────────────────────────────┐
    Output widget: 流式渲染 Agent 回复               │

发送逻辑 (_send 函数):
  1. 获取用户输入的文本
  2. 显示用户消息气泡 (蓝色, 右对齐)
  3. for event in client.run_agent_stream(agent_id, query):
    type="parse"           → 记录工具调用名
    type="model_output_thinking" → 追加到回复缓冲
    type="final_answer"    → 追加到回复缓冲, 结束
  4. 每 8 个 chunk 或 final_answer 时刷新显示
  5. 显示 Agent 回复 (Markdown 渲染)
  6. 如有工具调用, 显示折叠的工具调用记录

run_agent_stream 的底层:
  POST {NEXENT_RUNTIME}/agent/run
  Headers: Authorization + Accept: text/event-stream
  Body: {agent_id, query}
  → SSE 流: data:{json}\n\n
```

## Cell 3: 数据分析看板

```
不经过 Agent/MCP — 直接读本地 SQLite

1. KPI 卡片:
   sqlite3 data/task2_medical_kg.db:
     SELECT COUNT(*) FROM kg_entities    → 79K 实体
     SELECT COUNT(*) FROM kg_triples    → 467K 三元组
   sqlite3 data/task3_analytics.db:
     SELECT COUNT(*) FROM diseases      → 14K 疾病
     SELECT COUNT(*) FROM disease_symptoms → 65K 症状记录

2. 图表 (Plotly):
   症状关联疾病数 Top 10:
     SELECT symptom, COUNT(*) cnt
     FROM disease_symptoms
     GROUP BY symptom ORDER BY cnt DESC LIMIT 10
     → px.bar() 柱状图

   疾病科室分布:
     SELECT department, COUNT(*) cnt
     FROM disease_departments
     GROUP BY department ORDER BY cnt DESC LIMIT 8
     → px.pie() 饼图

注意: 这些查询完全本地执行, 不依赖任何网络服务
```

## Cell 4: 全链路演示

```
依次调用 3 个 Agent, 展示完整数据流:

Stage 1: 任务一 Agent → 清洗医疗文本
  输入: "请清洗以下医疗文本: 患者T2DM病史8年..."
  预期 Agent 行为:
    → upload_text_to_datamate()
    → run_task1_mixed_cleaning()
    → 返回清洗结果 (文件数、算子链、质量评分)

Stage 2: 任务二 Agent → 知识抽取
  输入: "请抽取实体、关系和三元组: 患者男65岁..."
  预期 Agent 行为:
    → extract_medical_entities()
    → extract_medical_relations()
    → generate_medical_triples()
    → 返回抽取结果

Stage 3: 任务三 Agent → 数据分析
  输入: "糖尿病有哪些症状"
  预期 Agent 行为:
    → query_disease_analytics("糖尿病", "symptoms")
    → 返回症状列表

每阶段:
  - 流式显示 Agent 思考过程和最终回复
  - 统计工具调用次数
  - 提供可视化平台链接
```

---

## 涉及的文件

| 文件 | 作用 |
|------|------|
| `demo/start_notebook_demo.bat` | Windows 启动脚本, 设置环境变量 |
| `demo/interactive_pipeline_demo.ipynb` | 主演示 Notebook (5 cells) |
| `demo/task1_pipeline_demo.ipynb` | 任务一专项 Notebook (备选) |
| `clients/nexent_client.py` | Nexent API 客户端 (230 行) |
| `clients/datamate_client.py` | DataMate API 客户端 (stub) |
| `clients/__init__.py` | 包导出 |

## NexentClient API 调用速查

| 方法 | HTTP | 用途 |
|------|------|------|
| `login()` | POST :5010/user/signin | 获取 JWT token |
| `list_agents()` | GET :5010/agent/list | 获取所有 Agent |
| `get_agent_info(id)` | POST :5010/agent/search_info | 获取 Agent 详情 |
| `update_agent(config)` | POST :5010/agent/update | 更新 Agent draft |
| `publish_agent(id)` | POST :5010/agent/{id}/publish | 发布 Agent 版本 |
| `add_mcp_server(url, name)` | POST :5010/mcp/add | 注册 MCP 服务 |
| `scan_tools()` | GET :5010/tool/scan_tool | 扫描 MCP 工具 |
| `list_tools()` | GET :5010/tool/list | 列出所有工具 |
| `run_agent_stream(id, query)` | POST :5014/agent/run | **SSE 流式对话** |
| `run_agent(id, query)` | POST :5014/agent/run | 阻塞式对话 |
| `list_knowledge_bases()` | GET :5010/indices | 列出知识库 |
| `import_documents(idx, docs)` | POST :5010/indices/{idx}/documents | 导入知识库文档 |

## 依赖

| 依赖 | 用途 | 不可用时的后果 |
|------|------|---------------|
| Nexent 在线服务 | Agent 对话 | Cell 2 和 Cell 4 不可用 |
| 演示账号 | 登录认证 | 完全无法启动 |
| task2_medical_kg.db | Cell 3 KPI + 图表 | Cell 3 看板空白 |
| task3_analytics.db | Cell 3 KPI + 图表 | Cell 3 看板空白 |
| Jupyter + ipywidgets | Notebook 运行 | 启动失败 |
| plotly + pandas | Cell 3 图表渲染 | 图表不显示 |

---

[← 返回项目首页](../../README.md)
