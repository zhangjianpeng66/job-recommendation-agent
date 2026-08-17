# -*- coding: utf-8 -*-
"""生成 10 个代表性岗位推荐结果（供用户确认档位判定是否符合预期）"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\23001\AppData\Roaming\reasonix\global-workspace\job-recommendation')
from agents.data_agent import JobDatabase
from agents.reasoning_agent import tier_for_job

db = JobDatabase()

# 精心挑选的 10 个代表性岗位（覆盖各档位+抗拒+人工过目）
cases = [
    ("字节跳动", "AI内容策划运营实习生 - 剪映CapCut"),     # 期望: 实习·优选 + 稳定档
    ("字节跳动", "策略产品实习生"),                        # 期望: 实习·优选 + 冲刺档
    ("小红书", "小红书内容运营项目实习生"),                 # 期望: 实习·稳健 + 保底档
    ("B站", "国创动画运营实习生"),                        # 期望: 实习·稳健 + 保底档
    ("快手", "商业化广告销售"),                            # 期望: 纯销售 拒绝
    ("腾讯", "内容运营"),                                 # 期望: 实习-冲/校招-稳定档
    ("网易", "AI向内容运营实习生"),                        # 期望: 实习·优选 + 稳定档
    ("字节跳动", "电商运营实习生"),                        # 期望: 方向不匹配-人工过目
    ("知乎", "策略运营实习生"),                          # 期望: 实习·稳健（知乎是中厂）
    ("阿里巴巴", "日常实习生-AI产品经理-未来生活实验室"),     # 期望: 实习·优选 + 冲刺档
]

for company, title_part in cases:
    hit = None
    for j in db.jobs:
        if j["company"] == company and title_part in j["title"]:
            hit = j
            break
    if not hit:
        print(f"!!! 未找到: {company} {title_part}")
        continue
    r = tier_for_job(hit)
    print(f"{hit['company']} | {hit['title']}")
    print(f"    subCat={hit['subCat']} jobType={hit['jobType']} 公司层级={hit['companyTier']} reject={hit['rejectFlags']}")
    print(f"    实习期={r['tierJump'] or '—'} | 冲刺期={r['tierFinal'] or '—'} | 最终归属={r['final_belong'] or '—'}")
    print(f"    理由: {r['recommendReason'] or r['rejectReason']}")
    print()

