# -*- coding: utf-8 -*-
"""
规格书第七节验收的自动化测试（交付物 8）：
  1. 销售岗应被拒（自动标红）
  2. 字节 AI 内容岗应归「实习·优选」
  3. 中厂内容岗应归「实习·稳健」
  4. 数据 Agent 查不到时明确说"数据库无此记录"（抗幻觉）
  5. 推理 Agent 输出全部基于数据 Agent 返回的事实（安全层校验）
运行：pytest tests/test_pipeline.py -v
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.data_agent import JobDatabase
from agents.reasoning_agent import tier_for_job, load_profile
from orchestrator import run_recommendation

ROOT = Path(__file__).resolve().parents[1]


def find_job(company: str, title_part: str):
    """从数据库找真实岗位（按公司+标题片段）。"""
    db = JobDatabase()
    for j in db.jobs:
        if j["company"] == company and title_part in j["title"]:
            return j
    return None


def test_sales_job_deleted():
    """1) 纯销售岗直接删除出库（不再标红保留，不进入数据库）。"""
    # 真实销售岗：快手商业化广告销售
    job = find_job("快手", "商业化广告销售")
    assert job is None, "纯销售岗应已从数据库删除（hard_delete）"
    # 同时验证清理后的库中无残留销售强词岗
    db = JobDatabase()
    leftovers = [j for j in db.jobs
                 if any(kw in j["title"] for kw in ["商务拓展", "广告销售", "KA销售"])]
    assert leftovers == [], f"库中不应残留纯销售岗：{leftovers}"


def test_bytedance_ai_content_jump_chong():
    """2) 字节 AI 内容向实习 → 实习·优选。"""
    job = find_job("字节跳动", "AI内容策划运营实习生")
    assert job, "数据库中应存在字节 AI内容策划运营实习生"
    r = tier_for_job(job)
    assert r["tierJump"] == "实习·优选", f"应归实习·优选，实际 {r['tierJump']}"
    assert r["recommendReason"], "应有推荐理由"


def test_mid_tier_content_jump_wen():
    """3) 中厂内容岗实习 → 实习·稳健。"""
    # 小红书为规格书明确的中厂（B站/小红书/快手）
    job = find_job("小红书", "内容运营")
    if job is None:
        job = find_job("小红书", "产品运营")
    assert job, "数据库中应存在小红书内容/产品运营实习岗"
    r = tier_for_job(job)
    assert r["tierJump"] == "实习·稳健", f"应归实习·稳健，实际 {r['tierJump']}"


def test_data_agent_no_hallucination():
    """4) 数据 Agent 抗幻觉：不存在的岗位明确说"数据库无此记录"。"""
    state = run_recommendation(
        {"exists": {"company": "不存在的公司", "title": "绝对不存在的岗位"}}
    )
    assert state["query_count"] == 0
    assert "数据库无此记录" in state["data_agent_note"], state["data_agent_note"]


def test_safety_layer_pass():
    """5) 安全层：推理 Agent 输出全部基于数据 Agent 返回的事实（无编造）。"""
    state = run_recommendation({"company": "字节跳动", "subCat": "AI内容", "limit": 5})
    assert state["safety_report"]["status"] == "PASS", state["safety_report"]
    fact_ids = {j["id"] for j in state["query_result"]}
    for r in state["recommendations"]:
        assert r["job"]["id"] in fact_ids, f"推理输出岗位 {r['job']['title']} 不在数据Agent 事实中"


def test_overseas_job_manual_review():
    """海外/TikTok 向岗位直接筛选掉（英语要求高），归人工过目不推荐。"""
    job = find_job("字节跳动", "海外")
    if job is None:
        job = find_job("字节跳动", "国际")
    if job is None:
        job = find_job("小红书", "海外")
    assert job, "数据库中应存在海外向岗位用于测试"
    r = tier_for_job(job)
    assert r["rejectReason"] and "海外" in r["rejectReason"], r["rejectReason"]
    assert not r["tierJump"] and not r["tierFinal"], "海外向岗位不应进入推荐"


def test_full_results_consistent():
    """6) 全量分档结果文件与数据库一致（UI 数据源完整性）。"""
    with open(ROOT / "data" / "results_full.json", encoding="utf-8") as f:
        results = json.load(f)
    db = JobDatabase()
    total = results["stats"]["total"]
    rec = results["stats"]["recommended"]
    rej = results["stats"]["rejected"]
    assert total == db.count(), f"分档结果 {total} 应与数据库 {db.count()} 一致"
    assert total == rec + rej, "推荐+拒绝 应等于总数"


def test_central_state_owned_to_baodi():
    """7) 央国企岗位（汉语言文学可报）归保底档。"""
    cso = [j for j in JobDatabase().jobs if j["companyTier"] == "央国企"]
    assert cso, "数据库中应存在央国企岗位"
    for j in cso[:3]:
        r = tier_for_job(j)
        assert r["tierFinal"] == "保底档", f"{j['company']} {j['title']} 应归保底档，实际 {r['tierFinal']}"


def test_case_evidence_in_reason():
    """8) 推荐理由包含真实案例佐证（2026年在招，非臆造）。"""
    db = JobDatabase()
    profile = load_profile()
    for j in db.jobs:
        if j["company"] == "字节跳动" and j["subCat"] == "AI内容":
            r = tier_for_job(j, profile)
            assert r["recommendReason"] and "真实案例佐证" in r["recommendReason"], r["recommendReason"]
            assert "2026年在招" in r["recommendReason"]
            return
    assert False, "数据库中应存在字节 AI内容岗用于案例佐证测试"


def test_llm_client_api():
    """9) DeepSeek API 客户端可用（key 已配置）。"""
    from lib.llm_client import api_key_available, chat_once
    assert api_key_available(), "DEEPSEEK_API_KEY 应已配置在 .env"
    reply = chat_once([{"role": "user", "content": "只回复两个字：收到"}],
                      system="你是测试助手，只按指令回复。")
    assert reply and len(reply) > 0, "DeepSeek 应返回非空回复"


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    tests = [test_sales_job_deleted, test_bytedance_ai_content_jump_chong,
             test_mid_tier_content_jump_wen, test_data_agent_no_hallucination,
             test_safety_layer_pass, test_overseas_job_manual_review,
             test_full_results_consistent, test_central_state_owned_to_baodi,
             test_case_evidence_in_reason, test_llm_client_api]
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {t.__name__}: {e}")
