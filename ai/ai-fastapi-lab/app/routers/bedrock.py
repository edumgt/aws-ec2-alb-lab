"""Bedrock (Anthropic Claude) 라우터.

환경 변수:
    ANTHROPIC_API_KEY : Anthropic API 키 (필수)
    CLAUDE_MODEL_ID   : 사용할 Claude 모델 ID (기본값: claude-opus-4-7)
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

DEFAULT_MODEL_ID = "claude-opus-4-7"


class AskRequest(BaseModel):
    prompt: str = Field(..., description="Claude에게 전달할 질문 또는 지시문")
    model_id: str = Field(DEFAULT_MODEL_ID, description="Claude 모델 ID")
    max_tokens: int = Field(512, ge=1, le=4096, description="최대 응답 토큰 수")


class AskResponse(BaseModel):
    response: str
    model_id: str


@router.post("/ask", response_model=AskResponse, summary="Claude에게 질문하기")
def ask_claude(req: AskRequest) -> AskResponse:
    """Anthropic API를 호출해 Claude의 응답 텍스트를 반환합니다."""
    try:
        import anthropic  # 런타임 임포트 (설치 여부 체크)
    except ImportError:
        raise HTTPException(status_code=500, detail="anthropic 패키지가 설치되지 않았습니다.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")

    model = os.getenv("CLAUDE_MODEL_ID", req.model_id)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=req.max_tokens,
            messages=[{"role": "user", "content": req.prompt}],
        )
        return AskResponse(response=message.content[0].text, model_id=model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
