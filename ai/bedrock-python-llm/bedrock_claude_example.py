#!/usr/bin/env python3
"""Anthropic Claude LLM 호출 예시.

사전 준비:
- ANTHROPIC_API_KEY 환경 변수 설정
- pip install anthropic
"""

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import os  # 환경 변수(ANTHROPIC_API_KEY, CLAUDE_MODEL_ID) 읽기용

import anthropic  # Anthropic 공식 Python SDK (pip install anthropic)


# 기본으로 사용할 Claude 모델 ID (환경 변수로 덮어쓸 수 있습니다)
DEFAULT_MODEL_ID = "claude-opus-4-7"


def ask_claude(prompt: str) -> str:
    """Anthropic API를 호출해 Claude의 응답 텍스트를 반환합니다.

    Args:
        prompt: 사용자가 Claude에게 전달할 질문 또는 지시문

    Returns:
        Claude가 생성한 텍스트 응답 (str)

    Raises:
        RuntimeError: ANTHROPIC_API_KEY 환경 변수가 설정되어 있지 않을 때
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")  # 환경 변수에서 API 키 읽기
    if not api_key:
        # API 키가 없으면 호출 자체가 불가능하므로 즉시 에러를 발생시킵니다
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

    model = os.getenv("CLAUDE_MODEL_ID", DEFAULT_MODEL_ID)
    # CLAUDE_MODEL_ID 환경 변수가 있으면 그 값을 사용하고, 없으면 DEFAULT_MODEL_ID를 사용합니다
    client = anthropic.Anthropic(api_key=api_key)  # Anthropic API 클라이언트 초기화

    message = client.messages.create(
        model=model,          # 사용할 Claude 모델 ID
        max_tokens=512,       # 응답 최대 토큰 수 (비용 및 응답 길이 제어)
        messages=[{"role": "user", "content": prompt}],  # 단일 사용자 메시지 형식
    )
    return message.content[0].text  # 첫 번째 콘텐츠 블록의 텍스트만 반환


if __name__ == "__main__":
    # 스크립트를 직접 실행할 때 테스트 질문을 Claude에 전송합니다
    user_prompt = "AWS ALB와 EC2를 사용하는 기본 아키텍처를 5줄로 설명해줘."
    print(ask_claude(user_prompt))  # Claude의 응답을 표준 출력에 출력합니다
