# -*- coding: utf-8 -*-
"""Task 2/3 interactive demo HTTP server."""

from __future__ import annotations

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from analysis_runtime import analyze_question, get_cached_analysis
from agent_gateway import query_nexent_agent
from dashboard_payloads import (
    disease_graph_payload,
    evaluation_payload,
    lineage_payload,
    overview_payload,
    quality_payload,
    search_diseases_payload,
)
from http_utils import json_response, read_json, static_response
from paths import ANALYTICS_DB, KG_DB, STATIC_DIR
from query_service import detect_stats_query, query_medical
from task3.report import build_report_archive
from source_management import delete_kg_source, maintenance_token_configured


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "Task3InteractiveDemo/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/":
                static_response(self, STATIC_DIR / "index.html")
            elif path.startswith("/static/"):
                static_response(self, STATIC_DIR / unquote(path.removeprefix("/static/")))
            elif path == "/api/health":
                json_response(
                    self,
                    {
                        "status": "ok",
                        "analytics_db_exists": ANALYTICS_DB.exists(),
                        "kg_db_exists": KG_DB.exists(),
                        "analytics_db": str(ANALYTICS_DB),
                        "kg_db": str(KG_DB),
                        "source_delete_enabled": maintenance_token_configured(),
                        "analysis_export_enabled": True,
                    },
                )
            elif path == "/api/overview":
                json_response(self, overview_payload())
            elif path == "/api/evaluation":
                json_response(self, evaluation_payload())
            elif path == "/api/lineage":
                json_response(self, lineage_payload())
            elif path == "/api/disease_graph":
                disease = query.get("disease", ["肺泡蛋白质沉积症"])[0]
                json_response(self, disease_graph_payload(disease))
            elif path == "/api/quality":
                json_response(self, quality_payload(query.get("q", [""])[0]))
            elif path == "/api/search_diseases":
                q = query.get("q", [""])[0]
                json_response(self, search_diseases_payload(q))
            else:
                json_response(self, {"error": "not found"}, status=404)
        except Exception as exc:  # pragma: no cover - surfaced in browser/API.
            json_response(self, {"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path in {"/api/query", "/api/agent_query"}:
                payload = read_json(self)
                question = str(payload.get("question", "")).strip()
                if not question:
                    json_response(self, {"error": "question is required"}, status=400)
                    return
                if parsed.path == "/api/agent_query":
                    json_response(self, query_nexent_agent(question))
                else:
                    json_response(self, query_medical(question))
            elif parsed.path == "/api/export_report":
                payload = read_json(self)
                analysis_id = str(payload.get("analysis_id") or "")
                question = str(payload.get("question") or "").strip()
                result = get_cached_analysis(analysis_id)
                if result is None and question:
                    result = analyze_question(question)
                if result is None:
                    raise ValueError("分析记录已失效，请重新提交问题后导出")
                filename, content = build_report_archive(result)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{quote(filename)}",
                )
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
            elif parsed.path == "/api/delete_source":
                payload = read_json(self)
                result = delete_kg_source(
                    KG_DB,
                    ANALYTICS_DB,
                    int(payload.get("source_id") or 0),
                    token=str(payload.get("token") or ""),
                    confirm_source_name=str(payload.get("source_name") or ""),
                    force_protected=bool(payload.get("force_protected")),
                )
                json_response(self, result)
            else:
                json_response(self, {"error": "not found"}, status=404)
        except PermissionError as exc:
            json_response(self, {"error": str(exc)}, status=403)
        except ValueError as exc:
            json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - surfaced in browser/API.
            json_response(self, {"error": str(exc)}, status=500)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 2/3 interactive demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"Task 2/3 interactive demo: http://{args.host}:{args.port}/")
    print(f"Analytics DB: {ANALYTICS_DB}")
    print(f"KG DB: {KG_DB}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
