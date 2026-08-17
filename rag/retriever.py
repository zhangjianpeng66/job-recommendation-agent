# -*- coding: utf-8 -*-
"""
向量检索器（借鉴 CareerPilot rag/retriever.py）：
自然语言/岗位描述 → ChromaDB 语义召回 → 返回数据库事实字段。
只返回向量库里存在的事实，不生成任何新内容（抗幻觉）。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb

from rag.embeddings import embed_text

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "data" / "chroma_db"
COLLECTION_NAME = "jobs"

# 返回给下游的事实字段（与统一 schema 对齐）
FACT_FIELDS = [
    "id", "url", "company", "title", "jdBrief", "salary", "requirements",
    "location", "education", "publishDate", "status", "createdAt", "lastSeenAt",
    "qualityScore", "jobType", "category", "subCat", "companyTier", "rejectFlags",
]


def _get_collection():
    client = chromadb.PersistentClient(path=str(DB_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def semantic_search(query_text: str, top_k: int = 10,
                    where: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """
    语义召回：返回命中的岗位事实列表（含 _score 距离，越小越相关）。
    where 过滤示例：{"companyTier": "头部大厂"}、{"jobType": "实习"}
    """
    collection = _get_collection()
    q_vec = embed_text(query_text)
    results = collection.query(
        query_embeddings=[q_vec],
        n_results=top_k,
        where=where,
    )
    docs = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i] or {}
        job = {k: meta.get(k) for k in FACT_FIELDS}
        # rejectFlags 是 JSON 字符串存进 metadata 的，还原成 list
        if isinstance(job.get("rejectFlags"), str):
            try:
                job["rejectFlags"] = json.loads(job["rejectFlags"])
            except Exception:
                job["rejectFlags"] = []
        # 补检索文本字段（documents 里有完整拼接文本）
        job["_searchText"] = results["documents"][0][i]
        job["_score"] = round(float(results["distances"][0][i]), 4)
        docs.append(job)
    return docs


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for q in ["AI 内容运营实习", "大模型产品经理", "小红书的实习岗位"]:
        print(f"\nquery: {q}")
        for d in semantic_search(q, top_k=3):
            print(f"  {d['_score']} | {d['company']} | {d['title']} | {d['subCat']} | {d['jobType']}")
