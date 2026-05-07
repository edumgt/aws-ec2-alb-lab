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

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리 (--text 옵션 처리)
import os        # 환경 변수(LEX_BOT_ID 등) 읽기용
import sys       # sys.exit()을 통한 비정상 종료 처리
import uuid      # 고유한 세션 ID 생성 (UUID4)

import boto3  # AWS SDK — Lex v2 런타임 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# Lex v2 지원 기본 리전 (서울 리전)
DEFAULT_REGION = "ap-northeast-2"
# 기본 로케일 ID (한국어)
DEFAULT_LOCALE = "ko_KR"


def get_client(region: str = DEFAULT_REGION):
    """지정 리전의 Lex v2 런타임 boto3 클라이언트를 반환합니다."""
    return boto3.client("lexv2-runtime", region_name=region)  # Lex v2 런타임 엔드포인트 사용


def recognize_text(
    client,
    bot_id: str,       # Lex v2 봇 ID (콘솔에서 확인)
    bot_alias_id: str, # 봇 별칭 ID (배포 버전 지정)
    locale_id: str,    # 로케일 (예: ko_KR, en_US)
    session_id: str,   # 대화 세션 식별자 (같은 세션이면 컨텍스트 유지)
    text: str,         # 사용자 발화 텍스트
) -> dict:
    """사용자 발화 텍스트를 Lex v2에 전송하고 봇 응답 정보를 구조화하여 반환합니다.

    Returns:
        {"messages": list, "intent_name": str, "intent_state": str,
         "slots": dict, "dialog_action": str} 형태의 응답 딕셔너리
    """
    resp = client.recognize_text(
        botId=bot_id,           # 봇 ID
        botAliasId=bot_alias_id, # 봇 별칭 ID
        localeId=locale_id,     # 로케일 ID
        sessionId=session_id,   # 세션 ID (컨텍스트 연속성)
        text=text,              # 사용자 발화
    )

    messages = [m["content"] for m in resp.get("messages", [])]
    # 봇이 반환한 메시지 목록에서 content(텍스트) 필드만 추출합니다
    intent = resp.get("sessionState", {}).get("intent", {})
    # 세션 상태에서 현재 인식된 인텐트 정보를 가져옵니다

    return {
        "messages": messages,                             # 봇의 응답 메시지 목록
        "intent_name": intent.get("name", "-"),           # 인식된 인텐트 이름 (없으면 "-")
        "intent_state": intent.get("state", "-"),         # 인텐트 상태 (InProgress, Fulfilled 등)
        "slots": {
            k: (v.get("value", {}).get("interpretedValue") if v else None)
            # 각 슬롯의 해석된 값(interpretedValue)을 추출 (슬롯이 None이면 None 반환)
            for k, v in intent.get("slots", {}).items()
        },
        "dialog_action": resp.get("sessionState", {})
                             .get("dialogAction", {})
                             .get("type", "-"),
        # 다음 대화 액션 타입 (ElicitSlot, Delegate, Close 등)
    }


def print_response(resp: dict) -> None:
    """recognize_text 결과 딕셔너리를 사람이 읽기 쉬운 형식으로 출력합니다."""
    print(f"  봇 응답: {' / '.join(resp['messages']) or '(응답 없음)'}")
    # 여러 메시지는 " / "로 구분하여 출력, 메시지 없으면 "(응답 없음)" 표시
    print(f"  인텐트: {resp['intent_name']} [{resp['intent_state']}]")
    # 인식된 인텐트 이름과 현재 상태(InProgress, Fulfilled 등) 출력
    if any(v for v in resp["slots"].values()):
        # 하나 이상의 슬롯에 값이 채워진 경우에만 슬롯 정보 출력
        print(f"  슬롯: {resp['slots']}")
    print(f"  다음 액션: {resp['dialog_action']}")  # 다음 대화 흐름 액션 출력


def run_interactive(client, bot_id: str, bot_alias_id: str, locale_id: str) -> None:
    """사용자 입력을 반복적으로 받아 Lex v2 봇과 대화형 세션을 진행합니다."""
    session_id = str(uuid.uuid4())  # 고유한 세션 ID 생성 (UUID4)
    print("=" * 60)
    print(f"[대화형 Lex 세션] session_id={session_id}")
    print("종료하려면 'quit' 또는 Ctrl+C 를 입력하세요.\n")

    while True:  # 사용자가 종료를 요청하거나 인텐트가 완료될 때까지 반복
        try:
            user_input = input("나: ").strip()  # 표준 입력에서 사용자 발화를 읽고 앞뒤 공백 제거
        except (EOFError, KeyboardInterrupt):
            # EOF(파이프 입력 종료) 또는 Ctrl+C 인터럽트 시 세션 종료
            print("\n[세션 종료]")
            break

        if not user_input or user_input.lower() in ("quit", "exit", "종료"):
            # 빈 입력이거나 종료 키워드 입력 시 루프 탈출
            print("[세션 종료]")
            break

        resp = recognize_text(client, bot_id, bot_alias_id, locale_id, session_id, user_input)
        # 사용자 발화를 Lex v2에 전송하고 봇 응답 수신
        print_response(resp)  # 응답 내용 출력
        print()               # 대화 간 빈 줄 구분

        if resp["intent_state"] in ("Fulfilled", "Failed", "ReadyForFulfillment"):
            # 인텐트가 완료(Fulfilled)·실패(Failed)·이행 준비(ReadyForFulfillment) 상태이면 종료
            print("[인텐트 완료 — 세션 종료]")
            break

    print("=" * 60)


def run_single(client, bot_id: str, bot_alias_id: str, locale_id: str, text: str) -> None:
    """단일 발화 텍스트를 Lex v2에 전송하고 결과를 출력합니다."""
    session_id = str(uuid.uuid4())  # 단일 요청용 임시 세션 ID 생성
    print("=" * 60)
    print(f"[단일 발화 테스트]")
    print(f"  입력: {text}")  # 전송할 발화 텍스트 출력
    resp = recognize_text(client, bot_id, bot_alias_id, locale_id, session_id, text)
    # 단일 발화를 Lex v2에 전송
    print_response(resp)  # 봇 응답 출력
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Lex v2 챗봇 예시")
    parser.add_argument("--text", help="단일 발화 텍스트 (생략 시 대화형 모드)")
    # --text 가 주어지면 단일 발화 모드, 없으면 대화형 모드로 동작합니다
    args = parser.parse_args()  # 커맨드라인 인수 파싱

    bot_id = os.getenv("LEX_BOT_ID")           # 환경 변수에서 봇 ID 읽기
    bot_alias_id = os.getenv("LEX_BOT_ALIAS_ID")  # 환경 변수에서 봇 별칭 ID 읽기
    locale_id = os.getenv("LEX_LOCALE_ID", DEFAULT_LOCALE)  # 로케일 (기본값: ko_KR)
    region = os.getenv("AWS_REGION", DEFAULT_REGION)        # 리전 (기본값: ap-northeast-2)

    if not bot_id or not bot_alias_id:
        # 필수 환경 변수가 없으면 설정 방법을 안내하고 비정상 종료합니다
        print("[오류] LEX_BOT_ID 와 LEX_BOT_ALIAS_ID 환경 변수를 설정해주세요.")
        print("  export LEX_BOT_ID=<봇 ID>")
        print("  export LEX_BOT_ALIAS_ID=<별칭 ID>")
        sys.exit(1)

    client = get_client(region)  # 지정 리전의 Lex v2 클라이언트 생성

    try:
        if args.text:
            run_single(client, bot_id, bot_alias_id, locale_id, args.text)
            # --text 옵션이 있으면 단일 발화 모드로 실행
        else:
            run_interactive(client, bot_id, bot_alias_id, locale_id)
            # --text 옵션 없으면 대화형 모드로 실행
    except ClientError as exc:
        # AWS 서비스 오류 (권한 부족, 잘못된 봇 ID 등) 처리
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        # 네트워크 연결 실패 등 SDK 수준 오류 처리
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
