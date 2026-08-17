# -*- coding: utf-8 -*-
"""
本地 Web UI（FastAPI）：展示分档推荐 + 推荐理由 + 抗拒标记 + 双 AI 对话窗口。
启动：python main.py 或 uvicorn ui.app:app --port 8000
"""
import json
import subprocess
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from orchestrator import run_recommendation

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "data" / "results_full.json"

app = FastAPI(title="多 Agent 求职岗位推荐系统", version="2.0.0")


def _load_results():
    if not RESULTS_PATH.exists():
        return {"stats": {}, "recommendations": [], "rejected": [],
                "error": "results_full.json 不存在，请先运行 python scripts/build_results.py"}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ============ AI 对话窗口（双 Agent） ============

def _load_profile() -> dict:
    with open(ROOT / "config" / "profile.json", encoding="utf-8") as f:
        return json.load(f)


# 数据库 AI：只处理数据库优化指令（system prompt 限定工具边界）
DATABASE_AI_PROMPT = """你是求职系统的【数据库 AI】，只负责管理和优化岗位数据库。你的职责范围：
1. 更新岗位数据：回复"更新数据"类指令时，执行爬取+清洗+分档+建库流水线（python scripts/update_all.py）
2. 调整规则：抗拒规则/公司分级/三档关键词（config/profile.json 可编辑），你只能建议，具体修改由用户确认
3. 查库统计：数据库现有多少岗位、各公司/方向分布（调用 /api/stats 或查询接口）
4. 重建向量库：python -m rag.ingest --force

硬约束：
- 你只回答数据库相关的问题，不做求职建议（那是推理 AI 的职责）
- 不编造数据：查不到就说"数据库无此记录"
- 每次执行指令后报告执行结果（成功/失败/影响条数）
- 遇到模糊指令，先列出可执行的操作让用户选，不擅自执行

数据库现状：{db_status}
"""

# 推理 AI：求职咨询（system prompt 注入画像）
REASONING_AI_PROMPT = """你是张建鹏的【个人求职推理 AI】，结合他的画像、经历和真实岗位数据库，帮他做求职决策。你的职责：
1. 理解求职需求 → 给出岗位方向建议（结合三档：实习·优选/稳健/保底 + 冲刺期：冲刺档/稳定档/保底档）
2. 分析岗位匹配度：把他的能力（AI内容创作/用户研究/产品项目/内容运营/团队管理/合规）与岗位 JD 对照
3. 简历/面试建议：基于他的真实经历
4. 明确告知：分档推荐基于数据库真实岗位 + config/cases.json 真实案例佐证（2026年在招）

硬约束：
- 不编造他的经历和岗位数据：只引用画像中已有的事实（见下）
- 岗位数据一律引用数据库（可通过查询接口获取），不自己编岗位
- 回答简洁、结构化、可执行
- 一次只问一个问题，意图不清先反问

【用户画像】
{profile_summary}
"""


def _db_status_text() -> str:
    try:
        res = _load_results()
        s = res.get("stats", {})
        return (f"岗位总数 {s.get('total', 0)}（推荐 {s.get('recommended', 0)} / 人工过目 {s.get('rejected', 0)}），"
                f"优选 {s.get('by_tierJump', {}).get('实习·优选', 0)}，稳健 {s.get('by_tierJump', {}).get('实习·稳健', 0)}，"
                f"冲刺档 {s.get('by_tierFinal', {}).get('冲刺档', 0)}，稳定档 {s.get('by_tierFinal', {}).get('稳定档', 0)}，"
                f"保底档 {s.get('by_tierFinal', {}).get('保底档', 0)}")
    except Exception:
        return "数据未就绪"


def _profile_summary() -> str:
    """加载画像摘要 + 求职 skill（推理 AI 的知识库）。"""
    try:
        p = _load_profile().get("profile", {})
        abilities = "；".join(
            f"{a['name']}（{a['evidence'][:80]}）"
            for a in p.get("core_abilities", [])
        )
        base = (f"姓名 {p.get('name')}，{p.get('school')} {p.get('major')}，{p.get('grade')}，GPA {p.get('gpa')}\n"
                f"目标方向：{p.get('target_direction')}\n"
                f"核心能力：{abilities}")
        # 附加求职 skill 的关键规则（三档定义 + 薪资参考）
        skill_path = ROOT / "skills" / "job-hunting" / "SKILL.md"
        if skill_path.exists():
            skill_text = skill_path.read_text(encoding="utf-8")
            # 提取三档定义和薪资参考部分
            import re
            m = re.search(r"## 三档定义.*?(?=## 推理流程)", skill_text, re.S)
            if m:
                base += "\n\n【三档定义】\n" + m.group(0).replace("## ", "").strip()
        return base
    except Exception:
        return "画像未加载"


@app.get("/api/agents")
def agents():
    """双 AI 角色元数据。"""
    return JSONResponse([
        {
            "id": "database",
            "name": "数据库 AI",
            "emoji": "🗄️",
            "desc": "管理岗位数据库：更新数据 / 改规则 / 查库统计 / 重建索引。只接受数据库相关指令。",
            "db_status": _db_status_text(),
        },
        {
            "id": "reasoning",
            "name": "推理 AI",
            "emoji": "🧠",
            "desc": "个人求职咨询：理解你的需求，结合画像与真实岗位给出三档推荐方案。",
            "db_status": _db_status_text(),
        },
    ])


@app.post("/api/chat")
def chat(req: dict):
    """SSE 流式对话：agent=数据库|推理，messages=历史消息。"""
    from lib.llm_client import chat_stream, api_key_available
    agent = req.get("agent", "reasoning")
    messages = req.get("messages", [])

    if agent == "database":
        system = DATABASE_AI_PROMPT.format(db_status=_db_status_text())
    else:
        system = REASONING_AI_PROMPT.format(profile_summary=_profile_summary())

    if not api_key_available():
        def fallback():
            yield "data: {\"content\":\"（未配置 DEEPSEEK_API_KEY，请检查 .env）\"}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(fallback(), media_type="text/event-stream")

    def gen():
        for chunk in chat_stream(messages, system=system):
            payload = json.dumps({"content": chunk}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/db-action")
def db_action(req: dict):
    """数据库 AI 的落地执行入口（更新数据 / 重建索引等）。action 由数据库 AI 在对话中建议。"""
    action = req.get("action", "")
    if action == "update":
        try:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "update_all.py")],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=600)
            return JSONResponse({"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-800:]})
        except subprocess.TimeoutExpired:
            return JSONResponse({"ok": False, "output": "更新超时（>10分钟）"})
    if action == "reindex":
        try:
            r = subprocess.run([sys.executable, "-m", "rag.ingest", "--force"],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=300)
            return JSONResponse({"ok": r.returncode == 0, "output": (r.stdout or r.stderr)[-500:]})
        except subprocess.TimeoutExpired:
            return JSONResponse({"ok": False, "output": "重建超时"})
    return JSONResponse({"ok": False, "output": f"未知操作: {action}"})


# ============ 原有接口 ============

@app.get("/")
def index():
    return FileResponse(ROOT / "ui" / "index.html")


@app.get("/api/results")
def get_results():
    return JSONResponse(_load_results())


@app.get("/api/query")
def query(company: str = "", subCat: str = "", jobType: str = "",
          companyTier: str = "", keyword: str = "", limit: int = 50,
          excludeReject: bool = True):
    """实时走编排层（数据Agent→推理Agent→安全层）的查询接口。"""
    q = {"limit": limit, "excludeReject": excludeReject}
    if company:
        q["company"] = company
    if subCat:
        q["subCat"] = subCat
    if jobType:
        q["jobType"] = jobType
    if companyTier:
        q["companyTier"] = companyTier
    if keyword:
        q["keyword"] = keyword
    state = run_recommendation(q)
    return JSONResponse({
        "note": state.get("data_agent_note", ""),
        "count": state.get("query_count", 0),
        "recommendations": state.get("recommendations", []),
        "rejected": state.get("rejected", []),
        "safety": state.get("safety_report", {}),
    })


@app.get("/api/semantic")
def semantic(query: str, limit: int = 20):
    """自然语言语义召回（ChromaDB），向量库未建时自动降级。"""
    q = {"semantic": query, "limit": limit, "excludeReject": True}
    state = run_recommendation(q)
    return JSONResponse({
        "note": state.get("data_agent_note", ""),
        "recommendations": state.get("recommendations", []),
        "rejected": state.get("rejected", []),
        "safety": state.get("safety_report", {}),
    })


@app.get("/api/stats")
def stats():
    return JSONResponse(_load_results().get("stats", {}))
