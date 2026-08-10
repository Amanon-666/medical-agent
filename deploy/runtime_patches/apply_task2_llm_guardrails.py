#!/usr/bin/env python3
"""Apply the fail-closed LLM reliability guardrails to a project checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 1:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return
    if count == 0 and text.count(new) == 1:
        return
    raise RuntimeError(f"expected one old or one new match in {path}: old={count}")


def replace_any(path: Path, olds: tuple[str, ...], new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(new) == 1:
        return
    matches = [old for old in olds if text.count(old) == 1]
    if len(matches) != 1:
        raise RuntimeError(f"expected one compatible match in {path}: {len(matches)}")
    path.write_text(text.replace(matches[0], new, 1), encoding="utf-8")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    replace_once(
        root / "core/medical_extraction_validation.py",
        '                    extraction_method="llm",\n'
        '                    reliability_level="",',
        '                    extraction_method="llm",\n'
        '                    reliability_level=reliability.level,',
    )
    replace_once(
        root / "core/medical_extraction_validation.py",
        '                extraction_method="llm",\n'
        '                reliability_level="",',
        '                extraction_method="llm",\n'
        '                reliability_level=reliability.level,',
    )
    replace_any(
        root / "mcp_server/kg/persistence.py",
        (
            "        method = t.get('extraction_method') or t.get('method') or 'llm'\n",
            "        method = str(t.get('extraction_method') or t.get('method') or 'unknown').strip().lower()\n"
            "        if not reliability:\n"
            "            reliability = 'medium' if method == 'llm' else 'low'\n",
        ),
        "        method = str(t.get('extraction_method') or t.get('method') or 'unknown').strip().lower()\n"
        "        if reliability not in {'high', 'medium', 'low'}:\n"
        "            reliability = 'medium' if method == 'llm' else 'low'\n",
    )
    replace_once(
        root / "core/medical_extraction_service.py",
        '    if selected == "hybrid" and llm is not None:\n',
        '    if selected == "hybrid" and llm is None:\n'
        '        llm_error = "LLM client is not configured; returned offline results only"\n'
        '    elif selected == "hybrid":\n',
    )
    print("task2 LLM guardrails applied")


if __name__ == "__main__":
    main()
