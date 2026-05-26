#!/bin/bash
# AWS FIS - CloudWatch Alarms (Safeguards) 생성
# FIS 실험 중 임계치 초과 시 자동으로 실험을 중단(Stop Condition)하는 안전장치
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
ALARM_PREFIX="fis-safeguard"

echo "======================================"
echo " FIS Safeguards - CloudWatch Alarms"
echo "======================================"

# 대상 EC2 인스턴스 ID 조회 (실행 중인 첫 번째 인스턴스)
INSTANCE_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null)

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo "[WARN] 실행 중인 EC2 인스턴스가 없습니다. 기본 알람만 생성합니다."
  INSTANCE_ID=""
fi

echo ""
echo "[1/4] EC2 CPU 사용률 임계치 알람 생성..."
# CPU 사용률이 80% 이상 5분 지속 시 알람 → FIS Stop Condition으로 사용
aws cloudwatch put-metric-alarm \
  --region "$REGION" \
  --alarm-name "${ALARM_PREFIX}-ec2-cpu-high" \
  --alarm-description "FIS Safeguard: EC2 CPU 사용률 80% 초과 시 실험 중단" \
  --namespace "AWS/EC2" \
  --metric-name "CPUUtilization" \
  --dimensions ${INSTANCE_ID:+Name=InstanceId,Value=$INSTANCE_ID} \
  --statistic Average \
  --period 60 \
  --evaluation-periods 3 \
  --threshold 80 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching
echo "[OK] CPU 알람 생성: ${ALARM_PREFIX}-ec2-cpu-high"

echo ""
echo "[2/4] EC2 상태 체크 실패 알람 생성..."
aws cloudwatch put-metric-alarm \
  --region "$REGION" \
  --alarm-name "${ALARM_PREFIX}-ec2-status-check" \
  --alarm-description "FIS Safeguard: EC2 상태 체크 실패 시 실험 중단" \
  --namespace "AWS/EC2" \
  --metric-name "StatusCheckFailed" \
  --dimensions ${INSTANCE_ID:+Name=InstanceId,Value=$INSTANCE_ID} \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching
echo "[OK] 상태 체크 알람 생성: ${ALARM_PREFIX}-ec2-status-check"

echo ""
echo "[3/4] 네트워크 오류 알람 생성..."
# ALB 5xx 에러율이 50% 초과 시 알람
aws cloudwatch put-metric-alarm \
  --region "$REGION" \
  --alarm-name "${ALARM_PREFIX}-alb-5xx-high" \
  --alarm-description "FIS Safeguard: ALB 5xx 에러 50개 초과 시 실험 중단" \
  --namespace "AWS/ApplicationELB" \
  --metric-name "HTTPCode_ELB_5XX_Count" \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching
echo "[OK] ALB 5xx 알람 생성: ${ALARM_PREFIX}-alb-5xx-high"

echo ""
echo "[4/4] 실험 전반적 가용성 알람 생성..."
# 헬스체크 실패율이 임계치 초과 시 알람 (복합 알람)
aws cloudwatch put-metric-alarm \
  --region "$REGION" \
  --alarm-name "${ALARM_PREFIX}-availability-breach" \
  --alarm-description "FIS Safeguard: 서비스 가용성 위반 - 실험 즉시 중단" \
  --namespace "AWS/EC2" \
  --metric-name "StatusCheckFailed_System" \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching
echo "[OK] 가용성 알람 생성: ${ALARM_PREFIX}-availability-breach"

echo ""
echo "======================================"
echo " 생성된 FIS Safeguard 알람 목록"
echo "======================================"
aws cloudwatch describe-alarms \
  --region "$REGION" \
  --alarm-name-prefix "${ALARM_PREFIX}" \
  --query 'MetricAlarms[].{AlarmName:AlarmName, State:StateValue, Threshold:Threshold}' \
  --output table

echo ""
echo "알람 ARN 확인 (Stop Condition에 사용):"
aws cloudwatch describe-alarms \
  --region "$REGION" \
  --alarm-name-prefix "${ALARM_PREFIX}" \
  --query 'MetricAlarms[].AlarmArn' \
  --output text | tr '\t' '\n'

# 알람 ARN 저장
mkdir -p /tmp/fis-lab
aws cloudwatch describe-alarms \
  --region "$REGION" \
  --alarm-name "${ALARM_PREFIX}-availability-breach" \
  --query 'MetricAlarms[0].AlarmArn' \
  --output text > /tmp/fis-lab/stop_condition_alarm_arn.txt

echo ""
echo "다음 단계: 03_create_experiment_template.sh 를 실행하세요."
