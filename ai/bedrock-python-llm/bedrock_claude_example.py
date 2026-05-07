#!/usr/bin/env python3
"""Amazon Bedrock(Claude) LLM 호출 예시.

사전 준비:
- AWS 자격 증명(예: aws configure)
- Bedrock 모델 사용 권한
"""

from __future__ import annotations

import json
import os

import boto3


MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
REGION = os.getenv("AWS_REGION", "us-east-1")


def ask_bedrock(prompt: str) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    payload = json.loads(response["body"].read())
    return payload["content"][0]["text"]


if __name__ == "__main__":
    user_prompt = "AWS ALB와 EC2를 사용하는 기본 아키텍처를 5줄로 설명해줘."
    print(ask_bedrock(user_prompt))
