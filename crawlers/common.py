# -*- coding: utf-8 -*-
"""
爬虫公共模块：统一输出 RawJob schema（与前身 lib/types.ts 的 RawJob 对齐），
保证新爬虫产出的数据能被 clean_jobs.py 直接清洗。
"""
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RawJob:
    """爬虫原始岗位（未打标签），schema 对齐前身 lib/types.ts 的 RawJob。"""
    url: str
    company: str
    title: str
    jdFull: str
    salary: str = "面议"
    requirements: str = ""
    publishDate: str = ""
    deadline: str = ""
    location: str = ""
    education: str = "不限"
    jobType: str = "实习"          # 实习/校招/应届/社招
    companyType: str = "民企"
    industry: str = "互联网"
    priorityLayer: str = "普通"
    inAuthoritativeList: bool = False
    sourceCredibility: str = "普通"
    source: str = ""              # 数据来源标记，如 "shixiseng"/"sinopec"
    companyTierHint: str = ""     # 公司层级提示（可选，供清洗参考）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def gen_id(company: str, title: str) -> str:
    """生成稳定 id：company+title 的哈希前缀，重复抓取同岗位 id 一致（配合去重）。"""
    h = uuid.uuid5(uuid.NAMESPACE_URL, f"{company}|{title}")
    return f"j_{h.hex[:6]}"


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 (company, title) 去重，保留最新一条。"""
    seen, out = set(), []
    for j in jobs:
        key = (j.get("company", ""), j.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def save_jobs(jobs: List[Dict[str, Any]], path) -> None:
    """输出到指定 JSON 文件（覆盖写）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    print(f"[crawlers] 已写入 {len(jobs)} 条 → {path}")


def throttle(seconds: float = 0.5) -> None:
    """礼貌爬取限速。"""
    time.sleep(seconds)
