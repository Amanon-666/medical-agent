# DataMate 自定义算子说明

`operators/` 存放任务一使用的 DataMate 自定义算子，以及任务二可复用的医学抽取算子。每个算子目录包含 `process.py` 和 `metadata.yml`，用于部署到 DataMate 算子运行环境并注册到算子库。

## 任务一清洗算子

| 算子 | 作用 |
| --- | --- |
| `emoji_cleaner` | 移除 Emoji 和表情符号。 |
| `url_remover` | 移除 URL、邮箱等外部噪声。 |
| `whitespace_normalizer` | 归一化空白、换行和不可见字符。 |
| `medical_term_normalizer` | 标准化医学缩写和常见术语。 |
| `table_column_cleaner` | 清洗 CSV 表格字段，保留表格结构。 |
| `json_field_cleaner` | 清洗 JSON / JSONL 字段，保留结构化字段。 |
| `llm_noise_filter` | 结合规则和医学词库识别语义噪声，输出质量证据。 |
| `medical_text_quality_filter` | 判断文本长度、特殊字符比例和重复内容。 |

## 任务二抽取算子

| 算子 | 作用 |
| --- | --- |
| `medical_record_splitter` | 将多段病历拆分为可抽取记录。 |
| `medical_entity_extractor` | 抽取疾病、症状、药物、检查等实体。 |
| `medical_relation_extractor` | 抽取实体之间的医学关系。 |
| `medical_triple_generator` | 生成知识图谱三元组。 |
| `unified_jsonl_exporter` | 将抽取结果导出为统一 JSONL。 |

## 部署方式

算子部署由 `deploy/02_deploy_operators.sh` 和 `deploy/03_register_operators.sh` 完成。修改算子后需要同步到 DataMate 运行容器，并重启 `datamate-runtime`，避免 Ray worker 继续使用旧模块缓存。

## 设计边界

- 算子只负责单步数据处理，不直接操作 Nexent Agent。
- 混合格式编排由 `mcp_server/task1/` 完成。
- 算子输出必须包含可追溯证据，例如字段变更、术语替换、噪声移除数量或过滤原因。

## 辅助知识库与审计模块

| 文件 | 作用 |
| --- | --- |
| `operators/medical_term_normalizer/medical_abbrev.py` | 医学缩写与处方频次词典，提供不依赖模型接口的快速术语标准化。 |
| `operators/llm_noise_filter/noise_logger.py` | 记录语义噪声信号、清洗状态和差异片段，用于质量审计和任务三噪声拦截展示。 |

这些文件是正式能力的一部分，不是临时调试代码。部署时应与对应算子目录一起同步到 DataMate 运行环境。
