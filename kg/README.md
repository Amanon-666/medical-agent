# 知识图谱与分析库构建

`kg/` 保存离线构建脚本，用于把医学知识数据整理为任务二知识图谱库，并派生出任务三使用的统计分析库。在线演示环境已经生成好数据库；本目录主要服务于新环境复现、数据更新和离线审计。

## 文件索引

| 文件 | 职责 | 输出 |
| --- | --- | --- |
| [`build_kg.py`](build_kg.py) | 基础知识图谱构建入口。 | `data/task2_medical_kg.db` |
| [`build_kg_v2.py`](build_kg_v2.py) | **当前主构建入口**，保留来源、格式、记录编号和质量标记。 | `data/task2_medical_kg.db` |
| [`build_analytics_v2.py`](build_analytics_v2.py) | 从知识图谱库生成疾病统计、关系统计、NL2SQL 表。 | `data/task3_analytics.db` |
| [`build_sql_db.py`](build_sql_db.py) | 构建任务三 NL2SQL 查询所需的结构化表。 | `data/task3_analytics.db` |

## 数据流

```text
公开医学知识数据 / 任务一清洗结果
  → 实体与关系归一化
  → 知识图谱库 task2_medical_kg.db
  → 疾病统计、关系统计、NL2SQL 表
  → 分析库 task3_analytics.db
  → MCP 工具与可视化平台读取
```

任务二在线流水线也会写入同一类表结构。离线脚本和在线工具使用相同的数据模型。

## 验证方式

1. 运行 [`deploy/04_build_databases.sh`](../deploy/04_build_databases.sh) 生成或刷新两个数据库。
2. 运行 [`deploy/08_verify.sh`](../deploy/08_verify.sh) 检查数据库文件和服务状态。
3. 数据库详细结构见 [`data/README.md`](../data/README.md)。

---

[← 返回项目首页](../README.md)
