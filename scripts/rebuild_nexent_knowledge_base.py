#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将本地文档清单以低并发方式重建到 Nexent 知识库。

这个脚本针对 Nexent v2.0.x 的兼容路径：先把短片段作为源文件上传到
MinIO，再用文档写入接口写入同一个向量索引。它不会删除旧知识库，也不会
调用旧版实例上容易堆积异步任务的 ``/file/process``。

输入清单的格式是 ``[{"title": ..., "content": ...}, ...]``。当原始文件包
不可取得时，清单可以由 Nexent 中仍保留的完整分片重组而来；这种输入应在
交付说明中明确标为“重组文档”，不能冒充原始文件包。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests


DEFAULT_CONFIG_BASE = os.environ.get("CCF_NEXENT_CONFIG_BASE", "http://127.0.0.1:5010").rstrip("/")
DEFAULT_EMAIL = os.environ.get("CCF_NEXENT_EMAIL", "")
DEFAULT_MODEL = "BAAI/bge-large-zh-v1.5"
DEFAULT_EMBEDDING_DIM = 1024


class NexentRequestError(RuntimeError):
    """包含接口状态码和响应摘要的可读错误。"""


def _response_summary(response: requests.Response) -> str:
    try:
        payload = response.json()
        return json.dumps(payload, ensure_ascii=False)[:600]
    except ValueError:
        return response.text[:600]


def _login(session: requests.Session, base_url: str, email: str, password: str) -> str:
    response = session.post(
        f"{base_url}/user/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if response.status_code != 200:
        raise NexentRequestError(f"登录失败 ({response.status_code}): {_response_summary(response)}")
    try:
        return response.json()["data"]["session"]["access_token"]
    except (KeyError, TypeError, ValueError) as exc:
        raise NexentRequestError("登录响应中没有 access_token") from exc


def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    retries: int,
    pause_seconds: float,
    **kwargs: Any,
) -> requests.Response:
    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            response = session.request(method, url, headers=headers, **kwargs)
            if 200 <= response.status_code < 300:
                return response
            last_error = f"HTTP {response.status_code}: {_response_summary(response)}"
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            time.sleep(pause_seconds * (attempt + 1))
    raise NexentRequestError(f"请求失败，已重试 {retries} 次: {last_error}")


def _load_segments(manifest_path: Path, max_chars: int) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("文档清单必须是 JSON 数组")

    segments: list[dict[str, Any]] = []
    for doc_no, document in enumerate(payload, start=1):
        if not isinstance(document, dict):
            raise ValueError(f"第 {doc_no} 条文档不是对象")
        title = str(document.get("title") or f"document-{doc_no}")
        content = str(document.get("content") or "")
        if not content:
            continue
        parts = [content[pos : pos + max_chars] for pos in range(0, len(content), max_chars)]
        for part_no, part in enumerate(parts, start=1):
            filename = f"mediflow_{doc_no:03d}_{part_no:03d}.txt"
            body = f"标题：{title}\n来源文档序号：{doc_no}\n内容片段：\n{part}"
            segments.append(
                {
                    "filename": filename,
                    "body": body,
                    "title": title,
                    "source_document_no": doc_no,
                    "part_no": part_no,
                    "total_parts": len(parts),
                }
            )
    return segments


def _create_index(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    display_name: str,
    embedding_model_name: str,
    embedding_dim: int,
    retries: int,
    pause_seconds: float,
) -> str:
    url = f"{base_url}/indices/{quote(display_name, safe='')}"
    response = _request_with_retry(
        session,
        "POST",
        url,
        headers=headers,
        params={"embedding_dim": embedding_dim},
        json={
            "embedding_model_name": embedding_model_name,
            "preserve_source_file": True,
            "ingroup_permission": "EDIT",
            "group_ids": [],
        },
        retries=retries,
        pause_seconds=pause_seconds,
        timeout=60,
    )
    try:
        index_name = response.json().get("id")
    except ValueError as exc:
        raise NexentRequestError("创建知识库响应不是 JSON") from exc
    if not index_name:
        raise NexentRequestError("创建知识库响应中没有索引名 id")
    return str(index_name)


def _iter_batches(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def rebuild(args: argparse.Namespace) -> int:
    if args.max_chars < 80:
        raise ValueError("--max-chars 过小，至少应为 80")
    if args.batch_size < 1:
        raise ValueError("--batch-size 必须为正数")
    if not args.password:
        raise ValueError("请通过 --password 或 CCF_NEXENT_PASSWORD 提供密码")
    if not args.index_name and not args.create_name:
        raise ValueError("请提供已有 --index-name，或提供 --create-name 创建并行库")
    if args.index_name and args.create_name:
        raise ValueError("--index-name 与 --create-name 只能二选一")
    if args.resume_mapping and args.create_name:
        raise ValueError("--resume-mapping 不能与 --create-name 同时使用")

    segments = _load_segments(Path(args.manifest), args.max_chars)
    resume_data: dict[str, Any] | None = None
    if args.resume_mapping:
        resume_path = Path(args.resume_mapping)
        if not resume_path.exists():
            raise ValueError(f"续跑映射文件不存在：{resume_path}")
        resume_data = json.loads(resume_path.read_text(encoding="utf-8"))
        if resume_data.get("index_name") != args.index_name:
            raise ValueError("续跑映射中的 index_name 与当前参数不一致")
    print(f"待处理文档片段：{len(segments)}")

    session = requests.Session()
    token = _login(session, args.base_url, args.email, args.password)
    headers = {"Authorization": f"Bearer {token}"}
    json_headers = {**headers, "Content-Type": "application/json"}

    index_name = args.index_name
    if args.create_name:
        index_name = _create_index(
            session,
            args.base_url,
            json_headers,
            args.create_name,
            args.embedding_model_name,
            args.embedding_dim,
            args.retries,
            args.pause_seconds,
        )
        print(f"已创建知识库索引：{index_name}")

    folder = args.folder or f"attachments/mediflow-kb-{int(time.time())}"
    if resume_data is not None:
        saved_folder = str(resume_data.get("folder") or "")
        if args.folder and saved_folder != args.folder:
            raise ValueError("续跑映射中的 folder 与当前参数不一致")
        folder = saved_folder or folder
        completed = {
            item.get("filename")
            for item in resume_data.get("uploaded", [])
            if item.get("filename")
        }
        segments = [item for item in segments if item["filename"] not in completed]
        retry_names = {item["filename"] for item in segments}
        resume_data["failed"] = [
            item
            for item in resume_data.get("failed", [])
            if item.get("filename") not in retry_names
        ]
    result: dict[str, Any] = {
        "index_name": index_name,
        "folder": folder,
        "embedding_model_name": args.embedding_model_name,
        "embedding_dim": args.embedding_dim,
        "manifest": str(Path(args.manifest).resolve()),
        "uploaded": [],
        "failed": [],
    }
    if resume_data is not None:
        result = resume_data
        result["folder"] = folder
        result["manifest"] = str(Path(args.manifest).resolve())

    for batch_no, batch in enumerate(_iter_batches(segments, args.batch_size), start=1):
        try:
            upload = _request_with_retry(
                session,
                "POST",
                f"{args.base_url}/file/upload",
                headers=headers,
                data={"destination": "minio", "folder": folder, "index_name": index_name},
                files=[
                    ("file", (item["filename"], item["body"].encode("utf-8"), "text/plain"))
                    for item in batch
                ],
                retries=args.retries,
                pause_seconds=args.pause_seconds,
                timeout=180,
            )
            payload = upload.json()
            paths = payload.get("uploaded_file_paths") or []
            names = payload.get("uploaded_filenames") or []
            # Nexent 遇到重名文件会把返回的 filename 改成 *_1、*_2；
            # 先按返回名去掉该后缀匹配，只有完整返回时才使用顺序兜底。
            originals = {item["filename"] for item in batch}
            path_by_name: dict[str, str] = {}
            for returned_name, path in zip(names, paths):
                candidate = returned_name
                while candidate not in originals:
                    reduced = re.sub(r"_\d+(?=\.[^.]+$)", "", candidate, count=1)
                    if reduced == candidate:
                        break
                    candidate = reduced
                if candidate in originals:
                    path_by_name[candidate] = path
            if not path_by_name and len(paths) == len(batch):
                path_by_name = {
                    item["filename"]: paths[pos]
                    for pos, item in enumerate(batch)
                }
        except (NexentRequestError, ValueError) as exc:
            path_by_name = {}
            result["failed"].extend(
                {"filename": item["filename"], "stage": "upload", "error": str(exc)[:600]}
                for item in batch
            )
        missing = [item for item in batch if item["filename"] not in path_by_name]
        for item in missing:
            result["failed"].append({"filename": item["filename"], "stage": "upload"})

        documents = []
        for item in batch:
            path = path_by_name.get(item["filename"])
            if not path:
                continue
            documents.append(
                {
                    "content": item["body"],
                    "path_or_url": path,
                    "source_type": "minio",
                    "file_size": len(item["body"].encode("utf-8")),
                    "filename": item["filename"],
                    "metadata": {
                        "title": item["title"],
                        "source": "reconstructed_manifest",
                        "source_document_no": item["source_document_no"],
                        "part_no": item["part_no"],
                        "total_parts": item["total_parts"],
                        "embedding_model": args.embedding_model_name,
                        "embedding_dim": args.embedding_dim,
                    },
                }
            )

        if documents:
            try:
                _request_with_retry(
                    session,
                    "POST",
                    f"{args.base_url}/indices/{index_name}/documents",
                    headers=json_headers,
                    json=documents,
                    retries=args.retries,
                    pause_seconds=args.pause_seconds,
                    timeout=180,
                )
                result["uploaded"].extend(
                    {"filename": item["filename"], "path_or_url": path_by_name[item["filename"]]}
                    for item in batch
                    if item["filename"] in path_by_name
                )
            except NexentRequestError as exc:
                result["failed"].extend(
                    {"filename": item["filename"], "stage": "index", "error": str(exc)[:600]}
                    for item in batch
                    if item["filename"] in path_by_name
                )

        print(
            f"批次 {batch_no}: {min(batch_no * args.batch_size, len(segments))}/{len(segments)} "
            f"成功 {len(result['uploaded'])}，失败 {len(result['failed'])}"
        )
        output = Path(args.mapping_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(args.pause_seconds)

    output = Path(args.mapping_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"映射记录：{output}")
    if result["failed"]:
        print("存在失败项；请先检查 Nexent 服务状态，再按映射记录补跑。", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="文档清单 JSON 路径")
    parser.add_argument("--index-name", default="", help="已有 Nexent 内部索引名")
    parser.add_argument("--create-name", default="", help="创建并行知识库时使用的显示名")
    parser.add_argument("--base-url", default=DEFAULT_CONFIG_BASE)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=os.environ.get("CCF_NEXENT_PASSWORD", ""))
    parser.add_argument("--embedding-model-name", default=DEFAULT_MODEL)
    parser.add_argument("--embedding-dim", type=int, default=DEFAULT_EMBEDDING_DIM)
    parser.add_argument("--max-chars", type=int, default=450)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--pause-seconds", type=float, default=3.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--folder", default="", help="MinIO 源文件目录；默认按时间生成")
    parser.add_argument(
        "--resume-mapping",
        default="",
        help="从已有映射记录续跑；只重试未成功片段",
    )
    parser.add_argument(
        "--mapping-output",
        default="output/nexent_kb_rebuild_mapping.json",
        help="保存上传路径与失败项的映射记录",
    )
    return parser


if __name__ == "__main__":
    try:
        raise SystemExit(rebuild(build_parser().parse_args()))
    except (ValueError, NexentRequestError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2)
