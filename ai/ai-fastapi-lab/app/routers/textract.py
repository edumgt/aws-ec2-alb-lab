"""Amazon Textract 라우터: 이미지/PDF에서 텍스트 추출 및 폼 분석."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()

DEFAULT_REGION = "us-east-1"


def _get_text(block: dict, blocks: dict) -> str:
    """블록의 CHILD 관계를 따라 WORD 텍스트를 연결합니다."""
    text = ""
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for child_id in rel["Ids"]:
                child = blocks.get(child_id, {})
                if child.get("BlockType") == "WORD":
                    text += child.get("Text", "") + " "
    return text.strip()


def _get_value_block(key_block: dict, blocks: dict) -> Optional[dict]:
    """KEY 블록에 연결된 VALUE 블록을 반환합니다."""
    for rel in key_block.get("Relationships", []):
        if rel["Type"] == "VALUE":
            for val_id in rel["Ids"]:
                return blocks.get(val_id)
    return None


@router.post("/extract", summary="문서에서 텍스트 추출")
async def extract(
    file: Optional[UploadFile] = File(None, description="로컬 이미지 또는 PDF 파일"),
    s3_bucket: Optional[str] = Form(None, description="S3 버킷 이름"),
    s3_key: Optional[str] = Form(None, description="S3 객체 키"),
    forms: bool = Form(False, description="폼 필드(KEY-VALUE) 분석 활성화"),
    region: str = Form(DEFAULT_REGION, description="AWS 리전"),
) -> dict:
    """문서(로컬 파일 또는 S3)에서 텍스트 라인 및 폼 필드를 추출합니다."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    client = boto3.client("textract", region_name=region)

    try:
        if file:
            data = await file.read()
            document: dict = {"Bytes": data}
        elif s3_bucket and s3_key:
            document = {"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
        else:
            raise HTTPException(status_code=400, detail="file 또는 s3_bucket + s3_key 중 하나가 필요합니다.")

        # 텍스트 라인 추출
        resp = client.detect_document_text(Document=document)
        lines = [
            block["Text"]
            for block in resp["Blocks"]
            if block["BlockType"] == "LINE"
        ]

        result: dict = {"lines": lines}

        # 폼 필드(KEY-VALUE) 분석
        if forms and file:
            # forms 분석은 로컬 파일(바이트)만 지원 (이미 읽은 data 재사용)
            form_resp = client.analyze_document(
                Document={"Bytes": data},
                FeatureTypes=["FORMS"],
            )
            blocks_map = {b["Id"]: b for b in form_resp["Blocks"]}
            form_fields = []
            for block in form_resp["Blocks"]:
                if block["BlockType"] != "KEY_VALUE_SET":
                    continue
                if "KEY" not in block.get("EntityTypes", []):
                    continue
                key_text = _get_text(block, blocks_map)
                value_block = _get_value_block(block, blocks_map)
                value_text = _get_text(value_block, blocks_map) if value_block else ""
                form_fields.append({"key": key_text, "value": value_text})
            result["forms"] = form_fields

        return result

    except ClientError as exc:
        err = exc.response.get("Error", {})
        raise HTTPException(status_code=500, detail=f"{err.get('Code')}: {err.get('Message')}")
    except BotoCoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
