# -*- coding: utf-8 -*-
"""
编排层 Orchestrator（LangGraph 图）：
  START → 数据Agent（查库/过滤，只输出事实） → 推理Agent（分档+理由） → 安全层（幻觉校验） → END

借鉴 CareerPilot 的 agents/workflow.py（StateGraph 编排）+ agents/safety.py（安全监控）。
上下文隔离：数据Agent 的 system prompt = 数据库约束；推理Agent 只读 query_result。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.graph import StateGraph, START, END

from agents.state import RecommendationState
from agents.data_agent import data_agent_node
from agents.reasoning_agent import reasoning_agent_node


# ---------- 安全层：幻觉校验 ----------
def safety_node(state: RecommendationState) -> RecommendationState:
    """
    安全监控（借鉴 CareerPilot agents/safety.py）：
    1. 校验推理Agent 输出的每个岗位 id 都来自数据Agent 返回的事实（防编造岗位）
    2. 校验抗拒标记与数据一致性
    3. 产出 safety_report: PASS / FAIL
    """
    issues = []
    fact_ids = {j.get("id") for j in state.get("query_result", [])}

    for r in state.get("recommendations", []):
        j = r.get("job", {})
        if j.get("id") not in fact_ids:
            issues.append(f"幻觉: 推荐岗位 '{j.get('title')}' 不在数据Agent 返回的事实中")
        if not r.get("recommendReason") and not r.get("rejectReason"):
            issues.append(f"推理缺理由: '{j.get('title')}' 无推荐理由")
    for r in state.get("rejected", []):
        j = r.get("job", {})
        if j.get("id") not in fact_ids:
            issues.append(f"幻觉: 拒绝岗位 '{j.get('title')}' 不在数据Agent 返回的事实中")

    # 抗拒规则校验：纯销售/纯技术必须出现在 rejected
    for r in state.get("recommendations", []):
        if r.get("job", {}).get("rejectFlags"):
            issues.append(f"抗拒标记遗漏: '{r['job']['title']}' 带 rejectFlags 却进了推荐")

    state["safety_report"] = {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
    }
    return state


def build_graph():
    graph = StateGraph(RecommendationState)
    graph.add_node("data_agent", data_agent_node)
    graph.add_node("reasoning_agent", reasoning_agent_node)
    graph.add_node("safety", safety_node)
    graph.add_edge(START, "data_agent")
    graph.add_edge("data_agent", "reasoning_agent")
    graph.add_edge("reasoning_agent", "safety")
    graph.add_edge("safety", END)
    return graph.compile()


def run_recommendation(query: Dict[str, Any]) -> Dict[str, Any]:
    """一键入口：输入结构化查询，返回完整结果 state。"""
    state: RecommendationState = {"query": query}
    return build_graph().invoke(state)


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    demo = [
        {"company": "字节跳动", "subCat": "AI内容", "jobType": "实习", "limit": 5},
        {"company": "小红书", "jobType": "实习", "limit": 5, "excludeReject": True},
        {"exists": {"company": "腾讯", "title": "游戏策划培训生"}},
    ]
    for q in demo:
        print(f"\n########## query: {json.dumps(q, ensure_ascii=False)} ##########")
        result = run_recommendation(q)
        print(result.get("data_agent_note", ""))
        print(result.get("final_response", ""))
        print("safety:", result.get("safety_report"))
