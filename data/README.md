# 数据资产说明

`data/` 保存在线服务和离线复现使用的数据文件。代码可以重新生成数据库，但当前目录中的数据库已经与可视化平台、MCP 工具和 Notebook 演示对齐，可直接用于验证任务二和任务三结果。

## 目录内容

| 路径 | 作用 |
| --- | --- |
| [`standard_diabetes_demo/datamate_upload/`](standard_diabetes_demo/datamate_upload/) | 糖尿病混合格式演示数据，覆盖 `txt/csv/json/jsonl`。 |
| `task2_medical_kg.db` | 任务二知识图谱库（不进 Git，通过 Release 或脚本构建）。 |
| `task3_analytics.db` | 任务三分析库（不进 Git，通过 Release 或脚本构建）。 |
| [`task3_nl2sql_eval_report.json`](task3_nl2sql_eval_report.json) | 任务三 NL2SQL 评测结果。 |

## 标准演示数据

[`standard_diabetes_demo/datamate_upload/`](standard_diabetes_demo/datamate_upload/) 中的四个文件：

```text
糖尿病医患问答脏文本.txt
糖尿病病例表格.csv
糖尿病知识图谱子集.json
糖尿病医疗记录.jsonl
```

这些文件故意包含可被算子识别的格式问题和噪声（URL、HTML、全角字符、繁体字、Emoji、导出提示、术语缩写等）。任务一清洗后应保持原始文件格式。

## 数据库构建

数据库属于数据产物，不进 Git。获取方式：
- 随 Release 资产包分发预构建 `.db` 文件
- 或通过 [`deploy/04_build_databases.sh`](../deploy/04_build_databases.sh) 从源数据构建

数据库详细结构见数据库表说明。

---

[← 返回项目首页](../README.md)

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
