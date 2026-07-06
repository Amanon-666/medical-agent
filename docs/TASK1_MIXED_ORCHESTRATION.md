# 任务一混合格式清洗编排

任务一面向 DataMate 中的医学混合格式数据集。系统先识别数据集文件类型，再按 `txt/csv/json/jsonl` 分派到不同清洗链，最后把清洗后的文件重新登记为同一个最终数据集，并写入血缘、质量标签和清洗证据。

## 编排流程

```text
inspect_dataset
  -> 识别文件类型和记录规模
  -> run_task1_mixed_cleaning
      -> 按格式拆分临时子集
      -> 分别执行文本、表格、JSON 字段清洗链
      -> 保留源格式输出清洗文件
      -> 注册最终数据集
      -> 写入质量报告和血缘关系
```

最终数据集保留输入文件格式：源 `txt` 输出为 `txt`，源 `csv` 输出为 `csv`，源 `json` 输出为 `json`，源 `jsonl` 输出为 `jsonl`。统一 JSONL 只作为任务二入口的可选转换，不作为任务一默认交付结果。

## 清洗链设计

| 文件类型 | 清洗链 | 设计原因 |
| --- | --- | --- |
| `txt` | 文本清洗链 | 适合病历、问答、指南片段等非结构化文本。 |
| `csv` | 表格字段清洗链 | 保留列名、行结构、逗号、引号和日期等字段。 |
| `json` / `jsonl` | JSON 字段清洗链 | 保留对象、数组、键名、数值、布尔值和空值结构。 |

### 文本清洗链

```text
EmojiCleaner
-> UrlRemover
-> GrableCharactersCleaner
-> InvisibleCharactersCleaner
-> FullWidthCharacterCleaner
-> TraditionalChineseCleaner
-> HtmlTagCleaner
-> WhitespaceNormalizer
-> MedicalTermNormalizer
-> LLMNoiseFilter
```

文本链负责清理 URL、HTML、Emoji、乱码、不可见字符、全角字符、繁体字、异常空白和常见医学术语缩写。

### 表格字段清洗链

```text
TableColumnCleaner
```

表格链逐字段处理医学文本列，保留病例编号、日期、年龄、性别等结构化字段，避免完整文本链破坏 CSV 结构。

### JSON 字段清洗链

```text
JsonFieldCleaner
```

JSON 链递归遍历字符串字段，只清理字段值，不改变对象层级和键名。这样任务二仍能从清洗后的 JSON/JSONL 中读取实体、关系和来源字段。

## 质量证据

任务一结果以工具返回的真实证据为准。报告中只展示已经被平台记录到的内容，例如：

- 文件数、记录数、字符变化；
- 解析错误、空文本、残留噪声、重复内容；
- 实际观察到的术语替换；
- 各格式子集的处理状态；
- 源数据集到最终数据集的血缘 ID。

如果平台未返回逐文件语义噪声明细，报告只说明“未提供逐文件语义噪声明细”，不会声称语义模型已经确认无噪声。

## 用户验证方式

1. 打开 `https://nexent.mashiro.xin/`，登录演示账号。
2. 选择任务一智能体，输入：

```text
处理糖尿病任务一二三贯通演示数据集_20260627，执行任务一混合清洗，并返回工具调用过程、输出数据集、质量报告和吞吐量。
```

3. 打开 `https://datamate.mashiro.xin/`，进入数据管理，查看任务一最终数据集。
4. 确认最终数据集仍包含 `txt/csv/json/jsonl` 四类文件，且质量报告中的变化与文件预览一致。

## 实现位置

| 模块 | 职责 |
| --- | --- |
| `mcp_server/tools/task1_data.py` | Nexent 可调用的任务一 MCP 工具入口。 |
| `mcp_server/task1/inspection.py` | 数据集探查和格式识别。 |
| `mcp_server/task1/mixed_cleaning_service.py` | 混合格式清洗编排。 |
| `mcp_server/task1/postprocess.py` | 最终数据集整理与格式保留。 |
| `mcp_server/task1/evidence.py` | 清洗证据汇总。 |
| `operators/` | DataMate 自定义清洗算子。 |
