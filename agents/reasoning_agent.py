# -*- coding: utf-8 -*-
"""
推理 Agent：按画像 + 抗拒规则 + 三档定义做分档推荐。

硬约束（来自需求规格书第三节）：
- 职责：按画像+抗拒规则+三档定义做分档、生成推荐理由
- 不查库、只基于数据Agent返回的事实判断、禁止补充岗位信息
- 查不到就说查不到（由数据Agent 的 data_agent_note 传递）

实现：
- 分档 = 确定性规则（公司层级 × 核心方向 × 时期），零幻觉、可测试
- 推荐理由 = 基于 profile.json 的 core_abilities 关键词 ↔ 岗位 title/jdBrief 重叠
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.state import RecommendationState

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "config" / "profile.json"

# 核心方向：用户目标「内容 × AI × 产品」交集。subCat 命中才认为方向匹配。
# 其余 subCat（电商运营/数据分析/市场营销/游戏/项目管理/管培生/其他）不自动拒绝，
# 但也不进推荐主列表 —— 归人工过目（符合规格书「其他岗位全部列出由用户过目」）。
CORE_SUBCAT = {
    "AI内容", "AI策略", "AI产品", "内容运营", "内容创作",
    "产品运营", "产品策划", "用户运营", "用户研究",
}
# 冲刺档专属：AI 产品/策略（大厂产品内容向）
SPRINT_SUBCAT = {"AI产品", "AI策略"}

# 画像能力关键词 ↔ 岗位 JD 匹配权重（推荐理由用，全部只读数据库字段）
ABILITY_MATCH = [
    {"ability": "AI 内容创作与工具化",
     "keywords": ["Prompt", "Agent", "剧本", "短剧", "AIGC", "AI创作", "内容创作", "编导", "编剧", "AI内容"]},
    {"ability": "用户研究与数据分析",
     "keywords": ["用户画像", "用户研究", "搜索意图", "数据分析", "调研", "洞察", "用户洞察"]},
    {"ability": "产品项目与流程体系",
     "keywords": ["产品", "项目", "SOP", "流程", "产品化", "项目管理"]},
    {"ability": "内容运营与爆款",
     "keywords": ["内容运营", "新媒体", "公众号", "小红书", "爆款", "图文", "社区运营", "自媒体"]},
    {"ability": "团队管理与组织",
     "keywords": ["团队", "管理", "考核", "组织", "统筹"]},
    {"ability": "内容合规与政策",
     "keywords": ["合规", "公文", "政策", "审核"]},
]


def load_profile() -> Dict[str, Any]:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _manual_flags(job: Dict[str, Any], profile: Dict[str, Any]) -> List[str]:
    """人工过目标记：返回命中的人工过目原因列表（海外向/打标存疑）。"""
    flags = []
    flags_cfg = profile.get("reject_rules", {}).get("manual_review_flags", {})
    title = job.get("title", "")
    text = f"{title} {job.get('subCat', '')} {job.get('jdBrief', '')}"
    # 岗位名主体：业务线后缀（-抖音电商、（xx业务）等）不参与打标存疑判定
    import re as _re
    main_part = _re.split(r"[-—–（(]", title)[0].strip()
    # 海外/外语向 → 直接筛选掉
    if any(kw in text for kw in flags_cfg.get("overseas", {}).get("keywords", [])):
        flags.append("海外/外语向（英语要求高）")
    # 打标存疑：岗位名主体含行业信号词但 subCat 是核心方向
    if job.get("subCat") in CORE_SUBCAT and any(
        sig in main_part for sig in flags_cfg.get("dubious_subcat", {}).get("signals", [])
    ):
        flags.append("打标存疑（title 与 subCat 方向不一致）")
    return flags


def _reason(job: Dict[str, Any]) -> str:
    """生成推荐理由：画像能力 ↔ 岗位事实的重叠 + 真实案例佐证。全部基于数据库字段。"""
    text = f"{job.get('title', '')} {job.get('subCat', '')} {job.get('jdBrief', '')}"
    matched = []
    for am in ABILITY_MATCH:
        if any(kw in text for kw in am["keywords"]):
            matched.append(am["ability"])
    parts = [f"方向={job.get('subCat')}（核心方向匹配）"]
    if matched:
        parts.append(f"画像能力重合：{'、'.join(matched[:3])}")

    # 真实案例佐证：按公司（同公司优先）找 cases.json 里 2026 年在招岗位
    case = _find_case(job)
    if case:
        parts.append(
            f"真实案例佐证（2026年在招）：{case['company']}『{case['title']}』"
            f"（{case.get('city', '')} {case.get('salary', '')}）"
        )
    return "；".join(parts)


CASES_PATH = ROOT / "config" / "cases.json"
_CASES_CACHE = None


def _load_cases() -> Dict[str, Any]:
    global _CASES_CACHE
    if _CASES_CACHE is None and CASES_PATH.exists():
        with open(CASES_PATH, encoding="utf-8") as f:
            _CASES_CACHE = json.load(f)
    return _CASES_CACHE or {}


def _find_case(job: Dict[str, Any]) -> Dict[str, Any] | None:
    """在真实案例证据库中找佐证：同公司同方向最优先，其次同方向。"""
    cases = _load_cases()
    if not cases:
        return None
    company = job.get("company", "")
    subcat = job.get("subCat", "")
    groups = []
    for key in ("jump_chong_examples", "jump_wen_examples", "jump_doudi_examples"):
        groups.extend(cases.get(key, []))
    # 同公司
    for c in groups:
        if c.get("company") == company:
            return c
    # 同方向（subCat 关键词命中）
    for c in groups:
        if subcat and any(kw in f"{c.get('title','')}{c.get('jd_key','')}"
                          for kw in (subcat[:2],) if kw):
            return c
    return None


def tier_for_job(job: Dict[str, Any], profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    对一个岗位做分档判定（确定性规则，零幻觉）。
    返回 dict：tierJump（实习期，仅实习）/ tierFinal（冲刺期）/ final_belong / reason。
    不修改岗位事实，只附加判定结果。
    """
    if profile is None:
        profile = load_profile()
    company_tier = job.get("companyTier", "未知")
    job_type = job.get("jobType", "")
    reject = job.get("rejectFlags") or []
    subcat = job.get("subCat", "")

    out: Dict[str, Any] = {
        "job": job,
        "tierJump": None,
        "tierFinal": None,
        "final_belong": None,
        "recommendReason": None,
        "rejectReason": None,
        "manualFlags": [],
    }

    # 1) 抗拒规则：纯销售/纯技术 → 自动标红，不推荐
    if reject:
        out["rejectReason"] = "、".join(reject) + "（自动标红，人工复核）"
        return out

    # 2) 人工过目规则：海外/外语向 → 直接筛选掉；打标存疑 → 归人工过目
    #    央国企岗位例外：清洗层已做汉语言文学专业过滤，不再重复人工过目
    if company_tier != "央国企":
        manual = _manual_flags(job, profile)
        if manual:
            out["manualFlags"] = manual
            out["rejectReason"] = "；".join(manual) + "（归人工过目，不自动推荐）"
            return out

    # 3) 方向匹配：只有核心方向才算匹配；央国企不要求核心方向（清洗已按专业可报过滤）
    in_core = subcat in CORE_SUBCAT
    if company_tier == "央国企":
        # 央国企岗位直接进入保底档评估（行政/宣传/党建/综合管理等汉语言文学可报岗）
        out["tierFinal"] = "保底档"
        out["final_belong"] = "央国企（湖北本省/高起薪优先，汉语言文学可报）"
        if job_type == "实习":
            out["tierJump"] = "实习·保底"
        out["recommendReason"] = f"央国企方向匹配（汉语言文学可报，subCat={subcat}）"
        return out

    # 4) 实习期分档（实习岗才有实习档）
    if job_type == "实习":
        if not in_core:
            out["rejectReason"] = f"方向不匹配（subCat={subcat}），归人工过目"
            return out
        if company_tier == "头部大厂":
            out["tierJump"] = "实习·优选"
        elif company_tier == "中厂":
            out["tierJump"] = "实习·稳健"
        elif company_tier == "腰部":
            out["tierJump"] = "实习·保底"
        else:
            out["rejectReason"] = f"公司层级未知（{company_tier}），归人工过目"
            return out

    # 5) 冲刺期分档（所有岗位都标最终归属，标注同一岗位不同时期的档位）
    if company_tier == "头部大厂":
        if subcat in SPRINT_SUBCAT:
            out["tierFinal"] = "冲刺档"
            out["final_belong"] = "大厂产品内容向（AI策略产品/AI产品内容向）"
        elif in_core:
            out["tierFinal"] = "稳定档"
            out["final_belong"] = "大厂内容/产品内容"
    elif company_tier == "中厂":
        if in_core:
            out["tierFinal"] = "保底档"
            out["final_belong"] = "中厂方向匹配（含考编备选）"
    elif company_tier == "腰部" and in_core:
        out["tierFinal"] = "保底档"
        out["final_belong"] = "腰部公司方向匹配"

    # 6) 推荐理由（仅对匹配岗位生成）
    if out["tierJump"] or out["tierFinal"]:
        out["recommendReason"] = _reason(job)
    else:
        out["rejectReason"] = out["rejectReason"] or f"方向不匹配（subCat={subcat}），归人工过目"

    return out


def reasoning_agent_node(state: RecommendationState) -> RecommendationState:
    """LangGraph node：推理Agent 只读数据Agent 返回的 query_result，写分档结果。"""
    jobs = state.get("query_result") or []
    recommendations, rejected = [], []
    for job in jobs:
        r = tier_for_job(job)
        if r["rejectReason"] or (not r["tierJump"] and not r["tierFinal"]):
            rejected.append(r)
        else:
            recommendations.append(r)
    state["recommendations"] = recommendations
    state["rejected"] = rejected

    lines = [state.get("data_agent_note", "")]
    for tag, items in [("推荐", recommendations), ("抗拒/待人工", rejected)]:
        if items:
            lines.append(f"\n【{tag}】{len(items)} 条")
            for r in items[:8]:
                j = r["job"]
                flags = f"实习:{r['tierJump'] or '-'} 冲刺:{r['tierFinal'] or '-'}"
                extra = f" 拒绝:{r['rejectReason']}" if r["rejectReason"] else ""
                lines.append(f"  {j['company']} | {j['title']} | {j['subCat']} | {flags}{extra}")
    state["final_response"] = "\n".join(lines)
    return state


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    from agents.data_agent import JobDatabase
    db = JobDatabase()
    state: RecommendationState = {
        "query_result": db.query({"limit": 12, "excludeReject": True}),
        "data_agent_note": "查询到 12 条记录",
    }
    reasoning_agent_node(state)
    print(state["final_response"])
