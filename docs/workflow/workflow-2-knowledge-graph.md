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
 纯本地: 外部医学词典 + 类型约束 + 否定识别
 不调 LLM API，适合可复现的批量抽取与质量分级
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
 从 data/task2/entity_lexicon.json 加载独立医学词典
 按实体类型建立首字符索引并扫描文本
 词典由 CMeEE 训练数据与既有医学图谱词汇构建，更新词典不需要修改算子代码
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
 Offline 路径在句内候选实体之间执行关系规则:
 - 先检查实体类型组合是否合法
 - 再检查治疗、症状、检查等关系触发词
 - 命中否定表达时阻断对应事实
 - 已在 CMeIE 训练数据中出现的实体对作为高优先级依据
 Relation 数据结构 (core/schemas.py): 
 {subject, predicate, object, confidence} 
 ▼
 Step 5: 三元组生成 + 分组可靠性
 文件: core/medical_triple.py 
 输入: Entity 列表 + Relation 列表 
 输出: Triple 列表 
 Triple 数据结构: 
 {subject, predicate, object, confidence, source} 
 Offline 路径不再把固定常量解释为真实概率。系统依据独立评测结果，
 按“处理阶段 + 抽取方法 + 实体或关系类型”读取可靠性等级:
 - 高: 写入主知识图谱
 - 中: 写入待复核事实记录
 - 低: 写入拦截审计记录，不进入主图谱
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
| `core/medical_offline_extraction.py` | 本地路径: 外部词典、否定识别与类型约束 |
| `core/medical_lexicon.py` | 加载实体词典和已知关系实体对 |
| `core/medical_reliability.py` | 加载分组可靠性配置并给出高/中/低等级 |
| `core/medical_re.py` | LLM 路径: 16 类关系抽取 |
| `core/medical_triple.py` | 三元组生成 + 置信度计算 |
| `core/medical_extraction_validation.py` | 去重、置信度过滤、实体标准化 |
| `core/medical_fewshot.py` | LLM few-shot 提示词示例 |
| `core/medical_normalize.py` | 医学术语标准化 (109 条规则) |
| `core/text_quality.py` | 文本质量评分 (4 维度) |
| `core/text_preprocessor.py` | 文本分段/预处理 |
| `core/llm_client.py` | 统一 LLM API 出口 |
| `core/schemas.py` | 数据契约 (Entity/Relation/Triple) |

### 本地抽取资产与构建工具
| 文件 | 作用 |
|------|------|
| `data/task2/entity_lexicon.json` | 按类型组织的医学实体词典 |
| `data/task2/relation_pairs.json` | 从训练数据整理的已知关系实体对 |
| `data/task2/reliability_profile.json` | 由独立评测集生成的分组可靠性配置 |
| `scripts/build_task2_offline_assets.py` | 从训练集构建资产，并在独立数据上评测和校准 |

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
| CBLUE CMeEE/CMeIE | 训练数据构建离线词典和关系词表；独立数据用于评测与可靠性校准 | 无法重建离线抽取资产和复核质量指标 |
| DataMate API | 读取数据集内容 (流水线模式) | 流水线模式不可用 (直接用文本仍可) |

## 两种后端对比

| | offline 后端 | llm 后端 | hybrid 后端 |
|---|---|---|---|
| 速度 | 快 (正则+词典) | 慢 (~2s/条) | 中等 |
| 质量口径 | 由独立评测与分组可靠性控制 | 由模型输出及校验规则控制 | 合并两路结果后校验 |
| 网络依赖 | 无 | 需要 DeepSeek API | 需要 |
| 适用场景 | 批量预处理 | 高质量要求 | 最终交付 |

## 当前评测结果与边界

本地抽取资产严格区分构建数据和评测数据。CMeEE/CMeIE 训练数据用于
构建词典、关系词表和已知实体对；独立数据再划分为校准部分和最终评测
部分，避免用参与建库的数据计算成绩。

| 指标 | 当前结果 |
|------|----------|
| 实体识别 | Precision 56.50%，Recall 29.57%，F1 38.82% |
| 原始关系抽取 | Precision 11.46%，Recall 17.93%，F1 13.98% |
| 中可靠关系组 | 824 条预测，Precision 58.50% |
| 低可靠关系组 | 7,472 条预测，Precision 6.26%，不进入主图谱 |

实体识别相较早期小词典版本已明显改善，但关系规则的原始 F1 仍然较低。
因此当前工程策略不是掩盖低质量预测，而是通过分组可靠性把大部分低质
事实隔离在主知识图谱之外。可靠性等级是同类抽取结果的经验质量等级，
不是逐条事实的概率，也不在用户对话中展示伪精确百分比。

---

[← 返回项目首页](../../README.md)
