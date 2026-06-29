#!/usr/bin/env bash
# IAM 유저 info-pro 에 ECR Push 정책 연결
# 용도: GitHub Actions Access Key 방식 CI/CD (deploy-ecr-ec2.yml)
set -euo pipefail

ACCOUNT_ID="086015456585"
REGION="ap-northeast-2"
IAM_USER="info-pro"
POLICY_NAME="ECRPushPolicy"
POLICY_FILE="$(dirname "$0")/../policies/ecr-push-policy.json"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "[1/3] 정책 생성 또는 버전 업데이트 — $POLICY_NAME"
if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
  # 기존 정책 버전 업데이트 (최대 5개 제한으로 가장 오래된 비기본 버전 삭제)
  OLD_VERSION=$(aws iam list-policy-versions \
    --policy-arn "$POLICY_ARN" \
    --query 'Versions[?!IsDefaultVersion] | sort_by(@, &CreateDate) | [0].VersionId' \
    --output text 2>/dev/null || true)
  if [[ -n "$OLD_VERSION" && "$OLD_VERSION" != "None" ]]; then
    aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$OLD_VERSION"
  fi
  aws iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document "file://$POLICY_FILE" \
    --set-as-default
  echo "  [OK] 정책 버전 업데이트 완료"
else
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE" \
    --description "ECR Push/Pull for GitHub Actions CI/CD (be-test, fe-test)" \
    --region "$REGION" > /dev/null
  echo "  [OK] 정책 생성 완료: $POLICY_ARN"
fi

echo "[2/3] 유저 $IAM_USER 에 정책 연결"
aws iam attach-user-policy \
  --user-name "$IAM_USER" \
  --policy-arn "$POLICY_ARN" 2>/dev/null && echo "  [OK] 연결 완료" || echo "  [SKIP] 이미 연결됨"

echo "[3/3] 현재 연결된 정책 확인"
aws iam list-attached-user-policies --user-name "$IAM_USER" \
  --query 'AttachedPolicies[].{PolicyName:PolicyName,PolicyArn:PolicyArn}' \
  --output table

echo ""
echo "완료. GitHub Secret 설정:"
echo "  AWS_ACCESS_KEY_ID     : info-pro Access Key ID"
echo "  AWS_SECRET_ACCESS_KEY : info-pro Secret Access Key"
