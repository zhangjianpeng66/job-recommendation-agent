# -*- coding: utf-8 -*-
"""
实习僧聚合适配器 v3：Playwright 渲染 + 动态字体反爬破解。
字体机制：岗位文本用 PUA 码点 + 动态 myFont（@font-face url 带 rand 参数），
cmap 把 PUA 码点映射到 glyph 名（uniXXXX 形式 = 对应 Unicode 字符）。
破解：页面加载后抓取当前 myFont 字体 → fontTools 解析 cmap → PUA→真实字符映射表 → 解码标题。
"""
import html
import re
import sys
import io
from typing import List, Dict

from crawlers.common import RawJob

TARGET_COMPANIES = [
    "爱奇艺", "喜马拉雅", "芒果TV", "芒果tv", "搜狐", "携程", "百度",
    "美图", "美团", "阅文", "网易", "得物", "知乎", "拼多多",
    "字节跳动", "腾讯", "阿里巴巴", "快手", "小红书", "B站", "bilibili",
]
KEYWORDS = ["AI内容", "AI内容运营", "内容运营", "内容创作", "AI产品", "内容策划"]


def get_font_mapping(page) -> Dict[str, str]:
    """抓取实习僧 myFont 字体（固定 URL，rand 参数不影响内容），解析 cmap 返回 {PUA字符: 真实字符}。"""
    import httpx
    from fontTools.ttLib import TTFont
    # 实测：字体文件内容固定（10400B / 98 个 PUA 映射），rand 参数只是迷惑
    font_url = "https://www.shixiseng.com/interns/iconfonts/file?rand=0.5"
    r = httpx.get(font_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.shixiseng.com/"})
    if r.status_code != 200:
        return {}
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "sxs_font.bin")
    with open(tmp, "wb") as f:
        f.write(r.content)
    mapping = {}
    try:
        font = TTFont(tmp)
        cmap = font.getBestCmap()
        for codepoint, glyph in cmap.items():
            if 0xE000 <= codepoint <= 0xF8FF:  # PUA
                # glyph 名是 uni+变长十六进制（uni78=x, uni5E02=市），或单个字符
                if isinstance(glyph, str) and glyph.startswith("uni"):
                    m = re.match(r"uni([0-9A-Fa-f]+)$", glyph)
                    if m:
                        try:
                            mapping[chr(codepoint)] = chr(int(m.group(1), 16))
                        except ValueError:
                            continue
                elif isinstance(glyph, str) and len(glyph) == 1:
                    mapping[chr(codepoint)] = glyph
    except Exception:
        pass
    return mapping


def decode_text(text: str, mapping: Dict[str, str]) -> str:
    """先 html.unescape，再用 PUA 映射还原真实字符。"""
    t = html.unescape(text)
    out = []
    for ch in t:
        if ch in mapping:
            out.append(mapping[ch])
        else:
            out.append(ch)
    return "".join(out)


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
        mapping = {}
        for kw in KEYWORDS:
            for pg in range(1, max_pages + 1):
                url = f"https://www.shixiseng.com/interns?k={kw}&t=JT&p={pg}"
                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    if not mapping:
                        mapping = get_font_mapping(page)
                        print(f"  字体映射: {len(mapping)} 个字符", flush=True)
                except Exception as e:
                    print(f"  [{kw} p{pg}] 加载失败 {str(e)[:60]}")
                    break
                links = page.locator("a[href*='/intern/']")
                n = links.count()
                if n == 0:
                    break
                for i in range(n):
                    try:
                        link = links.nth(i)
                        href = link.get_attribute("href") or ""
                        if not href or "/intern/" not in href:
                            continue
                        # 向上找含目标公司名的容器
                        card = link
                        for _ in range(4):
                            parent = card.locator("xpath=..")
                            t = parent.inner_text()
                            if any(c in t for c in TARGET_COMPANIES):
                                card = parent
                                break
                            card = parent
                        raw_text = card.inner_text()
                        text = decode_text(raw_text, mapping)
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        company = ""
                        for l in lines:
                            for c in TARGET_COMPANIES:
                                if c.lower() in l.lower():
                                    company = c
                                    break
                            if company:
                                break
                        if not company:
                            continue
                        title = decode_text(link.inner_text(), mapping).strip()
                        if not title or len(title) < 2 or "实习" not in title:
                            continue
                        location, salary = "", ""
                        for l in lines:
                            if re.search(r"上海|北京|广州|深圳|杭州|成都|武汉|长沙|厦门|南京|苏州|天津|重庆", l):
                                location = l.strip()
                            if re.search(r"\d+-\d+元|面议|元/天|\d+元", l):
                                salary = l.strip()
                        key = (company, title)
                        if key in seen:
                            continue
                        seen.add(key)
                        full_url = href if href.startswith("http") else f"https://www.shixiseng.com{href}"
                        jobs.append(RawJob(
                            url=full_url, company=company, title=title,
                            jdFull=text[:800], salary=salary or "面议",
                            location=location, jobType="实习",
                            source="shixiseng", sourceCredibility="普通",
                        ).to_dict())
                    except Exception:
                        continue
                print(f"  [{kw} p{pg}] 累计 {len(jobs)} 条", flush=True)
        browser.close()
    return jobs


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    jobs = crawl(max_pages=1)
    print(f"\n实习僧抓取：{len(jobs)} 条")
    from collections import Counter
    print(Counter(j["company"] for j in jobs).most_common(15))
    for j in jobs[:10]:
        print(" ", j["company"], "|", j["title"], "|", j["location"], "|", j["salary"])
