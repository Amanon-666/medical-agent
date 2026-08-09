# MediFlow Task 3 NL2SQL Benchmark 概要

- **总题数**: 133 题
- **dev**: 40 题（开发调试用，可查看结果改进系统）
- **test**: 93 题（冻结测试集，最终评测用，不应根据结果调参）
- **数据库**: task3_analytics.db（15 张表、5 个视图；结构快照由构建脚本生成）
- **构建时间**: 2026-08-09
- **构建原则**: 先写 Gold SQL → 数据库真实执行验证 → 再配自然语言问题

## 题型分布

| 题型 | 总计 | dev | test | 说明 |
|---|---|---|---|---|
| 单表筛选 | 25 | 8 | 17 | 疾病查症状/药物/科室/检查 |
| 聚合统计 | 24 | 7 | 17 | COUNT/AVG/MAX/MIN/SUM |
| 分组统计 | 20 | 6 | 14 | GROUP BY + 排序 |
| Top-K排序 | 17 | 5 | 12 | ORDER BY + LIMIT |
| 多条件查询 | 19 | 6 | 13 | HAVING/多条件 WHERE/子查询 |
| 多表联查 | 13 | 4 | 9 | JOIN/多表关联/三表联查 |
| 复杂综合 | 15 | 4 | 11 | WITH子句/交集分析/比例计算/多跳关联 |

## 难度分布

| 难度 | 总计 | dev | test |
|---|---|---|---|
| easy | 54 | 17 | 37 |
| medium | 52 | 18 | 34 |
| hard | 27 | 5 | 22 |

## 涉及表分布

- disease_symptoms: 51 题
- disease_drugs: 40 题
- disease_departments: 20 题
- disease_tests: 17 题
- diseases: 10 题
- disease_facts: 6 题
- disease_complications: 4 题
- disease_preventions: 3 题
- disease_causes: 2 题
- disease_procedures: 2 题
- 统计视图（v_*）: 3 题

## 高级 SQL 特性覆盖

- JOIN 查询: 27 题（含自连接和三表 JOIN）
- 聚合函数: 87 题
- WITH 子句 (CTE): 2 题
- 子查询: 8 题
- HAVING 子句: 6 题
- CASE WHEN: 2 题
- 交集分析: 3 题
- 比例计算: 3 题

## 评测指标

- **主指标**: Execution Accuracy（执行结果与 Gold Result 完全一致的题目比例）
- **计算方式**: 预测 SQL 执行结果 == Gold Result → 正确；否则 → 错误
- **目标**: ≥ 85%
- **注意**: 模板命中查询和自由 NL2SQL 分开统计，不混合计算

## 文件清单

| 文件 | 说明 |
|---|---|
| `nl2sql_dev.jsonl` | 40 道开发题（可查看、可调参） |
| `nl2sql_test.jsonl` | 93 道冻结测试题（最终评测，冻结后不修改） |
| `schema_snapshot.json` | 数据库结构快照（构建时的表结构记录） |
| `benchmark_summary.md` | 本文件 |
| `task3_ppt_copy.md` | PPT 展示文案 |
| `build_nl2sql_benchmark.py` | 构建脚本（可重现） |

## 2026-08-09 实测结果

| 阶段 | 正确/总数 | 执行准确率 | 说明 |
|---|---:|---:|---|
| 开发集基线 | 25/40 | 62.5% | 优化前运行态基线 |
| 开发集优化后 | 38/40 | 95.0% | 通用语义模板与模型兜底 |
| 测试集首次冻结运行 | 57/93 | 61.3% | 查看失败题型前的首次运行 |
| 测试集迭代后回归 | 89/93 | 95.7% | 已使用失败题型信息，不属于盲测 |

中文结果表、CSV 和图表由 `generate_benchmark_report.py` 生成，复现说明见本目录 `README.md`。
