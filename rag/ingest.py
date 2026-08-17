# -*- coding: utf-8 -*-
"""
岗位向量库构建：读 data/jobs_clean.json → ChromaDB（本地持久化）。
用法：python -m rag.ingest
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chromadb

from rag.embeddings import embed_batch

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "data" / "jobs_clean.json"
DB_DIR = ROOT / "data" / "chroma_db"
COLLECTION_NAME = "jobs"

# 用于检索的文本字段（只拼数据库事实，供语义召回）
SEARCH_TEXT_FIELDS = ["title", "subCat", "category", "company", "jdBrief"]
# 写入 metadata 的字段（全部来自统一 schema 的事实字段）
META_FIELDS = ["id", "company", "title", "subCat", "category", "companyTier",
               "jobType", "rejectFlags", "location", "education", "salary"]


def build_text(job: dict) -> str:
    parts = [str(job.get(f, "")) for f in SEARCH_TEXT_FIELDS if job.get(f)]
    return " ".join(p for p in parts if p)


def build_metadata(job: dict) -> dict:
    meta = {}
    for f in META_FIELDS:
        v = job.get(f)
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        meta[f] = v
    return meta


def ingest(force: bool = False):
    with open(JOBS_PATH, encoding="utf-8") as f:
        jobs = json.load(f)

    client = chromadb.PersistentClient(path=str(DB_DIR))
    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
    collection = client.get_or_create_collection(COLLECTION_NAME)

    existing = collection.count()
    if existing >= len(jobs):
        print(f"向量库已是最新：{existing} 条（跳过，force=True 可重建）")
        return

    texts = [build_text(j) for j in jobs]
    metas = [build_metadata(j) for j in jobs]
    ids = [j["id"] for j in jobs]

    print(f"构建向量库：{len(jobs)} 条岗位（首次会加载 bge-small-zh 模型，较慢）...")
    vectors = embed_batch(texts)
    batch = 128
    for i in range(0, len(jobs), batch):
        collection.upsert(
            ids=ids[i:i + batch],
            embeddings=vectors[i:i + batch],
            documents=texts[i:i + batch],
            metadatas=metas[i:i + batch],
        )
        print(f"  已写入 {min(i + batch, len(jobs))}/{len(jobs)}")
    print(f"完成：collection={COLLECTION_NAME}，条数={collection.count()}")


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    force = "--force" in sys.argv
    ingest(force=force)
