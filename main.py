# -*- coding: utf-8 -*-
"""
一键启动入口：python main.py
流程：确保数据已清洗 + 全量分档已生成 → 启动本地 Web UI（FastAPI）。
"""
import sys
import io
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent
JOBS_CLEAN = ROOT / "data" / "jobs_clean.json"
RESULTS = ROOT / "data" / "results_full.json"


def ensure_data():
    """保证数据与全量分档就绪（幂等）。"""
    if not JOBS_CLEAN.exists():
        print("[1/2] 清洗岗位数据…")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "clean_jobs.py")], check=True)
    else:
        print(f"[1/2] 数据已就绪: {JOBS_CLEAN.name}")

    if not RESULTS.exists():
        print("[2/2] 生成全量分档结果…")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_results.py")], check=True)
    else:
        print(f"[2/2] 分档结果已就绪: {RESULTS.name}")


def main():
    ensure_data()
    print("\n启动本地 Web UI: http://127.0.0.1:8000")
    import uvicorn
    uvicorn.run("ui.app:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
