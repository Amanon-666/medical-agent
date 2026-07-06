# 任务三 NL2SQL 指标说明

## 评估口径

- 评估对象：任务三自然语言统计查询引擎。
- 评估原因：该路径无模型随机性，可在相同数据库上稳定复现。
- 判定标准：模板命中正确、SQL 只读执行成功、必需列存在、返回行数满足样例要求。
- 说明：指标用于展示当前分析库上的只读统计查询能力。

## 输入

- 数据库：`D:\ccf-medical-ai-final-submission\data\task3_analytics.db`
- 评测集：`D:\ccf-medical-ai-final-submission\tests\task3_nl2sql_eval_set.json`
- 样例数：42

## 汇总指标

| 指标 | 数值 |
|---|---:|
| 综合准确率 | 100.00% |
| 模板命中率 | 100.00% |
| SQL 执行成功率 | 100.00% |
| 列匹配率 | 100.00% |
| 行数要求满足率 | 100.00% |
| 非空结果率 | 100.00% |
| 是否达到 85% | 是 |

## 逐项结果

| ID | 问题 | 期望模板 | 命中模板 | 行数 | 结论 |
|---|---|---|---|---:|---|
| stat_001 | 总共有多少种疾病？ | count_diseases | count_diseases | 1 | 通过 |
| stat_002 | 统计实体类型分布 | entity_type_counts | entity_type_counts | 12 | 通过 |
| stat_003 | 统计关系类型分布 | relation_counts | relation_counts | 30 | 通过 |
| stat_004 | 统计每个科室关联的疾病数量 | department_counts | department_counts | 30 | 通过 |
| stat_005 | 哪个科室的疾病数量最多？ | department_counts | department_counts | 30 | 通过 |
| stat_006 | 症状出现频率最高的有哪些？ | top_symptoms | top_symptoms | 30 | 通过 |
| stat_007 | 药物高频排行前几项是什么？ | top_drugs | top_drugs | 30 | 通过 |
| disease_001 | 百日咳有哪些症状？ | disease_symptoms | disease_symptoms | 27 | 通过 |
| disease_002 | 肺泡蛋白质沉积症有哪些症状？ | disease_symptoms | disease_symptoms | 4 | 通过 |
| disease_003 | 糖尿病有哪些症状？ | disease_symptoms | disease_symptoms | 40 | 通过 |
| disease_004 | 高血压有哪些临床表现？ | disease_symptoms | disease_symptoms | 40 | 通过 |
| disease_005 | 肺炎有什么表现？ | disease_symptoms | disease_symptoms | 40 | 通过 |
| test_001 | 肺泡蛋白质沉积症需要做哪些检查？ | disease_tests | disease_tests | 3 | 通过 |
| test_002 | 百日咳要做什么检查？ | disease_tests | disease_tests | 10 | 通过 |
| test_003 | 糖尿病需要做哪些检查？ | disease_tests | disease_tests | 40 | 通过 |
| test_004 | 高血压怎么检查？ | disease_tests | disease_tests | 40 | 通过 |
| cause_001 | 百日咳的病因是什么？ | disease_causes | disease_causes | 8 | 通过 |
| cause_002 | 肺泡蛋白质沉积症是什么原因？ | disease_causes | disease_causes | 1 | 通过 |
| cause_003 | 高血压为什么会发生？ | disease_causes | disease_causes | 10 | 通过 |
| prevent_001 | 百日咳怎么预防？ | disease_preventions | disease_preventions | 10 | 通过 |
| prevent_002 | 糖尿病如何预防？ | disease_preventions | disease_preventions | 10 | 通过 |
| prevent_003 | 高血压怎么防？ | disease_preventions | disease_preventions | 10 | 通过 |
| procedure_001 | 百日咳怎么治疗？ | disease_procedures | disease_procedures | 2 | 通过 |
| procedure_002 | 肺泡蛋白质沉积症怎么治疗？ | disease_procedures | disease_procedures | 1 | 通过 |
| procedure_003 | 糖尿病治疗方法有哪些？ | disease_procedures | disease_procedures | 17 | 通过 |
| population_001 | 百日咳哪些人容易得？ | disease_populations | disease_populations | 3 | 通过 |
| population_002 | 糖尿病易感人群有哪些？ | disease_populations | disease_populations | 13 | 通过 |
| population_003 | 肺炎好发人群有哪些？ | disease_populations | disease_populations | 30 | 通过 |
| drug_001 | 百日咳用什么药？ | disease_drugs | disease_drugs | 38 | 通过 |
| drug_002 | 糖尿病有哪些药？ | disease_drugs | disease_drugs | 50 | 通过 |
| drug_003 | 高血压药物治疗有哪些？ | disease_drugs | disease_drugs | 50 | 通过 |
| drug_004 | 肺炎治疗药物有哪些？ | disease_drugs | disease_drugs | 50 | 通过 |
| comp_001 | 百日咳有哪些并发症？ | disease_complications | disease_complications | 8 | 通过 |
| comp_002 | 糖尿病常见并发症有哪些？ | disease_complications | disease_complications | 40 | 通过 |
| comp_003 | 高血压有什么并发症？ | disease_complications | disease_complications | 40 | 通过 |
| dept_001 | 百日咳挂什么科？ | disease_departments | disease_departments | 2 | 通过 |
| dept_002 | 肺泡蛋白质沉积症看哪个科？ | disease_departments | disease_departments | 2 | 通过 |
| dept_003 | 糖尿病属于哪个科？ | disease_departments | disease_departments | 15 | 通过 |
| reverse_001 | 哪些疾病有恶心症状？ | symptom_to_diseases | symptom_to_diseases | 50 | 通过 |
| reverse_002 | 阿司匹林可以治疗哪些疾病？ | drug_to_diseases | drug_to_diseases | 50 | 通过 |
| reverse_003 | 胸部CT检查可以查出哪些疾病？ | test_to_diseases | test_to_diseases | 50 | 通过 |
| reverse_004 | 内科有哪些疾病？ | department_to_diseases | department_to_diseases | 80 | 通过 |
