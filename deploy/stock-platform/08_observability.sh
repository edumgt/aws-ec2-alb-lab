#!/usr/bin/env bash
# Phase G. SNS 알림, CloudWatch 알람 5종, WAF(CloudFront), Budgets
source "$(dirname "$0")/00_common.sh"
need ALB_ARN TG_ARN INSTANCE_ID DIST_ID

step "[1/4] SNS 토픽 + 이메일 구독"
save TOPIC_ARN "$(aws sns create-topic --name ${APP}-alerts --query TopicArn --output text)"
aws sns subscribe --topic-arn "$TOPIC_ARN" --protocol email --notification-endpoint "$ALERT_EMAIL" >/dev/null
echo "  $ALERT_EMAIL 로 온 확인 메일의 링크를 클릭하세요."

step "[2/4] CloudWatch 알람"
ALB_SUFFIX="${ALB_ARN#*loadbalancer/}"; TG_SUFFIX="targetgroup/${TG_ARN#*:targetgroup/}"
alarm() { aws cloudwatch put-metric-alarm --alarm-actions "$TOPIC_ARN" "$@" >/dev/null; echo "  ${2}"; }
alarm --alarm-name ${APP}-alb-5xx --namespace AWS/ApplicationELB --metric-name HTTPCode_ELB_5XX_Count \
  --dimensions Name=LoadBalancer,Value="$ALB_SUFFIX" --statistic Sum --period 300 --evaluation-periods 1 \
  --threshold 10 --comparison-operator GreaterThanOrEqualToThreshold --treat-missing-data notBreaching
alarm --alarm-name ${APP}-no-healthy-host --namespace AWS/ApplicationELB --metric-name HealthyHostCount \
  --dimensions Name=LoadBalancer,Value="$ALB_SUFFIX" Name=TargetGroup,Value="$TG_SUFFIX" --statistic Minimum --period 60 \
  --evaluation-periods 3 --threshold 1 --comparison-operator LessThanThreshold
alarm --alarm-name ${APP}-app-cpu-high --namespace AWS/EC2 --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value="$INSTANCE_ID" --statistic Average --period 300 --evaluation-periods 2 \
  --threshold 80 --comparison-operator GreaterThanThreshold
alarm --alarm-name ${APP}-mariadb-storage-low --namespace AWS/RDS --metric-name FreeStorageSpace \
  --dimensions Name=DBInstanceIdentifier,Value=${APP}-mariadb --statistic Average --period 300 --evaluation-periods 1 \
  --threshold 2000000000 --comparison-operator LessThanThreshold
alarm --alarm-name ${APP}-collector-errors --namespace AWS/Lambda --metric-name Errors \
  --dimensions Name=FunctionName,Value=${APP}-price-collector --statistic Sum --period 300 --evaluation-periods 1 \
  --threshold 3 --comparison-operator GreaterThanOrEqualToThreshold --treat-missing-data notBreaching

step "[3/4] WAF (us-east-1, CLOUDFRONT 스코프) → 배포 연결"
if ! nz "${WAF_ARN:-}"; then
  save WAF_ARN "$(aws wafv2 create-web-acl --region us-east-1 --name ${APP}-waf --scope CLOUDFRONT --default-action Allow={} \
    --rules "file://$SP_DIR/templates/waf-rules.json" \
    --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=${APP}-waf --query Summary.ARN --output text)"
fi
ETAG=$(aws cloudfront get-distribution-config --id "$DIST_ID" --query ETag --output text)
CFG=$(mktemp); aws cloudfront get-distribution-config --id "$DIST_ID" --query DistributionConfig | jq --arg w "$WAF_ARN" '.WebACLId=$w' > "$CFG"
aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" --distribution-config "file://$CFG" >/dev/null; rm -f "$CFG"
echo "  WAF 연결 완료"

step "[4/4] 월 예산 (${MONTHLY_BUDGET_USD} USD, 80% 도달 시 메일)"
aws budgets describe-budget --account-id "$ACCOUNT_ID" --budget-name ${APP}-monthly >/dev/null 2>&1 || \
aws budgets create-budget --account-id "$ACCOUNT_ID" \
  --budget "{\"BudgetName\":\"${APP}-monthly\",\"BudgetLimit\":{\"Amount\":\"${MONTHLY_BUDGET_USD}\",\"Unit\":\"USD\"},\"TimeUnit\":\"MONTHLY\",\"BudgetType\":\"COST\"}" \
  --notifications-with-subscribers "[{\"Notification\":{\"NotificationType\":\"ACTUAL\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":80,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"${ALERT_EMAIL}\"}]}]"
echo; echo "관측·보안 완료"
