# -*- coding: utf-8 -*-
"""
全量分档：把 jobs_clean.json 全部岗位跑一遍推理 Agent，结果存 data/results_full.json。
推理 Agent 是纯规则（零幻觉、无需 LLM），2232 条毫秒级完成。
用法：python scripts/build_results.py
"""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.data_agent import JobDatabase
from agents.reasoning_agent import tier_for_job, load_profile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "results_full.json"


def main():
    db = JobDatabase()
    jobs = db.jobs  # 全部岗位
    profile = load_profile()

    recommendations, rejected = [], []
    for job in jobs:
        r = tier_for_job(job, profile)
        # 只保留 UI 需要的字段 + 判定结果
        slim = {
            "id": job["id"], "company": job["company"], "title": job["title"],
            "subCat": job["subCat"], "category": job["category"],
            "companyTier": job["companyTier"], "jobType": job["jobType"],
            "location": job["location"], "salary": job["salary"],
            "education": job.get("education", ""), "publishDate": job.get("publishDate", ""),
            "jdBrief": job["jdBrief"], "jdFull": job.get("jdFull") or "",
            "requirements": job.get("requirements") or "",
            "url": job.get("url") or "",
            "rejectFlags": job["rejectFlags"],
            "tierJump": r["tierJump"], "tierFinal": r["tierFinal"],
            "final_belong": r["final_belong"],
            "recommendReason": r["recommendReason"],
            "rejectReason": r["rejectReason"],
            "manualFlags": r.get("manualFlags", []),
        }
        if r["rejectReason"] or (not r["tierJump"] and not r["tierFinal"]):
            rejected.append(slim)
        else:
            recommendations.append(slim)

    # 分档计数（供前端筛选统计）
    from collections import Counter
    stats = {
        "total": len(jobs),
        "recommended": len(recommendations),
        "rejected": len(rejected),
        "by_tierJump": dict(Counter(r["tierJump"] for r in recommendations if r["tierJump"])),
        "by_tierFinal": dict(Counter(r["tierFinal"] for r in recommendations if r["tierFinal"])),
        "by_reject": dict(Counter("+".join(r["rejectFlags"]) or "无" for r in rejected)),
        "top_companies": dict(Counter(j["company"] for j in jobs).most_common(12)),
    }

    result = {"stats": stats, "recommendations": recommendations, "rejected": rejected}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"已写入 {OUT}")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
