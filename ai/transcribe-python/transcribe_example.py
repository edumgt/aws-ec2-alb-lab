#!/usr/bin/env python3
"""Amazon Transcribe 예시: 오디오 파일 → 텍스트 변환.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: transcribe:StartTranscriptionJob, transcribe:GetTranscriptionJob, s3:PutObject, s3:GetObject
- 오디오 파일은 S3에 업로드되어야 합니다
- pip install boto3

사용 방법:
  # S3에 있는 파일 직접 변환
  python3 transcribe_example.py --s3-uri s3://my-bucket/audio/sample.mp3 --lang ko-KR

  # 로컬 파일을 S3에 업로드 후 변환
  python3 transcribe_example.py --file sample.mp3 --bucket my-bucket --lang ko-KR
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "ap-northeast-2"
POLL_INTERVAL = 5
MAX_WAIT_SECONDS = 300


def get_clients(region: str = DEFAULT_REGION):
    return (
        boto3.client("transcribe", region_name=region),
        boto3.client("s3", region_name=region),
    )


def upload_to_s3(s3_client, file_path: str, bucket: str) -> str:
    key = f"transcribe-lab/{Path(file_path).name}"
    print(f"  S3 업로드 중: s3://{bucket}/{key}")
    s3_client.upload_file(file_path, bucket, key)
    return f"s3://{bucket}/{key}"


def start_job(transcribe_client, s3_uri: str, lang: str) -> str:
    job_name = f"lab-{uuid.uuid4().hex[:8]}"
    ext = s3_uri.rsplit(".", 1)[-1].lower()
    media_format = {"mp3": "mp3", "mp4": "mp4", "wav": "wav", "flac": "flac",
                    "ogg": "ogg", "amr": "amr", "webm": "webm"}.get(ext, "mp3")

    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": s3_uri},
        MediaFormat=media_format,
        LanguageCode=lang,
        Settings={"ShowSpeakerLabels": False},
    )
    return job_name


def wait_for_job(transcribe_client, job_name: str) -> dict:
    elapsed = 0
    while elapsed < MAX_WAIT_SECONDS:
        resp = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job = resp["TranscriptionJob"]
        status = job["TranscriptionJobStatus"]

        print(f"  [{elapsed:3d}s] 상태: {status}")

        if status == "COMPLETED":
            return job
        if status == "FAILED":
            raise RuntimeError(f"변환 실패: {job.get('FailureReason', '알 수 없는 오류')}")

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"{MAX_WAIT_SECONDS}초 내에 완료되지 않았습니다.")


def fetch_transcript(job: dict) -> str:
    uri = job["Transcript"]["TranscriptFileUri"]
    with urllib.request.urlopen(uri) as f:
        import json
        data = json.loads(f.read())
    return data["results"]["transcripts"][0]["transcript"]


def run_lab(args) -> None:
    region = getattr(args, "region", DEFAULT_REGION)
    transcribe_client, s3_client = get_clients(region)

    print("=" * 60)

    if args.file:
        if not args.bucket:
            print("[오류] --file 사용 시 --bucket 이 필요합니다.")
            sys.exit(1)
        s3_uri = upload_to_s3(s3_client, args.file, args.bucket)
    else:
        s3_uri = args.s3_uri

    print(f"[입력] {s3_uri}")
    print(f"[언어] {args.lang}")

    job_name = start_job(transcribe_client, s3_uri, args.lang)
    print(f"[작업 시작] job_name={job_name}\n[진행 상황]")

    job = wait_for_job(transcribe_client, job_name)
    transcript = fetch_transcript(job)

    print(f"\n[변환 결과]")
    print(f"  {transcript}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Transcribe 음성 변환 예시")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="로컬 오디오 파일 경로 (--bucket 도 필요)")
    group.add_argument("--s3-uri", help="S3 URI (예: s3://bucket/key.mp3)")
    parser.add_argument("--bucket", help="로컬 파일 업로드용 S3 버킷")
    parser.add_argument("--lang", default="ko-KR",
                        help="언어 코드 (기본값: ko-KR, 영어: en-US)")
    args = parser.parse_args()

    try:
        run_lab(args)
    except FileNotFoundError as exc:
        print(f"[오류] 파일을 찾을 수 없습니다: {exc}")
        sys.exit(1)
    except (RuntimeError, TimeoutError) as exc:
        print(f"[오류] {exc}")
        sys.exit(1)
    except ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
