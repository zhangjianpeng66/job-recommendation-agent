# -*- coding: utf-8 -*-
"""
爬虫统一调度：按顺序跑各适配器，合并输出 data/raw_jobs.json。
被 scripts/update_all.py 调用。

用法：python crawlers/run_all.py
     python crawlers/run_all.py tencent   # 只跑指定适配器
"""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RAW_OUT = ROOT / "data" / "raw_jobs.json"

# 适配器注册表：name -> (module 路径, 公司名)
# 只注册已验证可直连的源；需登录态/逆向的（中石化/国聘网等）待登录态方案
ADAPTERS = [
    ("tencent", "crawlers.adapters.tencent", "腾讯"),
    ("shixiseng", "crawlers.adapters.shixiseng", "实习僧(聚合)"),
    ("iguopin", "crawlers.adapters.iguopin", "国聘网(央国企)"),
]

# 各源独立输出（便于单源失败不影响整体）
SOURCE_FILES = {
    "tencent": ROOT / "data" / "raw_tencent.json",
    "shixiseng": ROOT / "data" / "raw_shixiseng.json",
    "iguopin": ROOT / "data" / "raw_iguopin.json",
}


def run_one(name: str) -> list:
    """运行单个适配器，返回岗位列表；失败返回 [] 并打印错误。"""
    for n, module, company in ADAPTERS:
        if n != name:
            continue
        print(f"\n===== 爬取 [{company}]（{module}）=====", flush=True)
        try:
            mod = __import__(module, fromlist=["crawl"])
            jobs = mod.crawl()
            out_path = SOURCE_FILES[name]
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(jobs, f, ensure_ascii=False, indent=1)
            print(f"[{company}] 完成：{len(jobs)} 条 → {out_path.name}", flush=True)
            return jobs
        except Exception as e:
            import traceback
            print(f"[{company}] 爬取失败：{e}", flush=True)
            traceback.print_exc()
            return []
    print(f"未知适配器: {name}，可用: {[a[0] for a in ADAPTERS]}")
    return []


def merge_all() -> None:
    """合并所有源输出到 data/raw_jobs.json（去重）。"""
    from crawlers.common import dedupe_jobs
    all_jobs = []
    for name, path in SOURCE_FILES.items():
        if path.exists():
            with open(path, encoding="utf-8") as f:
                all_jobs.extend(json.load(f))
    merged = dedupe_jobs(all_jobs)
    with open(RAW_OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print(f"\n[merge] 合并 {len(all_jobs)} → 去重后 {len(merged)} 条 → {RAW_OUT.name}")


def main():
    args = sys.argv[1:]
    if args:
        for name in args:
            run_one(name)
    else:
        for name, _, _ in ADAPTERS:
            run_one(name)
    merge_all()


if __name__ == "__main__":
    main()
