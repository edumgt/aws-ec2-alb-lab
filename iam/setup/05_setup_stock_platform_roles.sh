#!/usr/bin/env bash
# 주식투자 플랫폼용 IAM 역할 3종 생성 (또는 --delete 로 삭제)
#   ${APP}-ec2-role       + ${APP}-ec2-profile : 앱 EC2 (SSM 읽기, ECR pull, Session Manager, CW Agent)
#   ${APP}-lambda-role                          : 시세 수집 Lambda (로그 + SSM 읽기)
#   ${APP}-scheduler-role                       : EventBridge Scheduler → Lambda 호출
# 환경변수: APP(기본 stock-trade), SSM_PREFIX(기본 /stock-coin-trade), AWS_REGION
set -euo pipefail

APP="${APP:-stock-trade}"
SSM_PREFIX="${SSM_PREFIX:-/stock-coin-trade}"
REGION="${AWS_REGION:-ap-northeast-2}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
DIR="$(cd "$(dirname "$0")/.." && pwd)"

render() { sed -e "s|__ACCOUNT_ID__|$ACCOUNT_ID|g" -e "s|__REGION__|$REGION|g" -e "s|__SSM_PREFIX__|$SSM_PREFIX|g" -e "s|__APP__|$APP|g" "$1"; }

EC2_ROLE="${APP}-ec2-role"; EC2_PROFILE="${APP}-ec2-profile"
LAMBDA_ROLE="${APP}-lambda-role"; SCHED_ROLE="${APP}-scheduler-role"

if [[ "${1:-}" == "--delete" ]]; then
  echo "[삭제] $EC2_ROLE / $LAMBDA_ROLE / $SCHED_ROLE"
  for r in "$EC2_ROLE" "$LAMBDA_ROLE" "$SCHED_ROLE"; do
    aws iam get-role --role-name "$r" >/dev/null 2>&1 || continue
    for p in $(aws iam list-role-policies --role-name "$r" --query PolicyNames --output text); do aws iam delete-role-policy --role-name "$r" --policy-name "$p"; done
    for a in $(aws iam list-attached-role-policies --role-name "$r" --query 'AttachedPolicies[*].PolicyArn' --output text); do aws iam detach-role-policy --role-name "$r" --policy-arn "$a"; done
  done
  aws iam remove-role-from-instance-profile --instance-profile-name "$EC2_PROFILE" --role-name "$EC2_ROLE" 2>/dev/null || true
  aws iam delete-instance-profile --instance-profile-name "$EC2_PROFILE" 2>/dev/null || true
  for r in "$EC2_ROLE" "$LAMBDA_ROLE" "$SCHED_ROLE"; do aws iam delete-role --role-name "$r" 2>/dev/null && echo "  삭제 $r" || true; done
  exit 0
fi

ensure_role() { # name trust-file
  if aws iam get-role --role-name "$1" >/dev/null 2>&1; then
    aws iam update-assume-role-policy --role-name "$1" --policy-document "file://$2"; echo "  [OK] $1 (신뢰 정책 갱신)"
  else
    aws iam create-role --role-name "$1" --assume-role-policy-document "file://$2" --tags Key=Project,Value="$APP" >/dev/null; echo "  [OK] $1 생성"
  fi
}

echo "[1/3] 앱 EC2 역할 — $EC2_ROLE"
ensure_role "$EC2_ROLE" "$DIR/trust-policies/ec2-instance-trust.json"
aws iam put-role-policy --role-name "$EC2_ROLE" --policy-name app-access --policy-document "$(render "$DIR/policies/stock-platform-ec2-app-policy.json")"
aws iam attach-role-policy --role-name "$EC2_ROLE" --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam attach-role-policy --role-name "$EC2_ROLE" --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy
if ! aws iam get-instance-profile --instance-profile-name "$EC2_PROFILE" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$EC2_PROFILE" >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name "$EC2_PROFILE" --role-name "$EC2_ROLE"
  echo "  [OK] 인스턴스 프로파일 $EC2_PROFILE"
fi

echo "[2/3] Lambda 역할 — $LAMBDA_ROLE"
ensure_role "$LAMBDA_ROLE" "$DIR/trust-policies/lambda-trust.json"
aws iam attach-role-policy --role-name "$LAMBDA_ROLE" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam put-role-policy --role-name "$LAMBDA_ROLE" --policy-name ssm-read --policy-document "$(render "$DIR/policies/stock-platform-lambda-policy.json")"

echo "[3/3] Scheduler 역할 — $SCHED_ROLE"
ensure_role "$SCHED_ROLE" "$DIR/trust-policies/scheduler-trust.json"
aws iam put-role-policy --role-name "$SCHED_ROLE" --policy-name invoke-lambda --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"lambda:InvokeFunction\",\"Resource\":\"arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${APP}-*\"}]}"

echo "  전파 대기 10초"; sleep 10
echo "완료."
