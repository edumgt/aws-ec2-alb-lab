"""시세 수집 / 장마감 배치 Lambda 골격.

- EventBridge Scheduler 가 장중 1분 주기(event 없음) 와 장마감(event={"job":"eod"}) 으로 호출
- API Gateway HTTP API 가 GET /v1/quotes 로 호출 (event 에 requestContext 존재)
- 증권사 키는 SSM Parameter Store(SecureString) 에서 읽고, 결과는 앱 API 로 전달
"""
import json
import os
import urllib.request

import boto3

ssm = boto3.client("ssm")
PREFIX = os.environ.get("SSM_PREFIX", "/stock-coin-trade")
APP_INGEST_URL = os.environ.get("APP_INGEST_URL", "")

_cache: dict = {}


def param(name: str) -> str:
    if name not in _cache:
        _cache[name] = ssm.get_parameter(Name=f"{PREFIX}/{name}", WithDecryption=True)["Parameter"]["Value"]
    return _cache[name]


def collect_quotes() -> list:
    # TODO: KIS / KB / Alpaca 시세 API 호출로 교체
    _ = param("kis/app_key")
    return [{"symbol": "005930", "price": 0, "source": "kis"}]


def post_to_app(payload: dict) -> int:
    if not APP_INGEST_URL:
        return 0
    req = urllib.request.Request(
        APP_INGEST_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def handler(event, context):
    # API Gateway 호출: 외부 Open API 응답
    if isinstance(event, dict) and "requestContext" in event:
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"quotes": collect_quotes()})}

    job = (event or {}).get("job", "quotes")
    if job == "eod":
        status = post_to_app({"job": "eod"})
        return {"job": "eod", "status": status}

    quotes = collect_quotes()
    status = post_to_app({"job": "quotes", "quotes": quotes})
    return {"job": "quotes", "count": len(quotes), "status": status}
