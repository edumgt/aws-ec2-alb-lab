"""Amazon Rekognition 라우터: 이미지 레이블 감지, 얼굴 분석, 텍스트 감지."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()

DEFAULT_REGION = "us-east-1"
CONFIDENCE_THRESHOLD = 80.0


@router.post("/analyze", summary="이미지 분석 (labels / faces / text)")
async def analyze(
    mode: str = Form("labels", description="분석 모드: labels | faces | text"),
    file: Optional[UploadFile] = File(None, description="로컬 이미지 파일 (JPEG/PNG)"),
    s3_bucket: Optional[str] = Form(None, description="S3 버킷 이름"),
    s3_key: Optional[str] = Form(None, description="S3 객체 키"),
    region: str = Form(DEFAULT_REGION, description="AWS 리전"),
    max_labels: int = Form(10, description="레이블 최대 개수 (mode=labels 전용)"),
) -> dict:
    """이미지(로컬 파일 또는 S3)에서 레이블·얼굴·텍스트를 감지합니다."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    # 이미지 파라미터 구성
    if file:
        image: dict = {"Bytes": await file.read()}
    elif s3_bucket and s3_key:
        image = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
    else:
        raise HTTPException(status_code=400, detail="file 또는 s3_bucket + s3_key 중 하나가 필요합니다.")

    client = boto3.client("rekognition", region_name=region)

    try:
        if mode == "labels":
            resp = client.detect_labels(
                Image=image,
                MaxLabels=max_labels,
                MinConfidence=CONFIDENCE_THRESHOLD,
            )
            labels = [
                {
                    "name": lbl["Name"],
                    "confidence": round(lbl["Confidence"], 2),
                    "categories": [c["Name"] for c in lbl.get("Categories", [])],
                }
                for lbl in resp["Labels"]
            ]
            return {"mode": "labels", "labels": labels}

        elif mode == "faces":
            resp = client.detect_faces(Image=image, Attributes=["ALL"])
            faces = []
            for face in resp["FaceDetails"]:
                faces.append(
                    {
                        "confidence": round(face["Confidence"], 2),
                        "age_range": f"{face['AgeRange']['Low']}~{face['AgeRange']['High']}세",
                        "gender": face["Gender"]["Value"],
                        "smile": face["Smile"]["Value"],
                        "emotions": sorted(
                            [
                                {"type": e["Type"], "confidence": round(e["Confidence"], 2)}
                                for e in face["Emotions"]
                            ],
                            key=lambda x: x["confidence"],
                            reverse=True,
                        )[:3],
                    }
                )
            return {"mode": "faces", "faces": faces}

        elif mode == "text":
            resp = client.detect_text(Image=image)
            texts = [
                {
                    "text": t["DetectedText"],
                    "type": t["Type"],
                    "confidence": round(t["Confidence"], 2),
                }
                for t in resp["TextDetections"]
                if t["Confidence"] >= CONFIDENCE_THRESHOLD
            ]
            lines = [t for t in texts if t["type"] == "LINE"]
            return {"mode": "text", "texts": lines}

        else:
            raise HTTPException(status_code=400, detail="mode는 labels | faces | text 중 하나여야 합니다.")

    except ClientError as exc:
        err = exc.response.get("Error", {})
        raise HTTPException(status_code=500, detail=f"{err.get('Code')}: {err.get('Message')}")
    except BotoCoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
