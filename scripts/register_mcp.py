# -*- coding: utf-8 -*-
"""
把本项目的 MCP Server 注册到 Nexent。
前提：MCP Server 已启动（python mcp_server/server.py）。

用法：python scripts/register_mcp.py
"""
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clients import NexentClient


def _mcp_already_registered(client: NexentClient, mcp_url: str, service: str) -> bool:
    resp = requests.get(f"{client.config_base}/mcp/list", headers=client.headers, timeout=20)
    if not resp.ok:
        return False
    data = resp.json()
    items = data if isinstance(data, list) else data.get("data", data.get("mcp_list", []))
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict):
            continue
        item_url = str(item.get("mcp_url") or item.get("url") or item.get("server_url") or "")
        item_service = str(item.get("service_name") or item.get("name") or "")
        if item_url.rstrip("/") == mcp_url.rstrip("/") or item_service == service:
            return True
    return False


def main():
    client = NexentClient(
        config_base=os.environ.get("CCF_NEXENT_CONFIG_BASE", "http://127.0.0.1:5010"),
        runtime_base=os.environ.get("CCF_NEXENT_RUNTIME_BASE", "http://127.0.0.1:5014"),
        email=os.environ.get("CCF_NEXENT_EMAIL", "suadmin@nexent.com"),
        password=os.environ.get("CCF_NEXENT_PASSWORD", ""),
    )
    client.login()
    print("Nexent 登录成功")

    mcp_url = os.environ.get("CCF_MCP_URL", "http://127.0.0.1:8900/mcp")
    service = os.environ.get("CCF_MCP_SERVICE_NAME", "medical-ai")

    if _mcp_already_registered(client, mcp_url, service):
        print(f"MCP server 已注册，跳过 add: {service} -> {mcp_url}")
    else:
        print(f"注册 MCP server: {service} -> {mcp_url}")
        result = client.add_mcp_server(mcp_url, service)
        print("注册结果:", result)

    # 先列工具验证连通
    print(f"列出 MCP server 工具: {mcp_url}")
    tools = client.list_mcp_tools(mcp_url, service)
    print(tools)

    print("扫描 MCP 工具...")
    scan = client.scan_tools()
    print("扫描结果:", scan)


if __name__ == "__main__":
    main()
