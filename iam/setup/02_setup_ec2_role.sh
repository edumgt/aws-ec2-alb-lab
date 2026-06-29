#!/usr/bin/env bash
# EC2 인스턴스 프로파일 생성 및 ECR Pull 정책 연결
# 용도: EC2(43.203.255.251)에서 aws ecr get-login-password 없이 pull 가능하게 함
set -euo pipefail

ACCOUNT_ID="086015456585"
REGION="ap-northeast-2"
ROLE_NAME="EC2ECRPullRole"
POLICY_NAME="EC2ECRPullPolicy"
INSTANCE_PROFILE_NAME="EC2ECRPullProfile"
TRUST_FILE="$(dirname "$0")/../trust-policies/ec2-instance-trust.json"
POLICY_FILE="$(dirname "$0")/../policies/ec2-ecr-pull-policy.json"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

echo "[1/5] IAM Role 생성 — $ROLE_NAME"
if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
  echo "  [SKIP] 이미 존재함"
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST_FILE" \
    --description "EC2 instance role for ECR pull (be-test, fe-test)" > /dev/null
  echo "  [OK] Role 생성 완료"
fi

echo "[2/5] Permission Policy 생성 — $POLICY_NAME"
if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
  echo "  [SKIP] 이미 존재함"
else
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE" \
    --description "ECR pull-only policy for EC2 instance (be-test, fe-test)" > /dev/null
  echo "  [OK] Policy 생성 완료: $POLICY_ARN"
fi

echo "[3/5] Policy → Role 연결"
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN" 2>/dev/null && echo "  [OK] 연결 완료" || echo "  [SKIP] 이미 연결됨"

echo "[4/5] Instance Profile 생성 및 Role 연결"
if aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" &>/dev/null; then
  echo "  [SKIP] Instance Profile 이미 존재함"
else
  aws iam create-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" > /dev/null
  aws iam add-role-to-instance-profile \
    --instance-profile-name "$INSTANCE_PROFILE_NAME" \
    --role-name "$ROLE_NAME"
  echo "  [OK] Instance Profile 생성 및 Role 연결 완료"
fi

echo "[5/5] EC2 인스턴스에 프로파일 연결 (인스턴스 ID를 직접 지정)"
INSTANCE_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=ip-address,Values=43.203.255.251" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null || echo "None")

if [[ "$INSTANCE_ID" == "None" || -z "$INSTANCE_ID" ]]; then
  echo "  [WARN] 인스턴스를 자동으로 찾지 못했습니다."
  echo "  아래 명령을 직접 실행하세요:"
  echo "  aws ec2 associate-iam-instance-profile \\"
  echo "    --region $REGION \\"
  echo "    --instance-id <INSTANCE_ID> \\"
  echo "    --iam-instance-profile Name=$INSTANCE_PROFILE_NAME"
else
  aws ec2 associate-iam-instance-profile \
    --region "$REGION" \
    --instance-id "$INSTANCE_ID" \
    --iam-instance-profile "Name=$INSTANCE_PROFILE_NAME" 2>/dev/null \
    && echo "  [OK] 인스턴스($INSTANCE_ID)에 프로파일 연결 완료" \
    || echo "  [SKIP] 이미 연결됨"
fi

echo ""
echo "완료. 이후 EC2에서 아래 명령이 자격증명 없이 동작합니다:"
echo "  aws ecr get-login-password --region $REGION | \\"
echo "    docker login --username AWS --password-stdin \\"
echo "    086015456585.dkr.ecr.$REGION.amazonaws.com"
