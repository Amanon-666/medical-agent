# 任务一混合格式清洗编排

任务一面向 DataMate 中的医学混合格式数据集。系统先识别数据集文件类型，再按 `txt/csv/json/jsonl/pdf` 分派到不同清洗链，最后把清洗后的文件重新登记为同一个最终数据集，并写入血缘、质量标签和清洗证据。

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

最终数据集保留 `txt/csv/json/jsonl` 的输入格式。PDF 属于显式格式转换：源 `pdf` 先提取为 `txt`，再执行文本清洗链。统一 JSONL 只作为任务二入口的可选转换，不作为任务一默认交付结果。

## 清洗链设计

| 文件类型 | 清洗链 | 设计原因 |
| --- | --- | --- |
| `txt` | 文本清洗链 | 适合病历、问答、指南片段等非结构化文本。 |
| `csv` | 表格字段清洗链 | 保留列名、行结构、逗号、引号和日期等字段。 |
| `json` / `jsonl` | JSON 字段清洗链 | 保留对象、数组、键名、数值、布尔值和空值结构。 |
| `pdf` | PDF 解析与文本清洗链 | MinerU 提取文本并导出 TXT，再复用文本清洗链。 |

### PDF 处理链

智能体先调用数据集探查工具；当发现 PDF 时，MCP 编排层检查 MinerU 官方 Agent 轻量接口是否可达。DataMate 内置 `MineruFormatter` 使用另一种远程推理协议，不能直接连接该云接口，因此工程通过独立适配器完成前置解析，不修改 DataMate 上游代码。检查通过后，编排顺序为：

1. `MinerUAgentRemoteParser` 以签名上传方式提交 PDF，轮询并下载 Markdown 结果；
2. 将 Markdown 规范化为 TXT，注册为 DataMate 临时子数据集；
3. 基础字符、URL、HTML、乱码和空白清理；
4. 文档质量过滤、医学术语标准化和语义噪声过滤；
5. 登记远程任务 ID、解析耗时、PDF 到 TXT 血缘和转换证据。

解析服务未就绪时，任务返回 `pdf_parser_unavailable`，不会跳过 PDF 后继续声称成功。Agent 轻量接口无需 Token，单文件限制为 10 MB、20 页且受 IP 限频；扫描版 PDF 的识别质量取决于原始页面质量。

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
4. 确认最终数据集仍包含 `txt/csv/json/jsonl` 四类源格式；若输入包含 PDF，则同时生成带转换血缘的 TXT 解析产物，且质量报告中的变化与文件预览一致。

## PDF 混合处理

探查阶段识别到 PDF 后，编排服务先检查 MinerU 远程解析能力是否可用。解析成功时，PDF 被转换为结构化文本并保留与源文件关联的转换证据；其余 TXT、CSV、JSON 和 JSONL 文件继续沿用各自的格式专用清洗链。解析结果随后与其他子集一并登记到最终数据集。

该设计避免将所有文件强制转换为纯文本：PDF 的交付格式为可追溯 TXT，其他格式保持原有结构，便于任务二继续读取记录、实体、关系及来源字段。

## 实现位置

| 模块 | 职责 |
| --- | --- |
| `mcp_server/tools/task1_data.py` | Nexent 可调用的任务一 MCP 工具入口。 |
| `mcp_server/task1/inspection.py` | 数据集探查和格式识别。 |
| `mcp_server/task1/mineru_client.py` | MinerU 远程接口、任务轮询和结果下载适配。 |
| `mcp_server/task1/pdf_support.py` | PDF 能力检查、解析结果规范化和质量证据。 |
| `mcp_server/task1/mixed_cleaning_service.py` | 混合格式清洗编排。 |
| `mcp_server/task1/postprocess.py` | 最终数据集整理与格式保留。 |
| `mcp_server/task1/evidence.py` | 清洗证据汇总。 |
| `operators/` | DataMate 自定义清洗算子。 |

---

[← 返回项目首页](../README.md)
