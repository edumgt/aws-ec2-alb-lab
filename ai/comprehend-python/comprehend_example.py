#!/usr/bin/env python3
"""Amazon Comprehend 예시: 감성 분석, 개체명 인식, 언어 감지.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: comprehend:DetectSentiment, comprehend:DetectEntities, comprehend:DetectDominantLanguage
- pip install boto3
"""

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import boto3  # AWS SDK for Python — Comprehend 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# Comprehend가 지원하는 기본 리전 (us-east-1은 Comprehend의 전체 기능 지원 리전입니다)
DEFAULT_REGION = "us-east-1"

# 언어별 샘플 입력 텍스트 (실습 실행 시 기본으로 사용됩니다)
SAMPLE_TEXTS = {
    "en": "AWS re:Invent is an amazing conference held in Las Vegas every year. I love the keynote sessions!",
    "ko": "아마존 웹 서비스는 클라우드 컴퓨팅 분야에서 매우 뛰어난 서비스를 제공합니다. 정말 훌륭한 플랫폼입니다.",
}


def get_client(region: str = DEFAULT_REGION):
    """지정 리전의 Amazon Comprehend boto3 클라이언트를 반환합니다."""
    return boto3.client("comprehend", region_name=region)


def detect_language(client, text: str) -> str:
    """텍스트에서 주요 언어를 감지하고 가장 높은 신뢰도를 가진 언어 코드를 반환합니다.

    Returns:
        언어 코드 문자열 (예: "en", "ko")
    """
    resp = client.detect_dominant_language(Text=text)  # Comprehend 언어 감지 API 호출
    languages = resp["Languages"]  # 감지된 언어 목록 (언어 코드 + 신뢰도 점수)
    top = max(languages, key=lambda x: x["Score"])  # 신뢰도(Score)가 가장 높은 언어 선택
    return top["LanguageCode"]  # 최고 신뢰도 언어 코드 반환 (예: "ko", "en")


def detect_sentiment(client, text: str, lang_code: str) -> dict:
    """텍스트의 감성(긍정·부정·중립·혼합)을 분석하고 각 감성의 신뢰도 점수를 반환합니다.

    Returns:
        {"sentiment": "POSITIVE"|"NEGATIVE"|"NEUTRAL"|"MIXED",
         "scores": {"Positive": float, "Negative": float, ...}}
    """
    resp = client.detect_sentiment(Text=text, LanguageCode=lang_code)  # 감성 분석 API 호출
    return {
        "sentiment": resp["Sentiment"],  # 전체 감성 레이블 (가장 높은 점수 기준)
        "scores": {k: round(v, 4) for k, v in resp["SentimentScore"].items()},
        # SentimentScore의 각 감성 점수를 소수점 4자리로 반올림하여 반환
    }


def detect_entities(client, text: str, lang_code: str) -> list[dict]:
    """텍스트에서 개체명(인물·조직·장소·날짜 등)을 인식하여 리스트로 반환합니다.

    Returns:
        [{"text": str, "type": str, "score": float}, ...] 형태의 개체명 목록
    """
    resp = client.detect_entities(Text=text, LanguageCode=lang_code)  # 개체명 인식 API 호출
    return [
        {"text": e["Text"], "type": e["Type"], "score": round(e["Score"], 4)}
        # 각 개체의 원문·타입·신뢰도를 딕셔너리로 정리 (신뢰도는 소수점 4자리로 반올림)
        for e in resp["Entities"]
    ]


def run_lab(text: str, region: str = DEFAULT_REGION) -> None:
    """단일 텍스트에 대해 언어 감지 → 감성 분석 → 개체명 인식을 순서대로 실행하고 결과를 출력합니다."""
    client = get_client(region)  # Comprehend 클라이언트 생성

    print("=" * 60)
    print(f"[입력 텍스트]\n{text}\n")  # 분석 대상 텍스트 출력

    lang = detect_language(client, text)  # 1단계: 언어 감지
    print(f"[언어 감지] {lang}\n")        # 감지된 언어 코드 출력

    sentiment = detect_sentiment(client, text, lang)  # 2단계: 감성 분석 (감지된 언어 사용)
    print(f"[감성 분석]")
    print(f"  결과: {sentiment['sentiment']}")  # 전체 감성 레이블 출력
    for label, score in sentiment["scores"].items():
        print(f"  {label}: {score}")  # 각 감성(긍정·부정·중립·혼합) 신뢰도 점수 출력

    print(f"\n[개체명 인식]")
    entities = detect_entities(client, text, lang)  # 3단계: 개체명 인식 (감지된 언어 사용)
    if entities:
        for e in entities:
            print(f"  [{e['type']}] {e['text']} (신뢰도: {e['score']})")
            # 개체 타입(PERSON, ORGANIZATION 등)·원문·신뢰도 출력
    else:
        print("  감지된 개체 없음")  # 인식된 개체가 없을 때 안내 메시지
    print("=" * 60)


if __name__ == "__main__":
    try:
        for label, text in SAMPLE_TEXTS.items():  # 영어·한국어 샘플 텍스트를 순서대로 처리
            run_lab(text)   # 각 텍스트에 대해 분석 실행
            print()         # 텍스트 간 빈 줄 구분
    except ClientError as exc:
        # AWS 서비스 오류 (권한 부족, 잘못된 파라미터 등) 처리
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
    except BotoCoreError as exc:
        # 네트워크 연결 실패, 자격 증명 오류 등 AWS SDK 수준의 오류 처리
        print(f"[AWS 연결 오류] {exc}")
