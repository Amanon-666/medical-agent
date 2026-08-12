# 数据资产说明

`data/` 保存在线服务和离线复现使用的本地数据文件。数据库属于独立数据资产，不进入 Git 历史。正式提交包的数据位置、用途、版本边界和 SHA-256 清单见 [`docs/数据资产包说明.md`](../docs/数据资产包说明.md)。数据库位于独立的 `MediFlow-数据包.zip`，不随代码主包重复分发。

## 目录内容

| 路径 | 作用 |
| --- | --- |
| [`standard_diabetes_demo/datamate_upload/`](standard_diabetes_demo/datamate_upload/) | 糖尿病混合格式演示数据，覆盖 `txt/csv/json/jsonl`。 |
| `task2_medical_kg.db` | 任务二知识图谱库（不进 Git，通过 Release 或脚本构建）。 |
| `task3_analytics.db` | 任务三分析库（不进 Git，通过 Release 或脚本构建）。 |

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
- 解压独立数据包中的 `release-data/` 目录；
- 按 [`docs/数据资产包说明.md`](../docs/数据资产包说明.md) 将运行库复制到项目默认路径；
- 或通过 [`deploy/04_build_databases.sh`](../deploy/04_build_databases.sh) 从源数据构建。

数据库详细结构见数据库表说明。

## 数据库关系

```text
任务一清洗结果
  -> 任务二抽取和入库
  -> task2_medical_kg.db
  -> 任务三统计和 NL2SQL 表
  -> task3_analytics.db
```

`task2_medical_kg.db` 和 `task3_analytics.db` 是数据产物，建议随正式提交包单独分发。数据分析服务的运行态数据库和基准评测数据库必须按 [`docs/数据资产包说明.md`](../docs/数据资产包说明.md) 区分使用。

## 验证入口

- 在线可视化平台：`https://demo.mashiro.xin/`
- 数据处理平台：`https://datamate.mashiro.xin/`
- 智能体平台：`https://nexent.mashiro.xin/`

---

[← 返回项目首页](../README.md)
