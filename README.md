# 多 Agent 求职岗位推荐系统

本地运行的多 Agent 岗位推荐系统：**数据 Agent**（查库·抗幻觉）→ **推理 Agent**（分档·推荐）→ **安全层**（幻觉校验），前端展示分档推荐结果 + **双 AI 对话窗口**（数据库 AI / 推理 AI）。

## 架构

```
前端展示层（本地 Web UI：FastAPI + 单页 HTML + 双 AI 对话窗口）
        │
编排层 Orchestrator（LangGraph 图）
  START → data_agent → reasoning_agent → safety → END
        │
数据 Agent（agents/data_agent.py）       推理 Agent（agents/reasoning_agent.py）
  · 查库/过滤/统计，只输出数据库事实       · 按画像+抗拒规则+三档定义分档
  · 硬约束：无数据不编造                  · 硬约束：不查库、只基于数据Agent返回的事实
  · 结构化查询 + ChromaDB 语义召回        · 分档=确定性规则，理由=画像↔JD匹配+真实案例佐证
        │
爬虫（crawlers/）：腾讯官方 API / 实习僧(字体反爬破解) / 国聘网(央国企)  每周一自动更新
数据源：data/jobs_clean.json（1869 条，统一 schema）
配置：  config/profile.json（画像/抗拒规则/三档矩阵/央国企白名单）+ config/cases.json（真实案例证据库）
对话：  ui/app.py /api/chat（SSE 流式 DeepSeek）+ skills/job-hunting/SKILL.md（求职 skill）
```

## 目录

| 路径 | 说明 |
|---|---|
| `config/profile.json` | 画像、抗拒规则、三档定义、公司分级、央国企白名单（**可直接编辑**） |
| `config/cases.json` | 三档真实案例证据库（2026 年在招 + 薪资，推荐理由佐证） |
| `agents/data_agent.py` | 数据 Agent（交付物 1） |
| `agents/reasoning_agent.py` | 推理 Agent（交付物 2） |
| `orchestrator.py` | LangGraph 编排层 + 安全层（交付物 3） |
| `crawlers/` | 爬虫（腾讯 API / 实习僧字体反爬 / 国聘网央国企） |
| `rag/` | ChromaDB 向量检索层（ingest/retriever/embeddings，bge-small-zh） |
| `data/jobs_clean.json` | 清洗后的统一 schema 岗位数据（交付物 5） |
| `data/results_full.json` | 全量分档结果（前端数据源） |
| `ui/` | 前端看板 + 双 AI 对话窗口（交付物 6） |
| `skills/job-hunting/SKILL.md` | 求职推理 skill（内嵌张建鹏画像，推理 AI 使用） |
| `tests/test_pipeline.py` | 测试（10 项，交付物 8） |
| `scripts/` | clean_jobs / build_results / update_all（统一流水线） |

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 一键启动（自动清洗数据 + 生成全量分档 + 启动 UI）
python main.py

# 打开浏览器访问 http://127.0.0.1:8000
```

首次运行会下载 bge-small-zh embedding 模型（约 100MB，用于语义搜索；纯规则查询不依赖它）。

## 可选步骤

```bash
# 重建向量库（数据清洗后需要）
python -m rag.ingest --force

# 命令行测试（10 项，对应规格书验收 + 新需求）
python tests/test_pipeline.py        # 或 pytest tests/test_pipeline.py -v

# 手动更新数据（每周一 08:00 自动执行，计划任务 JobRecommendationWeeklyUpdate）
python scripts/update_all.py

# AI 对话窗口（页面内）：
#   🧠 推理 AI：问方向/匹配度/简历建议（加载求职 skill）
#   🗄️ 数据库 AI：更新数据/查库/改规则（需先安装 playwright: pip install playwright && python -m playwright install chromium）

# 编排层命令行演示
python orchestrator.py
```

## 三档定义（config/profile.json 可调）

- **实习期**（现在→2027.03）：实习·优选（大厂 AI 内容向实习）/ 实习·稳健（中厂内容/产品内容实习）/ 实习·保底（腰部公司，当前数据源暂无）
- **冲刺期**（2027.03→毕业）：冲刺档（大厂产品内容向）/ 稳定档（大厂或中厂内容/产品内容）/ 保底档（中厂方向匹配）
- 同一岗位双标：如字节 AI 策略岗，实习期=实习·优选，冲刺期=冲刺档

## 抗拒规则

- ❌ 纯销售岗（title 命中销售强词，如商务拓展/广告销售/KA销售）→ 自动标红
- ❌ 纯技术岗（研发/算法/后端等，title 无产品/内容/管理信号词）→ 自动标红
- ⚠️ 海外/外语向岗位（TikTok/海外/国际/英语/日语等）→ 直接筛选掉，归人工过目
- ⚠️ 打标存疑岗（title 主体含行业信号词但 subCat 是核心方向，如"电商运营"被标内容运营）→ 归人工过目
- ⚠️ 其余岗位全部列出，由用户人工过目（不做自动拒绝）

> 以上规则全部在 `config/profile.json` 的 `reject_rules` 中，可编辑。

## 数据说明

- 源数据：`assets/job-aggregation-site/data/jobs.json`（2316 条，求职雷达前身）
- 清洗规则：排除社招（24）/ 已下线（41）/ qualityScore=0（19）/ 重复 id（107）→ 2125 条
- 修复的数据错误：小红书等公司 95 条"实习生"岗被源数据标为"校招"，已按 title 含"实习"标准化为实习
- 全量分档：1869 条 → 推荐 940（实习·优选 693 / 实习·稳健 182；冲刺档 178 / 稳定档 525 / 保底档 237）、人工过目 929

## 遗留风险

1. **数据源无央国企/腰部公司（实习·保底档部分）**：湖北本省央国企岗位较少，UI 相应档位可能为空（需扩充爬虫数据源）
2. **subCat 依赖前身打标**：约 15 条空缺由规则补全；个别岗位 subCat 可能不精确（如电商运营岗被标为内容运营），推理基于 subCat 判定，人工过目可兜底
3. **推荐理由为规则模板**：基于画像能力关键词↔JD 重叠，未接入 DeepSeek 润色（如需要可在 `agents/reasoning_agent.py` 的 `_reason()` 处接入 LLM）
4. **语义搜索依赖本地模型**：首次需下载 bge-small-zh；向量库未构建时自动降级为关键词查询
5. **已下线岗位已排除**：数据是 2026-08 快照，岗位时效以 `publishDate` 为准，建议定期用前身爬虫更新
