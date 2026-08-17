# -*- coding: utf-8 -*-
"""编排层共享状态定义（借鉴 CareerPilot agents/state.py 的 TypedDict 模式）"""
from typing import TypedDict, List, Dict, Any


class RecommendationState(TypedDict, total=False):
    """数据Agent → 推理Agent 的共享轻量状态。
    上下文隔离：数据Agent 只读写 query/query_result/query_stats；
    推理Agent 只读 query_result + profile，写推理结果。"""

    # 用户输入
    user_query: str                 # 自然语言或结构化查询请求
    query: Dict[str, Any]           # 结构化查询条件（数据Agent 解析产出）

    # 数据Agent 产出（数据库事实，抗幻觉依据）
    query_result: List[Dict[str, Any]]   # 命中岗位（unified schema 字段）
    query_count: int                # 命中条数
    query_stats: Dict[str, Any]     # 统计信息（存在性检查/分布统计）
    data_agent_note: str            # 数据Agent 的说明（如"数据库无此记录"）

    # 推理Agent 产出
    recommendations: List[Dict[str, Any]]  # 分档推荐结果
    rejected: List[Dict[str, Any]]         # 抗拒标记岗位
    final_response: str             # 面向用户的结果摘要

    # 安全层
    safety_report: Dict[str, Any]
