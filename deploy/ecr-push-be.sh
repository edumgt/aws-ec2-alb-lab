#!/usr/bin/env bash

set -euo pipefail

REGION="ap-northeast-2"
ACCOUNT_ID="086015456585"
IMAGE_TAG="${IMAGE_TAG:-latest}"

ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BE_DIR="$SCRIPT_DIR/BE-fastapi"
FE_DIR="$SCRIPT_DIR/ag-grid-app"

BE_IMAGE="$ECR_REGISTRY/be-test"
FE_IMAGE="$ECR_REGISTRY/fe-test"

echo "[1/6] ECR 로그인 — $ECR_REGISTRY"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "[2/6] BE 이미지 빌드 — $BE_IMAGE:$IMAGE_TAG"
docker build -t "$BE_IMAGE:$IMAGE_TAG" "$BE_DIR"

echo "[3/6] BE ECR 푸시 — $BE_IMAGE:$IMAGE_TAG"
docker push "$BE_IMAGE:$IMAGE_TAG"

echo "[4/6] FE 이미지 빌드 — $FE_IMAGE:$IMAGE_TAG"
docker build -t "$FE_IMAGE:$IMAGE_TAG" "$FE_DIR"

echo "[5/6] FE ECR 푸시 — $FE_IMAGE:$IMAGE_TAG"
docker push "$FE_IMAGE:$IMAGE_TAG"

echo "[6/6] 완료"
echo "  BE : $BE_IMAGE:$IMAGE_TAG"
echo "  FE : $FE_IMAGE:$IMAGE_TAG"
