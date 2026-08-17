# -*- coding: utf-8 -*-
"""
数据 Agent：管岗位数据库（保证准确、抗幻觉）。

硬约束（来自需求规格书第三节）：
- 职责：查库/过滤/统计，只输出数据库里存在的事实
- 不推理、不推荐、无数据不编造、查不到就说"数据库无此记录"

实现方式：纯规则查询（无 LLM），保证输出 100% 来自 jobs_clean.json。
查询 DSL（state.query）：
  {company: "字节跳动", subCat: "AI产品", keyword: "内容",
   jobType: "实习", category: "内容", companyTier: "头部大厂",
   limit: 20, offset: 0, excludeReject: true}
  {exists: {company: "字节跳动", title: "内容运营实习生"}}  → 存在性检查
  {stats: true}  → 分布统计
字段均与 jobs_clean.json 的 unified schema 对齐。
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# 允许直接运行 python agents/data_agent.py（把项目根加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.state import RecommendationState

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "data" / "jobs_clean.json"

# 允许数据Agent 输出的事实字段（溯源+判定；推理字段不属于数据库事实，不输出）
FACT_FIELDS = [
    "id", "url", "company", "title", "jdBrief", "salary", "requirements",
    "location", "education", "publishDate", "status", "createdAt", "lastSeenAt",
    "qualityScore", "jobType", "category", "subCat", "companyTier", "rejectFlags",
]


class JobDatabase:
    """岗位数据库访问层：只读、只返回事实。"""

    def __init__(self, path: Path = JOBS_PATH):
        with open(path, encoding="utf-8") as f:
            self.jobs: List[Dict[str, Any]] = json.load(f)
        self._index: Dict[str, Dict[str, Any]] = {j["id"]: j for j in self.jobs}

    # ---------- 基础能力 ----------
    def count(self) -> int:
        return len(self.jobs)

    def get_by_id(self, job_id: str) -> Dict[str, Any] | None:
        j = self._index.get(job_id)
        return self._fact(j) if j else None

    def exists(self, company: str, title: str | None = None) -> List[Dict[str, Any]]:
        """存在性检查：按公司（+可选精确 title）查，返回命中的事实列表，查不到返回 []。"""
        if title:
            hits = [j for j in self.jobs
                    if j["company"] == company and j["title"].strip() == title.strip()]
        else:
            hits = [j for j in self.jobs if j["company"] == company]
        return [self._fact(j) for j in hits]

    # ---------- 查询 ----------
    def query(self, q: Dict[str, Any]) -> List[Dict[str, Any]]:
        """结构化过滤查询（全部条件 AND）。"""
        results = self.jobs
        if "company" in q and q["company"]:
            results = [j for j in results if q["company"] in j["company"]]
        if "subCat" in q and q["subCat"]:
            results = [j for j in results if j["subCat"] == q["subCat"]]
        if "category" in q and q["category"]:
            results = [j for j in results if j["category"] == q["category"]]
        if "jobType" in q and q["jobType"]:
            results = [j for j in results if j["jobType"] == q["jobType"]]
        if "companyTier" in q and q["companyTier"]:
            results = [j for j in results if j["companyTier"] == q["companyTier"]]
        if "keyword" in q and q["keyword"]:
            kw = q["keyword"]
            results = [j for j in results
                       if kw in j["title"] or kw in (j["jdBrief"] or "")]
        if q.get("excludeReject"):
            results = [j for j in results if not j["rejectFlags"]]

        # 排序：qualityScore 降序（数据库事实字段），保持稳定
        results = sorted(results, key=lambda j: j.get("qualityScore", 0), reverse=True)

        offset = int(q.get("offset", 0))
        limit = int(q.get("limit", 0))
        if limit > 0:
            results = results[offset:offset + limit]
        elif offset > 0:
            results = results[offset:]
        return [self._fact(j) for j in results]

    def stats(self) -> Dict[str, Any]:
        """分布统计（只基于数据库事实）。"""
        from collections import Counter
        return {
            "total": len(self.jobs),
            "by_jobType": dict(Counter(j["jobType"] for j in self.jobs)),
            "by_category": dict(Counter(j["category"] for j in self.jobs)),
            "by_subCat": dict(Counter(j["subCat"] for j in self.jobs)),
            "by_companyTier": dict(Counter(j["companyTier"] for j in self.jobs)),
            "by_reject": dict(Counter(tuple(j["rejectFlags"]) for j in self.jobs)),
            "top_companies": dict(Counter(j["company"] for j in self.jobs).most_common(15)),
        }

    @staticmethod
    def _fact(j: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪为事实字段（去掉推理字段，防止数据Agent 输出非数据库内容）。"""
        return {k: j.get(k) for k in FACT_FIELDS}


def data_agent_node(state: RecommendationState) -> RecommendationState:
    """LangGraph node：数据Agent 入口。解析 query，查库，只写 query_result/query_stats。"""
    db = JobDatabase()
    q = state.get("query") or {}

    if q.get("exists"):
        cond = q["exists"]
        hits = db.exists(cond.get("company", ""), cond.get("title"))
        if hits:
            state["query_result"] = hits
            state["query_count"] = len(hits)
            state["query_stats"] = {"exists": True, "matched": len(hits)}
            state["data_agent_note"] = f"数据库存在 {len(hits)} 条匹配记录"
        else:
            state["query_result"] = []
            state["query_count"] = 0
            state["query_stats"] = {"exists": False, "matched": 0}
            state["data_agent_note"] = "数据库无此记录"
    elif q.get("stats"):
        state["query_stats"] = db.stats()
        state["query_count"] = db.count()
        state["data_agent_note"] = f"数据库共 {db.count()} 条岗位记录"
    elif q.get("by_id"):
        j = db.get_by_id(q["by_id"])
        state["query_result"] = [j] if j else []
        state["query_count"] = 1 if j else 0
        state["data_agent_note"] = "" if j else "数据库无此记录"
    elif q.get("semantic"):
        # 语义召回（ChromaDB）：自然语言 → 事实列表；向量库未构建时降级为关键词查询
        try:
            from rag.retriever import semantic_search
            where = {}
            for k in ("companyTier", "jobType", "category"):
                if q.get(k):
                    where[k] = q[k]
            hits = semantic_search(q["semantic"], top_k=int(q.get("limit", 10)) or 10,
                                   where=where or None)
            state["query_result"] = hits
            state["query_count"] = len(hits)
            state["data_agent_note"] = (
                f"语义召回 {len(hits)} 条记录" if hits else "数据库无此记录"
            )
        except Exception as e:
            kw_q = dict(q)
            kw_q["keyword"] = q["semantic"]
            kw_q.pop("semantic", None)
            hits = db.query(kw_q)
            state["query_result"] = hits
            state["query_count"] = len(hits)
            state["data_agent_note"] = (
                f"向量库未就绪，降级关键词召回 {len(hits)} 条（{type(e).__name__}）"
                if hits else "数据库无此记录"
            )
    else:
        hits = db.query(q)
        state["query_result"] = hits
        state["query_count"] = len(hits)
        state["data_agent_note"] = (
            f"查询到 {len(hits)} 条记录" if hits else "数据库无此记录"
        )
    return state


if __name__ == "__main__":
    # 命令行自测
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    db = JobDatabase()
    print("总条数:", db.count())
    demo = [
        {"exists": {"company": "字节跳动", "title": "内容运营实习生（不存在）"}},
        {"company": "字节跳动", "subCat": "AI内容", "limit": 3},
        {"keyword": "内容运营", "jobType": "实习", "excludeReject": True, "limit": 3},
    ]
    for q in demo:
        state: RecommendationState = {}
        state["query"] = q
        data_agent_node(state)
        print("\nquery:", q)
        print("note:", state.get("data_agent_note"))
        for j in state["query_result"][:3]:
            print("  ", j["company"], "|", j["title"], "|", j["subCat"], "|", j["jobType"])
