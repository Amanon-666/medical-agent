"""
MediFlow 任务三 NL2SQL Benchmark 构建脚本
==========================================
基于 task3_analytics.db 真实 schema 和数据，构建 133 道 NL2SQL 测试题。

构建原则：
1. 先写 Gold SQL → 在数据库上真实执行 → 再写自然语言问题
2. 所有题目严格限制在数据库能真实回答的范围内
3. 不查看当前系统预测结果来选题（避免数据泄漏）
"""

import sqlite3
import json
import random
from pathlib import Path

# 固定随机种子，保证可复现
random.seed(20260809)

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "task3_analytics.db"
DB_RELATIVE_PATH = Path("data") / "task3_analytics.db"
OUT_DIR = ROOT / "evaluation" / "task3"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 第一步：读取 schema 和采样数据
# ============================================================

def explore_db():
    """读取数据库结构并采样真实数据"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row

    info = {}

    # 所有用户表
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' AND name NOT LIKE '\\_%' ESCAPE '\\'"
    ).fetchall()]

    for t in tables:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info('{t}')").fetchall()]
        count = db.execute(f"SELECT COUNT(*) FROM '{t}'").fetchone()[0]
        # 采样前5条
        try:
            samples = [dict(r) for r in db.execute(f"SELECT * FROM '{t}' LIMIT 5").fetchall()]
        except:
            samples = []
        info[t] = {"columns": cols, "row_count": count, "samples": samples}

    # 视图定义
    views = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='view'"
    ).fetchall()]
    for v in views:
        try:
            count = db.execute(f"SELECT COUNT(*) FROM '{v}'").fetchone()[0]
            samples = [dict(r) for r in db.execute(f"SELECT * FROM '{v}' LIMIT 3").fetchall()]
        except:
            count = 0
            samples = []
        info[v] = {"columns": [], "row_count": count, "samples": samples, "is_view": True}

    # 查询一些有价值的统计数据
    stats = {}
    # 常见疾病名
    stats["top_diseases"] = [r[0] for r in db.execute(
        "SELECT name FROM diseases ORDER BY source_count DESC LIMIT 30"
    ).fetchall()]
    # 常见症状
    stats["top_symptoms"] = [r[0] for r in db.execute(
        "SELECT symptom, COUNT(DISTINCT disease) as cnt FROM disease_symptoms "
        "GROUP BY symptom ORDER BY cnt DESC LIMIT 30"
    ).fetchall()]
    # 常见药物
    stats["top_drugs"] = [r[0] for r in db.execute(
        "SELECT drug, COUNT(DISTINCT disease) as cnt FROM disease_drugs "
        "GROUP BY drug ORDER BY cnt DESC LIMIT 20"
    ).fetchall()]
    # 科室列表
    stats["departments"] = [r[0] for r in db.execute(
        "SELECT DISTINCT department FROM disease_departments LIMIT 20"
    ).fetchall()]
    # 检查项目
    stats["top_tests"] = [r[0] for r in db.execute(
        "SELECT test, COUNT(DISTINCT disease) as cnt FROM disease_tests "
        "GROUP BY test ORDER BY cnt DESC LIMIT 20"
    ).fetchall()]
    # 事实类型
    stats["fact_types"] = [r[0] for r in db.execute(
        "SELECT DISTINCT fact_type FROM disease_facts LIMIT 20"
    ).fetchall()]

    # 实体统计
    stats["entity_stats"] = [dict(r) for r in db.execute("SELECT * FROM entity_stats").fetchall()]
    # 关系统计
    stats["relation_stats"] = [dict(r) for r in db.execute("SELECT * FROM relation_stats").fetchall()]

    db.close()
    return info, stats


# ============================================================
# 第二步：定义题目模板并生成
# ============================================================

class BenchmarkBuilder:
    def __init__(self, info, stats):
        self.info = info
        self.stats = stats
        self.cases = []
        self.case_id = 0
        # 用于检查的数据库连接
        self.db = sqlite3.connect(str(DB_PATH))

    def add_case(self, question, gold_sql, difficulty, query_type, tables, notes=""):
        """添加一个测试用例，先执行 gold_sql 验证"""
        self.case_id += 1

        # 执行 gold_sql 并获取结果
        try:
            cursor = self.db.execute(gold_sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            # 把结果转为可序列化的格式
            gold_result = {
                "columns": columns,
                "rows": [list(r) for r in rows],
                "row_count": len(rows)
            }
            executable = True
            error = None
        except Exception as e:
            gold_result = {"columns": [], "rows": [], "row_count": 0}
            executable = False
            error = str(e)

        case = {
            "id": f"nl2sql_{self.case_id:04d}",
            "question": question,
            "difficulty": difficulty,
            "query_type": query_type,
            "gold_sql": gold_sql,
            "gold_result": gold_result,
            "tables": tables,
            "executable": executable,
            "error": error,
            "notes": notes
        }
        self.cases.append(case)
        return executable

    def finish(self):
        self.db.close()

    def build_all(self):
        """构建全部题目"""
        self._build_filter_queries()       # 单表筛选: 25
        self._build_aggregation_queries()  # COUNT/聚合: 25
        self._build_groupby_queries()      # GROUP BY: 25
        self._build_topk_queries()         # ORDER BY / Top-K: 20
        self._build_join_queries()         # JOIN: 25
        self._build_multicond_queries()    # 多条件: 20
        self._build_complex_queries()      # 复杂综合: 20

        # 去重
        self._deduplicate()

        # 删除不可执行的
        bad = [c for c in self.cases if not c["executable"]]
        if bad:
            print(f"  删除 {len(bad)} 条不可执行题目:")
            for b in bad:
                print(f"    {b['id']}: {b['error']}")
        self.cases = [c for c in self.cases if c["executable"]]

        print(f"\n  共生成 {len(self.cases)} 道有效题目")

    # ---- 单表筛选 25 题 ----
    def _build_filter_queries(self):
        diseases = self.stats["top_diseases"]

        # 疾病-症状查询
        for i, disease in enumerate(diseases[:8]):
            self.add_case(
                question=f"{disease}有哪些常见症状？",
                gold_sql=f"SELECT symptom, confidence FROM disease_symptoms WHERE disease LIKE '%{disease}%' ORDER BY confidence DESC LIMIT 20",
                difficulty="easy", query_type="单表筛选",
                tables=["disease_symptoms"]
            )

        # 疾病-药物查询
        for disease in diseases[8:16]:
            self.add_case(
                question=f"治疗{disease}的常用药物有哪些？",
                gold_sql=f"SELECT drug, confidence FROM disease_drugs WHERE disease LIKE '%{disease}%' ORDER BY confidence DESC LIMIT 20",
                difficulty="easy", query_type="单表筛选",
                tables=["disease_drugs"]
            )

        # 疾病-科室查询
        for disease in diseases[16:22]:
            self.add_case(
                question=f"{disease}应该去哪个科室就诊？",
                gold_sql=f"SELECT DISTINCT department FROM disease_departments WHERE disease LIKE '%{disease}%'",
                difficulty="easy", query_type="单表筛选",
                tables=["disease_departments"]
            )

        # 疾病-检查查询
        for disease in diseases[22:25]:
            self.add_case(
                question=f"诊断{disease}需要做哪些检查？",
                gold_sql=f"SELECT test, confidence FROM disease_tests WHERE disease LIKE '%{disease}%' ORDER BY confidence DESC LIMIT 20",
                difficulty="easy", query_type="单表筛选",
                tables=["disease_tests"]
            )

    # ---- COUNT/聚合 25 题 ----
    def _build_aggregation_queries(self):
        # 总计数
        self.add_case(
            question="知识库中一共收录了多少种疾病？",
            gold_sql="SELECT COUNT(*) AS total_diseases FROM diseases",
            difficulty="easy", query_type="聚合统计",
            tables=["diseases"]
        )
        self.add_case(
            question="数据库中一共有多少条疾病事实记录？",
            gold_sql="SELECT COUNT(*) AS total_facts FROM disease_facts",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_facts"]
        )
        self.add_case(
            question="知识图谱中包含多少种症状信息？",
            gold_sql="SELECT COUNT(DISTINCT symptom) AS unique_symptoms FROM disease_symptoms",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="数据库中收录了多少种药物？",
            gold_sql="SELECT COUNT(DISTINCT drug) AS unique_drugs FROM disease_drugs",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="共有多少个不同的科室？",
            gold_sql="SELECT COUNT(DISTINCT department) AS unique_departments FROM disease_departments",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_departments"]
        )
        self.add_case(
            question="共有多少种不同的检查项目？",
            gold_sql="SELECT COUNT(DISTINCT test) AS unique_tests FROM disease_tests",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_tests"]
        )

        # 特定疾病关联计数
        diseases = self.stats["top_diseases"][:6]
        for disease in diseases:
            self.add_case(
                question=f"与{disease}相关的症状一共有多少种？",
                gold_sql=f"SELECT COUNT(*) AS symptom_count FROM disease_symptoms WHERE disease LIKE '%{disease}%'",
                difficulty="easy", query_type="聚合统计",
                tables=["disease_symptoms"]
            )

        for disease in diseases[3:]:
            self.add_case(
                question=f"治疗{disease}的药物共有多少种？",
                gold_sql=f"SELECT COUNT(*) AS drug_count FROM disease_drugs WHERE disease LIKE '%{disease}%'",
                difficulty="easy", query_type="聚合统计",
                tables=["disease_drugs"]
            )

        # 置信度相关聚合
        self.add_case(
            question="药物-疾病关联的平均置信度是多少？",
            gold_sql="SELECT ROUND(AVG(confidence), 4) AS avg_confidence FROM disease_drugs",
            difficulty="medium", query_type="聚合统计",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="症状-疾病关联的平均置信度是多少？",
            gold_sql="SELECT ROUND(AVG(confidence), 4) AS avg_confidence FROM disease_symptoms",
            difficulty="medium", query_type="聚合统计",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="检查-疾病关联的最高置信度是多少？",
            gold_sql="SELECT MAX(confidence) AS max_confidence FROM disease_tests",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_tests"]
        )
        self.add_case(
            question="疾病-科室关联的最低置信度是多少？",
            gold_sql="SELECT MIN(confidence) AS min_confidence FROM disease_departments",
            difficulty="easy", query_type="聚合统计",
            tables=["disease_departments"]
        )

        # 有描述的疾病数
        self.add_case(
            question="有多少种疾病带有文字描述？",
            gold_sql="SELECT COUNT(*) AS diseases_with_description FROM diseases WHERE description IS NOT NULL AND description != ''",
            difficulty="medium", query_type="聚合统计",
            tables=["diseases"]
        )
        self.add_case(
            question="有多少种疾病没有描述信息？",
            gold_sql="SELECT COUNT(*) AS diseases_without_description FROM diseases WHERE description IS NULL OR description = ''",
            difficulty="medium", query_type="聚合统计",
            tables=["diseases"]
        )

        # 多来源疾病
        self.add_case(
            question="有多少种疾病同时被多个来源收录？",
            gold_sql="SELECT COUNT(*) AS multi_source_diseases FROM diseases WHERE source_count > 1",
            difficulty="easy", query_type="聚合统计",
            tables=["diseases"]
        )

        # Entity stats 相关
        self.add_case(
            question="知识图谱中总共包含多少个实体？",
            gold_sql="SELECT SUM(entity_count) AS total_entities FROM entity_stats",
            difficulty="easy", query_type="聚合统计",
            tables=["entity_stats"]
        )
        self.add_case(
            question="知识图谱中共有多少个三元组关系？",
            gold_sql="SELECT SUM(triple_count) AS total_triples FROM relation_stats",
            difficulty="easy", query_type="聚合统计",
            tables=["relation_stats"]
        )

    # ---- GROUP BY 25 题 ----
    def _build_groupby_queries(self):
        # 实体类型分布
        self.add_case(
            question="知识图谱中各类实体的数量分布是怎样的？",
            gold_sql="SELECT entity_type, entity_count FROM entity_stats ORDER BY entity_count DESC",
            difficulty="easy", query_type="分组统计",
            tables=["entity_stats"]
        )

        # 关系类型分布
        self.add_case(
            question="知识图谱中各种关系类型的数量分布如何？",
            gold_sql="SELECT display_name, triple_count FROM relation_stats ORDER BY triple_count DESC",
            difficulty="easy", query_type="分组统计",
            tables=["relation_stats"]
        )

        # 科室-疾病数
        self.add_case(
            question="每个科室分别关联了多少种疾病？按数量从高到低排序。",
            gold_sql="SELECT department, COUNT(DISTINCT disease) AS disease_count FROM disease_departments GROUP BY department ORDER BY disease_count DESC LIMIT 30",
            difficulty="medium", query_type="分组统计",
            tables=["disease_departments"]
        )

        # 事实类型分布
        self.add_case(
            question="各种事实类型（症状、药物、检查等）分别有多少条记录？",
            gold_sql="SELECT fact_type, COUNT(*) AS record_count FROM disease_facts GROUP BY fact_type ORDER BY record_count DESC",
            difficulty="medium", query_type="分组统计",
            tables=["disease_facts"]
        )

        # 按症状分组
        self.add_case(
            question="哪些症状关联的疾病种类最多？列出前20种。",
            gold_sql="SELECT symptom, COUNT(DISTINCT disease) AS disease_count FROM disease_symptoms GROUP BY symptom ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_symptoms"]
        )

        # 按药物分组
        self.add_case(
            question="哪些药物关联的疾病种类最多？列出前20种。",
            gold_sql="SELECT drug, COUNT(DISTINCT disease) AS disease_count FROM disease_drugs GROUP BY drug ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_drugs"]
        )

        # 按来源分组
        self.add_case(
            question="各数据来源分别贡献了多少条疾病事实？",
            gold_sql="SELECT source_name, COUNT(*) AS fact_count FROM disease_facts GROUP BY source_name ORDER BY fact_count DESC",
            difficulty="medium", query_type="分组统计",
            tables=["disease_facts"]
        )
        self.add_case(
            question="各来源分别贡献了多少条症状记录？",
            gold_sql="SELECT source_name, COUNT(*) AS symptom_count FROM disease_symptoms GROUP BY source_name ORDER BY symptom_count DESC",
            difficulty="medium", query_type="分组统计",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="各来源分别收录了多少种药物关联？",
            gold_sql="SELECT source_name, COUNT(*) AS drug_count FROM disease_drugs GROUP BY source_name ORDER BY drug_count DESC",
            difficulty="medium", query_type="分组统计",
            tables=["disease_drugs"]
        )

        # 按人群分组
        self.add_case(
            question="各种易感人群分别关联了多少种疾病？",
            gold_sql="SELECT population, COUNT(DISTINCT disease) AS disease_count FROM disease_populations GROUP BY population ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_populations"]
        )

        # 按并发症分组
        self.add_case(
            question="哪些并发症涉及的疾病种类最多？列出前20种。",
            gold_sql="SELECT complication, COUNT(DISTINCT disease) AS disease_count FROM disease_complications GROUP BY complication ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_complications"]
        )

        # 预防措施分组
        self.add_case(
            question="各种预防措施分别关联了多少种疾病？",
            gold_sql="SELECT prevention, COUNT(DISTINCT disease) AS disease_count FROM disease_preventions GROUP BY prevention ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_preventions"]
        )

        # 病因分组
        self.add_case(
            question="各种病因类型分别涉及多少种疾病？",
            gold_sql="SELECT cause, COUNT(DISTINCT disease) AS disease_count FROM disease_causes GROUP BY cause ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_causes"]
        )

        # 检查项目分组
        self.add_case(
            question="哪些检查项目涉及的疾病种类最多？列出前20种。",
            gold_sql="SELECT test, COUNT(DISTINCT disease) AS disease_count FROM disease_tests GROUP BY test ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_tests"]
        )

        # 治疗操作分组
        self.add_case(
            question="哪些治疗操作/手术涉及疾病种类最多？",
            gold_sql="SELECT procedure, COUNT(DISTINCT disease) AS disease_count FROM disease_procedures GROUP BY procedure ORDER BY disease_count DESC LIMIT 20",
            difficulty="medium", query_type="分组统计",
            tables=["disease_procedures"]
        )

        # 高/低置信度分组
        self.add_case(
            question="按置信度区间统计疾病-药物关联的数量分布（高≥0.8, 中0.5-0.8, 低<0.5）？",
            gold_sql="SELECT CASE WHEN confidence >= 0.8 THEN '高置信度' WHEN confidence >= 0.5 THEN '中置信度' ELSE '低置信度' END AS confidence_level, COUNT(*) AS count FROM disease_drugs GROUP BY confidence_level ORDER BY count DESC",
            difficulty="hard", query_type="分组统计",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="按置信度区间统计疾病-症状关联的数量分布（高≥0.8, 中0.5-0.8, 低<0.5）？",
            gold_sql="SELECT CASE WHEN confidence >= 0.8 THEN '高置信度' WHEN confidence >= 0.5 THEN '中置信度' ELSE '低置信度' END AS confidence_level, COUNT(*) AS count FROM disease_symptoms GROUP BY confidence_level ORDER BY count DESC",
            difficulty="hard", query_type="分组统计",
            tables=["disease_symptoms"]
        )

        # 疾病多来源分组
        self.add_case(
            question="按来源数量分组统计疾病：单来源 vs 多来源各有多少种？",
            gold_sql="SELECT CASE WHEN source_count = 1 THEN '单来源' ELSE '多来源' END AS source_type, COUNT(*) AS disease_count FROM diseases GROUP BY source_type",
            difficulty="medium", query_type="分组统计",
            tables=["diseases"]
        )

        # 高关联疾病
        self.add_case(
            question="哪些疾病关联的事实记录最多？列出前15种。",
            gold_sql="SELECT disease, COUNT(*) AS fact_count FROM disease_facts GROUP BY disease ORDER BY fact_count DESC LIMIT 15",
            difficulty="medium", query_type="分组统计",
            tables=["disease_facts"]
        )

        # 症状-药物的来源分析
        self.add_case(
            question="各来源的症状数据量是多少？",
            gold_sql="SELECT source_name, COUNT(*) AS count FROM disease_symptoms GROUP BY source_name ORDER BY count DESC",
            difficulty="medium", query_type="分组统计",
            tables=["disease_symptoms"]
        )

    # ---- Top-K 20 题 ----
    def _build_topk_queries(self):
        self.add_case(
            question="关联疾病数量最多的前10种症状是什么？",
            gold_sql="SELECT symptom, COUNT(DISTINCT disease) AS disease_count FROM disease_symptoms GROUP BY symptom ORDER BY disease_count DESC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="关联疾病种类最多的前10种药物是什么？",
            gold_sql="SELECT drug, COUNT(DISTINCT disease) AS disease_count FROM disease_drugs GROUP BY drug ORDER BY disease_count DESC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="涉及疾病种类最多的前5个科室是哪些？",
            gold_sql="SELECT department, COUNT(DISTINCT disease) AS disease_count FROM disease_departments GROUP BY department ORDER BY disease_count DESC LIMIT 5",
            difficulty="easy", query_type="Top-K排序",
            tables=["disease_departments"]
        )
        self.add_case(
            question="疾病数量最少的是哪5个科室？",
            gold_sql="SELECT department, COUNT(DISTINCT disease) AS disease_count FROM disease_departments GROUP BY department ORDER BY disease_count ASC LIMIT 5",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_departments"]
        )
        self.add_case(
            question="哪些检查项目关联疾病数排名前10？",
            gold_sql="SELECT test, COUNT(DISTINCT disease) AS disease_count FROM disease_tests GROUP BY test ORDER BY disease_count DESC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_tests"]
        )
        self.add_case(
            question="哪些并发症影响范围最广？列出关联疾病数前8的并发症。",
            gold_sql="SELECT complication, COUNT(DISTINCT disease) AS disease_count FROM disease_complications GROUP BY complication ORDER BY disease_count DESC LIMIT 8",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_complications"]
        )
        self.add_case(
            question="哪些病因影响疾病种类最多？列出前8种。",
            gold_sql="SELECT cause, COUNT(DISTINCT disease) AS disease_count FROM disease_causes GROUP BY cause ORDER BY disease_count DESC LIMIT 8",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_causes"]
        )
        self.add_case(
            question="含最多事实记录的疾病是哪10种？",
            gold_sql="SELECT disease, COUNT(*) AS fact_count FROM disease_facts GROUP BY disease ORDER BY fact_count DESC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_facts"]
        )
        self.add_case(
            question="来源引用最多的前5种疾病是什么？",
            gold_sql="SELECT name, source_count FROM diseases ORDER BY source_count DESC LIMIT 5",
            difficulty="easy", query_type="Top-K排序",
            tables=["diseases"]
        )
        self.add_case(
            question="取置信度最高的前10条症状-疾病关联记录。",
            gold_sql="SELECT disease, symptom, confidence FROM disease_symptoms ORDER BY confidence DESC LIMIT 10",
            difficulty="easy", query_type="Top-K排序",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="置信度最高的前10种药物-疾病关联是哪些？",
            gold_sql="SELECT disease, drug, confidence FROM disease_drugs ORDER BY confidence DESC LIMIT 10",
            difficulty="easy", query_type="Top-K排序",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="关联疾病排行倒数前10的症状有哪些？",
            gold_sql="SELECT symptom, COUNT(DISTINCT disease) AS disease_count FROM disease_symptoms GROUP BY symptom ORDER BY disease_count ASC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_symptoms"]
        )

        # 使用视图的 Top-K
        self.add_case(
            question="前20种最常见的症状是什么？",
            gold_sql="SELECT * FROM v_top_symptoms LIMIT 20",
            difficulty="easy", query_type="Top-K排序",
            tables=["v_top_symptoms"]
        )
        self.add_case(
            question="各科室疾病数量排名（用视图）？",
            gold_sql="SELECT * FROM v_department_disease_counts ORDER BY disease_count DESC",
            difficulty="easy", query_type="Top-K排序",
            tables=["v_department_disease_counts"]
        )
        self.add_case(
            question="关联疾病最多的前15种药物排名（用视图）？",
            gold_sql="SELECT * FROM v_drug_disease_counts LIMIT 15",
            difficulty="easy", query_type="Top-K排序",
            tables=["v_drug_disease_counts"]
        )

        # 更多 Top-K 变体
        self.add_case(
            question="哪些治疗操作最常用？按涉及疾病数排序取前10。",
            gold_sql="SELECT procedure, COUNT(DISTINCT disease) AS disease_count FROM disease_procedures GROUP BY procedure ORDER BY disease_count DESC LIMIT 10",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_procedures"]
        )
        self.add_case(
            question="哪些预防措施涉及疾病最多？取前8。",
            gold_sql="SELECT prevention, COUNT(DISTINCT disease) AS disease_count FROM disease_preventions GROUP BY prevention ORDER BY disease_count DESC LIMIT 8",
            difficulty="medium", query_type="Top-K排序",
            tables=["disease_preventions"]
        )

    # ---- JOIN 多表联查 25 题 ----
    def _build_join_queries(self):
        # 疾病同时跨表查询
        self.add_case(
            question="哪些疾病既关联了症状又关联了药物？列出疾病名称及其症状数和药物数。",
            gold_sql="SELECT s.disease, COUNT(DISTINCT s.symptom) AS symptom_count, COUNT(DISTINCT d.drug) AS drug_count FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease GROUP BY s.disease ORDER BY (symptom_count + drug_count) DESC LIMIT 20",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_drugs"]
        )
        self.add_case(
            question="哪些疾病同时有症状记录和检查记录？",
            gold_sql="SELECT DISTINCT s.disease FROM disease_symptoms s INNER JOIN disease_tests t ON s.disease = t.disease LIMIT 30",
            difficulty="medium", query_type="多表联查",
            tables=["disease_symptoms", "disease_tests"]
        )
        self.add_case(
            question="找出同时出现在 disease_symptoms 和 disease_departments 中的疾病名称。",
            gold_sql="SELECT DISTINCT s.disease FROM disease_symptoms s INNER JOIN disease_departments d ON s.disease = d.disease LIMIT 30",
            difficulty="medium", query_type="多表联查",
            tables=["disease_symptoms", "disease_departments"]
        )
        self.add_case(
            question="哪些疾病同时有关联科室和关联检查记录？取前20条。",
            gold_sql="SELECT DISTINCT d.disease FROM disease_departments d INNER JOIN disease_tests t ON d.disease = t.disease LIMIT 20",
            difficulty="medium", query_type="多表联查",
            tables=["disease_departments", "disease_tests"]
        )

        # Join + Group by
        self.add_case(
            question="同时有症状和药物记录的疾病中，哪些疾病的事实总数最多？",
            gold_sql="SELECT s.disease, (COUNT(DISTINCT s.symptom) + COUNT(DISTINCT d.drug)) AS total_facts FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease GROUP BY s.disease ORDER BY total_facts DESC LIMIT 15",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_drugs"]
        )

        # 多对多关系：症状-药物通过疾病关联
        self.add_case(
            question="哪些症状和药物经常同时出现在同一种疾病中？统计共同出现的疾病数。",
            gold_sql="SELECT s.symptom, d.drug, COUNT(DISTINCT s.disease) AS shared_diseases FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease GROUP BY s.symptom, d.drug ORDER BY shared_diseases DESC LIMIT 15",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_drugs"]
        )

        # 科室-药物关联（通过疾病）
        self.add_case(
            question="每个科室关联的疾病平均使用多少种药物？",
            gold_sql="SELECT dep.department, ROUND(AVG(drug_counts.cnt), 1) AS avg_drug_count FROM disease_departments dep JOIN (SELECT disease, COUNT(DISTINCT drug) AS cnt FROM disease_drugs GROUP BY disease) drug_counts ON dep.disease = drug_counts.disease GROUP BY dep.department ORDER BY avg_drug_count DESC LIMIT 15",
            difficulty="hard", query_type="多表联查",
            tables=["disease_departments", "disease_drugs"]
        )

        # Join + filter
        self.add_case(
            question="列出既关联症状'发热'又关联药物'头孢'的疾病。",
            gold_sql="SELECT DISTINCT s.disease FROM disease_symptoms s INNER JOIN disease_drugs d ON s.disease = d.disease WHERE s.symptom LIKE '%发热%' AND d.drug LIKE '%头孢%'",
            difficulty="medium", query_type="多表联查",
            tables=["disease_symptoms", "disease_drugs"],
            notes="需要发热和头孢都实际存在于数据库中"
        )

        # 检查-药物关联
        self.add_case(
            question="哪些疾病既需要做血液检查又需要用药治疗？列出疾病和对应的检查及药物。",
            gold_sql="SELECT t.disease, t.test, d.drug FROM disease_tests t JOIN disease_drugs d ON t.disease = d.disease WHERE t.test LIKE '%血%' LIMIT 30",
            difficulty="hard", query_type="多表联查",
            tables=["disease_tests", "disease_drugs"]
        )

        # 症状-科室关联
        self.add_case(
            question="哪些症状在内科相关的疾病中最常见？",
            gold_sql="SELECT s.symptom, COUNT(DISTINCT s.disease) AS disease_count FROM disease_symptoms s JOIN disease_departments d ON s.disease = d.disease WHERE d.department LIKE '%内科%' GROUP BY s.symptom ORDER BY disease_count DESC LIMIT 15",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_departments"]
        )

        # 三表 JOIN
        self.add_case(
            question="哪些疾病同时有关联症状、药物和检查记录？列出疾病名及各类型记录数。",
            gold_sql="SELECT s.disease, COUNT(DISTINCT s.symptom) AS symptom_count, COUNT(DISTINCT d.drug) AS drug_count, COUNT(DISTINCT t.test) AS test_count FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease JOIN disease_tests t ON s.disease = t.disease GROUP BY s.disease ORDER BY (symptom_count + drug_count + test_count) DESC LIMIT 15",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_drugs", "disease_tests"]
        )

        # 疾病-并发症-药物
        self.add_case(
            question="哪些疾病既有并发症记录又有药物记录？",
            gold_sql="SELECT DISTINCT c.disease FROM disease_complications c INNER JOIN disease_drugs d ON c.disease = d.disease LIMIT 20",
            difficulty="medium", query_type="多表联查",
            tables=["disease_complications", "disease_drugs"]
        )

        # 多来源关联疾病
        self.add_case(
            question="多来源收录的疾病中，哪些同时有症状和检查记录？",
            gold_sql="SELECT DISTINCT s.disease FROM disease_symptoms s INNER JOIN disease_tests t ON s.disease = t.disease INNER JOIN diseases d ON s.disease = d.name WHERE d.source_count > 1 LIMIT 20",
            difficulty="hard", query_type="多表联查",
            tables=["disease_symptoms", "disease_tests", "diseases"]
        )

        # 事实表 + 实体统计
        self.add_case(
            question="事实数量最多的疾病与实体统计表中的疾病数量是否匹配？列出事实最多的10种疾病。",
            gold_sql="SELECT disease, COUNT(*) AS fact_count FROM disease_facts GROUP BY disease ORDER BY fact_count DESC LIMIT 10",
            difficulty="easy", query_type="多表联查",
            tables=["disease_facts"]
        )

    # ---- 多条件查询 20 题 ----
    def _build_multicond_queries(self):
        self.add_case(
            question="找出置信度高于0.9且关联疾病数大于5的症状。",
            gold_sql="SELECT symptom, COUNT(DISTINCT disease) AS disease_count, AVG(confidence) AS avg_conf FROM disease_symptoms GROUP BY symptom HAVING AVG(confidence) > 0.9 AND disease_count > 5 ORDER BY disease_count DESC LIMIT 15",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="找出置信度高于0.9且关联疾病数大于10的药物。",
            gold_sql="SELECT drug, COUNT(DISTINCT disease) AS disease_count, AVG(confidence) AS avg_conf FROM disease_drugs GROUP BY drug HAVING AVG(confidence) > 0.9 AND disease_count > 10 ORDER BY disease_count DESC LIMIT 15",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="列出关联疾病数超过100种的症状及其疾病数量。",
            gold_sql="SELECT symptom, COUNT(DISTINCT disease) AS disease_count FROM disease_symptoms GROUP BY symptom HAVING disease_count > 100 ORDER BY disease_count DESC",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="列出关联疾病数超过500种的药物名称。",
            gold_sql="SELECT drug, COUNT(DISTINCT disease) AS disease_count FROM disease_drugs GROUP BY drug HAVING disease_count > 500 ORDER BY disease_count DESC",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="在来源'QASystemOnMedicalKG'中，置信度大于0.8的症状记录有多少条？",
            gold_sql="SELECT COUNT(*) AS high_conf_count FROM disease_symptoms WHERE source_name LIKE '%QASystemOnMedicalKG%' AND confidence > 0.8",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="在来源'QASystemOnMedicalKG'中，置信度大于0.8的药物记录有多少条？",
            gold_sql="SELECT COUNT(*) AS high_conf_count FROM disease_drugs WHERE source_name LIKE '%QASystemOnMedicalKG%' AND confidence > 0.8",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="同时包含症状'头痛'和'发热'的疾病有哪些？",
            gold_sql="SELECT s1.disease FROM disease_symptoms s1 JOIN disease_symptoms s2 ON s1.disease = s2.disease WHERE s1.symptom LIKE '%头痛%' AND s2.symptom LIKE '%发热%' LIMIT 20",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="同时使用药物'阿司匹林'和'二甲双胍'的疾病有哪些？",
            gold_sql="SELECT d1.disease FROM disease_drugs d1 JOIN disease_drugs d2 ON d1.disease = d2.disease WHERE d1.drug LIKE '%阿司匹林%' AND d2.drug LIKE '%二甲双胍%' LIMIT 20",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="同时包含症状'咳嗽'和检查'X线'的疾病有哪些？",
            gold_sql="SELECT s.disease FROM disease_symptoms s JOIN disease_tests t ON s.disease = t.disease WHERE s.symptom LIKE '%咳嗽%' AND t.test LIKE '%X线%' LIMIT 20",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms", "disease_tests"]
        )
        self.add_case(
            question="列出在内科就诊且关联药物数超过50种的疾病。",
            gold_sql="SELECT d.disease, COUNT(DISTINCT dr.drug) AS drug_count FROM disease_departments d JOIN disease_drugs dr ON d.disease = dr.disease WHERE d.department LIKE '%内科%' GROUP BY d.disease HAVING drug_count > 50 ORDER BY drug_count DESC LIMIT 15",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_departments", "disease_drugs"]
        )
        self.add_case(
            question="找出置信度高于0.8且来源为'structured_triples'的症状记录数。",
            gold_sql="SELECT COUNT(*) AS cnt FROM disease_symptoms WHERE confidence > 0.8 AND source_name = 'structured_triples'",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="找出置信度高于0.8且来源为'structured_triples'的药物记录数。",
            gold_sql="SELECT COUNT(*) AS cnt FROM disease_drugs WHERE confidence > 0.8 AND source_name = 'structured_triples'",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_drugs"]
        )
        self.add_case(
            question="列出疾病名称以'急性'开头且关联症状数大于5的疾病。",
            gold_sql="SELECT disease, COUNT(DISTINCT symptom) AS symptom_count FROM disease_symptoms WHERE disease LIKE '急性%' GROUP BY disease HAVING symptom_count > 5 ORDER BY symptom_count DESC LIMIT 15",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="列出科室名称含'外科'且关联检查数超过20种的疾病。",
            gold_sql="SELECT d.disease, COUNT(DISTINCT t.test) AS test_count FROM disease_departments d JOIN disease_tests t ON d.disease = t.disease WHERE d.department LIKE '%外科%' GROUP BY d.disease HAVING test_count > 20 ORDER BY test_count DESC LIMIT 15",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_departments", "disease_tests"]
        )
        self.add_case(
            question="疾病名称包含'糖尿病'且同时有关联症状和药物记录的有哪些？列出症状数和药物数。",
            gold_sql="SELECT s.disease, COUNT(DISTINCT s.symptom) AS symptom_count, COUNT(DISTINCT d.drug) AS drug_count FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease WHERE s.disease LIKE '%糖尿病%' GROUP BY s.disease",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_symptoms", "disease_drugs"]
        )
        self.add_case(
            question="列出既不是单来源也没有描述信息的疾病数量。",
            gold_sql="SELECT COUNT(*) AS cnt FROM diseases WHERE source_count > 1 AND (description IS NULL OR description = '')",
            difficulty="medium", query_type="多条件查询",
            tables=["diseases"]
        )
        self.add_case(
            question="查找同时有并发症和预防措施的疾病，列出疾病名、并发症数和预防措施数。",
            gold_sql="SELECT c.disease, COUNT(DISTINCT c.complication) AS comp_count, COUNT(DISTINCT p.prevention) AS prev_count FROM disease_complications c JOIN disease_preventions p ON c.disease = p.disease GROUP BY c.disease ORDER BY comp_count DESC LIMIT 15",
            difficulty="hard", query_type="多条件查询",
            tables=["disease_complications", "disease_preventions"]
        )
        self.add_case(
            question="找出 CBLUE CMeIE 来源中，置信度大于0.75的疾病-检查关联有多少条？",
            gold_sql="SELECT COUNT(*) AS cnt FROM disease_tests WHERE source_name LIKE '%CMeIE%' AND confidence > 0.75",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_tests"]
        )
        self.add_case(
            question="在 disease_facts 表中查询 fact_type='symptom' 且 confidence > 0.8 的记录数。",
            gold_sql="SELECT COUNT(*) AS cnt FROM disease_facts WHERE fact_type = 'symptom' AND confidence > 0.8",
            difficulty="medium", query_type="多条件查询",
            tables=["disease_facts"]
        )

    # ---- 复杂综合 20 题 ----
    def _build_complex_queries(self):
        # 子查询
        self.add_case(
            question="找出疾病关联数量高于所有疾病平均关联数的科室。",
            gold_sql="SELECT department, AVG(cnt) AS avg_disease_links FROM (SELECT d.department, COUNT(DISTINCT s.symptom) AS cnt FROM disease_departments d JOIN disease_symptoms s ON d.disease = s.disease GROUP BY d.disease) sub GROUP BY department HAVING AVG(cnt) > (SELECT AVG(symptom_count) FROM (SELECT COUNT(DISTINCT symptom) AS symptom_count FROM disease_symptoms GROUP BY disease)) ORDER BY avg_disease_links DESC LIMIT 10",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_departments", "disease_symptoms"]
        )

        # 使用 WITH 子句的查询
        self.add_case(
            question="使用 WITH 查询：找出症状关联数排名前三的疾病及其关联药物数。",
            gold_sql="WITH top_diseases AS (SELECT disease, COUNT(DISTINCT symptom) AS symptom_count FROM disease_symptoms GROUP BY disease ORDER BY symptom_count DESC LIMIT 3) SELECT td.disease, td.symptom_count, COUNT(DISTINCT dd.drug) AS drug_count FROM top_diseases td LEFT JOIN disease_drugs dd ON td.disease = dd.disease GROUP BY td.disease ORDER BY td.symptom_count DESC",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms", "disease_drugs"]
        )

        # 排名相关
        self.add_case(
            question="在疾病-症状关联中，按疾病关联症状的数量排名，列出第 5 到第 15 名。",
            gold_sql="SELECT disease, symptom_count FROM (SELECT disease, COUNT(DISTINCT symptom) AS symptom_count, ROW_NUMBER() OVER (ORDER BY COUNT(DISTINCT symptom) DESC) AS rn FROM disease_symptoms GROUP BY disease) WHERE rn BETWEEN 5 AND 15",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms"]
        )

        # 交集分析：两个疾病共享的症状
        self.add_case(
            question="糖尿病和高血压有哪些共同的症状？",
            gold_sql="SELECT s1.symptom FROM disease_symptoms s1 INNER JOIN disease_symptoms s2 ON s1.symptom = s2.symptom WHERE s1.disease LIKE '%糖尿病%' AND s2.disease LIKE '%高血压%' ORDER BY s1.symptom",
            difficulty="medium", query_type="复杂综合",
            tables=["disease_symptoms"]
        )
        self.add_case(
            question="肺炎和支气管炎有哪些共同的检查项目？",
            gold_sql="SELECT t1.test FROM disease_tests t1 INNER JOIN disease_tests t2 ON t1.test = t2.test WHERE t1.disease LIKE '%肺炎%' AND t2.disease LIKE '%支气管炎%' ORDER BY t1.test",
            difficulty="medium", query_type="复杂综合",
            tables=["disease_tests"]
        )
        self.add_case(
            question="糖尿病和高血压有哪些共同的药物？",
            gold_sql="SELECT d1.drug FROM disease_drugs d1 INNER JOIN disease_drugs d2 ON d1.drug = d2.drug WHERE d1.disease LIKE '%糖尿病%' AND d2.disease LIKE '%高血压%' ORDER BY d1.drug",
            difficulty="medium", query_type="复杂综合",
            tables=["disease_drugs"]
        )

        # 比例计算
        self.add_case(
            question="有症状记录的疾病占全部疾病的比例是多少？",
            gold_sql="SELECT ROUND(CAST(COUNT(DISTINCT disease) AS REAL) / (SELECT COUNT(*) FROM diseases) * 100, 2) AS percentage FROM disease_symptoms",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms", "diseases"]
        )
        self.add_case(
            question="有药物记录的疾病占全部疾病的比例是多少？",
            gold_sql="SELECT ROUND(CAST(COUNT(DISTINCT disease) AS REAL) / (SELECT COUNT(*) FROM diseases) * 100, 2) AS percentage FROM disease_drugs",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_drugs", "diseases"]
        )

        # 条件统计
        self.add_case(
            question="内科疾病中有症状记录的比例是多少？",
            gold_sql="SELECT ROUND(CAST(COUNT(DISTINCT s.disease) AS REAL) / (SELECT COUNT(DISTINCT disease) FROM disease_departments WHERE department LIKE '%内科%') * 100, 2) AS percentage FROM disease_symptoms s JOIN disease_departments d ON s.disease = d.disease WHERE d.department LIKE '%内科%'",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms", "disease_departments"]
        )

        # 比较分析
        self.add_case(
            question="比较有症状记录的疾病数与有药物记录的疾病数，哪个更多？",
            gold_sql="SELECT (SELECT COUNT(DISTINCT disease) FROM disease_symptoms) AS symptoms_diseases, (SELECT COUNT(DISTINCT disease) FROM disease_drugs) AS drugs_diseases",
            difficulty="medium", query_type="复杂综合",
            tables=["disease_symptoms", "disease_drugs"]
        )

        # 相关性分析：症状-药物在相同疾病中的共现
        self.add_case(
            question="对于疾病'肺炎'，列出其所有症状及每种症状关联的药物数（在该疾病中）。",
            gold_sql="SELECT s.symptom, COUNT(DISTINCT d.drug) AS drug_count FROM disease_symptoms s JOIN disease_drugs d ON s.disease = d.disease WHERE s.disease LIKE '%肺炎%' GROUP BY s.symptom ORDER BY drug_count DESC",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms", "disease_drugs"]
        )

        # 多跳分析
        self.add_case(
            question="找出与'糖尿病'共享症状最多的前10种疾病。",
            gold_sql="SELECT s2.disease, COUNT(*) AS shared_symptoms FROM disease_symptoms s1 JOIN disease_symptoms s2 ON s1.symptom = s2.symptom WHERE s1.disease LIKE '%糖尿病%' AND s2.disease NOT LIKE '%糖尿病%' GROUP BY s2.disease ORDER BY shared_symptoms DESC LIMIT 10",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms"]
        )

        # 复杂关联
        self.add_case(
            question="在所有症状中，哪些症状同时是至少5种不同科室的疾病所共有的？",
            gold_sql="SELECT s.symptom, COUNT(DISTINCT d.department) AS dept_count, COUNT(DISTINCT s.disease) AS disease_count FROM disease_symptoms s JOIN disease_departments d ON s.disease = d.disease GROUP BY s.symptom HAVING dept_count >= 5 ORDER BY disease_count DESC LIMIT 15",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_symptoms", "disease_departments"]
        )

        # WITH 子句 + 多表
        self.add_case(
            question="使用 WITH 查询：找出药物数超过100种的疾病，列出它们的症状数和检查数。",
            gold_sql="WITH drug_rich AS (SELECT disease, COUNT(DISTINCT drug) AS drug_count FROM disease_drugs GROUP BY disease HAVING drug_count > 100) SELECT dr.disease, dr.drug_count, COUNT(DISTINCT s.symptom) AS symptom_count, COUNT(DISTINCT t.test) AS test_count FROM drug_rich dr LEFT JOIN disease_symptoms s ON dr.disease = s.disease LEFT JOIN disease_tests t ON dr.disease = t.disease GROUP BY dr.disease ORDER BY dr.drug_count DESC LIMIT 15",
            difficulty="hard", query_type="复杂综合",
            tables=["disease_drugs", "disease_symptoms", "disease_tests"]
        )

        # 差距分析
        self.add_case(
            question="列出关联药物数最多的疾病和关联药物数最少的疾病，比较它们的差距。",
            gold_sql="SELECT MAX(drug_count) AS max_drugs, MIN(drug_count) AS min_drugs, MAX(drug_count) - MIN(drug_count) AS difference FROM (SELECT disease, COUNT(DISTINCT drug) AS drug_count FROM disease_drugs GROUP BY disease)",
            difficulty="medium", query_type="复杂综合",
            tables=["disease_drugs"]
        )

    # ---- 去重 ----
    def _deduplicate(self):
        """删除 SQL 签名重复的题目"""
        seen_sql = set()
        unique = []
        removed = 0
        for c in self.cases:
            # 标准化 SQL 用于去重
            sig = c["gold_sql"].strip().lower()
            sig = ' '.join(sig.split())  # 归一化空白
            if sig in seen_sql:
                removed += 1
                continue
            seen_sql.add(sig)
            unique.append(c)
        if removed:
            print(f"  去重删除 {removed} 条重复 SQL 题目")
        self.cases = unique

        # 删除语义重复的问题
        seen_q = set()
        unique = []
        removed = 0
        for c in self.cases:
            q = c["question"].strip()
            if q in seen_q:
                removed += 1
                continue
            seen_q.add(q)
            unique.append(c)
        if removed:
            print(f"  去重删除 {removed} 条重复问题")
        self.cases = unique


# ============================================================
# 第三步：划分 dev/test 并输出
# ============================================================

def split_and_output(cases):
    """按难度分层抽样，划分 dev=40, test=剩余"""
    # 按难度分组
    by_diff = {"easy": [], "medium": [], "hard": []}
    for c in cases:
        d = c.get("difficulty", "medium")
        if d not in by_diff:
            d = "medium"
        by_diff[d].append(c)

    # 每个难度组按比例抽 dev，固定种子
    dev_cases = []
    test_cases = []
    dev_total = 40

    # 按比例分配 dev 配额
    total = len(cases)
    for diff in ["easy", "medium", "hard"]:
        pool = by_diff[diff]
        n_dev = max(1, round(len(pool) / total * dev_total))
        shuffled = sorted(pool, key=lambda x: x["id"])
        random.shuffle(shuffled)
        dev_cases.extend(shuffled[:n_dev])
        test_cases.extend(shuffled[n_dev:])

    # 确保 dev 恰好 40 条
    if len(dev_cases) < dev_total:
        extra = [c for c in test_cases if c not in dev_cases]
        needed = dev_total - len(dev_cases)
        dev_cases.extend(extra[:needed])
        test_cases = [c for c in test_cases if c not in dev_cases]
    elif len(dev_cases) > dev_total:
        overflow = len(dev_cases) - dev_total
        moved = dev_cases[-overflow:]
        dev_cases = dev_cases[:-overflow]
        test_cases.extend(moved)

    return dev_cases, test_cases


def print_summary(dev_cases, test_cases):
    """打印 benchmark 统计报告"""
    all_cases = dev_cases + test_cases
    print("\n" + "=" * 60)
    print("  MediFlow Task 3 NL2SQL Benchmark 构建报告")
    print("=" * 60)

    print(f"\n总题数: {len(all_cases)} (dev={len(dev_cases)}, test={len(test_cases)})")

    # 按题型
    print("\n--- 按题型分布 ---")
    by_type = {}
    for c in all_cases:
        t = c["query_type"]
        by_type[t] = by_type.get(t, {"total": 0, "dev": 0, "test": 0})
        by_type[t]["total"] += 1
    for c in dev_cases:
        by_type[c["query_type"]]["dev"] += 1
    for c in test_cases:
        by_type[c["query_type"]]["test"] += 1
    for t, cnt in sorted(by_type.items()):
        print(f"  {t}: {cnt['total']} (dev={cnt['dev']}, test={cnt['test']})")

    # 按难度
    print("\n--- 按难度分布 ---")
    by_diff = {}
    for c in all_cases:
        d = c["difficulty"]
        by_diff[d] = by_diff.get(d, {"total": 0, "dev": 0, "test": 0})
        by_diff[d]["total"] += 1
    for c in dev_cases:
        by_diff[c["difficulty"]]["dev"] += 1
    for c in test_cases:
        by_diff[c["difficulty"]]["test"] += 1
    for d, cnt in sorted(by_diff.items()):
        print(f"  {d}: {cnt['total']} (dev={cnt['dev']}, test={cnt['test']})")

    # 按涉及表
    print("\n--- 涉及表 ---")
    tbl_count = {}
    for c in all_cases:
        for t in c["tables"]:
            tbl_count[t] = tbl_count.get(t, 0) + 1
    for t, cnt in sorted(tbl_count.items(), key=lambda x: -x[1]):
        print(f"  {t}: {cnt} 题")

    # JOIN 统计
    join_count = sum(1 for c in all_cases if len(c["tables"]) > 1)
    agg_count = sum(1 for c in all_cases if any(
        kw in c["gold_sql"].upper() for kw in ["COUNT(", "AVG(", "SUM(", "MAX(", "MIN("]
    ))
    with_count = sum(1 for c in all_cases if "WITH " in c["gold_sql"].upper())

    print(f"\n--- 高级 SQL 特性 ---")
    print(f"  JOIN 查询: {join_count} 题")
    print(f"  聚合函数: {agg_count} 题")
    print(f"  WITH 子句: {with_count} 题")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=== Step 1: 探索数据库结构 ===")
    info, stats = explore_db()

    print(f"  表数: {len(info)}")
    for name, meta in info.items():
        is_view = meta.get("is_view", False)
        tag = "[VIEW]" if is_view else "[TABLE]"
        print(f"  {tag} {name}: {meta['row_count']} rows, columns={meta['columns']}")

    print(f"\n  top_diseases sample: {stats['top_diseases'][:5]}")
    print(f"  top_symptoms sample: {[(r[0], r[1]) for r in stats['top_symptoms'][:5]]}")
    print(f"  top_drugs sample: {[(r[0], r[1]) for r in stats['top_drugs'][:5]]}")

    print("\n=== Step 2: 构建测试题 ===")
    builder = BenchmarkBuilder(info, stats)
    builder.build_all()
    builder.finish()

    print("\n=== Step 3: 划分 dev/test ===")
    dev, test = split_and_output(builder.cases)
    print_summary(dev, test)

    print("\n=== Step 4: 输出文件 ===")

    # 写入 dev
    dev_path = OUT_DIR / "nl2sql_dev.jsonl"
    with open(dev_path, "w", encoding="utf-8") as f:
        for c in dev:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  dev: {dev_path} ({len(dev)} cases)")

    # 写入 test
    test_path = OUT_DIR / "nl2sql_test.jsonl"
    with open(test_path, "w", encoding="utf-8") as f:
        for c in test:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  test: {test_path} ({len(test)} cases)")

    # 写入 schema snapshot
    schema_path = OUT_DIR / "schema_snapshot.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump({
            "db_path": DB_RELATIVE_PATH.as_posix(),
            "tables": {k: {"columns": v["columns"], "row_count": v["row_count"]}
                       for k, v in info.items() if not v.get("is_view")},
            "views": {k: {"row_count": v["row_count"]}
                      for k, v in info.items() if v.get("is_view")},
            "stats": {k: v for k, v in stats.items()
                      if k not in ["top_diseases", "top_symptoms", "top_drugs",
                                   "departments", "top_tests", "fact_types"]}
        }, f, ensure_ascii=False, indent=2)
    print(f"  schema: {schema_path}")

    print("\n=== 完成 ===")
