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

# Python 3.10 미만에서도 X | Y 타입 힌트를 사용하기 위해 임포트합니다
from __future__ import annotations

import argparse  # 커맨드라인 인수 파싱 라이브러리
import sys       # sys.exit()을 통한 비정상 종료 처리
from pathlib import Path  # 로컬 이미지 파일 바이너리 읽기용

import boto3  # AWS SDK — Rekognition 클라이언트 생성에 사용합니다
from botocore.exceptions import BotoCoreError, ClientError  # AWS 호출 관련 예외 클래스

# Rekognition이 지원하는 기본 리전 (us-east-1은 전체 기능 지원 리전)
DEFAULT_REGION = "us-east-1"
# 결과에 포함할 최소 신뢰도 임계값 (%) - 이 값 이상인 결과만 반환합니다
CONFIDENCE_THRESHOLD = 80.0


def get_client(region: str = DEFAULT_REGION):
    """지정 리전의 Amazon Rekognition boto3 클라이언트를 반환합니다."""
    return boto3.client("rekognition", region_name=region)


def _image_param(file_path: str | None, bucket: str | None, key: str | None) -> dict:
    """Rekognition API의 Image 파라미터 딕셔너리를 생성합니다.

    로컬 파일이면 바이트 데이터로, S3 오브젝트이면 버킷/키 참조로 반환합니다.
    """
    if file_path:
        return {"Bytes": Path(file_path).read_bytes()}  # 로컬 파일을 바이너리로 읽어 전달
    return {"S3Object": {"Bucket": bucket, "Name": key}}  # S3 오브젝트 참조 형식으로 전달


def detect_labels(client, image: dict, max_labels: int = 10) -> list[dict]:
    """이미지에서 객체·장면·활동 레이블을 감지하여 신뢰도 순으로 반환합니다.

    Args:
        max_labels: 반환할 최대 레이블 수 (기본값: 10)

    Returns:
        [{"name": str, "confidence": float, "categories": list}, ...] 형태의 레이블 목록
    """
    resp = client.detect_labels(
        Image=image,
        MaxLabels=max_labels,            # 최대 반환 레이블 수
        MinConfidence=CONFIDENCE_THRESHOLD,  # 최소 신뢰도 임계값
    )
    return [
        {
            "name": lbl["Name"],                             # 레이블 이름 (예: "Person", "Car")
            "confidence": round(lbl["Confidence"], 2),       # 신뢰도 (소수점 2자리)
            "categories": [c["Name"] for c in lbl.get("Categories", [])],
            # 레이블이 속한 상위 카테고리 목록 (예: ["Transportation", "Vehicle"])
        }
        for lbl in resp["Labels"]
    ]


def detect_faces(client, image: dict) -> list[dict]:
    """이미지에서 얼굴을 감지하고 나이·성별·감정 등 속성을 분석하여 반환합니다.

    Returns:
        각 얼굴에 대한 {"confidence", "age_range", "gender", "smile", "emotions"} 딕셔너리 목록
    """
    resp = client.detect_faces(Image=image, Attributes=["ALL"])  # 모든 얼굴 속성 분석 요청
    results = []
    for face in resp["FaceDetails"]:  # 감지된 각 얼굴 정보 처리
        results.append({
            "confidence": round(face["Confidence"], 2),  # 얼굴 감지 신뢰도 (소수점 2자리)
            "age_range": f"{face['AgeRange']['Low']}~{face['AgeRange']['High']}세",
            # 예상 나이 범위 (예: "25~35세")
            "gender": face["Gender"]["Value"],   # 성별 예측값 (Male/Female)
            "smile": face["Smile"]["Value"],     # 미소 여부 (True/False)
            "emotions": sorted(
                [{"type": e["Type"], "confidence": round(e["Confidence"], 2)}
                 for e in face["Emotions"]],
                key=lambda x: x["confidence"],   # 감정을 신뢰도 기준으로 내림차순 정렬
                reverse=True,
            )[:3],  # 상위 3개 감정만 반환 (HAPPY, SAD, CALM 등)
        })
    return results


def detect_text(client, image: dict) -> list[dict]:
    """이미지에서 텍스트를 감지하고 신뢰도 임계값 이상의 결과를 반환합니다.

    Returns:
        [{"text": str, "type": "LINE"|"WORD", "confidence": float}, ...] 형태의 텍스트 목록
    """
    resp = client.detect_text(Image=image)  # 이미지 내 텍스트 감지 API 호출
    return [
        {
            "text": t["DetectedText"],              # 감지된 텍스트 내용
            "type": t["Type"],                      # 텍스트 타입 (LINE 또는 WORD)
            "confidence": round(t["Confidence"], 2),  # 신뢰도 (소수점 2자리)
        }
        for t in resp["TextDetections"]
        if t["Confidence"] >= CONFIDENCE_THRESHOLD  # 신뢰도 임계값 이상만 포함
    ]


def run_lab(args) -> None:
    """커맨드라인 인수에 따라 레이블 감지·얼굴 분석·텍스트 감지 중 하나를 실행하고 결과를 출력합니다."""
    client = get_client(DEFAULT_REGION)  # Rekognition 클라이언트 생성
    image = _image_param(args.file, args.s3_bucket, args.s3_key)  # 이미지 파라미터 구성
    source = args.file or f"s3://{args.s3_bucket}/{args.s3_key}"  # 표시용 이미지 소스 문자열

    print("=" * 60)
    print(f"[이미지] {source}")        # 분석 대상 이미지 경로 출력
    print(f"[분석 모드] {args.mode}\n")  # 선택된 분석 모드 출력

    if args.mode == "labels":  # 레이블 감지 모드
        labels = detect_labels(client, image)
        print(f"[레이블 감지 ({len(labels)}개, 신뢰도 {CONFIDENCE_THRESHOLD}% 이상)]")
        for lbl in labels:
            cats = ", ".join(lbl["categories"]) or "-"  # 카테고리 없으면 "-" 표시
            print(f"  {lbl['name']} ({lbl['confidence']}%)  카테고리: {cats}")
            # 레이블 이름·신뢰도·카테고리 출력

    elif args.mode == "faces":  # 얼굴 분석 모드
        faces = detect_faces(client, image)
        print(f"[얼굴 분석 ({len(faces)}명 감지)]")
        for i, f in enumerate(faces, 1):  # 1번부터 순서 번호 부여
            top_emotion = f["emotions"][0]["type"] if f["emotions"] else "-"
            # 감정 목록에서 신뢰도 1위 감정 타입 추출 (없으면 "-")
            print(f"  얼굴 {i}: {f['gender']}, {f['age_range']}, "
                  f"미소={'예' if f['smile'] else '아니오'}, 주요감정={top_emotion} "
                  f"(신뢰도 {f['confidence']}%)")
            # 성별·나이범위·미소 여부·주요 감정·전체 신뢰도 출력

    elif args.mode == "text":  # 텍스트 감지 모드
        texts = detect_text(client, image)
        lines = [t for t in texts if t["type"] == "LINE"]  # LINE 타입(줄 단위)만 필터링
        print(f"[텍스트 감지 ({len(lines)}줄)]")
        for t in lines:
            print(f"  \"{t['text']}\" ({t['confidence']}%)")  # 감지된 텍스트 줄·신뢰도 출력

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amazon Rekognition 이미지 분석 예시")
    group = parser.add_mutually_exclusive_group(required=True)  # --file 또는 --s3-bucket 중 하나 필수
    group.add_argument("--file", help="로컬 이미지 파일 경로 (JPEG/PNG)")
    group.add_argument("--s3-bucket", help="S3 버킷 이름")
    parser.add_argument("--s3-key", help="S3 객체 키")
    parser.add_argument(
        "--mode",
        choices=["labels", "faces", "text"],  # 허용되는 분석 모드 값
        default="labels",                     # 기본값: 레이블 감지
        help="분석 모드 (기본값: labels)",
    )
    args = parser.parse_args()  # 커맨드라인 인수 파싱

    if args.s3_bucket and not args.s3_key:
        # S3 버킷 지정 시 키(객체 경로)도 반드시 필요
        parser.error("--s3-bucket 사용 시 --s3-key 도 필요합니다.")

    try:
        run_lab(args)  # 파싱된 인수로 분석 실행
    except FileNotFoundError as exc:
        # 로컬 이미지 파일이 존재하지 않을 때 오류 처리
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
