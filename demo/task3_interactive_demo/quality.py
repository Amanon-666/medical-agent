# -*- coding: utf-8 -*-
"""
可视化平台质量审计模块。

该模块对噪声拦截记录进行聚合、脱敏和展示过滤。
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from db_utils import connect
from paths import KG_DB


SYMPTOM_CUES = (
    "痛", "疼", "热", "烧", "咳", "痰", "喘", "泻", "吐", "呕", "血", "肿",
    "麻", "痒", "晕", "厥", "抽", "搐", "悸", "乏力", "无力", "困难", "障碍",
    "呼吸", "发绀", "紫绀", "胸闷", "低热", "高热", "水肿", "腹泻", "恶心",
)

COMMON_SURNAME_CHARS = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁"
    "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍"
    "虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程"
    "邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧"
    "隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹束龙"
    "叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双"
    "闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚"
    "农温别庄晏柴瞿阎闫充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都"
    "耿满弘匡国文寇广禄阙东殴殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛"
    "阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查後荆红游竺权逯盖益桓公"
    "代岳栗兰"
)

KNOWN_BAD_FACT_VALUES = {"测试", "毓卓", "驻站医", "衣玉品"}
SENSITIVE_QUALITY_TERMS = (
    "阴茎",
    "早泄",
    "阳痿",
    "勃起",
    "龟头",
    "睾丸",
    "阴道",
    "性交",
    "包皮",
    "人民",
)
PERSON_NAME_NOISE = ("建国", "丽丽", "岳军", "亚庆", "卫庆", "代明", "毓卓", "衣玉品", "驻站医", "疑似姓名")
QUALITY_DISPLAY_TEXT_KEYS = {"可疑值", "示例证据", "原始证据"}


def looks_like_person_name(value: str) -> bool:
    text = re.sub(r"\s+", "", str(value or ""))
    if len(text) not in {2, 3}:
        return False
    if any(cue in text for cue in SYMPTOM_CUES):
        return False
    return text[0] in COMMON_SURNAME_CHARS


def load_quality_values() -> set[str]:
    if not KG_DB.exists():
        return set()
    try:
        with connect(KG_DB) as conn:
            rows = conn.execute("SELECT DISTINCT value FROM kg_quality_issues").fetchall()
            return {str(row[0]) for row in rows if row[0]}
    except sqlite3.Error:
        return set()


def is_suspicious_fact_value(value: Any, known_values: set[str] | None = None) -> bool:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return True
    known = known_values if known_values is not None else load_quality_values()
    if text in KNOWN_BAD_FACT_VALUES or text in known:
        return True
    return looks_like_person_name(text)


def filter_suspicious_rows(rows: list[dict[str, Any]], value_key: str) -> tuple[list[dict[str, Any]], int]:
    known = load_quality_values()
    clean_rows = [row for row in rows if not is_suspicious_fact_value(row.get(value_key), known)]
    return clean_rows, len(rows) - len(clean_rows)


def mask_quality_text(value: Any) -> str:
    text = str(value or "")
    for term in SENSITIVE_QUALITY_TERMS:
        text = text.replace(term, "敏感词")
    for name in PERSON_NAME_NOISE:
        text = text.replace(name, "疑似姓名")
    return text


def mask_quality_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    masked = []
    for row in rows:
        next_row = {}
        for key, value in row.items():
            next_row[key] = mask_quality_text(value) if key in QUALITY_DISPLAY_TEXT_KEYS else value
        masked.append(next_row)
    return masked


def should_hide_quality_value(value: Any) -> bool:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return True
    if any(bad in text for bad in KNOWN_BAD_FACT_VALUES):
        return True
    if any(term in text for term in SENSITIVE_QUALITY_TERMS):
        return True
    if any(name in text for name in PERSON_NAME_NOISE):
        return True
    return looks_like_person_name(text)


def classify_hidden_quality_text(value: Any) -> str | None:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return "空值或无效字段"
    if any(bad in text for bad in KNOWN_BAD_FACT_VALUES):
        return "测试/占位数据"
    if any(term in text for term in SENSITIVE_QUALITY_TERMS):
        return "敏感词"
    if any(name in text for name in PERSON_NAME_NOISE) or looks_like_person_name(text):
        return "疑似姓名"
    return None


def classify_hidden_quality_row(row: dict[str, Any]) -> str | None:
    for key in QUALITY_DISPLAY_TEXT_KEYS:
        if key not in row:
            continue
        category = classify_hidden_quality_text(row.get(key))
        if category:
            return category
    return None


def should_hide_quality_row(row: dict[str, Any]) -> bool:
    for key in QUALITY_DISPLAY_TEXT_KEYS:
        if key not in row:
            continue
        value = row.get(key)
        if should_hide_quality_value(value):
            return True
    return False


def filter_quality_display_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    visible = [row for row in rows if not should_hide_quality_row(row)]
    return visible[:limit]


def summarize_hidden_quality_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, int] = {}
    fields: dict[str, set[str]] = {}
    for row in rows:
        category = classify_hidden_quality_row(row)
        if category:
            count = int(row.get("出现次数") or row.get("拦截数量") or 1)
            grouped[category] = grouped.get(category, 0) + count
            field = str(row.get("来源字段") or row.get("字段") or "").strip()
            if field:
                fields.setdefault(category, set()).add(field)
    return [
        {
            "可疑值": category,
            "出现次数": count,
            "示例证据": build_grouped_quality_evidence(category, fields.get(category, set())),
            "说明": "已拦截，未进入主图谱/问答库",
        }
        for category, count in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def build_grouped_quality_evidence(category: str, fields: set[str]) -> str:
    field_text = "、".join(sorted(fields)) if fields else "症状/实体候选字段"
    rules = {
        "测试/占位数据": "命中测试词、占位词或调试样例规则",
        "疑似姓名": "命中中文姓名形态规则或姓名占位标记",
        "敏感词": "命中敏感词规则",
        "空值或无效字段": "命中空值、无效字段规则",
    }
    return f"命中字段：{field_text}；{rules.get(category, '命中质量审计规则')}；具体值已隐藏"
