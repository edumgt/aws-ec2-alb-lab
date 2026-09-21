#!/usr/bin/env bash

set -euo pipefail

REGION="ap-northeast-2"
ACCOUNT_ID="086015456585"
IMAGE_TAG="${IMAGE_TAG:-latest}"

ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BE_DIR="$REPO_ROOT/BE-fastapi"
PROXY_DIR="$REPO_ROOT/deploy/rag-api-proxy"

BE_IMAGE="$ECR_REGISTRY/be-test"
PROXY_IMAGE="$ECR_REGISTRY/rag-api-proxy"

echo "[1/7] ECR 로그인 — $ECR_REGISTRY"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "[2/7] HTTPS 프록시 ECR 리포지토리 확인"
if ! aws ecr describe-repositories --region "$REGION" --repository-names rag-api-proxy >/dev/null 2>&1; then
  aws ecr create-repository --region "$REGION" --repository-name rag-api-proxy >/dev/null
fi

echo "[3/7] BE 이미지 빌드 — $BE_IMAGE:$IMAGE_TAG"
docker build -t "$BE_IMAGE:$IMAGE_TAG" "$BE_DIR"

echo "[4/7] BE ECR 푸시 — $BE_IMAGE:$IMAGE_TAG"
docker push "$BE_IMAGE:$IMAGE_TAG"

echo "[5/7] HTTPS 프록시 이미지 빌드 — $PROXY_IMAGE:$IMAGE_TAG"
docker build -t "$PROXY_IMAGE:$IMAGE_TAG" "$PROXY_DIR"

echo "[6/7] HTTPS 프록시 ECR 푸시 — $PROXY_IMAGE:$IMAGE_TAG"
docker push "$PROXY_IMAGE:$IMAGE_TAG"

echo "[7/7] 완료"
echo "  BE : $BE_IMAGE:$IMAGE_TAG"
echo "  HTTPS 프록시 : $PROXY_IMAGE:$IMAGE_TAG"
echo "  FE : rf.edumgt.co.kr (S3/CloudFront 정적 호스팅, 이 스크립트의 배포 대상 아님)"
