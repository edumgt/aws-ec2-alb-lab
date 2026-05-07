#!/usr/bin/env python3
"""Amazon Textract 예시: 이미지/PDF에서 텍스트 추출.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: textract:DetectDocumentText, textract:AnalyzeDocument
- pip install boto3 pillow
- 테스트용 이미지 파일 또는 S3 버킷의 문서

사용 방법:
  # 로컬 이미지 파일
  python3 textract_example.py --file sample.png

  # S3 버킷 문서
  python3 textract_example.py --s3-bucket my-bucket --s3-key docs/sample.pdf
"""

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리
import sys       # sys.exit()을 통한 비정상 종료 처리
from pathlib import Path  # 로컬 파일 바이너리 읽기용

import boto3  # AWS SDK — Textract 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# Textract가 지원하는 기본 리전 (us-east-1은 전체 기능 지원 리전)
DEFAULT_REGION = "us-east-1"


def get_client(region: str = DEFAULT_REGION):
    """지정 리전의 Amazon Textract boto3 클라이언트를 반환합니다."""
    return boto3.client("textract", region_name=region)


def extract_from_file(client, file_path: str) -> list[str]:
    """로컬 이미지/PDF 파일에서 텍스트 라인을 추출하여 반환합니다.

    Args:
        file_path: 로컬 이미지 또는 PDF 파일 경로

    Returns:
        감지된 텍스트 라인(LINE 블록) 문자열 목록
    """
    data = Path(file_path).read_bytes()  # 로컬 파일을 바이너리로 읽기
    resp = client.detect_document_text(Document={"Bytes": data})
    # 바이트 데이터를 Textract에 직접 전달하여 텍스트 감지
    return [
        block["Text"]              # 각 LINE 블록의 텍스트 내용 추출
        for block in resp["Blocks"]
        if block["BlockType"] == "LINE"  # LINE 타입 블록(줄 단위 텍스트)만 필터링
    ]


def extract_from_s3(client, bucket: str, key: str) -> list[str]:
    """S3에 저장된 문서에서 텍스트 라인을 추출하여 반환합니다.

    Args:
        bucket: S3 버킷 이름
        key: S3 객체 키 (파일 경로)

    Returns:
        감지된 텍스트 라인(LINE 블록) 문자열 목록
    """
    resp = client.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
        # S3 오브젝트 참조 형식으로 문서 지정 (바이트 전송 없이 S3 내 처리)
    )
    return [
        block["Text"]
        for block in resp["Blocks"]
        if block["BlockType"] == "LINE"  # LINE 타입 블록만 필터링
    ]


def analyze_forms(client, file_path: str) -> list[dict]:
    """KEY_VALUE_SET 추출 (폼 필드 분석).

    AnalyzeDocument API로 폼의 KEY-VALUE 쌍(예: "이름: 홍길동")을 추출합니다.

    Returns:
        [{"key": str, "value": str}, ...] 형태의 폼 필드 목록
    """
    data = Path(file_path).read_bytes()  # 로컬 파일을 바이너리로 읽기
    resp = client.analyze_document(
        Document={"Bytes": data},
        FeatureTypes=["FORMS"],  # FORMS 기능 활성화: KEY_VALUE_SET 블록 반환
    )

    blocks = {b["Id"]: b for b in resp["Blocks"]}  # 블록 ID를 키로 하는 딕셔너리로 변환 (빠른 참조용)
    results = []

    for block in resp["Blocks"]:  # 모든 블록 순회
        if block["BlockType"] != "KEY_VALUE_SET":  # KEY_VALUE_SET 타입만 처리
            continue
        if "KEY" not in block.get("EntityTypes", []):  # KEY 타입 블록만 선택 (VALUE 블록 제외)
            continue

        key_text = _get_text(block, blocks)               # KEY 블록의 텍스트 내용 추출
        value_block = _get_value_block(block, blocks)     # KEY와 연결된 VALUE 블록 가져오기
        value_text = _get_text(value_block, blocks) if value_block else ""
        # VALUE 블록이 있으면 텍스트 추출, 없으면 빈 문자열
        results.append({"key": key_text, "value": value_text})  # 키-값 쌍을 결과 목록에 추가

    return results


def _get_text(block: dict, blocks: dict) -> str:
    """블록의 CHILD 관계를 따라가 WORD 블록들의 텍스트를 연결한 문자열을 반환합니다."""
    text = ""
    for rel in block.get("Relationships", []):  # 블록의 관계 목록 순회
        if rel["Type"] == "CHILD":              # CHILD 타입 관계만 처리 (자식 블록)
            for child_id in rel["Ids"]:         # 각 자식 블록 ID에 대해
                child = blocks.get(child_id, {})  # ID로 실제 블록 조회
                if child.get("BlockType") == "WORD":  # WORD 타입 블록(단어)만 텍스트 추출
                    text += child.get("Text", "") + " "  # 단어 뒤에 공백 추가하여 연결
    return text.strip()  # 앞뒤 공백 제거 후 반환


def _get_value_block(key_block: dict, blocks: dict) -> dict | None:
    """KEY 블록에 연결된 VALUE 블록을 찾아 반환합니다. 없으면 None을 반환합니다."""
    for rel in key_block.get("Relationships", []):  # KEY 블록의 관계 목록 순회
        if rel["Type"] == "VALUE":                  # VALUE 타입 관계 (KEY와 쌍을 이루는 값)
            for val_id in rel["Ids"]:               # 연결된 VALUE 블록 ID 중 첫 번째 반환
                return blocks.get(val_id)
    return None  # VALUE 관계가 없으면 None 반환


def run_lab(args) -> None:
    """커맨드라인 인수에 따라 텍스트 추출 또는 폼 분석을 실행하고 결과를 출력합니다."""
    client = get_client(DEFAULT_REGION)  # Textract 클라이언트 생성

    print("=" * 60)
    if args.file:  # 로컬 파일 모드
        print(f"[파일] {args.file}")  # 처리 대상 파일 경로 출력
        lines = extract_from_file(client, args.file)  # 로컬 파일에서 텍스트 라인 추출
        print(f"\n[추출된 텍스트 라인 ({len(lines)}개)]")
        for i, line in enumerate(lines, 1):  # 1번부터 순서 번호 부여하여 출력
            print(f"  {i:02d}. {line}")      # 두 자리 번호(01, 02 ...)로 정렬하여 출력

        if args.forms:  # --forms 옵션이 활성화된 경우 폼 필드 분석 추가 실행
            print("\n[폼 필드 분석 (KEY-VALUE)]")
            fields = analyze_forms(client, args.file)  # 폼 필드(KEY-VALUE 쌍) 분석
            if fields:
                for f in fields:
                    print(f"  {f['key']}: {f['value']}")  # 각 폼 필드의 키-값 출력
            else:
                print("  감지된 폼 필드 없음")  # 폼 필드가 없을 때 안내 메시지

    elif args.s3_bucket and args.s3_key:  # S3 문서 모드
        print(f"[S3] s3://{args.s3_bucket}/{args.s3_key}")  # S3 경로 출력
        lines = extract_from_s3(client, args.s3_bucket, args.s3_key)  # S3 문서에서 텍스트 추출
        print(f"\n[추출된 텍스트 라인 ({len(lines)}개)]")
        for i, line in enumerate(lines, 1):  # 1번부터 순서 번호 부여하여 출력
            print(f"  {i:02d}. {line}")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Textract 텍스트 추출 예시")
    group = parser.add_mutually_exclusive_group(required=True)  # --file 또는 --s3-bucket 중 하나 필수
    group.add_argument("--file", help="로컬 이미지 또는 PDF 파일 경로")
    group.add_argument("--s3-bucket", help="S3 버킷 이름")
    parser.add_argument("--s3-key", help="S3 객체 키")
    parser.add_argument("--forms", action="store_true", help="폼 필드(KEY-VALUE) 분석 활성화")
    args = parser.parse_args()  # 커맨드라인 인수 파싱

    if args.s3_bucket and not args.s3_key:
        # S3 버킷 지정 시 객체 키도 필수
        parser.error("--s3-bucket 사용 시 --s3-key 도 필요합니다.")

    try:
        run_lab(args)  # 파싱된 인수로 실습 실행
    except FileNotFoundError as exc:
        # 로컬 파일이 존재하지 않을 때 오류 처리
        print(f"[오류] 파일을 찾을 수 없습니다: {exc}")
        sys.exit(1)
    except ClientError as exc:
        # AWS 서비스 오류 (권한 부족, 잘못된 S3 경로 등) 처리
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        # 네트워크 연결 실패 등 SDK 수준 오류 처리
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
