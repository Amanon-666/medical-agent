# -*- coding: utf-8 -*-
"""
DataMate 平台 API 客户端。

该客户端用于 Notebook 和部署脚本中的轻量查询；任务一在线清洗的完整
编排位于 ``mcp_server/task1``，那里会直接访问 DataMate 数据集、清洗
任务和运行时文件。
"""
import requests
from typing import List, Dict, Any, Optional


class DataMateClient:
    def __init__(self, api_base: str = "http://localhost:8080"):
        self.api_base = api_base.rstrip("/")

    # ---------- 算子市场 ----------
    def list_operators(self, keyword: str = "") -> Dict[str, Any]:
        resp = requests.post(f"{self.api_base}/api/operators/list",
                             json={"keyword": keyword})
        resp.raise_for_status()
        return resp.json()

    # ---------- 数据集 ----------
    def list_datasets(self, page: int = 0, size: int = 20) -> Dict[str, Any]:
        resp = requests.get(f"{self.api_base}/api/v1/datasets",
                            params={"page": page, "size": size})
        resp.raise_for_status()
        return resp.json()

    def create_dataset(self, name: str, dataset_type: str = "TEXT") -> Dict[str, Any]:
        """该轻量客户端不负责创建数据集；请使用任务一 MCP 工具完成。"""
        raise NotImplementedError("create_dataset is handled by task1 MCP tools")

    def upload_file(self, dataset_id: str, file_path: str) -> Dict[str, Any]:
        """该轻量客户端不负责上传文件；请使用任务一 MCP 工具完成。"""
        raise NotImplementedError("upload_file is handled by task1 MCP tools")

    # ---------- 清洗管道 ----------
    def run_pipeline(self, dataset_id: str, operators: List[Dict[str, Any]]) -> Dict[str, Any]:
        """该轻量客户端不负责运行清洗管道；请使用任务一 MCP 工具完成。"""
        raise NotImplementedError("run_pipeline is handled by task1 MCP tools")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """该轻量客户端不负责查询清洗状态；请使用任务一 MCP 工具完成。"""
        raise NotImplementedError("get_task_status is handled by task1 MCP tools")
