"""任务一 PDF 分派、远程解析和质量证据回归测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CCF_DATAMATE_BASE", "http://datamate.test")
os.environ.setdefault("CCF_DATASET_VOLUME", "/tmp/datamate-datasets")

from mcp_server.task1.chains import task1_mixed_chain_map
from mcp_server.task1.datasets import classify_source_file, count_source_file_groups
from mcp_server.task1.inspection import build_preview_samples, recommend_chain, summarize_file_types
from mcp_server.task1.mineru_client import MineruAgentClient
from mcp_server.task1.pdf_support import (
    PARSER_ID,
    inspect_pdf_capability,
    markdown_to_plain_text,
    parse_pdf_files,
    summarize_pdf_evidence,
)


class _Response:
    def __init__(self, data: dict | None = None, *, status_code: int = 200, text: str = ""):
        self._data = data or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self) -> dict:
        return self._data


class _Session:
    def __init__(self) -> None:
        self.uploaded = b""

    def post(self, url: str, **_kwargs) -> _Response:
        self.created_url = url
        return _Response(
            {"code": 0, "msg": "ok", "data": {"task_id": "task-1", "file_url": "https://upload.test/file"}}
        )

    def put(self, _url: str, *, data, **_kwargs) -> _Response:
        self.uploaded = data.read()
        return _Response(status_code=200)

    def get(self, url: str, **_kwargs) -> _Response:
        if url.endswith("task-1"):
            return _Response(
                {"code": 0, "msg": "ok", "data": {"state": "done", "markdown_url": "https://cdn.test/full.md"}}
            )
        if url == "https://cdn.test/full.md":
            return _Response(text="# 糖尿病病例\n\n患者糖化血红蛋白升高。")
        return _Response({"code": -60012, "msg": "task not found"}, status_code=200)


class _CapabilityClient:
    base_url = "https://mineru.net/api/v1/agent"

    @staticmethod
    def probe() -> tuple[bool, str]:
        return True, "远程接口可达"


class PdfRoutingTests(unittest.TestCase):
    def test_existing_formats_keep_original_groups(self) -> None:
        self.assertEqual(classify_source_file("病例.txt"), ("text", "txt"))
        self.assertEqual(classify_source_file("病例.csv"), ("csv", "csv"))
        self.assertEqual(classify_source_file("病例.json"), ("json", "json"))
        self.assertEqual(classify_source_file("病例.jsonl"), ("jsonl", "jsonl"))

    def test_pdf_is_classified_and_recommended(self) -> None:
        self.assertEqual(classify_source_file("指南.PDF"), ("pdf", "pdf"))
        self.assertEqual(classify_source_file("指南", "application/pdf"), ("pdf", "pdf"))
        self.assertEqual(summarize_file_types([["指南.pdf", "", "application/pdf"]]), {"pdf": 1})
        self.assertEqual(recommend_chain({"pdf"})[0], "pdf_chain")
        self.assertEqual(recommend_chain({"pdf", "txt"})[0], "mixed")
        counts, unsupported = count_source_file_groups([["指南.pdf", "", "pdf"]])
        self.assertEqual(counts["pdf"], 1)
        self.assertEqual(unsupported, [])

    def test_pdf_preview_does_not_read_binary_as_text(self) -> None:
        def fail_read(_path: str) -> str:
            raise AssertionError("PDF binary must not be read as UTF-8 text")

        samples, hint = build_preview_samples(
            [["指南.pdf", "/dataset/id/指南.pdf", "pdf"]],
            "/volume",
            "id",
            fail_read,
        )
        self.assertFalse(hint)
        self.assertIn("PDF", samples[0]["preview"])

    def test_pdf_chain_reuses_text_cleaners_after_remote_preprocessing(self) -> None:
        chains = task1_mixed_chain_map()
        self.assertEqual(chains["pdf"], chains["text"])
        self.assertNotIn("MineruFormatter", chains["pdf"])

    def test_existing_structured_chains_are_unchanged(self) -> None:
        chains = task1_mixed_chain_map()
        self.assertEqual(chains["csv"][-1], "TableColumnCleaner")
        self.assertEqual(chains["json"][-1], "JsonFieldCleaner")
        self.assertEqual(chains["jsonl"][-1], "JsonFieldCleaner")


class MineruRemoteClientTests(unittest.TestCase):
    def test_parser_has_no_default_task_deadline(self) -> None:
        client = MineruAgentClient(session=_Session(), sleep=lambda _seconds: None)
        self.assertIsNone(client.timeout_seconds)

    def test_signed_upload_poll_and_download(self) -> None:
        session = _Session()
        client = MineruAgentClient(session=session, sleep=lambda _seconds: None)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "糖尿病指南.pdf"
            source.write_bytes(b"%PDF-1.4\nfixture")
            result = client.parse_file(source)
        self.assertEqual(result.task_id, "task-1")
        self.assertIn("糖化血红蛋白", result.markdown)
        self.assertEqual(session.uploaded, b"%PDF-1.4\nfixture")

    def test_markdown_is_converted_to_cleaning_text(self) -> None:
        plain = markdown_to_plain_text(
            "## 检查\n\n| 项目 | 结果 |\n| --- | --- |\n| HbA1c | 8.2% |\n\n[来源](https://example.test)"
        )
        self.assertIn("检查", plain)
        self.assertIn("HbA1c", plain)
        self.assertIn("来源", plain)
        self.assertNotIn("https://example.test", plain)

    def test_parse_pdf_files_writes_txt_and_evidence(self) -> None:
        session = _Session()
        client = MineruAgentClient(session=session, sleep=lambda _seconds: None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "病例.pdf"
            source.write_bytes(b"%PDF-1.4\nfixture")
            converted, reports = parse_pdf_files([source], root / "parsed", client=client)
            output_path = converted[0][0]
            evidence = summarize_pdf_evidence([source], [output_path], reports)
            content = output_path.read_text(encoding="utf-8")
        self.assertTrue(evidence["conversion_verified"])
        self.assertEqual(evidence["parser"], PARSER_ID)
        self.assertIn("糖尿病病例", content)
        self.assertEqual(converted[0][1], "txt")


class PdfCapabilityTests(unittest.TestCase):
    def test_remote_service_is_available_without_datamate_operator(self) -> None:
        result = inspect_pdf_capability(client=_CapabilityClient())
        self.assertTrue(result["available"])
        self.assertEqual(result["parser_id"], PARSER_ID)
        self.assertEqual(result["limits"]["max_pages"], 20)


if __name__ == "__main__":
    unittest.main()
