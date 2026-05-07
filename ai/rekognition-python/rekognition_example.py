#!/usr/bin/env python3
"""Amazon Rekognition 예시: 이미지 레이블 감지, 얼굴 분석, 텍스트 감지.

사전 준비:
- AWS 자격 증명 (aws configure 또는 IAM Role)
- IAM 권한: rekognition:DetectLabels, rekognition:DetectFaces, rekognition:DetectText
- pip install boto3

사용 방법:
  python3 rekognition_example.py --file photo.jpg
  python3 rekognition_example.py --s3-bucket my-bucket --s3-key images/photo.jpg
  python3 rekognition_example.py --file photo.jpg --mode faces
  python3 rekognition_example.py --file photo.jpg --mode text
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_REGION = "us-east-1"
CONFIDENCE_THRESHOLD = 80.0


def get_client(region: str = DEFAULT_REGION):
    return boto3.client("rekognition", region_name=region)


def _image_param(file_path: str | None, bucket: str | None, key: str | None) -> dict:
    if file_path:
        return {"Bytes": Path(file_path).read_bytes()}
    return {"S3Object": {"Bucket": bucket, "Name": key}}


def detect_labels(client, image: dict, max_labels: int = 10) -> list[dict]:
    resp = client.detect_labels(
        Image=image,
        MaxLabels=max_labels,
        MinConfidence=CONFIDENCE_THRESHOLD,
    )
    return [
        {
            "name": lbl["Name"],
            "confidence": round(lbl["Confidence"], 2),
            "categories": [c["Name"] for c in lbl.get("Categories", [])],
        }
        for lbl in resp["Labels"]
    ]


def detect_faces(client, image: dict) -> list[dict]:
    resp = client.detect_faces(Image=image, Attributes=["ALL"])
    results = []
    for face in resp["FaceDetails"]:
        results.append({
            "confidence": round(face["Confidence"], 2),
            "age_range": f"{face['AgeRange']['Low']}~{face['AgeRange']['High']}세",
            "gender": face["Gender"]["Value"],
            "smile": face["Smile"]["Value"],
            "emotions": sorted(
                [{"type": e["Type"], "confidence": round(e["Confidence"], 2)}
                 for e in face["Emotions"]],
                key=lambda x: x["confidence"],
                reverse=True,
            )[:3],
        })
    return results


def detect_text(client, image: dict) -> list[dict]:
    resp = client.detect_text(Image=image)
    return [
        {
            "text": t["DetectedText"],
            "type": t["Type"],
            "confidence": round(t["Confidence"], 2),
        }
        for t in resp["TextDetections"]
        if t["Confidence"] >= CONFIDENCE_THRESHOLD
    ]


def run_lab(args) -> None:
    client = get_client(DEFAULT_REGION)
    image = _image_param(args.file, args.s3_bucket, args.s3_key)
    source = args.file or f"s3://{args.s3_bucket}/{args.s3_key}"

    print("=" * 60)
    print(f"[이미지] {source}")
    print(f"[분석 모드] {args.mode}\n")

    if args.mode == "labels":
        labels = detect_labels(client, image)
        print(f"[레이블 감지 ({len(labels)}개, 신뢰도 {CONFIDENCE_THRESHOLD}% 이상)]")
        for lbl in labels:
            cats = ", ".join(lbl["categories"]) or "-"
            print(f"  {lbl['name']} ({lbl['confidence']}%)  카테고리: {cats}")

    elif args.mode == "faces":
        faces = detect_faces(client, image)
        print(f"[얼굴 분석 ({len(faces)}명 감지)]")
        for i, f in enumerate(faces, 1):
            top_emotion = f["emotions"][0]["type"] if f["emotions"] else "-"
            print(f"  얼굴 {i}: {f['gender']}, {f['age_range']}, "
                  f"미소={'예' if f['smile'] else '아니오'}, 주요감정={top_emotion} "
                  f"(신뢰도 {f['confidence']}%)")

    elif args.mode == "text":
        texts = detect_text(client, image)
        lines = [t for t in texts if t["type"] == "LINE"]
        print(f"[텍스트 감지 ({len(lines)}줄)]")
        for t in lines:
            print(f"  \"{t['text']}\" ({t['confidence']}%)")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Rekognition 이미지 분석 예시")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="로컬 이미지 파일 경로 (JPEG/PNG)")
    group.add_argument("--s3-bucket", help="S3 버킷 이름")
    parser.add_argument("--s3-key", help="S3 객체 키")
    parser.add_argument(
        "--mode",
        choices=["labels", "faces", "text"],
        default="labels",
        help="분석 모드 (기본값: labels)",
    )
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
