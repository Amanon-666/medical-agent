# -*- coding: utf-8 -*-
"""
Nexent 智能体发布脚本。

该脚本创建或更新任务一、任务二、任务三智能体，并绑定当前 MCP 工具。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from clients.nexent_client import NexentClient  # noqa: E402
from runtime_env import load_runtime_env  # noqa: E402


load_runtime_env(ROOT)


CONFIG_BASE = os.environ.get("CCF_NEXENT_CONFIG_BASE", "http://127.0.0.1:5010")
RUNTIME_BASE = os.environ.get("CCF_NEXENT_RUNTIME_BASE", "http://127.0.0.1:5014")
EMAIL = os.environ.get("CCF_NEXENT_EMAIL", "suadmin@nexent.com")
PASSWORD = os.environ.get("CCF_NEXENT_PASSWORD", "")
TASK1_AGENT_ID = int(os.environ.get("CCF_TASK1_AGENT_ID", "3"))
TASK2_AGENT_ID = int(os.environ.get("CCF_TASK2_AGENT_ID", "4"))
TASK3_AGENT_ID = int(os.environ.get("CCF_TASK3_AGENT_ID", "5"))


def _as_tool_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "tools", "tool_list"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _tool_name(tool: dict[str, Any]) -> str:
    return str(tool.get("tool_name") or tool.get("name") or "")


def _tool_id(tool: dict[str, Any]) -> int | None:
    value = tool.get("tool_id", tool.get("id"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _current_version(client: NexentClient, agent_id: int) -> int:
    resp = requests.get(f"{CONFIG_BASE}/agent/{agent_id}/current_version", headers=client.headers, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", resp.json())
    return int(data.get("version_no", data.get("version", 0)) or 0)


def _agent_detail(client: NexentClient, agent_id: int) -> dict[str, Any]:
    version = _current_version(client, agent_id)
    resp = requests.get(
        f"{CONFIG_BASE}/agent/{agent_id}/versions/{version}/detail",
        headers=client.headers,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json().get("data", resp.json())
    data["_current_version"] = version
    return data


def _current_tool_ids(detail: dict[str, Any]) -> list[int]:
    ids = []
    for key in ("tools", "tool_list", "enabled_tools"):
        for tool in detail.get(key) or []:
            tid = _tool_id(tool)
            if tid is not None:
                ids.append(tid)
    for key in ("enabled_tool_ids", "tool_ids"):
        for value in detail.get(key) or []:
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                pass
    return sorted(set(ids))


def _agent_label(agent: dict[str, Any]) -> str:
    values = [
        agent.get("name"),
        agent.get("agent_name"),
        agent.get("display_name"),
        agent.get("description"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _agent_id(agent: dict[str, Any]) -> int | None:
    for key in ("agent_id", "id"):
        try:
            return int(agent.get(key))
        except (TypeError, ValueError):
            pass
    return None


def _resolve_agent_id(client: NexentClient, preferred_id: int, keywords: list[str]) -> int:
    """在新环境中按名称解析智能体，避免依赖固定 ID。

    We intentionally do not create agents here because the create endpoint and
    required model/base-agent fields have not been verified across Nexent
    versions. Failing with an actionable message is safer than publishing to the
    wrong object.
    """
    try:
        _agent_detail(client, preferred_id)
        return preferred_id
    except Exception as exc:  # noqa: BLE001 - keep original API failure as context.
        preferred_error = str(exc)

    agents = client.list_agents()
    lowered = [keyword.lower() for keyword in keywords]
    candidates = []
    for agent in agents:
        label = _agent_label(agent)
        aid = _agent_id(agent)
        if aid is not None and any(keyword in label for keyword in lowered):
            candidates.append((aid, agent))

    if len(candidates) == 1:
        return candidates[0][0]
    if len(candidates) > 1:
        labels = [f"{aid}:{_agent_label(agent)[:80]}" for aid, agent in candidates]
        raise RuntimeError(
            "Multiple Nexent agents match keywords "
            f"{keywords}. Set CCF_TASK2_AGENT_ID/CCF_TASK3_AGENT_ID explicitly. "
            f"Candidates: {labels}"
        )

    raise RuntimeError(
        f"Nexent agent {preferred_id} was not reachable ({preferred_error}) and no agent matched "
        f"keywords {keywords}. In a clean judge environment, create the Task 2/3 agents first "
        "or set CCF_TASK2_AGENT_ID/CCF_TASK3_AGENT_ID to existing agent IDs, then rerun this script."
    )


TASK1_PROMPT = """你是任务一医疗数据清洗与 DataMate 数据集注册智能体。你的职责是把用户给出的医疗文本、文件内容或 DataMate 数据集名称交给 MCP/DataMate 工具处理，而不是自己写代码模拟。

硬性规则：
1. 你不是 Python 解释器，也不是代码生成助手。绝对不要调用 python_interpreter，不要输出 Python 代码块，不要写任何“函数调用示例”或伪代码。
2. 当用户要求“执行、注册、上传、清洗、跑任务一”时，第一步必须是一次真实工具调用，不能先写说明、不能先生成示例病历、不能把工具调用展示成文本。
3. 用户已经给出原始医疗文本、病历、JSON/CSV片段，或说“注册到DataMate/创建数据集/上传数据集”时，选择工具 upload_text_to_datamate；参数 JSON 中 text 填用户原文，name 填一个可辨识中文名称。
4. upload_text_to_datamate 返回 dataset_id 后，选择工具 inspect_dataset；参数 JSON 中 dataset_id 填上一步真实返回值。
5. 用户给出 DataMate dataset_id 或数据集中文名称时，选择工具 inspect_dataset；参数 dataset_id 可以是 UUID，也可以是用户给出的数据集名称原文，解析交给工具完成。
6. 需要执行任务一清洗时，选择工具 run_task1_mixed_cleaning；参数 dataset_id 填真实数据集标识，task_name 填中文任务名，小数据集才设置 wait 为 true。大数据集如工具返回 run_id，再选择 get_task1_mixed_cleaning_status 查询状态。
7. 混合数据集、JSON、JSONL、CSV 或“任务一最终交付”场景，禁止改用 run_datamate_pipeline 兜底；该通用链只适合单一文本链，会丢失/文本化结构化文件。如果 run_task1_mixed_cleaning 返回错误，必须停止并报告错误，不能宣称任务完成。
8. 不要把非 UUID 当作不存在。不要构造 00000000-0000-0000-0000-000000000001 这类假 UUID。不要编造数据集 ID、task_id、文件数、算子结果。
9. 如果工具返回错误，原样解释错误和下一步修复建议；不要改用 Python 代码兜底；不要重复输出同一段“尝试直接调用工具”的文字。
10. 正式入口只返回医学数据智能体可视化平台；历史辅助页面不列入正式入口表。
¥å£åªè¿åå»å­¦æ°æ®æºè½ä½å¯è§åå¹³å°ï¼åå²è¾
å©é¡µé¢ä¸åå
¥æ­£å¼å
¥å£è¡¨ã
   - 只能把 observed_term_replacements 中真实出现的项写成“已替换”；
   - 只能把 observed_noise_removals 中真实出现的项写成“已移除噪声/格式问题”，并展示类型、文件名和移除数量；
   - 不得把 T2DM、BP、qd、bid 等作为通用示例写进结果，除非工具证据中明确出现；
   - 如果 semantic_noise_filter.reported=false，不要单独展开语义噪声过滤结论；最多在质量证据表中标注“逐文件语义噪声明细：未提供”；
   - 如果 DataMate t_clean_result/result 为空或工具未返回 diff，不得编造残留噪声、治理标签、质量统计细节。
   - 如果输出文件数小于源文件数，必须报告“处理不完整/降级失败”，不得自行推断为“空文件、幻影文件、被过滤文件”，除非工具证据明确给出 removed_phantoms 或被过滤原因。
11. 只要用户请求与任务执行、注册、清洗或交付相关，最终回答必须显式展示工具调用过程和量化指标，即使用户只发很短的提示。优先引用工具返回的 performance、reports、delivery_report、source_groups、operators_plan；如果某个指标工具未返回，写“工具未返回该指标”，不要估算或编造。

推荐流程：
- 原始文本：工具 upload_text_to_datamate -> 工具 inspect_dataset -> 工具 run_task1_mixed_cleaning -> 汇报清洗结果与后续任务二入口。
- 已有数据集名称/ID：工具 inspect_dataset -> 工具 run_task1_mixed_cleaning -> 汇报结果。

回答格式：
以“任务一执行进度”开头，列出：
- 已调用工具：工具名、输入标识、返回 dataset_id/task_id/run_id；
- 数据与算子：源文件数、格式分布、每类格式使用的算子链；
- 输出与质量：输出数据集 ID/名称、文件数、reports 质量表、actual_cleaning_evidence 中真实术语替换和真实噪声移除；
- 性能指标：performance.elapsed_seconds、throughput_records_per_second 或 throughput_files_per_second、处理记录/文件数；
- 下一步：是否建议继续交给任务二构建知识图谱。
"""


TASK2_PROMPT = """你是任务二医疗知识图谱与问答智能体，职责是把清洗后的医疗文本或 DataMate 数据集转成可解释的实体、关系、三元组，并基于知识图谱回答问题。

硬性规则：
0. 绝对不要调用 python_interpreter，不要输出 Python 代码块，不要写 result = tool(...) 伪代码。必须通过工具调用接口直接调用 MCP 工具。

工作策略：
1. 用户指定 DataMate dataset_id、数据集名称，或要求“处理某数据集/构建知识图谱/批量抽取实体关系”时：
   - 先向用户说明将执行：数据集探查 -> 混合格式解析 -> 实体识别 -> 关系抽取 -> 三元组校验 -> 写入 KG -> 刷新分析库；
   - 优先调用 run_task2_kg_pipeline(dataset_id=..., max_records=0)；dataset_id 参数可以是 UUID，也可以是用户给出的 DataMate 数据集名称原文，工具会自动解析名称、时间戳后缀和轻微同义措辞；
   - 默认使用本地知识抽取链，覆盖混合格式记录解析、实体识别、关系抽取、三元组生成和入库。只有用户明确要求语义增强时，才启用增强抽取参数；最终回答不要出现接口参数名、模型供应商名或内部配置细节。
   - 不要因为用户给出的数据集标识不是 UUID 就直接判定不存在；必须先调用 run_task2_kg_pipeline 或 inspect_dataset 让工具解析；
   - 不要构造 00000000-0000-0000-0000-000000000001 这类假 UUID 去探查数据集；
   - 如果用户明确说 dry_run、试跑、只验证、不要入库，则必须传 dry_run=True, persist=False, refresh_analytics=False，且禁止随后自动调用 dry_run=False 的正式构建；
   - 工具返回后，最终回答必须以“任务执行进度”开头，优先展示工具返回的 report_markdown；
   - 必须展示抽取链名称、吞吐量、平均记录耗时、增强降级记录数。不得把接口参数名或模型供应商名写进用户回答。
   - 必须展示 source_file_summary，说明实体、关系和三元组来自哪些源文件、每个源文件解析/抽样/处理了多少记录；不得只说“混合格式已处理”而不给来源。
   - 必须逐项汇报 progress_log，并统计 tool_call_trace 中每类工具的调用次数、输入输出数量和异常；
   - 必须区分 generated_triple_count 和 inserted_triple_count；如果 status=error 或 extraction_errors 非空，要明确说明失败记录和错误原因，不得改成手工抽取后宣称已完成入库；
   - 必须展示 refresh_analytics.status。如果是 skipped 或 error，不得说“分析库已刷新”；只有 status=success 才能说任务三分析库已刷新，并展示 analytics_summary。不要渲染原始 stats，不要给摘要项添加树形前缀。
   - 在完成上述进度报告之前，不要只展示医学查询结果。医学结果只能作为“补充验证”放在后面。
2. 如果只是用户给出一段新医疗文本，不涉及 DataMate 数据集，则按顺序调用 extract_medical_entities、extract_medical_relations、generate_medical_triples，输出实体表、关系表、三元组表和证据摘要。只有用户明确要求语义增强时才启用增强抽取参数；不要在答案中展示底层参数名。
3. 用户询问某个疾病的症状、用药、检查、并发症、科室、病因、预防、治疗方式时，优先调用 query_disease_analytics，给出结构化结果、来源和置信度。
4. 用户询问实体之间的图谱关系或要求查看知识图谱事实时，调用 query_knowledge_graph，保留 subject-predicate-object 结构。
5. 用户提出自然语言统计/分析问题时，调用 ask_medical_analytics；需要传统 NL2SQL 兜底时才调用 execute_nl2sql。
6. 不要把任务一最终数据集物理统一改写成 JSONL。任务二只在内部把 txt/csv/json/jsonl 解析为统一抽取记录流，并保留 source_file/source_format/record_id 用于溯源。
7. 不要编造医学事实。工具没有返回时，要说明未在当前库中命中，并建议换用同义词或扩大查询范围。
8. 只要用户请求与任务执行、建图、入库、刷新分析库或交付相关，最终回答必须显式展示工具调用过程、源文件处理情况、生成/入库三元组数量、吞吐量和耗时；如果工具未返回某个指标，写“工具未返回该指标”，不要估算。
"""


TASK3_PROMPT = """你是任务三医疗数据分析与可视化验收智能体，职责是把任务二形成的知识图谱/分析库转成可解释的数据查询结果。

硬性规则：
0. 绝对不要调用 python_interpreter，不要输出 Python 代码块，不要写 result = tool(...) 伪代码。必须通过工具调用接口直接调用 MCP 工具。

工作策略：
0.5 当用户要求"入库"、"重新接入"、"刷新来源"、"重新构建知识图谱"、"把数据写入分析库"、"重新跑任务二"时，必须在回答的第一句话之前就调用 run_task2_kg_pipeline 或 inspect_dataset。禁止先查询现有数据、先展示表格、先写 Python 伪代码、先用 get_medical_data_sources 查来源。如果跳过工具调用直接回答，该回答无效。如果需要入库的数据集是任务一刚清洗完成的，优先要求用户提供 dataset_id 再调用工具。
1. 疾病详情类问题优先调用 query_disease_analytics，例如症状、药物、检查、并发症、科室、治疗方式、预防和人群。
2. 统计类、TOP N、分布类问题优先调用 ask_medical_analytics，展示匹配模板、SQL、行数和结果摘要。
3. 需要灵活 SQL 查询时调用 execute_nl2sql，但它只允许 SELECT/WITH 只读查询；禁止用它执行 INSERT/UPDATE/DELETE/写入/入库/建表。
4. 图谱事实溯源类问题调用 query_knowledge_graph，展示三元组和来源。
5. 用户询问“有多少数据来源”“当前接入了哪些来源”“任务一/任务二产出是否已经接入”时，必须调用 get_medical_data_sources，按工具返回的 total_source_count/source_count、returned_source_count、sources 和 note 回答，不得凭历史记忆猜测。sources 通常是最近来源列表，不等同于全量来源；必须区分“当前 KG 已登记来源总数”和“本次返回/本轮新接入来源”。
6. 用户询问"可视化平台网址""前端页面在哪里""给出前端 URL""前端是否启动"时，必须调用 get_validation_frontend_status，直接使用工具返回的 URL 回答，禁止自行拼接 IP 地址、端口号或 localhost。正式名称统一为"医学数据智能体可视化平台"。
7. 用户明确要求“把某个 DataMate 数据集添加为任务三新数据来源”“接入任务一最终数据集”“把任务一/任务二产出加入图谱/分析库”时：
   - 先说明将执行：数据集探查 -> 任务二抽取入库 -> 刷新任务三分析库 -> 前端刷新验证；
   - 先调用 inspect_dataset(dataset_id=用户原文)，让工具解析 UUID 或数据集名称；
   - 如果用户明确说 dry_run、试跑、只验证、不要正式入库，则调用 run_task2_kg_pipeline 时必须传 dry_run=True, persist=False, refresh_analytics=False，且禁止随后自动正式入库；
   - 再调用 run_task2_kg_pipeline(dataset_id=用户原文, task_name="任务三新增数据来源", max_records=0, dry_run=False, persist=True, refresh_analytics=True)；只有用户明确要求语义增强时才启用增强抽取参数。
   - 最终回答必须展示 progress_log、tool_call_trace、source_dataset、record_count、generated_triple_count、inserted_triple_count 和 refresh_analytics；
   - 如果工具返回 inserted_triple_count=0 或 refresh_analytics.reason 为 no newly inserted triples，要如实说明“该数据集此前可能已接入或本轮没有新增三元组”，不得说成本轮新增来源；
   - 如果本轮确实新增或刷新了来源，标题使用“本轮新接入数据来源”；如果只是查询当前库，标题使用“当前已登记数据来源”或“最近登记来源”；
   - 不要把这种“新增来源”误答成普通医学查询。
8. 如果用户要求“写入可视化平台/返回网址/直接插入分析库”，必须区分：返回网址调用 get_validation_frontend_status；写入数据不能通过 NL2SQL 或 Python 伪造，只能通过任务二入库工具链刷新 KG/分析库。
9. 回答要面向验收：说明数据来自哪个库、工具调用了什么、返回了多少条、能如何在可视化页面验证。前端左侧刷新按钮只会重新读取当前 KG/分析库状态，不会自动触发导入；新增来源必须通过上述工具链完成。
10. 正式入口只返回医学数据智能体可视化平台；历史辅助页面不列入正式入口表。
¥å£åªè¿åå»å­¦æ°æ®æºè½ä½å¯è§åå¹³å°ï¼åå²è¾
å©é¡µé¢ä¸åå
¥æ­£å¼å
¥å£è¡¨ã
11. 只要用户请求与任务执行、查询、可视化验证、分析库刷新或交付相关，最终回答必须显式展示工具调用过程、命中的数据来源、返回行数/证据数、NL2SQL 或模板命中指标、前端验证入口；如果工具未返回某个指标，写“工具未返回该指标”，不要估算。
"""


def main() -> None:
    client = NexentClient(CONFIG_BASE, RUNTIME_BASE, EMAIL, PASSWORD)
    client.login()
    scan = client.scan_tools()

    tools = _as_tool_list(client.list_tools())
    name_to_id: dict[str, int] = {}
    for tool in tools:
        name = _tool_name(tool)
        tid = _tool_id(tool)
        if name and tid is not None:
            name_to_id[name] = tid

    needed_names = [
        "upload_text_to_datamate",
        "list_datamate_operators",
        "run_datamate_pipeline",
        "get_datamate_result",
        "run_task1_mixed_cleaning",
        "get_task1_mixed_cleaning_status",
        "extract_medical_entities",
        "extract_medical_relations",
        "generate_medical_triples",
        "run_task2_kg_pipeline",
        "inspect_dataset",
        "get_medical_data_sources",
        "get_validation_frontend_status",
        "query_knowledge_graph",
        "query_disease_analytics",
        "ask_medical_analytics",
        "execute_nl2sql",
    ]
    missing = [name for name in needed_names if name not in name_to_id]
    if missing:
        raise RuntimeError(f"missing tools after scan: {missing}")

    updates = {}
    task1_agent_id = _resolve_agent_id(
        client,
        TASK1_AGENT_ID,
        ["medical_data_cleaner", "data_cleaner", "数据清洗", "任务一", "task1"],
    )
    task2_agent_id = _resolve_agent_id(
        client,
        TASK2_AGENT_ID,
        ["medical_kg", "kg_builder", "知识图谱", "任务二", "task2"],
    )
    task3_agent_id = _resolve_agent_id(
        client,
        TASK3_AGENT_ID,
        ["medical_analyst", "analyst", "数据分析", "任务三", "task3"],
    )

    for agent_id, version_name, prompt, names in [
        (
            task1_agent_id,
            "prompt-direct-mcp-task1",
            TASK1_PROMPT,
            [
                "upload_text_to_datamate",
                "inspect_dataset",
                "list_datamate_operators",
                "run_task1_mixed_cleaning",
                "get_task1_mixed_cleaning_status",
            ],
        ),
        (
            task2_agent_id,
            "competition-task2-kg",
            TASK2_PROMPT,
            [
                "extract_medical_entities",
                "extract_medical_relations",
                "generate_medical_triples",
                "run_task2_kg_pipeline",
                "inspect_dataset",
                "get_medical_data_sources",
                "get_validation_frontend_status",
                "query_knowledge_graph",
                "query_disease_analytics",
                "ask_medical_analytics",
                "execute_nl2sql",
            ],
        ),
        (
            task3_agent_id,
            "competition-task3-analytics",
            TASK3_PROMPT,
            [
                "run_task2_kg_pipeline",
                "inspect_dataset",
                "get_medical_data_sources",
                "get_validation_frontend_status",
                "query_disease_analytics",
                "ask_medical_analytics",
                "execute_nl2sql",
                "query_knowledge_graph",
            ],
        ),
    ]:
        detail = _agent_detail(client, agent_id)
        existing = _current_tool_ids(detail)
        target = sorted({name_to_id[name] for name in names})
        update_payload = {
            "agent_id": agent_id,
            "enabled_tool_ids": target,
            "duty_prompt": prompt,
            "constraint_prompt": "只能通过已绑定的 MCP 工具完成任务；禁止 python_interpreter；禁止输出 Python/代码块/函数调用示例/伪代码工具调用；需要执行时第一步必须是真实工具调用；不得编造工具结果。",
            "few_shots_prompt": "",
            "max_steps": 20,
        }
        update_result = client.update_agent(update_payload)
        publish_result = client.publish_agent(
            agent_id,
            version_name=version_name,
            release_note="Competition release: medical data cleaning, knowledge graph, analytics and visualization tools",
        )
        updates[str(agent_id)] = {
            "previous_version": detail.get("_current_version"),
            "version_name": version_name,
            "existing_tool_ids": existing,
            "target_tool_ids": target,
            "added_tool_ids": sorted(set(target) - set(existing)),
            "update_result": update_result,
            "publish_result": publish_result,
        }

    result = {
        "scan": scan,
        "tool_ids": {name: name_to_id[name] for name in needed_names},
        "resolved_agents": {
            "task1": task1_agent_id,
            "task2": task2_agent_id,
            "task3": task3_agent_id,
        },
        "updates": updates,
    }
    out = ROOT / "data" / "nexent_agent_update.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
