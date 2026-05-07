#!/usr/bin/env python3
"""Amazon Lex v2 예시: 챗봇 대화 세션 관리.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: lex:RecognizeText
- Lex v2 봇 생성 완료 (콘솔 또는 AWS CLI)
- pip install boto3

환경 변수:
  LEX_BOT_ID       : Lex 봇 ID (예: ABCDE12345)
  LEX_BOT_ALIAS_ID : 봇 별칭 ID (예: TSTALIASID 또는 프로덕션 별칭)
  LEX_LOCALE_ID    : 로케일 (기본값: ko_KR)
  AWS_REGION       : 리전 (기본값: ap-northeast-2)

사용 방법:
  # 환경 변수 설정 후 대화형 실행
  export LEX_BOT_ID=ABCDE12345
  export LEX_BOT_ALIAS_ID=TSTALIASID
  python3 lex_example.py

  # 단일 발화 테스트
  python3 lex_example.py --text "서울 날씨 알려줘"
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "ap-northeast-2"
DEFAULT_LOCALE = "ko_KR"


def get_client(region: str = DEFAULT_REGION):
    return boto3.client("lexv2-runtime", region_name=region)


def recognize_text(
    client,
    bot_id: str,
    bot_alias_id: str,
    locale_id: str,
    session_id: str,
    text: str,
) -> dict:
    resp = client.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=locale_id,
        sessionId=session_id,
        text=text,
    )

    messages = [m["content"] for m in resp.get("messages", [])]
    intent = resp.get("sessionState", {}).get("intent", {})

    return {
        "messages": messages,
        "intent_name": intent.get("name", "-"),
        "intent_state": intent.get("state", "-"),
        "slots": {
            k: (v.get("value", {}).get("interpretedValue") if v else None)
            for k, v in intent.get("slots", {}).items()
        },
        "dialog_action": resp.get("sessionState", {})
                             .get("dialogAction", {})
                             .get("type", "-"),
    }


def print_response(resp: dict) -> None:
    print(f"  봇 응답: {' / '.join(resp['messages']) or '(응답 없음)'}")
    print(f"  인텐트: {resp['intent_name']} [{resp['intent_state']}]")
    if any(v for v in resp["slots"].values()):
        print(f"  슬롯: {resp['slots']}")
    print(f"  다음 액션: {resp['dialog_action']}")


def run_interactive(client, bot_id: str, bot_alias_id: str, locale_id: str) -> None:
    session_id = str(uuid.uuid4())
    print("=" * 60)
    print(f"[대화형 Lex 세션] session_id={session_id}")
    print("종료하려면 'quit' 또는 Ctrl+C 를 입력하세요.\n")

    while True:
        try:
            user_input = input("나: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[세션 종료]")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "종료"):
            print("[세션 종료]")
            break

        resp = recognize_text(client, bot_id, bot_alias_id, locale_id, session_id, user_input)
        print_response(resp)
        print()

        if resp["intent_state"] in ("Fulfilled", "Failed", "ReadyForFulfillment"):
            print("[인텐트 완료 — 세션 종료]")
            break

    print("=" * 60)


def run_single(client, bot_id: str, bot_alias_id: str, locale_id: str, text: str) -> None:
    session_id = str(uuid.uuid4())
    print("=" * 60)
    print(f"[단일 발화 테스트]")
    print(f"  입력: {text}")
    resp = recognize_text(client, bot_id, bot_alias_id, locale_id, session_id, text)
    print_response(resp)
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Lex v2 챗봇 예시")
    parser.add_argument("--text", help="단일 발화 텍스트 (생략 시 대화형 모드)")
    args = parser.parse_args()

    bot_id = os.getenv("LEX_BOT_ID")
    bot_alias_id = os.getenv("LEX_BOT_ALIAS_ID")
    locale_id = os.getenv("LEX_LOCALE_ID", DEFAULT_LOCALE)
    region = os.getenv("AWS_REGION", DEFAULT_REGION)

    if not bot_id or not bot_alias_id:
        print("[오류] LEX_BOT_ID 와 LEX_BOT_ALIAS_ID 환경 변수를 설정해주세요.")
        print("  export LEX_BOT_ID=<봇 ID>")
        print("  export LEX_BOT_ALIAS_ID=<별칭 ID>")
        sys.exit(1)

    client = get_client(region)

    try:
        if args.text:
            run_single(client, bot_id, bot_alias_id, locale_id, args.text)
        else:
            run_interactive(client, bot_id, bot_alias_id, locale_id)
    except ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
