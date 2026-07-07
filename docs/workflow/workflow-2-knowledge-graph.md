# 链路二：任务二 — 知识图谱生成

> 从清洗后文本 → 实体识别 → 关系抽取 → 三元组生成 → SQLite 持久化

---

## 流程总览

```
用户输入 "基于清洗后的数据构建知识图谱"
 ▼
 Step 1: Agent 调用 MCP 工具 
 三项独立工具 (可单独调用, 也可通过 pipeline 批量): 
 extract_medical_entities(text, backend) ← 实体识别 
 extract_medical_relations(text, backend) ← 关系抽取 
 generate_medical_triples(text, backend) ← 三元组生成 
 一个编排工具: 
 run_task2_kg_pipeline(dataset_id, ...) ← 全流程批量构建 
 文件: mcp_server/tools/task2_extract.py 
 mcp_server/tools/task2_pipeline.py 
 ▼
 Step 2: 统一抽取入口 
 文件: core/medical_extraction_service.py 
 函数: extract_medical_knowledge(text, backend, ...) 
 backend 参数决定走哪条路径: 
 "offline" 
 → core/medical_offline_extraction.py 
 纯本地: 正则 + AC 自动机 + 词典匹配 
 不调 LLM API，速度快，精度较低 
 "llm" 
 → core/medical_ner.py + core/medical_re.py 
 调 DeepSeek API，使用 few-shot 提示词 
 精度高，依赖网络和 API key 
 "hybrid" 
 offline 先过一遍 → LLM 补充和校验 
 ▼
 Step 3: 实体识别 (NER) 
 识别 9 类医疗实体: 
 疾病、症状、药物、检查、科室、治疗、病因、预防、易感人群 
 LLM 路径: core/medical_ner.py 
 构建 prompt (含 few-shot 示例) 
 core/medical_fewshot.py 
 调 core/llm_client.py → DeepSeek API 
 解析 JSON 输出 → Entity 对象列表 
 Offline 路径: core/medical_offline_extraction.py 
 正则模式匹配 (疾病名称、药物名称等) 
 AC 自动机多模式匹配 
 词典查找 (查 task2_medical_kg.db 已有实体) 
 Entity 数据结构 (core/schemas.py): 
 {name, type, start, end, confidence} 
 ▼
 Step 4: 关系抽取 (RE) 
 识别 16 类实体间关系: 
 治疗、症状、检查、并发、病因、预防、 
 易感人群、就诊科室、病理、鉴别诊断、 
 药物相互作用、禁忌、副作用、预后、传播、关联 
 LLM 路径: core/medical_re.py 
 输入: 文本 + Step 3 识别出的实体列表 
 调 LLM API → 输出实体对 + 关系类型 
 返回 Relation 对象列表 
 Relation 数据结构 (core/schemas.py): 
 {subject, predicate, object, confidence} 
 ▼
 Step 5: 三元组生成 + 置信度 
 文件: core/medical_triple.py 
 输入: Entity 列表 + Relation 列表 
 输出: Triple 列表 
 Triple 数据结构: 
 {subject, predicate, object, confidence, source} 
 置信度计算: 
 - LLM 路径: 模型输出的 confidence 字段 
 - Offline 路径: 基于词典匹配度的启发式计算 
 校验 (core/medical_extraction_validation.py): 
 - 去重: 相同 (s, p, o) 保留最高置信度 
 - 过滤: confidence < 阈值的丢弃 
 - 实体名标准化: core/medical_normalize.py (109 条规则) 
 ▼
 Step 6: KG 流水线批量构建 (run_task2_kg_pipeline) 
 文件: mcp_server/task2/pipeline_service.py 
 大规模场景下不逐条调 Agent，而是走批量流程: 
 6a. 记录选择 
 mcp_server/task2/selection.py 
 从 DataMate 数据集选记录 (支持 limit/max_records) 
 6b. 批量抽取 
 对每条记录调 extract_medical_knowledge() 
 支持 backend 参数切换 offline/llm/hybrid 
 6c. KG 持久化 
 mcp_server/kg/persistence.py 
 写入 task2_medical_kg.db (SQLite): 
 • kg_entities (79,600 条) 
 • kg_triples (467,400 条) 
 • kg_relations (15 种) 
 • kg_aliases (8,807 条别名) 
 • kg_sources (数据来源记录) 
 • kg_quality_issues (质量审计) 
 6d. 分析库刷新 
 mcp_server/kg/analytics_refresh.py 
 从 KG 库刷新 task3_analytics.db (16 表) 
 6e. 报告生成 
 mcp_server/task2/reporting.py 
 统计: 实体数、关系数、三元组数、耗时、吞吐量 
 ▼
 Step 7: 离线大规模 KG 构建 (独立脚本, 不走 MCP) 
 kg/build_kg_v2.py 
 从 QASystemOnMedicalKG/data/medical.json 直接读数据 
 构建完整 task2_medical_kg.db (213MB) 
 命令行: python kg/build_kg_v2.py --db data/xxx.db \ 
 --medical-json /path/to/medical.json 
 kg/build_analytics_v2.py 
 从 KG 库构建分析库 
 生成 task3_analytics.db (211MB, 16 表) 
 命令行: python kg/build_analytics_v2.py \ 
 --kg-db data/task2_medical_kg.db \ 
 --analytics-db data/task3_analytics.db 
```

---

## 涉及的提交侧文件

### MCP 工具层
| 文件 | 作用 |
|------|------|
| `mcp_server/tools/task2_extract.py` | 实体/关系/三元组 3 个 @mcp.tool |
| `mcp_server/tools/task2_pipeline.py` | KG 流水线编排 @mcp.tool |

### 编排服务层
| 文件 | 作用 |
|------|------|
| `mcp_server/task2/pipeline_service.py` | KG 批量构建主逻辑 |
| `mcp_server/task2/selection.py` | 从 DataMate 数据集选记录 |
| `mcp_server/task2/reporting.py` | KG 构建统计报告 |

### 核心算法层 (core/)
| 文件 | 作用 |
|------|------|
| `core/medical_extraction_service.py` | 统一抽取入口，backend 路由 |
| `core/medical_ner.py` | LLM 路径: 9 类实体识别 |
| `core/medical_offline_extraction.py` | 本地路径: 正则+AC自动机+词典 |
| `core/medical_re.py` | LLM 路径: 16 类关系抽取 |
| `core/medical_triple.py` | 三元组生成 + 置信度计算 |
| `core/medical_extraction_validation.py` | 去重、置信度过滤、实体标准化 |
| `core/medical_fewshot.py` | LLM few-shot 提示词示例 |
| `core/medical_normalize.py` | 医学术语标准化 (109 条规则) |
| `core/text_quality.py` | 文本质量评分 (4 维度) |
| `core/text_preprocessor.py` | 文本分段/预处理 |
| `core/llm_client.py` | 统一 LLM API 出口 |
| `core/schemas.py` | 数据契约 (Entity/Relation/Triple) |

### KG 存储层 (mcp_server/kg/)
| 文件 | 作用 |
|------|------|
| `mcp_server/kg/persistence.py` | SQLite 写入 (实体/三元组/来源/别名) |
| `mcp_server/kg/normalization.py` | 实体名标准化 |
| `mcp_server/kg/analytics_refresh.py` | 从 KG 刷新分析库 |
| `mcp_server/kg/analytics.py` | 分析查询辅助 |
| `mcp_server/kg/schema.py` | 表结构定义 |

### 离线构建脚本 (kg/)
| 文件 | 作用 |
|------|------|
| `kg/build_kg_v2.py` | KG 构建脚本 |
| `kg/build_analytics_v2.py` | 分析库构建 (新版) |

### DataMate 算子 (任务二专用, 在 DataMate Runtime 内执行)
| 文件 | 作用 |
|------|------|
| `operators/medical_entity_extractor/process.py` | DataMate 内实体抽取 |
| `operators/medical_relation_extractor/process.py` | DataMate 内关系抽取 |
| `operators/medical_triple_generator/process.py` | DataMate 内三元组生成 |
| `operators/medical_text_quality_filter/process.py` | DataMate 内文本质量过滤 |

---

## 数据流向

```
输入方式 A: 用户直接给文本
 文本 → extract_medical_knowledge(text) → Entity[] + Relation[] + Triple[]
 → 返回 JSON 给 Agent → Agent 组织语言展示

输入方式 B: 基于 DataMate 数据集
 dataset_id → task2/selection.py 选记录
 → 每条记录调 extract_medical_knowledge()
 → kg/persistence.py 写入 SQLite
 → kg/analytics_refresh.py 刷新分析库
 → task2/reporting.py 生成统计报告
 → 返回统计摘要给 Agent

输入方式 C: 离线脚本
 medical.json → kg/build_kg_v2.py → task2_medical_kg.db
 task2_medical_kg.db → kg/build_analytics_v2.py → task3_analytics.db
```

## 需要的外部服务/数据

| 依赖 | 用途 | 不可用时的后果 |
|------|------|---------------|
| DeepSeek API | LLM 路径的 NER/RE/三元组 | 回退到 offline 本地规则 |
| QASystemOnMedicalKG | KG 离线构建源数据 | 无法构建 task2_medical_kg.db |
| CBLUE CMeEE/CMeIE | 评测和 few-shot 示例 | 评测脚本无法运行 |
| DataMate API | 读取数据集内容 (流水线模式) | 流水线模式不可用 (直接用文本仍可) |

## 两种后端对比

| | offline 后端 | llm 后端 | hybrid 后端 |
|---|---|---|---|
| 速度 | 快 (正则+词典) | 慢 (~2s/条) | 中等 |
| 精度 | 较低 | 较高 (F1=0.614) | 最高 |
| 网络依赖 | 无 | 需要 DeepSeek API | 需要 |
| 适用场景 | 批量预处理 | 高质量要求 | 最终交付 |

---

[← 返回项目首页](../../README.md)
