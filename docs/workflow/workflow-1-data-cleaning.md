# 链路一：任务一 — 数据处理

> 从用户输入医疗文本 → 12 算子清洗 → 源格式保留输出

---

## 流程总览

```
用户输入 "清洗这段医疗文本：患者T2DM病史8年..."
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 1: Agent 选择工具                                    │
│ 文件: (Nexent 平台内部，不在提交侧)                         │
│ Agent 根据 duty_prompt 决定调用哪个 MCP 工具                │
└──────────────────────────────────────────────────────────┘
    │
    ├─── inspect_dataset(dataset_id)     ← 探查数据集构成
    ├─── upload_text_to_datamate(text)   ← 上传用户文本
    └─── run_task1_mixed_cleaning(id)    ← 执行混合清洗
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│ Step 2: MCP 工具入口                                      │
│ 文件: mcp_server/tools/task1_data.py                      │
│                                                          │
│ 共 7 个 @mcp.tool 函数:                                   │
│   inspect_dataset()          探查数据集                    │
│   upload_text_to_datamate()  上传文本到 DataMate           │
│   run_task1_mixed_cleaning() 混合格式清洗编排 (★核心)       │
│   get_task1_mixed_cleaning_status()  查询异步任务状态       │
│   get_datamate_result()      获取清洗结果                   │
│   list_datamate_operators()  列出可用算子                   │
│   run_datamate_pipeline()    直接创建清洗流水线             │
└──────────────────────────────────────────────────────────┘
    │
    │ 以 run_task1_mixed_cleaning 为例:
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 3: 混合格式清洗编排                                   │
│ 文件: mcp_server/task1/mixed_cleaning_service.py          │
│ 函数: run_task1_mixed_cleaning_service()                  │
│                                                          │
│ 3a. 解析数据集                                            │
│     └─ mcp_server/datamate/resolver.py                   │
│     └─ DataMate API 查询: 数据集名 → UUID 映射            │
│                                                          │
│ 3b. 文件分类                                              │
│     └─ mcp_server/task1/datasets.py                      │
│     └─ classify_source_file() → txt/csv/json/jsonl 四组   │
│                                                          │
│ 3c. 异步判断 (>50 个文件时走后台)                          │
│     └─ mcp_server/task1/async_worker.py                  │
│     └─ subprocess 启动独立进程执行清洗                     │
│     └─ 状态通过 mcp_server/task1/status.py 写 JSON 文件    │
│                                                          │
│ 3d. 为每组文件创建清洗任务  ← runtime_helpers 调用点       │
│     └─ 延迟 import (函数体内):                             │
│        from mcp_server.task1.runtime_helpers.\            │
│          datamate_ops import register_dataset, run_sudo   │
│        from mcp_server.task1.runtime_helpers.\            │
│          preserved_pipeline import run_pipeline, ...      │
│        from mcp_server.task1.runtime_helpers.\            │
│          quality_eval import evaluate_file, summarize     │
│        from mcp_server.task1.runtime_helpers.\            │
│          governance import register_governance            │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 4: DataMate 清洗任务创建与轮询                        │
│ 文件: runtime_helpers/preserved_pipeline.py               │
│ 函数: run_pipeline()                                      │
│                                                          │
│ POST /api/cleaning/tasks                                  │
│   Body: {                                                │
│     srcDatasetId, destDatasetName,                       │
│     instance: [算子1, 算子2, ...]   ← 来自 chains.py      │
│   }                                                      │
│                                                          │
│ 轮询 GET /api/cleaning/tasks/{id}                         │
│   每 5 秒一次，最多 300 秒                                 │
│   等待 status = COMPLETED                                 │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 5: DataMate 执行算子链                                │
│ 运行位置: DataMate Runtime 容器 (Docker)                   │
│ 不在 MCP 进程内                                           │
│                                                          │
│ 清洗链定义: mcp_server/task1/chains.py                    │
│                                                          │
│ ┌─── text 链 (14 个算子) ───────────────────────────┐     │
│ │ EmojiCleaner          → 去 emoji                  │     │
│ │ UrlRemover            → 去 URL/HTML 实体           │     │
│ │ GrableCharacters      → 去乱码 (DataMate 内置)     │     │
│ │ InvisibleCharacters   → 去不可见字符 (内置)         │     │
│ │ FullWidthCharacter    → 全角转半角 (内置)           │     │
│ │ TraditionalChinese    → 繁转简 (内置)              │     │
│ │ HtmlTagCleaner        → 去 HTML 标签 (内置)         │     │
│ │ WhitespaceNormalizer  → 规范化空格/换行             │     │
│ │ 4 个 Filter           → 长度/重复率/特殊字符 (内置)  │     │
│ │ MedicalTermNormalizer → 术语标准化 (本地+LLM)       │     │
│ │ LLMNoiseFilter        → 语义噪声过滤 (本地+LLM)     │     │
│ └──────────────────────────────────────────────────┘     │
│                                                          │
│ ┌─── csv 链 ───────────────────────────────────────┐     │
│ │ 基础 8 算子 + TableColumnCleaner (pandas 逐列清洗) │     │
│ └──────────────────────────────────────────────────┘     │
│                                                          │
│ ┌─── json/jsonl 链 ────────────────────────────────┐     │
│ │ 基础 8 算子 + JsonFieldCleaner (递归清洗字段)      │     │
│ └──────────────────────────────────────────────────┘     │
│                                                          │
│ 算子代码位置: operators/{算子名}/process.py                │
│ 内置算子: DataMate 平台自带，不在提交侧                     │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 6: 收集清洗结果                                       │
│ 文件: runtime_helpers/preserved_pipeline.py               │
│ 函数: collect_outputs()                                   │
│                                                          │
│ 1. 通过 SQL 查询 DataMate PostgreSQL                      │
│    → 获取输出文件列表                                      │
│ 2. 从 Docker volume 读文件 (需要 sudo)                     │
│    → datamate_ops.run_sudo(['cat', path])                 │
│ 3. 合并被分块的文本                                        │
│    → merge_numbered_text_chunks()                         │
│ 4. 恢复结构化文件后缀                                      │
│    → restore_structured_output_suffix()                   │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 7: 质量评估 + 后处理                                  │
│                                                          │
│ 7a. 质量评估                                              │
│     └─ quality_eval.evaluate_file()                       │
│     └─ 13 条残留噪声正则检测                               │
│     └─ quality_eval.summarize() → pass/fail               │
│                                                          │
│ 7b. 后处理 (确定性字段级清理)                               │
│     └─ local_cleaning.clean_json() / clean_jsonl()        │
│     └─ 18 步规则驱动清理                                   │
│     └─ 包括: 全角转半角、繁转简、HTML移除、URL移除、       │
│        分页标记、重复片段、OCR尾标记、乱码、控制字符等       │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 8: 注册最终交付数据集                                  │
│ 文件: runtime_helpers/preserved_pipeline.py               │
│ 函数: register_final_delivery()                           │
│                                                          │
│ 1. 合并所有输出文件为一个数据集                              │
│ 2. 调 DataMate API 注册                                   │
│ 3. governance.register_governance()                       │
│    → 记录血缘、标签、统计元数据                              │
│ 4. check_db_health()                                      │
│    → 验证 DataMate PostgreSQL 无数据异常                    │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│ Step 9: 返回结果给 Agent                                   │
│                                                          │
│ 返回内容:                                                 │
│   - source_grouping: 文件分组信息                          │
│   - per_type_results: 每条链的执行结果                      │
│   - final_delivery: 最终数据集 ID 和名称                    │
│   - quality: 质量评分和残留噪声统计                         │
│   - operators_plan: 使用的算子列表                          │
│                                                          │
│ Agent 收到结果后，用自然语言组织回复展示给用户               │
└──────────────────────────────────────────────────────────┘
```

---

## 涉及的提交侧文件

### MCP 工具层
| 文件 | 作用 |
|------|------|
| `mcp_server/tools/task1_data.py` | 7 个 @mcp.tool 函数入口 |
| `mcp_server/tools/__init__.py` | mcp 实例共享 (mcp = None → 运行时注入) |

### 编排服务层
| 文件 | 作用 |
|------|------|
| `mcp_server/task1/mixed_cleaning_service.py` | **核心**: 混合格式清洗主逻辑，import runtime_helpers |
| `mcp_server/task1/pipeline_service.py` | 创建 DataMate 清洗任务 + 轮询状态 (60×5秒) |
| `mcp_server/task1/dataset_service.py` | DataMate 数据集上传和探查 |
| `mcp_server/task1/chains.py` | 三条清洗链的算子列表定义 |
| `mcp_server/task1/datasets.py` | 文件分类 (txt/csv/json/jsonl) 和路径解析 |
| `mcp_server/task1/evidence.py` | 清洗质量证据收集和汇总 |
| `mcp_server/task1/inspection.py` | 文件类型识别 + 清洗链推荐 |
| `mcp_server/task1/postprocess.py` | 输出数据集整理 |
| `mcp_server/task1/preserved_cleanup.py` | 源格式保留文件清理 |
| `mcp_server/task1/status.py` | 异步任务状态 JSON 读写 |

### 重构辅助层 (runtime_helpers/)
| 文件 | 作用 |
|------|------|
| `mcp_server/task1/runtime_helpers/__init__.py` | 包说明 |
| `mcp_server/task1/runtime_helpers/datamate_ops.py` | DataMate API 封装: 数据工厂、基准构建、sudo 命令 |
| `mcp_server/task1/runtime_helpers/preserved_pipeline.py` | **409行**: 流水线编排、输出收集、合并、最终注册 |
| `mcp_server/task1/runtime_helpers/quality_eval.py` | 13 条残留噪声正则检测 |
| `mcp_server/task1/runtime_helpers/governance.py` | 治理元数据 (血缘/标签/统计) 登记 |
| `mcp_server/task1/runtime_helpers/local_cleaning.py` | 18 步确定性字段级清洗 |

### 异步执行
| 文件 | 作用 |
|------|------|
| `mcp_server/task1/async_worker.py` | subprocess 后台执行入口，解析 CLI 参数→调用 mixed_cleaning_service |

### DataMate 通信层
| 文件 | 作用 |
|------|------|
| `mcp_server/datamate/client.py` | HTTP POST/GET 封装 + 临时数据集文件写入 |
| `mcp_server/datamate/resolver.py` | 数据集名 → UUID 映射解析 |

### 算子实现 (在 DataMate Runtime 容器内执行)
| 文件 | 类型 | 依赖 |
|------|------|------|
| `operators/emoji_cleaner/process.py` | 纯本地 | 无外部依赖 |
| `operators/url_remover/process.py` | 纯本地 | 无外部依赖 |
| `operators/whitespace_normalizer/process.py` | 纯本地 | 无外部依赖 |
| `operators/llm_noise_filter/process.py` | 本地规则 + LLM | noise_kb.db, noise_rule_engine.py |
| `operators/llm_noise_filter/noise_logger.py` | 可选辅助 | SQLite (try/except 兜底) |
| `operators/medical_term_normalizer/process.py` | 本地词典 + LLM | term_kb.db, medical_abbrev.py |
| `operators/medical_term_normalizer/medical_abbrev.py` | 数据文件 | 114 条缩写 (try/except 兜底) |
| `operators/table_column_cleaner/process.py` | 本地 | **pandas** (⚠ requirements.txt 未列) |
| `operators/json_field_cleaner/process.py` | 本地 | 无外部依赖 |
| `operators/medical_record_splitter/process.py` | 纯本地 | 无外部依赖 |
| `operators/unified_jsonl_exporter/process.py` | 纯本地 | 无外部依赖 |

> DataMate 内置算子 (GrableCharacters, InvisibleCharacters, FullWidthCharacter, TraditionalChinese, HtmlTagCleaner, 4 个 Filter) 不在提交侧，由 DataMate 平台自带。

---

## 数据流向

```
输入: 用户文本 (string)
    │
    ├─ upload_text_to_datamate()
    │   → 写入 DATASET_VOLUME/xxx/input.txt
    │   → DataMate API 注册 → dataset_id (UUID)
    │
    ├─ run_task1_mixed_cleaning(dataset_id)
    │   → DataMate 按格式分组创建清洗任务
    │   → 算子链在 Docker 容器内执行
    │   → 输出写入 DataMate volume
    │
    ├─ collect_outputs()
    │   → sudo cat 从 volume 读取清洗后文件
    │   → 合并分块、恢复后缀
    │
    ├─ 质量评估 + 后处理
    │   → 13 条正则扫描 + 18 步字段清理
    │
    └─ 最终输出: dict
        {
          status: "success",
          final_delivery: {dataset_id, dataset_name},
          per_type_results: {text: {...}, csv: {...}, json: {...}},
          quality: {pass: true, totals: {...}},
          operators_plan: ["EmojiCleaner", "UrlRemover", ...]
        }
```

## 需要的外部服务

| 服务 | 地址 | 用途 |
|------|------|------|
| DataMate API | `{DATAMATE_BASE}/api/cleaning/tasks` | 创建和查询清洗任务 |
| DataMate Gateway | `{DATAMATE_GATEWAY}` | 数据集管理 |
| DataMate Runtime | Docker 容器 `datamate-runtime` | 算子执行环境 |
| DataMate Database | Docker 容器 `datamate-database` | 数据集和任务元数据 (PostgreSQL) |
| Docker socket | `/var/run/docker.sock` | docker exec 查询数据库 |
| sudo | 系统级 | 读取 DataMate volume 中的文件 |

---

[← 返回项目首页](../../README.md)
