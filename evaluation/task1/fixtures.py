# -*- coding: utf-8 -*-
"""任务一自建多格式评测数据与人工金标准。

这里的输入数据刻意覆盖任务一链路中最容易出错的几类内容：
医疗术语、系统导出废话、链接/HTML/Emoji、结构化字段保护，以及
“免疫系统”等容易被宽泛规则误判的医学短语。

金标准只描述预期结果，不参与清洗过程，避免评测脚本用算子自身生成答案。
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TermExpectation:
    """一个需要被标准化的术语。"""

    raw: str
    normalized: str


@dataclass(frozen=True)
class CorpusCase:
    """一个输入文件及其独立金标准。"""

    case_id: str
    file_format: str
    file_name: str
    payload: Any
    expected: Any
    noise_labels: tuple[str, ...]
    terms: tuple[TermExpectation, ...]
    protected: tuple[str, ...]
    expected_records: int
    description: str
    semantic_noise_labels: tuple[str, ...] = ()
    learned_noise_labels: tuple[str, ...] = ()
    unseen_noise_labels: tuple[str, ...] = ()

    def raw_text(self) -> str:
        """把输入按文件格式序列化，供指标计算使用。"""

        return serialize_payload(self.file_format, self.payload)

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "file_format": self.file_format,
            "file_name": self.file_name,
            "description": self.description,
            "expected_records": self.expected_records,
            "noise_labels": list(self.noise_labels),
            "semantic_noise_labels": list(self.semantic_noise_labels),
            "learned_noise_labels": list(self.learned_noise_labels),
            "unseen_noise_labels": list(self.unseen_noise_labels),
            "terms": [asdict(item) for item in self.terms],
            "protected": list(self.protected),
            "gold_output": self.expected,
        }


def serialize_payload(file_format: str, payload: Any) -> str:
    """按 DataMate 输入文件的源格式序列化。"""

    if file_format == "txt":
        return str(payload)
    if file_format == "csv":
        rows = list(payload)
        fieldnames = list(rows[0].keys()) if rows else []
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue()
    if file_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if file_format == "jsonl":
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in payload) + "\n"
    raise ValueError(f"unsupported fixture format: {file_format}")


def _json_labels(labels: Iterable[str]) -> str:
    return json.dumps(list(labels), ensure_ascii=False)


def build_cases() -> list[CorpusCase]:
    """返回固定、可重复的四种源格式评测文件。"""

    txt1_noise = (
        "由HIS系统自动导出",
        "@护士小王",
        "填表时间：2026-08-09",
        "填表人：实习护士陈某",
        "图片链接已失效",
        "controlled_noise_20260809",
    )
    txt1 = CorpusCase(
        case_id="txt-001",
        file_format="txt",
        file_name="case_001.txt",
        payload=(
            "患者主诉：胸闷，针扎样疼痛；否认发热。\n"
            "Ｔ２ＤＭ患者，HbA1c 7.8%，BP 140/90 mmHg，建议 bid 口服。"
            "<p>已记录</p> https://hospital.example/record/1 😀\n"
            "由HIS系统自动导出 @护士小王\n"
            "填表时间：2026-08-09 填表人：实习护士陈某\n"
            "图片链接已失效 controlled_noise_20260809\n"
            "免疫系统功能正常，保留此句。"
        ),
        expected=(
            "患者主诉：胸闷，针扎样疼痛；否认发热。\n"
            "2型糖尿病患者，糖化血红蛋白 7.8%，血压 140/90 毫米汞柱，"
            "建议 每日两次 口服。已记录\n"
            "免疫系统功能正常，保留此句。"
        ),
        noise_labels=txt1_noise,
        terms=(
            TermExpectation("Ｔ２ＤＭ", "2型糖尿病"),
            TermExpectation("HbA1c", "糖化血红蛋白"),
            TermExpectation("BP", "血压"),
            TermExpectation("mmHg", "毫米汞柱"),
            TermExpectation("bid", "每日两次"),
        ),
        protected=(
            "针扎样疼痛",
            "否认发热",
            "7.8%",
            "免疫系统功能正常",
        ),
        expected_records=1,
        description="文本链：术语、全角字符、HTML、URL、Emoji、系统元数据和医学短语保护。",
    )

    txt2_noise = (
        "【系统提示】自动生成内容请忽略",
        "广告合作请联系 demo@example.com",
        "@医生助手",
        "controlled_noise_20260810",
        "电子病历系统自动导出",
    )
    txt2 = CorpusCase(
        case_id="txt-002",
        file_format="txt",
        file_name="case_002.txt",
        payload=(
            "患者有咳嗽，偶有刀割样痛，否认胸痛。\n"
            "HTN，FPG 6.1 mmol/L，CHD待排，继续观察。\n"
            "【系统提示】自动生成内容请忽略\n"
            "广告合作请联系 demo@example.com\n"
            "@医生助手 controlled_noise_20260810\n"
            "患者姓名：王芳，病历号：r002。\n"
            "电子病历系统自动导出"
        ),
        expected=(
            "患者有咳嗽，偶有刀割样痛，否认胸痛。\n"
            "高血压，空腹血糖 6.1 毫摩尔/升，冠心病待排，继续观察。\n"
            "患者姓名：王芳，病历号：r002。"
        ),
        noise_labels=txt2_noise,
        terms=(
            TermExpectation("HTN", "高血压"),
            TermExpectation("FPG", "空腹血糖"),
            TermExpectation("mmol/L", "毫摩尔/升"),
            TermExpectation("CHD", "冠心病"),
        ),
        protected=(
            "刀割样痛",
            "否认胸痛",
            "患者姓名：王芳",
            "病历号：r002",
            "6.1",
        ),
        expected_records=1,
        description="文本链：系统提示、广告、@通知、病历标识和相似症状的误删保护。",
    )

    csv_noise = (
        "图片链接已失效",
        "@护士小王",
        "系统自动生成",
        "HIS system auto export",
        "controlled_noise_20260809",
    )
    csv_payload = [
        {
            "record_id": "csv-001",
            "patient_name": "张三",
            "age": "42",
            "diagnosis": "T2DM",
            "notes": "胸闷，针扎样疼痛。图片链接已失效 @护士小王",
            "measurement": "HbA1c 7.8%",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(csv_noise[:2]),
            "output_format_hint": "csv",
        },
        {
            "record_id": "csv-002",
            "patient_name": "李四",
            "age": "55",
            "diagnosis": "免疫系统相关疾病待排除",
            "notes": "否认发热，建议监测BP。系统自动生成",
            "measurement": "140/90 mmHg",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(csv_noise[2:3]),
            "output_format_hint": "csv",
        },
        {
            "record_id": "csv-003",
            "patient_name": "王五",
            "age": "61",
            "diagnosis": "HTN（高血压）",
            "notes": "<b>头晕</b>，HIS system auto export controlled_noise_20260809",
            "measurement": "BP 120 mmHg",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(csv_noise[3:]),
            "output_format_hint": "csv",
        },
    ]
    csv_expected = [
        {
            "record_id": "csv-001",
            "patient_name": "张三",
            "age": "42",
            "diagnosis": "2型糖尿病",
            "notes": "胸闷，针扎样疼痛",
            "measurement": "糖化血红蛋白 7.8%",
        },
        {
            "record_id": "csv-002",
            "patient_name": "李四",
            "age": "55",
            "diagnosis": "免疫系统相关疾病待排除",
            "notes": "否认发热，建议监测血压",
            "measurement": "140/90 毫米汞柱",
        },
        {
            "record_id": "csv-003",
            "patient_name": "王五",
            "age": "61",
            "diagnosis": "高血压",
            "notes": "头晕",
            "measurement": "血压 120 毫米汞柱",
        },
    ]
    csv_case = CorpusCase(
        case_id="csv-001",
        file_format="csv",
        file_name="case_001.csv",
        payload=csv_payload,
        expected=csv_expected,
        noise_labels=csv_noise,
        terms=(
            TermExpectation("T2DM", "2型糖尿病"),
            TermExpectation("HbA1c", "糖化血红蛋白"),
            TermExpectation("BP", "血压"),
            TermExpectation("mmHg", "毫米汞柱"),
            TermExpectation("HTN", "高血压"),
        ),
        protected=(
            "csv-001",
            "张三",
            "胸闷，针扎样疼痛",
            "免疫系统相关疾病待排除",
            "csv-003",
            "王五",
            "7.8%",
        ),
        expected_records=3,
        description="CSV 链：医疗文本列清洗，标识列原样保留，评测辅助列删除。",
    )

    json_noise = (
        "图片链接已失效",
        "@护士小王",
        "系统自动生成",
        "controlled_noise_20260810",
        "https://example.org/x",
    )
    json_payload = [
        {
            "id": "json-001",
            "name": "李雷",
            "age": 38,
            "diagnosis": "T2DM",
            "note": "主诉胸闷，针扎样疼痛。<p>图片链接已失效</p> @护士小王",
            "department": "内科",
            "metadata": {
                "visit_date": "2026-08-09",
                "preserve_text": "免疫系统功能正常",
            },
            "lab_value": "HbA1c 6.5%",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(json_noise[:2]),
            "output_format_hint": "json",
        },
        {
            "id": "json-002",
            "name": "韩梅",
            "age": 55,
            "diagnosis": "HTN",
            "note": "否认胸痛，BP 130/80 mmHg。系统自动生成 controlled_noise_20260810",
            "department": "心内科",
            "metadata": {
                "visit_date": "2026-08-10",
                "preserve_text": "症状持续两天",
            },
            "lab_value": "140/90 mmHg",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(json_noise[2:4]),
            "output_format_hint": "json",
        },
        {
            "id": "json-003",
            "name": "赵敏",
            "age": 29,
            "diagnosis": "CHD待排",
            "note": "刀割样痛，否认呼吸困难。https://example.org/x 😀",
            "department": "急诊",
            "metadata": {
                "visit_date": "2026-08-11",
                "preserve_text": "免疫系统完整",
            },
            "tags": ["胸痛", "T2DM"],
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(json_noise[4:]),
            "output_format_hint": "json",
        },
    ]
    json_expected = [
        {
            "id": "json-001",
            "name": "李雷",
            "age": 38,
            "diagnosis": "2型糖尿病",
            "note": "主诉胸闷，针扎样疼痛",
            "department": "内科",
            "metadata": {
                "visit_date": "2026-08-09",
                "preserve_text": "免疫系统功能正常",
            },
            "lab_value": "糖化血红蛋白 6.5%",
        },
        {
            "id": "json-002",
            "name": "韩梅",
            "age": 55,
            "diagnosis": "高血压",
            "note": "否认胸痛，血压 130/80 毫米汞柱",
            "department": "心内科",
            "metadata": {
                "visit_date": "2026-08-10",
                "preserve_text": "症状持续两天",
            },
            "lab_value": "140/90 毫米汞柱",
        },
        {
            "id": "json-003",
            "name": "赵敏",
            "age": 29,
            "diagnosis": "冠心病待排",
            "note": "刀割样痛，否认呼吸困难",
            "department": "急诊",
            "metadata": {
                "visit_date": "2026-08-11",
                "preserve_text": "免疫系统完整",
            },
            "tags": ["胸痛", "2型糖尿病"],
        },
    ]
    json_case = CorpusCase(
        case_id="json-001",
        file_format="json",
        file_name="case_001.json",
        payload=json_payload,
        expected=json_expected,
        noise_labels=json_noise,
        terms=(
            TermExpectation("T2DM", "2型糖尿病"),
            TermExpectation("HbA1c", "糖化血红蛋白"),
            TermExpectation("HTN", "高血压"),
            TermExpectation("BP", "血压"),
            TermExpectation("mmHg", "毫米汞柱"),
            TermExpectation("CHD", "冠心病"),
        ),
        protected=(
            "json-001",
            "李雷",
            "针扎样疼痛",
            "免疫系统功能正常",
            "json-003",
            "赵敏",
            "刀割样痛",
            "130/80",
        ),
        expected_records=3,
        description="JSON 链：递归清洗医疗字段，保留标识/日期/数值和嵌套结构。",
    )

    jsonl_noise = (
        "图片链接已失效",
        "系统自动生成",
        "controlled_noise_20260811",
    )
    jsonl_payload = [
        {
            "id": "jsonl-001",
            "name": "周强",
            "record_text": "T2DM患者胸闷，针扎样疼痛。图片链接已失效",
            "value": "HbA1c 6.9%",
            "clean_reference": "评测侧金标准，不应进入交付文件",
            "noise_labels": _json_labels(jsonl_noise[:1]),
        },
        {
            "id": "jsonl-002",
            "name": "陈洁",
            "record_text": "免疫系统功能正常；否认发热",
            "department": "内科",
            "output_format_hint": "jsonl",
        },
        {
            "id": "jsonl-003",
            "name": "林雪",
            "record_text": "FPG 5.8 mmol/L，BP 118/76 mmHg。系统自动生成 controlled_noise_20260811",
            "department": "全科",
            "noise": "评测侧噪声标签，不应进入交付文件",
        },
    ]
    jsonl_expected = [
        {
            "id": "jsonl-001",
            "name": "周强",
            "record_text": "2型糖尿病患者胸闷，针扎样疼痛",
            "value": "糖化血红蛋白 6.9%",
        },
        {
            "id": "jsonl-002",
            "name": "陈洁",
            "record_text": "免疫系统功能正常；否认发热",
            "department": "内科",
        },
        {
            "id": "jsonl-003",
            "name": "林雪",
            "record_text": "空腹血糖 5.8 毫摩尔/升，血压 118/76 毫米汞柱",
            "department": "全科",
        },
    ]
    jsonl_case = CorpusCase(
        case_id="jsonl-001",
        file_format="jsonl",
        file_name="case_001.jsonl",
        payload=jsonl_payload,
        expected=jsonl_expected,
        noise_labels=jsonl_noise,
        terms=(
            TermExpectation("T2DM", "2型糖尿病"),
            TermExpectation("HbA1c", "糖化血红蛋白"),
            TermExpectation("FPG", "空腹血糖"),
            TermExpectation("mmol/L", "毫摩尔/升"),
            TermExpectation("BP", "血压"),
            TermExpectation("mmHg", "毫米汞柱"),
        ),
        protected=(
            "jsonl-001",
            "周强",
            "针扎样疼痛",
            "jsonl-002",
            "免疫系统功能正常",
            "jsonl-003",
            "118/76",
        ),
        expected_records=3,
        description="JSONL 链：逐行解析、术语标准化、噪声移除和字段/记录数保护。",
    )

    return [txt1, txt2, csv_case, json_case, jsonl_case]


def _write_case(case: CorpusCase, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if case.file_format == "csv":
        rows = list(case.payload)
        fieldnames = list(rows[0].keys()) if rows else []
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return
    if case.file_format == "json":
        path.write_text(
            json.dumps(case.payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    if case.file_format == "jsonl":
        path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in case.payload) + "\n",
            encoding="utf-8",
        )
        return
    path.write_text(str(case.payload), encoding="utf-8")


def build_corpus(output_dir: Path) -> tuple[list[CorpusCase], dict[str, Any]]:
    """写入输入文件和金标准旁车文件。"""

    output_dir.mkdir(parents=True, exist_ok=True)
    from .stress_fixtures import build_stress_cases

    cases = build_stress_cases()
    for case in cases:
        _write_case(case, output_dir / case.file_name)

    manifest = {
        "schema_version": "task1-local-gold-v3",
        "scope": "local_operator_quality",
        "source_note": "固定生成的多格式压力语料，包含已学习与未见噪声；金标准独立保存，不送入算子。",
        "formats": sorted({case.file_format for case in cases}),
        "cases": [case.manifest_entry() for case in cases],
    }
    (output_dir / "gold_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return cases, manifest
