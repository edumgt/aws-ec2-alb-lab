#!/usr/bin/env python3
"""Anthropic Claude LLM 호출 예시.

사전 준비:
- ANTHROPIC_API_KEY 환경 변수 설정
- pip install anthropic
"""

from __future__ import annotations

import os

import anthropic


DEFAULT_MODEL_ID = "claude-opus-4-7"


def ask_claude(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

    model = os.getenv("CLAUDE_MODEL_ID", DEFAULT_MODEL_ID)
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


if __name__ == "__main__":
    user_prompt = "AWS ALB와 EC2를 사용하는 기본 아키텍처를 5줄로 설명해줘."
    print(ask_claude(user_prompt))
