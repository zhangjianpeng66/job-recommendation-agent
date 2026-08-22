# AI 求职工作台（公开技术快照）

一个本地运行的多 Agent 求职决策原型：把分散岗位先整理成可查询数据，再由规则推理完成分档，最后通过安全层检查推荐结果是否来自真实岗位记录。

> 这个仓库保留的是早期技术快照，用于展示数据、推理与安全校验如何分层。最新个性化 V1 仍在本地迭代，尚未把未完成的网申助手和用户资料管理功能包装成公开成品。

## 为什么做

岗位越多并不等于决策越容易。这个原型优先解决三个问题：

- **信息口径不一：** 先清洗、去重和统一字段，再讨论推荐。
- **推荐理由不透明：** 数据 Agent 只返回事实，推理 Agent 只基于这些事实分档。
- **AI 容易说得像真的：** 安全层检查输出中的岗位 ID 是否确实来自本次查询。

## 当前可以验证什么

- `data/jobs_clean.json`：1,869 条统一结构的岗位数据。
- `config/profile.json`：个人约束、分档矩阵和人工复核规则，可直接修改。
- `agents/` + `orchestrator.py`：数据查询、规则推理、安全校验三层流程。
- `ui/`：本地 FastAPI 看板和可选的 DeepSeek 对话入口。
- `tests/test_pipeline.py`：10 个测试函数；其中 9 项可离线运行，1 项需要用户自行配置 DeepSeek API Key。

2026-08-22 本地离线验证结果：`9 passed, 1 deselected`。仓库暂未配置 CI，因此这里不使用“持续 10/10 通过”之类无法公开复核的表述。

## 架构

```text
本地 Web UI（FastAPI）
        │
LangGraph Orchestrator
START → Data Agent → Reasoning Agent → Safety → END
        │               │               │
查询/过滤/统计       规则分档与理由      事实 ID 校验
只返回数据库事实     不自行补造岗位      异常进入人工复核
        │
结构化岗位数据 + 可选 ChromaDB 语义检索
```

这个版本中的岗位分档主要由确定性规则完成；DeepSeek 用于可选对话，不决定基础推荐结果。

## 快速体验

建议使用 Python 3.11，并在虚拟环境中运行：

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python main.py
```

打开 `http://127.0.0.1:8000`。

首次使用语义搜索时会下载 embedding 模型；只运行规则查询与离线测试不需要配置 DeepSeek API Key。

## 测试

```bash
# 推荐：运行 9 项无需外部 API 的测试
python -m pytest tests/test_pipeline.py -k "not test_llm_client_api" -q

# 配置 DEEPSEEK_API_KEY 后，才运行完整测试
python -m pytest tests/test_pipeline.py -q
```

测试覆盖销售岗过滤、AI 内容岗分档、海外岗人工复核、数据 Agent 抗幻觉、推荐事实校验、结果文件一致性和案例证据等路径。

## 主要目录

| 路径 | 作用 |
|---|---|
| `config/profile.json` | 画像约束、分档定义、公司分级、人工复核规则 |
| `config/cases.json` | 推荐理由使用的案例证据 |
| `agents/data_agent.py` | 岗位查询与数据库事实输出 |
| `agents/reasoning_agent.py` | 确定性分档和推荐理由 |
| `orchestrator.py` | LangGraph 编排与安全层 |
| `rag/` | ChromaDB 语义检索（可选） |
| `data/jobs_clean.json` | 清洗后的岗位数据快照 |
| `ui/` | FastAPI 看板与对话入口 |
| `tests/test_pipeline.py` | 端到端规则测试 |

## 已知限制

1. 岗位数据是 2026-08 快照，具体招聘状态必须回到招聘官网确认。
2. 数据源对央国企、湖北本地和腰部公司的覆盖仍不完整。
3. 个人规则目前写在配置文件中，还不是面向任意用户的成熟资料管理产品。
4. 推荐理由主要是规则模板，真实帮助程度还需要更多用户任务验证。
5. 语义检索首次需要下载本地模型；未构建向量库时会降级为关键词查询。
6. 对话能力依赖用户自己的 API Key；`.env` 已被 Git 忽略，不应提交密钥。

## 下一步产品方向

- 将简历与详细经历整理为用户可维护的本地资料包，而不是把某个人的画像写死。
- 让每条推荐展示来源、约束命中和待确认信息，保留人的最终判断权。
- 用小范围任务测试验证“节省了多少时间、减少了多少遗漏”，再决定是否扩大上线。
