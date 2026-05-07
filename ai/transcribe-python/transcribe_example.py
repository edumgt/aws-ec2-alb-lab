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

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse       # 커맨드라인 인수 파싱 라이브러리
import sys            # sys.exit()을 통한 비정상 종료 처리
import time           # time.sleep()으로 폴링 대기 간격 구현
import urllib.request # HTTP로 Transcribe 결과(JSON) 파일을 다운로드하는 표준 라이브러리
import uuid           # 중복 없는 고유 작업 이름(job_name) 생성용
from pathlib import Path  # 파일 이름(stem, name) 추출용

import boto3  # AWS SDK — Transcribe·S3 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# 기본 설정값 상수
DEFAULT_REGION = "ap-northeast-2"  # 한국어(ko-KR) 지원 서울 리전
POLL_INTERVAL = 5                  # 작업 상태 폴링 간격 (초)
MAX_WAIT_SECONDS = 300             # 작업 완료 대기 최대 시간 (5분)


def get_clients(region: str = DEFAULT_REGION):
    """지정 리전의 Transcribe와 S3 boto3 클라이언트를 튜플로 반환합니다."""
    return (
        boto3.client("transcribe", region_name=region),  # Transcribe 클라이언트
        boto3.client("s3", region_name=region),          # S3 클라이언트 (로컬 파일 업로드용)
    )


def upload_to_s3(s3_client, file_path: str, bucket: str) -> str:
    """로컬 오디오 파일을 S3의 transcribe-lab/ 프리픽스로 업로드하고 S3 URI를 반환합니다."""
    key = f"transcribe-lab/{Path(file_path).name}"  # S3 키: "transcribe-lab/파일명" 형식
    print(f"  S3 업로드 중: s3://{bucket}/{key}")
    s3_client.upload_file(file_path, bucket, key)   # 로컬 파일을 S3 버킷에 업로드
    return f"s3://{bucket}/{key}"                   # 업로드된 파일의 S3 URI 반환


def start_job(transcribe_client, s3_uri: str, lang: str) -> str:
    """Transcribe 비동기 변환 작업을 시작하고 작업 이름(job_name)을 반환합니다."""
    job_name = f"lab-{uuid.uuid4().hex[:8]}"  # 고유 작업 이름 생성 (예: lab-a3f2b1c4)
    ext = s3_uri.rsplit(".", 1)[-1].lower()   # S3 URI에서 파일 확장자 추출 (소문자)
    media_format = {"mp3": "mp3", "mp4": "mp4", "wav": "wav", "flac": "flac",
                    "ogg": "ogg", "amr": "amr", "webm": "webm"}.get(ext, "mp3")
    # 확장자를 Transcribe 지원 포맷 이름에 매핑 (알 수 없는 확장자는 mp3로 기본 처리)

    transcribe_client.start_transcription_job(
        TranscriptionJobName=job_name,             # 고유 작업 이름
        Media={"MediaFileUri": s3_uri},            # 변환할 오디오의 S3 URI
        MediaFormat=media_format,                  # 오디오 포맷 (mp3, wav 등)
        LanguageCode=lang,                         # 음성 언어 코드 (예: ko-KR, en-US)
        Settings={"ShowSpeakerLabels": False},     # 화자 구분 비활성화 (단순 변환용)
    )
    return job_name  # 상태 조회에 사용할 작업 이름 반환


def wait_for_job(transcribe_client, job_name: str) -> dict:
    """Transcribe 작업이 완료(COMPLETED)될 때까지 폴링하며 대기하고 작업 정보를 반환합니다.

    Raises:
        RuntimeError: 작업이 FAILED 상태가 된 경우
        TimeoutError: MAX_WAIT_SECONDS 내에 완료되지 않은 경우
    """
    elapsed = 0  # 경과 시간 (초)
    while elapsed < MAX_WAIT_SECONDS:  # 최대 대기 시간 내에서 반복
        resp = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        # 현재 작업 상태 조회
        job = resp["TranscriptionJob"]               # 작업 정보 딕셔너리
        status = job["TranscriptionJobStatus"]       # 작업 상태: IN_PROGRESS, COMPLETED, FAILED

        print(f"  [{elapsed:3d}s] 상태: {status}")  # 경과 시간과 현재 상태 출력

        if status == "COMPLETED":    # 변환 완료 시 즉시 작업 정보 반환
            return job
        if status == "FAILED":
            # 변환 실패 시 실패 원인을 포함한 예외 발생
            raise RuntimeError(f"변환 실패: {job.get('FailureReason', '알 수 없는 오류')}")

        time.sleep(POLL_INTERVAL)  # 다음 폴링까지 5초 대기
        elapsed += POLL_INTERVAL   # 경과 시간 누산

    raise TimeoutError(f"{MAX_WAIT_SECONDS}초 내에 완료되지 않았습니다.")
    # 최대 대기 시간 초과 시 TimeoutError 발생


def fetch_transcript(job: dict) -> str:
    """완료된 작업 정보에서 Transcript URL을 가져와 변환된 텍스트를 반환합니다."""
    uri = job["Transcript"]["TranscriptFileUri"]  # 결과 JSON 파일의 presigned URL
    with urllib.request.urlopen(uri) as f:        # HTTP GET으로 결과 파일 다운로드
        import json
        data = json.loads(f.read())  # JSON 파싱
    return data["results"]["transcripts"][0]["transcript"]
    # Transcribe 결과 JSON의 첫 번째 transcript 텍스트 반환


def run_lab(args) -> None:
    """커맨드라인 인수에 따라 S3 업로드(선택) → 작업 시작 → 완료 대기 → 결과 출력을 실행합니다."""
    region = getattr(args, "region", DEFAULT_REGION)  # 리전 인수 (없으면 기본 리전 사용)
    transcribe_client, s3_client = get_clients(region)  # Transcribe·S3 클라이언트 생성

    print("=" * 60)

    if args.file:  # --file 옵션: 로컬 파일을 S3에 업로드 후 변환
        if not args.bucket:
            # 로컬 파일 업로드 시 S3 버킷 이름이 없으면 실행 중단
            print("[오류] --file 사용 시 --bucket 이 필요합니다.")
            sys.exit(1)
        s3_uri = upload_to_s3(s3_client, args.file, args.bucket)  # S3 업로드 및 URI 반환
    else:
        s3_uri = args.s3_uri  # --s3-uri 옵션: 이미 S3에 있는 파일 직접 사용

    print(f"[입력] {s3_uri}")    # 변환 대상 S3 URI 출력
    print(f"[언어] {args.lang}") # 변환 언어 코드 출력

    job_name = start_job(transcribe_client, s3_uri, args.lang)  # Transcribe 작업 시작
    print(f"[작업 시작] job_name={job_name}\n[진행 상황]")

    job = wait_for_job(transcribe_client, job_name)  # 작업 완료까지 폴링 대기
    transcript = fetch_transcript(job)               # 완료된 작업에서 변환 텍스트 가져오기

    print(f"\n[변환 결과]")
    print(f"  {transcript}")  # 음성에서 변환된 텍스트 출력
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Transcribe 음성 변환 예시")
    group = parser.add_mutually_exclusive_group(required=True)  # --file 또는 --s3-uri 중 하나 필수
    group.add_argument("--file", help="로컬 오디오 파일 경로 (--bucket 도 필요)")
    group.add_argument("--s3-uri", help="S3 URI (예: s3://bucket/key.mp3)")
    parser.add_argument("--bucket", help="로컬 파일 업로드용 S3 버킷")
    parser.add_argument("--lang", default="ko-KR",
                        help="언어 코드 (기본값: ko-KR, 영어: en-US)")
    args = parser.parse_args()  # 커맨드라인 인수 파싱

    try:
        run_lab(args)  # 파싱된 인수로 실습 실행
    except FileNotFoundError as exc:
        # 로컬 오디오 파일이 존재하지 않을 때 오류 처리
        print(f"[오류] 파일을 찾을 수 없습니다: {exc}")
        sys.exit(1)
    except (RuntimeError, TimeoutError) as exc:
        # 변환 실패 또는 타임아웃 시 오류 메시지 출력 후 종료
        print(f"[오류] {exc}")
        sys.exit(1)
    except ClientError as exc:
        # AWS 서비스 오류 (권한 부족, 잘못된 S3 URI 등) 처리
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        # 네트워크 연결 실패 등 SDK 수준 오류 처리
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
