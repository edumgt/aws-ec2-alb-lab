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

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "us-east-1"


def get_client(region: str = DEFAULT_REGION):
    return boto3.client("textract", region_name=region)


def extract_from_file(client, file_path: str) -> list[str]:
    data = Path(file_path).read_bytes()
    resp = client.detect_document_text(Document={"Bytes": data})
    return [
        block["Text"]
        for block in resp["Blocks"]
        if block["BlockType"] == "LINE"
    ]


def extract_from_s3(client, bucket: str, key: str) -> list[str]:
    resp = client.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    return [
        block["Text"]
        for block in resp["Blocks"]
        if block["BlockType"] == "LINE"
    ]


def analyze_forms(client, file_path: str) -> list[dict]:
    """KEY_VALUE_SET 추출 (폼 필드 분석)."""
    data = Path(file_path).read_bytes()
    resp = client.analyze_document(
        Document={"Bytes": data},
        FeatureTypes=["FORMS"],
    )

    blocks = {b["Id"]: b for b in resp["Blocks"]}
    results = []

    for block in resp["Blocks"]:
        if block["BlockType"] != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue

        key_text = _get_text(block, blocks)
        value_block = _get_value_block(block, blocks)
        value_text = _get_text(value_block, blocks) if value_block else ""
        results.append({"key": key_text, "value": value_text})

    return results


def _get_text(block: dict, blocks: dict) -> str:
    text = ""
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = blocks.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    text += child.get("Text", "") + " "
    return text.strip()


def _get_value_block(key_block: dict, blocks: dict) -> dict | None:
    for rel in key_block.get("Relationships", []):
        if rel["Type"] == "VALUE":
            for val_id in rel["Ids"]:
                return blocks.get(val_id)
    return None


def run_lab(args) -> None:
    client = get_client(DEFAULT_REGION)

    print("=" * 60)
    if args.file:
        print(f"[파일] {args.file}")
        lines = extract_from_file(client, args.file)
        print(f"\n[추출된 텍스트 라인 ({len(lines)}개)]")
        for i, line in enumerate(lines, 1):
            print(f"  {i:02d}. {line}")

        if args.forms:
            print("\n[폼 필드 분석 (KEY-VALUE)]")
            fields = analyze_forms(client, args.file)
            if fields:
                for f in fields:
                    print(f"  {f['key']}: {f['value']}")
            else:
                print("  감지된 폼 필드 없음")

    elif args.s3_bucket and args.s3_key:
        print(f"[S3] s3://{args.s3_bucket}/{args.s3_key}")
        lines = extract_from_s3(client, args.s3_bucket, args.s3_key)
        print(f"\n[추출된 텍스트 라인 ({len(lines)}개)]")
        for i, line in enumerate(lines, 1):
            print(f"  {i:02d}. {line}")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Textract 텍스트 추출 예시")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="로컬 이미지 또는 PDF 파일 경로")
    group.add_argument("--s3-bucket", help="S3 버킷 이름")
    parser.add_argument("--s3-key", help="S3 객체 키")
    parser.add_argument("--forms", action="store_true", help="폼 필드(KEY-VALUE) 분석 활성화")
    args = parser.parse_args()

    if args.s3_bucket and not args.s3_key:
        parser.error("--s3-bucket 사용 시 --s3-key 도 필요합니다.")

    try:
        run_lab(args)
    except FileNotFoundError as exc:
        print(f"[오류] 파일을 찾을 수 없습니다: {exc}")
        sys.exit(1)
    except ClientError as exc:
        err = exc.response.get("Error", {})
        print(f"[오류] {err.get('Code')}: {err.get('Message')}")
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"[AWS 연결 오류] {exc}")
        sys.exit(1)
