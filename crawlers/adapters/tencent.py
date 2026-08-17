# -*- coding: utf-8 -*-
"""
腾讯招聘适配器：官方 API careers.tencent.com（直连，返回 JSON）。
按目标方向关键词抓取：内容/运营/产品/AI。
"""
import httpx
import sys
import io
from typing import List

from crawlers.common import RawJob, gen_id

API = "https://careers.tencent.com/tencentcareer/api/post/Query"
KEYWORDS = ["内容运营", "内容创作", "内容策划", "AI", "AIGC", "产品运营", "产品经理", "内容策略"]
PAGE_SIZE = 50


def fetch_page(keyword: str, page: int) -> tuple[List[dict], int]:
    r = httpx.get(API, params={
        "pageIndex": page, "pageSize": PAGE_SIZE,
        "keyword": keyword, "timestamp": 0,
    }, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    d = r.json()
    posts = d.get("Data", {}).get("Posts", []) or []
    total = d.get("Data", {}).get("TotalCount", 0) or 0
    return posts, total


def crawl(max_pages: int = 3) -> List[dict]:
    """抓取腾讯在招岗位，keyword 轮询。"""
    jobs, seen = [], set()
    for kw in KEYWORDS:
        for page in range(1, max_pages + 1):
            try:
                posts, _ = fetch_page(kw, page)
            except Exception:
                break
            if not posts:
                break
            for p in posts:
                title = p.get("RecruitPostName", "").strip()
                url = p.get("PostURL", "") or ""
                key = (title, url)
                if key in seen:
                    continue
                seen.add(key)
                j = RawJob(
                    url=url,
                    company="腾讯",
                    title=title,
                    jdFull=(p.get("Responsibility") or "")[:2000],
                    location=(p.get("LocationName") or "").strip(),
                    salary="面议",
                    requirements="",
                    publishDate=p.get("LastUpdateTime", ""),
                    jobType="校招" if "校招" in (p.get("CategoryName") or "") else "实习",
                    industry="互联网",
                    priorityLayer="优秀雇主",
                    inAuthoritativeList=True,
                    sourceCredibility="官网",
                    source="tencent-official",
                    companyTierHint="头部大厂",
                )
                jobs.append(j.to_dict())
    return jobs


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    jobs = crawl(max_pages=2)
    print(f"腾讯爬取：{len(jobs)} 条")
    for j in jobs[:5]:
        print(" ", j["title"], "|", j["location"], "|", j["jobType"])
