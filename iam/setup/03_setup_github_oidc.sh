#!/usr/bin/env bash
# GitHub Actions OIDC Identity Provider + IAM Role 설정
# 용도: Access Key 없이 GitHub Actions에서 AWS 인증 (deploy-ecr-ec2.yml OIDC 방식 전환 시 사용)
#
# 전제 조건:
#   - GitHub repo: edumgt/aws-ec2-alb-lab
#   - main 브랜치에서만 AssumeRole 허용
set -euo pipefail

ACCOUNT_ID="086015456585"
REGION="ap-northeast-2"
GITHUB_ORG="edumgt"
GITHUB_REPO="aws-ec2-alb-lab"
OIDC_URL="https://token.actions.githubusercontent.com"
OIDC_THUMBPRINT="6938fd4d98bab03faadb97b34396831e3780aea1"
ROLE_NAME="GitHubActionsECRRole"
POLICY_NAME="GitHubActionsECRPolicy"
TRUST_FILE="$(dirname "$0")/../trust-policies/github-oidc-trust.json"
POLICY_FILE="$(dirname "$0")/../policies/github-oidc-deploy-policy.json"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
OIDC_PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

echo "[1/4] GitHub OIDC Identity Provider 등록"
if aws iam get-open-id-connect-provider \
    --open-id-connect-provider-arn "$OIDC_PROVIDER_ARN" &>/dev/null; then
  echo "  [SKIP] OIDC Provider 이미 존재함"
else
  aws iam create-open-id-connect-provider \
    --url "$OIDC_URL" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "$OIDC_THUMBPRINT" > /dev/null
  echo "  [OK] OIDC Provider 등록 완료: $OIDC_PROVIDER_ARN"
fi

echo "[2/4] IAM Role 생성 — $ROLE_NAME"
if aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
  # 기존 Role의 Trust Policy를 최신 파일로 업데이트
  aws iam update-assume-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-document "file://$TRUST_FILE"
  echo "  [OK] Trust Policy 업데이트 완료"
else
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST_FILE" \
    --description "GitHub Actions OIDC Role for ECR push (edumgt/aws-ec2-alb-lab)" > /dev/null
  echo "  [OK] Role 생성 완료"
fi

echo "[3/4] Permission Policy 생성 및 연결 — $POLICY_NAME"
if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
  echo "  [SKIP] Policy 이미 존재함"
else
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document "file://$POLICY_FILE" \
    --description "ECR push policy for GitHub Actions OIDC" > /dev/null
  echo "  [OK] Policy 생성 완료: $POLICY_ARN"
fi

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN" 2>/dev/null && echo "  [OK] Policy 연결 완료" || echo "  [SKIP] 이미 연결됨"

echo "[4/4] Role ARN 출력"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "  Role ARN: $ROLE_ARN"
echo ""
echo "완료. OIDC 방식 사용 시 GitHub Secret 설정:"
echo "  AWS_ROLE_TO_ASSUME : $ROLE_ARN"
echo ""
echo "deploy-ecr-ec2.yml 에서 아래로 교체하면 Access Key 없이 동작합니다:"
echo "  - name: AWS 자격 증명 설정"
echo "    uses: aws-actions/configure-aws-credentials@v4"
echo "    with:"
echo "      role-to-assume: \${{ secrets.AWS_ROLE_TO_ASSUME }}"
echo "      aws-region: $REGION"
