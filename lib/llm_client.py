# -*- coding: utf-8 -*-
"""
LLM 客户端封装：DeepSeek API（OpenAI 兼容），支持流式（SSE）。
key 只从 .env 读取，服务端使用，不暴露给浏览器。
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    """轻量 .env 加载（不依赖 python-dotenv 时可用）。"""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env()

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

DEFAULT_SYSTEM_PROMPT = "你是张建鹏的个人求职 AI 助手，回答简洁、结构化、基于事实，不编造。"


def api_key_available() -> bool:
    return bool(API_KEY)


def chat_stream(messages: List[Dict[str, str]],
                system: str | None = None,
                temperature: float = 0.3) -> Iterator[str]:
    """
    流式对话：逐段 yield 增量 content。
    messages: [{"role": "user"|"assistant", "content": "..."}]
    system: 角色 system prompt（覆盖默认）
    """
    if not API_KEY:
        yield "（未配置 DEEPSEEK_API_KEY，请检查 .env）"
        return
    full = [{"role": "system", "content": system or DEFAULT_SYSTEM_PROMPT}]
    full.extend(messages)
    payload: Dict[str, Any] = {
        "model": MODEL,
        "messages": full,
        "stream": True,
        "temperature": temperature,
    }
    with httpx.Client(timeout=None) as client:
        with client.stream("POST", f"{BASE_URL}/chat/completions",
                           headers={
                               "Authorization": f"Bearer {API_KEY}",
                               "Content-Type": "application/json",
                           },
                           json=payload) as resp:
            if resp.status_code != 200:
                yield f"（API 错误 {resp.status_code}：{resp.text[:200]}）"
                return
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content


def chat_once(messages: List[Dict[str, str]],
              system: str | None = None,
              temperature: float = 0.3) -> str:
    """非流式单次对话：返回完整回复。"""
    return "".join(chat_stream(messages, system=system, temperature=temperature))


if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("API key 可用:", api_key_available())
    print("模型:", MODEL)
    if api_key_available():
        text = chat_once([{"role": "user", "content": "用一句话介绍你自己"}],
                         system="你是测试助手，只说一句话。")
        print("回复:", text)
