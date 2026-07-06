# 数据资产说明

`data/` 保存在线服务和离线复现使用的数据文件。代码可以重新生成数据库，但当前目录中的数据库已经与可视化平台、MCP 工具和 Notebook 演示对齐，可直接用于验证任务二和任务三结果。

## 目录内容

| 路径 | 作用 |
| --- | --- |
| `standard_diabetes_demo/datamate_upload/` | 糖尿病混合格式演示数据，覆盖 `txt/csv/json/jsonl`，用于任务一 DataMate 混合清洗。 |
| `task2_medical_kg.db` | 任务二知识图谱库，保存实体、关系、三元组、来源登记和质量审计。 |
| `task3_analytics.db` | 任务三分析库，支持疾病详情、统计图表、NL2SQL 查询和可视化平台。 |

## 标准演示数据

`standard_diabetes_demo/datamate_upload/` 中的四个文件与在线 DataMate 中使用的糖尿病混合格式数据集保持同类结构：

```text
糖尿病医患问答脏文本.txt
糖尿病病例表格.csv
糖尿病知识图谱子集.json
糖尿病医疗记录.jsonl
```

这些文件故意包含可被算子识别的格式问题和噪声，例如 URL、HTML 标签、全角字符、繁体字、Emoji、导出提示、术语缩写和空白异常。任务一清洗后应保持原始文件格式，不把混合数据集强行转成纯文本。

## 数据库关系

```text
任务一清洗结果
  -> 任务二抽取和入库
  -> task2_medical_kg.db
  -> 任务三统计和 NL2SQL 表
  -> task3_analytics.db
```

`task2_medical_kg.db` 和 `task3_analytics.db` 是数据产物，适合随工程目录提供；不建议写入 Git 历史。新环境可通过 `deploy/04_build_databases.sh` 重新生成。

## 验证入口

- 在线可视化平台：`https://demo.mashiro.xin/`
- 数据处理平台：`https://datamate.mashiro.xin/`
- 智能体平台：`https://nexent.mashiro.xin/`
