# -*- coding: utf-8 -*-
"""固定生成任务一多格式压力语料。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .fixtures import CorpusCase, TermExpectation


@dataclass(frozen=True)
class Scenario:
    diagnosis_raw: str
    diagnosis_clean: str
    note_raw: str
    note_clean: str
    measurement_raw: str
    measurement_clean: str
    terms: tuple[TermExpectation, ...]
    protected: tuple[str, ...]


SCENARIOS = (
    Scenario(
        "Ｔ２ＤＭ",
        "2型糖尿病",
        "主诉胸闷伴针扎样疼痛，否认发热",
        "主诉胸闷伴针扎样疼痛，否认发热",
        "HbA1c 7.2%，BP 138/86 mmHg",
        "糖化血红蛋白 7.2%，血压 138/86 毫米汞柱",
        (
            TermExpectation("Ｔ２ＤＭ", "2型糖尿病"),
            TermExpectation("HbA1c", "糖化血红蛋白"),
            TermExpectation("BP", "血压"),
            TermExpectation("mmHg", "毫米汞柱"),
        ),
        ("针扎样疼痛", "否认发热", "138/86"),
    ),
    Scenario(
        "HTN",
        "高血压",
        "咳嗽三天，偶有刀割样痛，否认胸痛",
        "咳嗽三天，偶有刀割样痛，否认胸痛",
        "FPG 6.1 mmol/L，CHD待排",
        "空腹血糖 6.1 毫摩尔/升，冠心病待排",
        (
            TermExpectation("HTN", "高血压"),
            TermExpectation("FPG", "空腹血糖"),
            TermExpectation("mmol/L", "毫摩尔/升"),
            TermExpectation("CHD", "冠心病"),
        ),
        ("刀割样痛", "否认胸痛", "6.1"),
    ),
    Scenario(
        "CKD",
        "慢性肾脏病",
        "双下肢无水肿，夜间睡眠尚可",
        "双下肢无水肿，夜间睡眠尚可",
        "Cr 135 umol/L，建议 qd 复查",
        "肌酐 135 微摩尔/升，建议 每日一次 复查",
        (
            TermExpectation("CKD", "慢性肾脏病"),
            TermExpectation("Cr", "肌酐"),
            TermExpectation("umol/L", "微摩尔/升"),
            TermExpectation("qd", "每日一次"),
        ),
        ("无水肿", "135", "夜间睡眠尚可"),
    ),
    Scenario(
        "COPD",
        "慢性阻塞性肺疾病",
        "活动后气促，表情淡漠，无咯血",
        "活动后气促，表情淡漠，无咯血",
        "SpO2 95%，HR 82 bpm",
        "血氧饱和度 95%，心率 82 次/分",
        (
            TermExpectation("COPD", "慢性阻塞性肺疾病"),
            TermExpectation("SpO2", "血氧饱和度"),
            TermExpectation("HR", "心率"),
            TermExpectation("bpm", "次/分"),
        ),
        ("表情淡漠", "无咯血", "95%"),
    ),
    Scenario(
        "HLP",
        "高脂血症",
        "近期无头晕及心悸，免疫系统功能正常",
        "近期无头晕及心悸，免疫系统功能正常",
        "LDL-C 3.6 mmol/L，建议 po tid",
        "低密度脂蛋白胆固醇 3.6 毫摩尔/升，建议 口服 每日三次",
        (
            TermExpectation("HLP", "高脂血症"),
            TermExpectation("LDL-C", "低密度脂蛋白胆固醇"),
            TermExpectation("mmol/L", "毫摩尔/升"),
            TermExpectation("po", "口服"),
            TermExpectation("tid", "每日三次"),
        ),
        ("无头晕及心悸", "免疫系统功能正常", "3.6"),
    ),
)

NAMES = ("张宁", "李玥", "王晨", "赵敏", "周强", "陈洁", "林雪", "韩梅")
LEARNED_NOISE = (
    "跟隔壁老王聊天，顺便聊了球赛",
    "哎呀妈呀，今天路上堵车太久了",
    "记得把这个录入，交接班群里再说",
)
UNSEEN_NOISE = (
    "家属还顺便聊了小区停车位",
    "患者临走前问了医院食堂几点关门",
    "陪诊人员提到周末准备去郊外露营",
    "候诊时大家讨论了昨晚的电视剧",
    "患者顺口说起新买的手机颜色",
)


def _common_noise(token: int) -> str:
    options = (
        "图片链接已失效",
        "系统自动生成",
        f"https://hospital.example/archive/{token}",
        "<span></span> 😀",
        f"controlled_noise_{20260810 + token % 3}",
        "@护士站",
    )
    return options[token % len(options)]


def _record(token: int, prefix: str) -> tuple[
    dict,
    dict,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[TermExpectation, ...],
    tuple[str, ...],
]:
    scenario = SCENARIOS[token % len(SCENARIOS)]
    record_id = f"{prefix}-{token:04d}"
    name = NAMES[token % len(NAMES)]
    common = _common_noise(token)
    learned: list[str] = []
    unseen: list[str] = []
    if token % 2 == 0:
        learned.append(LEARNED_NOISE[token % len(LEARNED_NOISE)])
    if token % 11 == 0:
        unseen.append(UNSEEN_NOISE[(token // 11) % len(UNSEEN_NOISE)])
    semantic = (*learned, *unseen)
    noise = (common, *semantic)
    raw_note = " ".join((scenario.note_raw, *noise))
    terms = list(scenario.terms)
    measurement_raw = scenario.measurement_raw
    measurement_clean = scenario.measurement_clean
    if token % 31 == 0:
        measurement_raw += "，eGFR 78 mL/min"
        measurement_clean += "，估算肾小球滤过率 78 mL/min"
        terms.append(TermExpectation("eGFR", "估算肾小球滤过率"))

    payload = {
        "record_id": record_id,
        "patient_name": name,
        "age": str(30 + token % 50),
        "diagnosis": scenario.diagnosis_raw,
        "notes": raw_note,
        "measurement": measurement_raw,
        "clean_reference": "评测旁车字段",
        "noise_labels": json.dumps(noise, ensure_ascii=False),
        "output_format_hint": prefix,
    }
    expected = {
        "record_id": record_id,
        "patient_name": name,
        "age": str(30 + token % 50),
        "diagnosis": scenario.diagnosis_clean,
        "notes": scenario.note_clean,
        "measurement": measurement_clean,
    }
    protected = (record_id, name, *scenario.protected)
    return (
        payload,
        expected,
        tuple(noise),
        tuple(semantic),
        tuple(learned),
        tuple(unseen),
        tuple(terms),
        tuple(protected),
    )


def _unique_terms(values: list[TermExpectation]) -> tuple[TermExpectation, ...]:
    unique = {(item.raw, item.normalized): item for item in values}
    return tuple(unique[key] for key in sorted(unique))


def _structured_case(file_format: str, file_index: int, rows_per_file: int = 4) -> CorpusCase:
    payloads, expected_rows = [], []
    noise, semantic, learned, unseen, terms, protected = [], [], [], [], [], []
    for row_index in range(rows_per_file):
        token = file_index * rows_per_file + row_index
        raw, clean, row_noise, row_semantic, row_learned, row_unseen, row_terms, row_protected = _record(token, file_format)
        if file_format in {"json", "jsonl"}:
            raw = {
                "id": raw.pop("record_id"),
                "name": raw.pop("patient_name"),
                **raw,
                "metadata": {"visit_date": f"2026-08-{10 + token % 18:02d}"},
            }
            clean = {
                "id": clean.pop("record_id"),
                "name": clean.pop("patient_name"),
                **clean,
                "metadata": {"visit_date": f"2026-08-{10 + token % 18:02d}"},
            }
        payloads.append(raw)
        expected_rows.append(clean)
        noise.extend(row_noise)
        semantic.extend(row_semantic)
        learned.extend(row_learned)
        unseen.extend(row_unseen)
        terms.extend(row_terms)
        protected.extend(row_protected)
    return CorpusCase(
        case_id=f"{file_format}-{file_index + 1:03d}",
        file_format=file_format,
        file_name=f"{file_format}_{file_index + 1:03d}.{file_format}",
        payload=payloads,
        expected=expected_rows,
        noise_labels=tuple(noise),
        semantic_noise_labels=tuple(semantic),
        learned_noise_labels=tuple(learned),
        unseen_noise_labels=tuple(unseen),
        terms=_unique_terms(terms),
        protected=tuple(protected),
        expected_records=rows_per_file,
        description=f"{file_format.upper()} 多记录压力样本：术语、固定噪声、学习噪声、保护片段与结构。",
    )


def _txt_case(file_index: int) -> CorpusCase:
    raw, clean, noise, semantic, learned, unseen, terms, protected = _record(file_index, "txt")
    payload = (
        f"患者姓名：{raw['patient_name']}，病历号：{raw['record_id']}。\n"
        f"诊断：{raw['diagnosis']}。\n{raw['notes']}\n检查：{raw['measurement']}。"
    )
    expected = (
        f"患者姓名：{clean['patient_name']}，病历号：{clean['record_id']}。\n"
        f"诊断：{clean['diagnosis']}。\n{clean['notes']}\n检查：{clean['measurement']}。"
    )
    return CorpusCase(
        case_id=f"txt-{file_index + 1:03d}",
        file_format="txt",
        file_name=f"txt_{file_index + 1:03d}.txt",
        payload=payload,
        expected=expected,
        noise_labels=noise,
        semantic_noise_labels=semantic,
        learned_noise_labels=learned,
        unseen_noise_labels=unseen,
        terms=terms,
        protected=protected,
        expected_records=1,
        description="TXT 压力样本：完整文本链、医学语义保护与噪声知识蒸馏。",
    )


def build_stress_cases(files_per_format: int = 20) -> list[CorpusCase]:
    cases = [_txt_case(index) for index in range(files_per_format)]
    for file_format in ("csv", "json", "jsonl"):
        cases.extend(_structured_case(file_format, index) for index in range(files_per_format))
    return cases
