#!/usr/bin/env python3
"""Amazon Polly 예시: 텍스트 → 음성(MP3) 변환.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: polly:SynthesizeSpeech, polly:DescribeVoices
- pip install boto3

사용 방법:
  # 기본 (한국어, Seoyeon 음성)
  python3 polly_example.py --text "안녕하세요, 아마존 폴리입니다."

  # 영어 음성 지정
  python3 polly_example.py --text "Hello, this is Amazon Polly." --voice Joanna

  # SSML 사용 (강조, 속도 조절)
  python3 polly_example.py --ssml "<speak>안녕하세요. <emphasis level='strong'>중요한</emphasis> 내용입니다.</speak>"

  # 사용 가능한 음성 목록 확인
  python3 polly_example.py --list-voices --lang ko-KR
"""

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리
import sys       # sys.exit()을 통한 비정상 종료 처리
from pathlib import Path  # 파일 경로 조작 및 파일 쓰기용

import boto3  # AWS SDK — Polly 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# 기본 설정값 상수
DEFAULT_REGION = "ap-northeast-2"  # Polly가 지원하는 서울 리전
DEFAULT_VOICE = "Seoyeon"          # 기본 한국어 음성 (뉴럴 엔진 지원)
DEFAULT_OUTPUT = "output.mp3"      # 변환된 오디오 파일의 기본 저장 경로


def get_client(region: str = DEFAULT_REGION):
    """지정 리전의 Amazon Polly boto3 클라이언트를 반환합니다."""
    return boto3.client("polly", region_name=region)


def synthesize(
    client,
    text: str,          # 변환할 텍스트 또는 SSML 문자열
    voice_id: str,      # 사용할 음성 ID (예: Seoyeon, Joanna)
    output_path: str,   # 출력 MP3 파일 경로
    is_ssml: bool = False,  # True이면 SSML 형식으로 처리, False이면 일반 텍스트
) -> int:
    """텍스트(또는 SSML)를 MP3 오디오로 변환하여 파일로 저장하고 파일 크기를 반환합니다."""
    resp = client.synthesize_speech(
        Text=text,                                   # 변환할 텍스트
        VoiceId=voice_id,                            # 음성 ID
        OutputFormat="mp3",                          # 출력 포맷 (MP3)
        TextType="ssml" if is_ssml else "text",      # 텍스트 타입 (SSML 또는 일반 텍스트)
        Engine="neural" if voice_id == "Seoyeon" else "standard",
        # Seoyeon은 뉴럴 엔진만 지원, 그 외 음성은 표준 엔진 사용
    )

    audio_data = resp["AudioStream"].read()  # 스트리밍 오디오 응답에서 전체 바이트 데이터 읽기
    Path(output_path).write_bytes(audio_data)  # 읽은 바이트 데이터를 파일로 저장
    return len(audio_data)  # 저장된 파일의 바이트 크기 반환


def list_voices(client, language_code: str | None = None) -> list[dict]:
    """사용 가능한 Polly 음성 목록을 조회하여 반환합니다.

    Args:
        language_code: 특정 언어로 필터링 (예: ko-KR). None이면 전체 언어 반환.

    Returns:
        [{"id": str, "name": str, "gender": str, "language": str, "engines": list}, ...] 형태의 음성 목록
    """
    kwargs = {}               # describe_voices API 호출 파라미터 딕셔너리
    if language_code:
        kwargs["LanguageCode"] = language_code  # 언어 코드 필터가 있으면 파라미터에 추가

    voices = []               # 결과를 담을 음성 목록 초기화
    paginator = client.get_paginator("describe_voices")  # 페이지네이션 지원 paginator 생성
    for page in paginator.paginate(**kwargs):  # 모든 페이지를 순서대로 순회
        for v in page["Voices"]:              # 현재 페이지의 각 음성 정보 처리
            voices.append({
                "id": v["Id"],                          # 음성 ID (API 호출 시 사용)
                "name": v["Name"],                      # 음성 이름
                "gender": v["Gender"],                  # 성별 (Male/Female)
                "language": v["LanguageName"],          # 언어 이름 (예: Korean)
                "engines": v.get("SupportedEngines", []),  # 지원 엔진 목록 (standard/neural)
            })
    return voices  # 조회된 전체 음성 목록 반환


def run_lab(args) -> None:
    """커맨드라인 인수에 따라 음성 합성 또는 음성 목록 조회를 실행합니다."""
    client = get_client(DEFAULT_REGION)  # Polly 클라이언트 생성
    print("=" * 60)

    if args.list_voices:  # --list-voices 옵션이 주어진 경우 음성 목록 출력 후 종료
        voices = list_voices(client, args.lang)  # 언어 필터 적용해 음성 목록 조회
        lang_label = f"({args.lang})" if args.lang else "(전체)"  # 필터 언어 표시 레이블
        print(f"[사용 가능한 음성 목록] {lang_label}")
        for v in voices:
            engines = ", ".join(v["engines"])  # 지원 엔진 목록을 콤마로 구분하여 문자열로 변환
            print(f"  {v['id']:12s}  {v['gender']:6s}  {v['language']}  [{engines}]")
            # 음성 ID(좌정렬 12자)·성별(좌정렬 6자)·언어 이름·지원 엔진 출력
        print("=" * 60)
        return  # 음성 목록 출력 후 함수 종료 (합성 수행 안 함)

    text = args.ssml or args.text  # SSML이 지정되면 SSML 사용, 없으면 일반 텍스트 사용
    is_ssml = bool(args.ssml)      # SSML 여부 플래그 설정
    voice = args.voice or DEFAULT_VOICE  # 음성 ID (없으면 기본값 Seoyeon)
    output = args.output or DEFAULT_OUTPUT  # 출력 경로 (없으면 기본값 output.mp3)

    print(f"[입력 텍스트] {text[:80]}{'...' if len(text) > 80 else ''}")
    # 텍스트가 80자를 초과하면 "..."으로 생략하여 표시
    print(f"[음성] {voice}  [포맷] MP3  [SSML] {'예' if is_ssml else '아니오'}")
    # 선택된 음성·출력 포맷·SSML 사용 여부 출력

    size = synthesize(client, text, voice, output, is_ssml)  # 텍스트 → MP3 변환 실행
    print(f"\n[변환 완료]")
    print(f"  저장 경로: {Path(output).resolve()}")  # 절대 경로로 저장 위치 출력
    print(f"  파일 크기: {size:,} bytes")            # 천 단위 구분자(,)를 포함하여 파일 크기 출력
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Polly 텍스트 → 음성 변환 예시")
    group = parser.add_mutually_exclusive_group()  # --text / --ssml / --list-voices 는 상호 배타적
    group.add_argument("--text", help="변환할 일반 텍스트")
    group.add_argument("--ssml", help="변환할 SSML 텍스트")
    group.add_argument("--list-voices", action="store_true", help="사용 가능한 음성 목록 출력")
    parser.add_argument("--voice", help=f"음성 ID (기본값: {DEFAULT_VOICE})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="출력 MP3 파일 경로")
    parser.add_argument("--lang", help="언어 코드 필터 (--list-voices 전용, 예: ko-KR)")
    args = parser.parse_args()  # 커맨드라인 인수 파싱

    if not args.list_voices and not args.text and not args.ssml:
        # 세 옵션 중 하나도 지정되지 않았으면 오류 메시지와 함께 도움말 출력
        parser.error("--text, --ssml, 또는 --list-voices 중 하나를 지정하세요.")

    try:
        run_lab(args)  # 파싱된 인수로 실습 실행
    except ClientError as exc:
        # AWS 서비스 오류 (권한 부족, 잘못된 음성 ID 등) 처리
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        # 네트워크 연결 실패 등 SDK 수준 오류 처리
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
