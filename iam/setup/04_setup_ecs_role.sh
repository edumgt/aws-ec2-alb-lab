#!/usr/bin/env bash
# ECS Task Execution Role 생성
# 용도: deploy-ecs-aws-cli.yml (ECS Fargate) 배포 시 컨테이너가 ECR pull 및 CloudWatch 로그 전송
set -euo pipefail

ACCOUNT_ID="086015456585"
REGION="ap-northeast-2"
ROLE_NAME="ecsTaskExecutionRole"
POLICY_NAME="ECSTaskExecutionCustomPolicy"
TRUST_FILE="$(dirname "$0")/../trust-policies/ecs-task-execution-trust.json"
POLICY_FILE="$(dirname "$0")/../policies/ecs-task-execution-policy.json"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
AWS_MANAGED_POLICY="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"

echo "[1/4] ECS Task Execution Role 생성 — $ROLE_NAME"
if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
  aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "file://$TRUST_FILE"
  echo "  [OK] Trust Policy 업데이트 완료"
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST_FILE" \
    --description "ECS Fargate Task Execution Role" > /dev/null
  echo "  [OK] Role 생성 완료"
fi

echo "[2/4] AWS 관리형 정책 연결 — AmazonECSTaskExecutionRolePolicy"
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$AWS_MANAGED_POLICY" 2>/dev/null \
  && echo "  [OK] 연결 완료" || echo "  [SKIP] 이미 연결됨"

echo "[3/4] 커스텀 Policy 생성 — $POLICY_NAME (SSM, Secrets Manager, CloudWatch)"
if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
  echo "  [SKIP] 이미 존재함"
else
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE" \
    --description "Custom policy for ECS Task Execution: ECR + CloudWatch + SSM + Secrets" > /dev/null
  echo "  [OK] Policy 생성 완료: $POLICY_ARN"
fi

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN" 2>/dev/null \
  && echo "  [OK] 커스텀 Policy 연결 완료" || echo "  [SKIP] 이미 연결됨"

echo "[4/4] Role ARN 출력"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "  Role ARN: $ROLE_ARN"
echo ""
echo "완료. deploy-ecs-aws-cli.yml Task Definition에서 사용됩니다:"
echo "  \"executionRoleArn\": \"$ROLE_ARN\""
