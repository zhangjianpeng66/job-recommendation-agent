# -*- coding: utf-8 -*-
"""
数据清洗：data/jobs.json → data/jobs_clean.json（统一 schema）
规则（用户已确认）：
  1. 排除 jobType=社招（库里 24 条社招均为正式岗，无日常实习）
  2. 排除 status=已下线
  3. 排除 qualityScore=0
  4. 补全 subCat（空值用关键词规则，复用前身 profile-filter.ts 的 16 类）
  5. 新增 companyTier（公司分级，映射来自 config/profile.json）
  6. 新增 rejectFlags（纯销售/纯技术，来自 config/profile.json 的 hard_reject）
输出统一 schema：溯源字段 + 判定字段 + 推理输出字段（初始为空）
"""
import json
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "job-aggregation-site" / "data" / "jobs.json"
RAW_JOBS = ROOT / "data" / "raw_jobs.json"   # 爬虫增量数据（可不存在）
OUT = ROOT / "data" / "jobs_clean.json"
PROFILE = ROOT / "config" / "profile.json"

# ---------- 载入配置 ----------
with open(PROFILE, encoding="utf-8") as f:
    CFG = json.load(f)
HARD_SALES = CFG["reject_rules"]["hard_reject"]["sales"]
HARD_TECH = CFG["reject_rules"]["hard_reject"]["tech"]
WATCH = CFG["reject_rules"]["manual_review"]["watch"]

# 纯销售强词（title 命中即标红；整词匹配，避免 CBD/BD 误伤）
SALES_STRONG = ["销售代表", "销售顾问", "销售专员", "销售经理", "销售总监", "KA销售",
                "电销", "电话营销", "电话销售", "商务拓展", "广告销售", "商务销售",
                "商业销售", "客户经理", "业绩提成", "销售工程师"]
# title 含"销售"但属于产品/支持岗的例外词（不标红，归人工过目）
SALES_EXCEPT = ["销售运营", "销售管理", "销售产品", "销售数据", "销售策略", "销售支持",
                "销售培训", "销售助理", "销售平台", "智能销售"]
# 产品/内容/管理类信号词：title 含这些词则不判纯技术
NON_TECH_SIGNAL = ["产品", "运营", "内容", "策划", "经理", "专员", "助理", "管理",
                   "研究", "分析", "创作", "编辑", "主编", "策划师"]
COMPANY_TIERS = CFG["company_tiers"]
TIER_TO_NAME = {}
for tier, names in COMPANY_TIERS.items():
    for n in names:
        TIER_TO_NAME[n] = tier

# ---------- subCat 规则（复用前身 profile-filter.ts 的 SUBCAT_RULES，转 Python） ----------
SUBCAT_RULES = [
    ("AI产品", [r"AI产品", r"大模型产品", r"LLM产品", r"AIGC产品", r"智能体产品", r"Agent产品", r"AI Coding产品", r"AI平台产品"]),
    ("AI策略", [r"AI策略", r"策略产品", r"推荐策略", r"模型策略", r"算法策略产品"]),
    ("AI内容", [r"AI内容", r"AIGC.*(运营|内容|创作)", r"AI视频", r"AI短剧", r"AI漫剧", r"AI创作", r"AI音乐", r"AI绘画", r"数字人"]),
    ("产品策划", [r"产品策划", r"产品经理", r"产品设计", r"B端产品", r"C端产品"]),
    ("产品运营", [r"产品运营", r"商业化运营", r"增长运营", r"运营.*产品"]),
    ("内容创作", [r"编剧", r"文案", r"内容创作", r"创作.*(策划|方向)", r"视频制作", r"剪辑", r"摄影", r"编导", r"稿件", r"小说", r"剧本"]),
    ("内容运营", [r"内容运营", r"社区运营", r"新媒体运营", r"内容.*运营", r"运营.*内容", r"图文", r"自媒体"]),
    ("电商运营", [r"电商运营", r"行业运营", r"商家运营", r"店铺运营", r"商品运营", r"电商.*运营", r"跨境.*运营", r"货品运营"]),
    ("用户运营", [r"用户运营", r"会员运营", r"社群运营", r"粉丝运营", r"用户增长", r"留存"]),
    ("数据分析", [r"数据分析", r"商业分析", r"数据运营", r"经营分析", r"数据产品", r"数据分析师"]),
    ("用户研究", [r"用户研究", r"市场研究", r"用户洞察", r"调研"]),
    ("市场营销", [r"市场营销", r"品牌", r"广告投放", r"商务拓展", r"BD", r"营销策划", r"市场推广", r"媒介"]),
    ("游戏", [r"游戏策划", r"游戏运营", r"游戏发行", r"数值策划", r"系统策划", r"关卡策划"]),
    ("项目管理", [r"项目管理", r"项目助理", r"项目经理"]),
    ("管培生", [r"管培生"]),
]


def gen_unified_id(company: str, title: str) -> str:
    """为爬虫增量岗位生成稳定 id（company+title 哈希）。"""
    import hashlib
    h = hashlib.md5(f"{company}|{title}".encode("utf-8")).hexdigest()[:6]
    return f"j_{h}"


def classify_subcat(title: str, jdBrief: str) -> str:
    text = title + " " + (jdBrief or "")[:200]
    for cat, pats in SUBCAT_RULES:
        if any(re.search(p, text) for p in pats):
            return cat
    return "其他"


def detect_reject(title: str, subcat: str, jdBrief: str) -> list:
    """返回抗拒标记列表：['纯销售'] / ['纯技术'] / 两者 / []
    title 命中强词才标红；销售例外词（销售运营/销售产品等）不标红，归人工过目。"""
    flags = []
    t = title or ""
    # 纯销售：命中强词（整词匹配），或 title 以"销售"结尾（非例外词）
    if any(kw in t for kw in SALES_STRONG) or (
        re.search(r"销售$", t) and not any(ex in t for ex in SALES_EXCEPT)
    ):
        flags.append("纯销售")
    # 纯技术：命中技术词，且 title 无产品/内容/管理类信号词
    elif any(kw in t for kw in HARD_TECH) and not any(sig in t for sig in NON_TECH_SIGNAL):
        flags.append("纯技术")
    return list(dict.fromkeys(flags))


# 直接删除出库规则（用户确认：不做人工筛选，直接从数据库删除）
# 1) 纯销售岗：SALES_STRONG 命中或 title 以"销售"结尾（同 detect_reject 的纯销售判定）
# 2) TikTok / 海外电商岗：TikTok 系岗位、跨境电商、出海电商
OVERSEAS_E_COMMERCE = ["TikTok", "tiktok", "TIKTOK", "跨境", "出海电商", "海外电商",
                       "国际电商", "跨境电商", "海外电商运营", "电商出海"]
# 例外：含"运营"且明确是国内电商的（如 抖音电商/淘宝电商）不误删 —— 由 OVERSEAS_E_COMMERCE 精确词控制


def should_hard_delete(title: str, subcat: str, jdBrief: str, company: str) -> str | None:
    """命中直接删除规则返回原因，否则 None。"""
    t = f"{title} {company}"
    # 1) 纯销售
    if any(kw in t for kw in SALES_STRONG) or (
        re.search(r"销售$", title or "") and not any(ex in title or "" for ex in SALES_EXCEPT)
    ):
        return "纯销售岗（直接删除，不人工筛选）"
    # 2) TikTok / 海外电商
    if any(kw in (title or "") for kw in OVERSEAS_E_COMMERCE):
        return "TikTok/海外电商岗（直接删除，不人工筛选）"
    return None


def main():
    with open(SRC, encoding="utf-8") as f:
        jobs = json.load(f)

    # 合并爬虫增量数据（raw_jobs.json，RawJob schema → 先补默认字段对齐）
    if RAW_JOBS.exists():
        with open(RAW_JOBS, encoding="utf-8") as f:
            raw_jobs = json.load(f)
        if raw_jobs:
            for j in raw_jobs:
                j.setdefault("id", gen_unified_id(j.get("company", ""), j.get("title", "")))
                j.setdefault("status", "在招")
                j.setdefault("qualityScore", 3)
                j.setdefault("jdBrief", (j.get("jdFull") or "")[:120])
                j.setdefault("publishDate", "")
                j.setdefault("category", "")
                j.setdefault("subCat", None)
            jobs = jobs + raw_jobs
            print(f"合并爬虫增量: +{len(raw_jobs)} 条（raw_jobs.json）")

    raw_total = len(jobs)
    stats = {"total_raw": raw_total, "excluded_shetiao": 0, "excluded_offline": 0,
             "excluded_quality0": 0, "hard_deleted": 0, "kept": 0,
             "subcat_filled_by_rule": 0, "hard_delete_samples": []}

    cleaned = []
    for j in jobs:
        if j.get("jobType") == "社招":
            stats["excluded_shetiao"] += 1
            continue
        if j.get("status") == "已下线":
            stats["excluded_offline"] += 1
            continue
        if j.get("qualityScore", 0) == 0:
            stats["excluded_quality0"] += 1
            continue

        # 直接删除规则：纯销售 / TikTok / 海外电商（用户确认不人工筛选）
        hd = should_hard_delete(j.get("title", ""), j.get("subCat") or "",
                                j.get("jdBrief", ""), j.get("company", ""))
        if hd:
            stats["hard_deleted"] += 1
            if len(stats["hard_delete_samples"]) < 12:
                stats["hard_delete_samples"].append(
                    f"{j.get('company')} | {j.get('title')} | {hd}")
            continue

        subcat = j.get("subCat") or None
        if not subcat:
            subcat = classify_subcat(j.get("title", ""), j.get("jdBrief", ""))
            stats["subcat_filled_by_rule"] += 1

        company = j.get("company", "")
        company_tier = TIER_TO_NAME.get(company, "未知")
        # 央国企识别：① 来源=iguopin/政务（国聘网官方）② companyType=央企/国企
        #          ③ 命中 preferred_companies / national_high_pay 白名单
        if company_tier == "未知":
            is_cso = (
                j.get("source") in ("iguopin",)
                or j.get("sourceCredibility") == "政务"
                or j.get("companyType") in ("央企", "国企")
            )
            if not is_cso:
                cso = CFG.get("central_state_owned", {})
                cso_names = cso.get("preferred_companies", []) + cso.get("national_high_pay", [])
                is_cso = any(cn in company for cn in cso_names)
            if is_cso:
                company_tier = "央国企"
        reject_flags = detect_reject(j.get("title", ""), subcat, j.get("jdBrief", ""))

        # 央国企专业过滤：汉语言文学只收能报的岗（title/JD 命中 major_eligible 关键词才保留）
        if company_tier == "央国企":
            eligible = CFG.get("central_state_owned", {}).get("major_eligible_keywords", {}).get("include", [])
            job_text = f"{j.get('title','')} {j.get('jdBrief','') or ''} {j.get('requirements','') or ''}"
            if not any(kw in job_text for kw in eligible):
                stats.setdefault("excluded_major_mismatch", 0)
                stats["excluded_major_mismatch"] += 1
                continue

        # jobType 标准化：title 含"实习/实习生"即实习岗（源数据把小红书等公司实习岗误标为校招）
        job_type = j.get("jobType")
        if "实习" in j.get("title", ""):
            job_type = "实习"

        unified = {
            # 溯源字段
            "id": j.get("id"), "url": j.get("url"), "company": company,
            "title": j.get("title"), "jdBrief": j.get("jdBrief"),
            "jdFull": j.get("jdFull") or "",   # 爬虫原始 JD 全文（无则空，抽屉兜底用 jdBrief）
            "salary": j.get("salary"), "requirements": j.get("requirements"),
            "location": j.get("location"), "education": j.get("education"),
            "publishDate": j.get("publishDate"), "status": j.get("status"),
            "createdAt": j.get("createdAt"), "lastSeenAt": j.get("lastSeenAt"),
            "qualityScore": j.get("qualityScore"),
            # 判定字段
            "jobType": job_type, "category": j.get("category"),
            "subCat": subcat, "companyTier": company_tier,
            "rejectFlags": reject_flags,
            # 推理输出字段（初始为空，推理 Agent 写回）
            "tierJump": None, "tierFinal": None,
            "recommendReason": None, "rejectReason": None,
        }
        cleaned.append(unified)

    stats["kept"] = len(cleaned)

    # 去重：按 (company, title) 去重（两套 id 体系可能同岗位不同 id；源数据存在重复抓取）
    seen_keys, deduped = set(), []
    for j in cleaned:
        key = (j.get("company"), j.get("title"))
        if key in seen_keys:
            stats.setdefault("duplicated_ids", 0)
            stats["duplicated_ids"] += 1
            continue
        seen_keys.add(key)
        deduped.append(j)
    cleaned = deduped
    stats["kept"] = len(cleaned)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=1)

    print("=== 清洗统计 ===")
    for k, v in stats.items():
        if k == "hard_delete_samples":
            print(f"{k}: {len(v)} 条样例")
            for s in v:
                print(f"    {s}")
        else:
            print(f"{k}: {v}")

    from collections import Counter
    print("\n=== companyTier 分布 ===")
    for k, v in Counter(j["companyTier"] for j in cleaned).most_common():
        print(f"{k}: {v}")
    print("\n=== rejectFlags 分布 ===")
    for k, v in Counter(tuple(j["rejectFlags"]) for j in cleaned).most_common():
        print(f"{k}: {v}")
    print("\n=== subCat 分布 ===")
    for k, v in Counter(j["subCat"] for j in cleaned).most_common():
        print(f"{k}: {v}")
    print("\n=== jobType 分布 ===")
    for k, v in Counter(j["jobType"] for j in cleaned).most_common():
        print(f"{k}: {v}")
    print(f"\n输出: {OUT}")


if __name__ == "__main__":
    main()
