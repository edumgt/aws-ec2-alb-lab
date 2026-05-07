#!/usr/bin/env python3
"""Amazon Comprehend 예시: 감성 분석, 개체명 인식, 언어 감지.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: comprehend:DetectSentiment, comprehend:DetectEntities, comprehend:DetectDominantLanguage
- pip install boto3
"""

from __future__ import annotations

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "us-east-1"

SAMPLE_TEXTS = {
    "en": "AWS re:Invent is an amazing conference held in Las Vegas every year. I love the keynote sessions!",
    "ko": "아마존 웹 서비스는 클라우드 컴퓨팅 분야에서 매우 뛰어난 서비스를 제공합니다. 정말 훌륭한 플랫폼입니다.",
}


def get_client(region: str = DEFAULT_REGION):
    return boto3.client("comprehend", region_name=region)


def detect_language(client, text: str) -> str:
    resp = client.detect_dominant_language(Text=text)
    languages = resp["Languages"]
    top = max(languages, key=lambda x: x["Score"])
    return top["LanguageCode"]


def detect_sentiment(client, text: str, lang_code: str) -> dict:
    resp = client.detect_sentiment(Text=text, LanguageCode=lang_code)
    return {
        "sentiment": resp["Sentiment"],
        "scores": {k: round(v, 4) for k, v in resp["SentimentScore"].items()},
    }


def detect_entities(client, text: str, lang_code: str) -> list[dict]:
    resp = client.detect_entities(Text=text, LanguageCode=lang_code)
    return [
        {"text": e["Text"], "type": e["Type"], "score": round(e["Score"], 4)}
        for e in resp["Entities"]
    ]


def run_lab(text: str, region: str = DEFAULT_REGION) -> None:
    client = get_client(region)

    print("=" * 60)
    print(f"[입력 텍스트]\n{text}\n")

    lang = detect_language(client, text)
    print(f"[언어 감지] {lang}\n")

    sentiment = detect_sentiment(client, text, lang)
    print(f"[감성 분석]")
    print(f"  결과: {sentiment['sentiment']}")
    for label, score in sentiment["scores"].items():
        print(f"  {label}: {score}")

    print(f"\n[개체명 인식]")
    entities = detect_entities(client, text, lang)
    if entities:
        for e in entities:
            print(f"  [{e['type']}] {e['text']} (신뢰도: {e['score']})")
    else:
        print("  감지된 개체 없음")
    print("=" * 60)


if __name__ == "__main__":
    try:
        for label, text in SAMPLE_TEXTS.items():
            run_lab(text)
            print()
    except ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
    except BotoCoreError as exc:
        print(f"[AWS 연결 오류] {exc}")
