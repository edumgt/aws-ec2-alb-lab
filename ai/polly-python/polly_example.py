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

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "ap-northeast-2"
DEFAULT_VOICE = "Seoyeon"
DEFAULT_OUTPUT = "output.mp3"


def get_client(region: str = DEFAULT_REGION):
    return boto3.client("polly", region_name=region)


def synthesize(
    client,
    text: str,
    voice_id: str,
    output_path: str,
    is_ssml: bool = False,
) -> int:
    resp = client.synthesize_speech(
        Text=text,
        VoiceId=voice_id,
        OutputFormat="mp3",
        TextType="ssml" if is_ssml else "text",
        Engine="neural" if voice_id == "Seoyeon" else "standard",
    )

    audio_data = resp["AudioStream"].read()
    Path(output_path).write_bytes(audio_data)
    return len(audio_data)


def list_voices(client, language_code: str | None = None) -> list[dict]:
    kwargs = {}
    if language_code:
        kwargs["LanguageCode"] = language_code

    voices = []
    paginator = client.get_paginator("describe_voices")
    for page in paginator.paginate(**kwargs):
        for v in page["Voices"]:
            voices.append({
                "id": v["Id"],
                "name": v["Name"],
                "gender": v["Gender"],
                "language": v["LanguageName"],
                "engines": v.get("SupportedEngines", []),
            })
    return voices


def run_lab(args) -> None:
    client = get_client(DEFAULT_REGION)
    print("=" * 60)

    if args.list_voices:
        voices = list_voices(client, args.lang)
        lang_label = f"({args.lang})" if args.lang else "(전체)"
        print(f"[사용 가능한 음성 목록] {lang_label}")
        for v in voices:
            engines = ", ".join(v["engines"])
            print(f"  {v['id']:12s}  {v['gender']:6s}  {v['language']}  [{engines}]")
        print("=" * 60)
        return

    text = args.ssml or args.text
    is_ssml = bool(args.ssml)
    voice = args.voice or DEFAULT_VOICE
    output = args.output or DEFAULT_OUTPUT

    print(f"[입력 텍스트] {text[:80]}{'...' if len(text) > 80 else ''}")
    print(f"[음성] {voice}  [포맷] MP3  [SSML] {'예' if is_ssml else '아니오'}")

    size = synthesize(client, text, voice, output, is_ssml)
    print(f"\n[변환 완료]")
    print(f"  저장 경로: {Path(output).resolve()}")
    print(f"  파일 크기: {size:,} bytes")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Polly 텍스트 → 음성 변환 예시")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text", help="변환할 일반 텍스트")
    group.add_argument("--ssml", help="변환할 SSML 텍스트")
    group.add_argument("--list-voices", action="store_true", help="사용 가능한 음성 목록 출력")
    parser.add_argument("--voice", help=f"음성 ID (기본값: {DEFAULT_VOICE})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="출력 MP3 파일 경로")
    parser.add_argument("--lang", help="언어 코드 필터 (--list-voices 전용, 예: ko-KR)")
    args = parser.parse_args()

    if not args.list_voices and not args.text and not args.ssml:
        parser.error("--text, --ssml, 또는 --list-voices 중 하나를 지정하세요.")

    try:
        run_lab(args)
    except ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
