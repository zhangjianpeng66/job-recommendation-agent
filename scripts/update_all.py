# -*- coding: utf-8 -*-
"""
统一数据流水线入口（供手动与 Windows 计划任务每周一调用）：
  爬取（crawlers/，可跳过）→ 清洗（clean_jobs.py）→ 全量分档（build_results.py）→ 重建向量库（rag.ingest）

用法：
  python scripts/update_all.py          # 完整流水线（含爬取）
  python scripts/update_all.py --no-crawl   # 跳过爬取，只用现有原始数据重新清洗+分档+建库
"""
import subprocess
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd: list, step: str) -> None:
    print(f"\n===== [{step}] {cmd[0]} {' '.join(cmd[1:])} =====", flush=True)
    r = subprocess.run([sys.executable, *cmd], cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit(f"[{step}] 失败，退出码 {r.returncode}")
    print(f"[{step}] 完成 ✓", flush=True)


def main():
    no_crawl = "--no-crawl" in sys.argv

    if not no_crawl:
        crawler = ROOT / "crawlers" / "run_all.py"
        if crawler.exists():
            run([str(crawler)], "爬取")
        else:
            print("crawlers/run_all.py 不存在，跳过爬取（仅重洗现有数据）")
    else:
        print("--no-crawl：跳过爬取")

    run([str(SCRIPTS / "clean_jobs.py")], "清洗")
    run([str(SCRIPTS / "build_results.py")], "全量分档")
    run(["-m", "rag.ingest", "--force"], "重建向量库")
    print("\n全部完成 ✓")


if __name__ == "__main__":
    main()
