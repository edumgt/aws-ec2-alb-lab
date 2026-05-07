#!/usr/bin/env python3
"""Amazon Bedrock(Claude) LLM 호출 예시.

사전 준비:
- AWS 자격 증명(예: aws configure)
- Bedrock 모델 사용 권한
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError


DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
DEFAULT_REGION = "us-east-1"


@lru_cache(maxsize=8)
def get_bedrock_client(region: str):
    return boto3.client("bedrock-runtime", region_name=region)


def ask_bedrock(prompt: str) -> str:
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    region = os.getenv("AWS_REGION", DEFAULT_REGION)
    client = get_bedrock_client(region)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }

    try:
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]
    except ClientError as exc:
        raise RuntimeError("Bedrock 호출이 거부되었습니다. IAM 권한/모델 접근 권한을 확인하세요.") from exc
    except BotoCoreError as exc:
        raise RuntimeError("AWS 연결 오류가 발생했습니다. 네트워크/리전 설정을 확인하세요.") from exc
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Bedrock 응답 형식 파싱에 실패했습니다. 모델/SDK 버전을 확인하세요.") from exc


if __name__ == "__main__":
    user_prompt = "AWS ALB와 EC2를 사용하는 기본 아키텍처를 5줄로 설명해줘."
    print(ask_bedrock(user_prompt))
