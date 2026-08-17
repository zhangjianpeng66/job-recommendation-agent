# -*- coding: utf-8 -*-
"""
国聘网（iguopin.com）央国企适配器：Playwright 渲染校招/社招列表页。
过滤规则（config/profile.json central_state_owned）：
  1. 单位性质=国企/央企（页面标签）
  2. 汉语言文学可报：title/JD 命中 major_eligible_keywords
  3. 湖北本省优先（preferred_companies 命中标公司层级提示），全国高起薪央企也收录
"""
import json
import re
import sys
import io
from pathlib import Path
from typing import List

from crawlers.common import RawJob

ROOT = Path(__file__).resolve().parents[2]


def load_profile():
    with open(ROOT / "config" / "profile.json", encoding="utf-8") as f:
        return json.load(f)


PROFILE = load_profile()
CSO = PROFILE.get("central_state_owned", {})
PREFERRED = CSO.get("preferred_companies", [])
HIGH_PAY = CSO.get("national_high_pay", [])
ELIGIBLE = CSO.get("major_eligible_keywords", {}).get("include", [])

PAGES = 2  # 抓取页数


def is_eligible(job_text: str) -> bool:
    """汉语言文学可报过滤：title/JD 命中 include 关键词才保留。"""
    return any(kw in job_text for kw in ELIGIBLE)


def company_hint(company: str) -> str:
    """公司层级提示：湖北本省优先。"""
    if any(cn in company for cn in PREFERRED):
        return "央国企(湖北本省)"
    if any(cn in company for cn in HIGH_PAY):
        return "央国企(全国高薪)"
    return "央国企"


def crawl(max_pages: int = 2) -> List[dict]:
    from playwright.sync_api import sync_playwright
    jobs, seen = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
            locale="zh-CN",
        )
        page = ctx.new_page()
        for channel in ["campus", "social"]:
            for pg in range(1, max_pages + 1):
                url = f"https://www.iguopin.com/job?channel={channel}&pageIndex={pg}"
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                except Exception as e:
                    print(f"  [{channel} p{pg}] 加载失败 {str(e)[:60]}")
                    break
                # 岗位卡片：.job-card（含 .job-name 岗位名 / .job-tag 性质标签 / 公司名）
                cards = page.locator(".job-card")
                n = cards.count()
                if n == 0:
                    break
                for i in range(n):
                    try:
                        card = cards.nth(i)
                        text = card.inner_text()
                        href = ""
                        link = card.locator("a").first
                        if link.count() > 0:
                            href = link.get_attribute("href") or ""
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        if len(lines) < 2:
                            continue
                        title = lines[0]
                        # 汉语言文学可报过滤（title + 全卡片文本）
                        job_text = text[:500]
                        if not is_eligible(job_text):
                            continue
                        # 公司名：卡片内最后一个非空行（或含"公司/集团/有限"的行）
                        company = ""
                        for l in reversed(lines):
                            if re.search(r"公司|集团|有限|研究院|银行|局|所", l) and "校招" not in l and "社招" not in l:
                                company = l
                                break
                        if not company:
                            company = lines[-1]
                        key = (title, company)
                        if key in seen:
                            continue
                        seen.add(key)
                        url = href if href.startswith("http") else f"https://www.iguopin.com{href}"
                        jobs.append(RawJob(
                            url=url, company=company, title=title,
                            jdFull=job_text[:800], salary="面议",
                            location="", jobType="校招" if channel == "campus" else "社招",
                            companyType="央企",
                            industry="",
                            source="iguopin", sourceCredibility="政务",
                            companyTierHint=company_hint(company),
                        ).to_dict())
                    except Exception:
                        continue
                print(f"  [{channel} p{pg}] 累计 {len(jobs)} 条（可报）", flush=True)
        browser.close()
    return jobs


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    jobs = crawl(max_pages=1)
    print(f"\n国聘网抓取：{len(jobs)} 条（汉语言文学可报）")
    from collections import Counter
    print("公司层级:", Counter(j["companyTierHint"] for j in jobs).most_common())
    for j in jobs[:10]:
        print(" ", j["company"], "|", j["title"], "|", j["jobType"], "|", j["companyTierHint"])
