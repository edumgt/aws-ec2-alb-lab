#!/bin/bash
# AWS FIS - 리소스 정리 (실험 종료 후 cleanup)
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
ROLE_NAME="FISExperimentRole"
POLICY_NAME="FISExperimentPolicy"
ALARM_PREFIX="fis-safeguard"

echo "======================================"
echo " FIS Lab 리소스 정리"
echo "======================================"
echo ""
echo "[!] 다음 리소스를 삭제합니다:"
echo "    - CloudWatch Alarms (${ALARM_PREFIX}-*)"
echo "    - FIS Experiment Templates"
echo "    - IAM Role: $ROLE_NAME"
echo "    - IAM Policy: $POLICY_NAME"
echo ""
read -r -p "계속 진행하시겠습니까? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo "[ABORT] 정리를 취소했습니다."
  exit 0
fi

# ──────────────────────────────────────────────
# 1. 진행 중인 실험 중단
# ──────────────────────────────────────────────
echo ""
echo "[1/4] 진행 중인 실험 중단..."
RUNNING_EXPERIMENTS=$(aws fis list-experiments \
  --region "$REGION" \
  --query 'experiments[?state.status==`running`].id' \
  --output text 2>/dev/null)

if [ -n "$RUNNING_EXPERIMENTS" ]; then
  for EXP_ID in $RUNNING_EXPERIMENTS; do
    echo "  중단: $EXP_ID"
    aws fis stop-experiment --region "$REGION" --id "$EXP_ID" > /dev/null 2>&1 || true
  done
  echo "[OK] 실행 중 실험 중단 완료"
else
  echo "[SKIP] 실행 중인 실험 없음"
fi

# ──────────────────────────────────────────────
# 2. Experiment Templates 삭제
# ──────────────────────────────────────────────
echo ""
echo "[2/4] Experiment Templates 삭제..."
TEMPLATE_IDS=$(aws fis list-experiment-templates \
  --region "$REGION" \
  --query 'experimentTemplates[?tags.Environment==`lab`].id' \
  --output text 2>/dev/null)

if [ -n "$TEMPLATE_IDS" ]; then
  for TEMPLATE_ID in $TEMPLATE_IDS; do
    echo "  삭제: $TEMPLATE_ID"
    aws fis delete-experiment-template \
      --region "$REGION" \
      --id "$TEMPLATE_ID" > /dev/null
  done
  echo "[OK] Templates 삭제 완료"
else
  echo "[SKIP] 삭제할 Template 없음"
fi

# ──────────────────────────────────────────────
# 3. CloudWatch Alarms 삭제
# ──────────────────────────────────────────────
echo ""
echo "[3/4] CloudWatch Alarms 삭제..."
ALARM_NAMES=$(aws cloudwatch describe-alarms \
  --region "$REGION" \
  --alarm-name-prefix "$ALARM_PREFIX" \
  --query 'MetricAlarms[].AlarmName' \
  --output text 2>/dev/null)

if [ -n "$ALARM_NAMES" ]; then
  aws cloudwatch delete-alarms \
    --region "$REGION" \
    --alarm-names $ALARM_NAMES
  echo "[OK] CloudWatch Alarms 삭제 완료"
  echo "     삭제된 알람: $ALARM_NAMES"
else
  echo "[SKIP] 삭제할 알람 없음"
fi

# ──────────────────────────────────────────────
# 4. IAM 정리
# ──────────────────────────────────────────────
echo ""
echo "[4/4] IAM Role & Policy 정리..."

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

# Policy 분리
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
  echo "  Policy 분리 중..."
  ATTACHED_POLICIES=$(aws iam list-attached-role-policies \
    --role-name "$ROLE_NAME" \
    --query 'AttachedPolicies[].PolicyArn' \
    --output text 2>/dev/null)

  for ATTACHED_ARN in $ATTACHED_POLICIES; do
    aws iam detach-role-policy \
      --role-name "$ROLE_NAME" \
      --policy-arn "$ATTACHED_ARN" 2>/dev/null
    echo "    분리: $ATTACHED_ARN"
  done

  # Role 삭제
  aws iam delete-role --role-name "$ROLE_NAME"
  echo "[OK] IAM Role '$ROLE_NAME' 삭제 완료"
else
  echo "[SKIP] IAM Role '$ROLE_NAME' 없음"
fi

# Custom Policy 삭제
if aws iam get-policy --policy-arn "$POLICY_ARN" > /dev/null 2>&1; then
  # Policy 버전 삭제 (기본 버전 외)
  POLICY_VERSIONS=$(aws iam list-policy-versions \
    --policy-arn "$POLICY_ARN" \
    --query 'Versions[?!IsDefaultVersion].VersionId' \
    --output text 2>/dev/null)

  for VERSION_ID in $POLICY_VERSIONS; do
    aws iam delete-policy-version \
      --policy-arn "$POLICY_ARN" \
      --version-id "$VERSION_ID" 2>/dev/null
  done

  aws iam delete-policy --policy-arn "$POLICY_ARN"
  echo "[OK] IAM Policy '$POLICY_NAME' 삭제 완료"
else
  echo "[SKIP] IAM Policy '$POLICY_NAME' 없음"
fi

# 임시 파일 정리
rm -rf /tmp/fis-lab /tmp/fis-template-*.json /tmp/fis-trust-policy.json /tmp/fis-permission-policy.json

echo ""
echo "======================================"
echo " FIS Lab 정리 완료"
echo "======================================"
