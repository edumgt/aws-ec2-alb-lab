#!/bin/bash
# AWS FIS - IAM Role & Policy Setup
set -euo pipefail

ROLE_NAME="FISExperimentRole"
POLICY_NAME="FISExperimentPolicy"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"

echo "======================================"
echo " [1/3] FIS IAM Role 생성"
echo "======================================"

# FIS 서비스가 Assume 할 수 있는 Trust Policy
cat > /tmp/fis-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "fis.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# IAM Role 생성 (이미 존재하면 스킵)
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
  echo "[SKIP] Role '$ROLE_NAME' 이미 존재합니다."
  ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
else
  echo "[CREATE] Role '$ROLE_NAME' 생성 중..."
  ROLE_ARN=$(aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document file:///tmp/fis-trust-policy.json \
    --description "AWS FIS Experiment Execution Role" \
    --query 'Role.Arn' \
    --output text)
  echo "[OK] Role 생성 완료: $ROLE_ARN"
fi

echo ""
echo "======================================"
echo " [2/3] FIS IAM Permission Policy 생성"
echo "======================================"

# FIS가 대상 리소스에 장애를 주입할 수 있는 권한 정책
cat > /tmp/fis-permission-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "FISComputeActions",
      "Effect": "Allow",
      "Action": [
        "ec2:StopInstances",
        "ec2:RebootInstances",
        "ec2:TerminateInstances",
        "ec2:SendSpotInstanceInterruptions",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus"
      ],
      "Resource": "*"
    },
    {
      "Sid": "FISNetworkActions",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateNetworkAclEntry",
        "ec2:DeleteNetworkAclEntry",
        "ec2:DescribeNetworkAcls"
      ],
      "Resource": "*"
    },
    {
      "Sid": "FISDatabaseActions",
      "Effect": "Allow",
      "Action": [
        "rds:RebootDBInstance",
        "rds:FailoverDBCluster",
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters"
      ],
      "Resource": "*"
    },
    {
      "Sid": "FISSSMActions",
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:DescribeInstanceInformation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "FISCloudWatchActions",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:GetMetricData",
        "logs:CreateLogDelivery",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "FISIAMPassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "fis.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# Policy 생성 또는 업데이트
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

if aws iam get-policy --policy-arn "$POLICY_ARN" > /dev/null 2>&1; then
  echo "[SKIP] Policy '$POLICY_NAME' 이미 존재합니다."
else
  echo "[CREATE] Policy '$POLICY_NAME' 생성 중..."
  aws iam create-policy \
    --policy-name "$POLICY_NAME" \
    --policy-document file:///tmp/fis-permission-policy.json \
    --description "AWS FIS Experiment Permission Policy" > /dev/null
  echo "[OK] Policy 생성 완료"
fi

echo ""
echo "======================================"
echo " [3/3] Policy를 Role에 연결"
echo "======================================"

aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN" 2>/dev/null && echo "[OK] Policy 연결 완료" || echo "[SKIP] 이미 연결되어 있습니다."

# CloudWatch Logs Full Access (실험 로그 기록용)
aws iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess" 2>/dev/null && echo "[OK] CloudWatchLogs Policy 연결 완료" || echo "[SKIP] CloudWatchLogs 이미 연결됨"

echo ""
echo "======================================"
echo " IAM 설정 완료"
echo "======================================"
echo "  Role ARN : $ROLE_ARN"
echo "  Policy ARN: $POLICY_ARN"
echo ""
echo "다음 단계: 02_create_cloudwatch_alarms.sh 를 실행하세요."

# 후속 스크립트를 위해 ARN 저장
mkdir -p /tmp/fis-lab
echo "$ROLE_ARN" > /tmp/fis-lab/role_arn.txt
echo "$ACCOUNT_ID" > /tmp/fis-lab/account_id.txt
