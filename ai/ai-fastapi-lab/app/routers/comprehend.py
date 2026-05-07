"""Amazon Comprehend 라우터: 감성 분석, 개체명 인식, 언어 감지."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

DEFAULT_REGION = "us-east-1"


class ComprehendRequest(BaseModel):
    text: str = Field(..., min_length=1, description="분석할 텍스트")
    region: str = Field(DEFAULT_REGION, description="AWS 리전")


class SentimentResult(BaseModel):
    label: str
    scores: dict[str, float]


class EntityResult(BaseModel):
    text: str
    type: str
    score: float


class ComprehendResponse(BaseModel):
    language: str
    sentiment: SentimentResult
    entities: list[EntityResult]


@router.post("/analyze", response_model=ComprehendResponse, summary="텍스트 분석")
def analyze(req: ComprehendRequest) -> ComprehendResponse:
    """언어 감지 → 감성 분석 → 개체명 인식을 순서대로 실행하고 결과를 반환합니다."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client("comprehend", region_name=req.region)
    try:
        # 1. 언어 감지
        lang_resp = client.detect_dominant_language(Text=req.text)
        lang = max(lang_resp["Languages"], key=lambda x: x["Score"])["LanguageCode"]

        # 2. 감성 분석
        sent_resp = client.detect_sentiment(Text=req.text, LanguageCode=lang)
        sentiment = SentimentResult(
            label=sent_resp["Sentiment"],
            scores={k: round(v, 4) for k, v in sent_resp["SentimentScore"].items()},
        )

        # 3. 개체명 인식
        ent_resp = client.detect_entities(Text=req.text, LanguageCode=lang)
        entities = [
            EntityResult(
                text=e["Text"],
                type=e["Type"],
                score=round(e["Score"], 4),
            )
            for e in ent_resp["Entities"]
        ]

        return ComprehendResponse(language=lang, sentiment=sentiment, entities=entities)
    except ClientError as exc:
        err = exc.response.get("Error", {})
        raise HTTPException(status_code=500, detail=f"{err.get('Code')}: {err.get('Message')}")
    except BotoCoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
