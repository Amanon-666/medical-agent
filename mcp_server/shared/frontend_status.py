"""
可视化平台状态模块。

该模块统一返回公网入口、服务健康状态和页面名称。
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.request


PUBLIC_DOMAIN = os.environ.get("CCF_PUBLIC_DOMAIN", "mashiro.xin").strip() or "mashiro.xin"


def _default_public_url(subdomain: str, path: str = "/") -> str:
    return f"https://{subdomain}.{PUBLIC_DOMAIN}{path}"


SERVICE_DEFINITIONS = [
    {
        "name": "task3_interactive_demo",
        "label": "医学数据智能体可视化平台",
        "port": 8765,
        "path": "/",
        "env_url": "CCF_TASK3_DEMO_URL",
        "public_subdomain": "demo",
        "start_command": "bash deploy/07_start_demo.sh",
        "purpose": "知识图谱子图、BI 图表、NL2SQL 查询和噪声拦截结果的正式展示入口",
    },
    {
        "name": "datamate_frontend",
        "label": "DataMate 前端",
        "port": 30000,
        "path": "/",
        "env_url": "CCF_DATAMATE_FRONTEND_URL",
        "public_subdomain": "datamate",
        "start_command": "docker compose up datamate-frontend",
        "purpose": "数据集、算子和清洗任务状态查看",
    },
    {
        "name": "nexent_frontend",
        "label": "Nexent 前端",
        "port": 3000,
        "path": "/",
        "env_url": "CCF_NEXENT_FRONTEND_URL",
        "public_subdomain": "nexent",
        "start_command": "docker compose up nexent",
        "purpose": "任务一、任务二、任务三智能体对话入口",
    },
]


def _public_url(service: dict) -> str:
    configured = os.environ.get(service["env_url"], "").strip()
    legacy_fragments = ("127.0.0.1", "localhost", "http://")
    raw_ip_url = re.match(r"^https?://\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/.*)?$", configured)
    # 面向智能体的结果返回稳定公网域名；本地探针和历史 IP 只用于运行态排查。
    if configured and not raw_ip_url and not any(fragment in configured for fragment in legacy_fragments):
        return configured
    return _default_public_url(service["public_subdomain"], service["path"])


def _probe_local(port: int, path: str = "/", timeout: float = 2.0) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return {"local_url": url, "reachable": True, "http_status": response.status, "error": ""}
    except urllib.error.HTTPError as exc:
        return {"local_url": url, "reachable": True, "http_status": exc.code, "error": ""}
    except Exception as exc:
        return {"local_url": url, "reachable": False, "http_status": None, "error": str(exc)}


def get_validation_frontend_status_payload() -> dict:
    services = []
    for service in SERVICE_DEFINITIONS:
        probe = _probe_local(service["port"], service["path"])
        services.append(
            {
                "name": service["name"],
                "label": service["label"],
                "purpose": service["purpose"],
                "public_url": _public_url(service),
                "status": "running" if probe["reachable"] else "stopped",
                "start_command": service["start_command"],
            }
        )

    primary = next((item for item in services if item["name"] == "task3_interactive_demo"), services[0])
    return {
        "status": "ok",
        "primary_url": primary["public_url"],
        "primary_service": primary["name"],
        "primary_label": primary["label"],
        "primary_status": primary["status"],
        "services": services,
        "note": (
            "前端只读取当前知识图谱和分析库状态。新增 DataMate 数据源需要先通过 "
            "run_task2_kg_pipeline 入库并刷新分析库，再打开或刷新前端验证。"
        ),
        "retired_services": [],
    }
