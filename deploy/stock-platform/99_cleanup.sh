#!/usr/bin/env bash
# 생성 역순 리소스 정리. 되돌릴 수 없으므로 실행 전 .state 내용을 확인하세요.
source "$(dirname "$0")/00_common.sh"
echo "삭제 대상 계정: $ACCOUNT_ID / 접두어: $APP"; read -r -p "정말 삭제할까요? (yes 입력) " ans; [[ "$ans" == "yes" ]] || exit 0
q() { "$@" >/dev/null 2>&1 || true; }

step "서버리스"
q aws scheduler delete-schedule --name ${APP}-market-hours; q aws scheduler delete-schedule --name ${APP}-eod-settlement
[[ -n "${API_ID:-}" ]] && q aws apigatewayv2 delete-api --api-id "$API_ID"
q aws lambda delete-function --function-name ${APP}-price-collector

step "알람·예산·SNS"
q aws cloudwatch delete-alarms --alarm-names ${APP}-alb-5xx ${APP}-no-healthy-host ${APP}-app-cpu-high ${APP}-mariadb-storage-low ${APP}-collector-errors
q aws budgets delete-budget --account-id "$ACCOUNT_ID" --budget-name ${APP}-monthly
[[ -n "${TOPIC_ARN:-}" ]] && q aws sns delete-topic --topic-arn "$TOPIC_ARN"

step "CloudFront (비활성화 → 삭제) / Route 53 / WAF"
if [[ -n "${DIST_ID:-}" ]]; then
  ETAG=$(aws cloudfront get-distribution-config --id "$DIST_ID" --query ETag --output text)
  aws cloudfront get-distribution-config --id "$DIST_ID" --query DistributionConfig | jq '.Enabled=false | .WebACLId=""' > /tmp/cf-off.json
  q aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" --distribution-config file:///tmp/cf-off.json
  aws cloudfront wait distribution-deployed --id "$DIST_ID"
  ETAG=$(aws cloudfront get-distribution-config --id "$DIST_ID" --query ETag --output text)
  q aws cloudfront delete-distribution --id "$DIST_ID" --if-match "$ETAG"
fi
[[ -n "${CF_DOMAIN:-}" ]] && q aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" --change-batch "{\"Changes\":[{\"Action\":\"DELETE\",\"ResourceRecordSet\":{\"Name\":\"${APP_HOST}\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"Z2FDTNDATAQYW2\",\"DNSName\":\"${CF_DOMAIN}\",\"EvaluateTargetHealth\":false}}}]}"
[[ -n "${OAC_ID:-}" ]] && q aws cloudfront delete-origin-access-control --id "$OAC_ID" --if-match "$(aws cloudfront get-origin-access-control --id "$OAC_ID" --query ETag --output text)"
if [[ -n "${WAF_ARN:-}" ]]; then
  WID="${WAF_ARN##*/}"; LT=$(aws wafv2 get-web-acl --region us-east-1 --scope CLOUDFRONT --name ${APP}-waf --id "$WID" --query LockToken --output text)
  q aws wafv2 delete-web-acl --region us-east-1 --scope CLOUDFRONT --name ${APP}-waf --id "$WID" --lock-token "$LT"
fi

step "S3 / ECR / SSM"
[[ -n "${FE_BUCKET:-}" ]] && { q aws s3 rm "s3://${FE_BUCKET}" --recursive; q aws s3api delete-bucket --bucket "$FE_BUCKET"; }
for r in "$FE_REPO" "$BE_REPO"; do q aws ecr delete-repository --repository-name "$r" --force; done
NAMES=$(aws ssm get-parameters-by-path --path "$SSM_PREFIX" --recursive --query 'Parameters[*].Name' --output text)
[[ -n "$NAMES" ]] && echo "$NAMES" | xargs -n 10 aws ssm delete-parameters --names >/dev/null

step "ALB / EC2"
if [[ -n "${ALB_ARN:-}" ]]; then
  for l in $(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[*].ListenerArn' --output text); do q aws elbv2 delete-listener --listener-arn "$l"; done
  q aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN"; sleep 20
fi
[[ -n "${TG_ARN:-}" ]] && q aws elbv2 delete-target-group --target-group-arn "$TG_ARN"
if [[ -n "${INSTANCE_ID:-}" ]]; then q aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"; aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"; fi
q aws ec2 delete-key-pair --key-name "$KEY_NAME"

step "RDS (삭제 방지 해제 → 최종 스냅샷 → 삭제)"
for db in ${APP}-mariadb ${APP}-postgres; do
  q aws rds modify-db-instance --db-instance-identifier $db --no-deletion-protection --apply-immediately
  q aws rds delete-db-instance --db-instance-identifier $db --final-db-snapshot-identifier ${db}-final-$(date +%Y%m%d%H%M)
done
for db in ${APP}-mariadb ${APP}-postgres; do q aws rds wait db-instance-deleted --db-instance-identifier $db; done
q aws rds delete-db-subnet-group --db-subnet-group-name ${APP}-db-subnets

step "네트워크"
for sg in "${SG_DB:-}" "${SG_APP:-}" "${SG_ALB:-}"; do [[ -n "$sg" ]] && q aws ec2 delete-security-group --group-id "$sg"; done
for s in "${PUB_A:-}" "${PUB_C:-}" "${PRI_A:-}" "${PRI_C:-}"; do [[ -n "$s" ]] && q aws ec2 delete-subnet --subnet-id "$s"; done
[[ -n "${RTB_PUB:-}" ]] && q aws ec2 delete-route-table --route-table-id "$RTB_PUB"
if [[ -n "${IGW_ID:-}" ]]; then q aws ec2 detach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"; q aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID"; fi
[[ -n "${VPC_ID:-}" ]] && q aws ec2 delete-vpc --vpc-id "$VPC_ID"

step "IAM"
APP="$APP" bash "$REPO_ROOT/iam/setup/05_setup_stock_platform_roles.sh" --delete
q aws iam delete-role-policy --role-name "$GHA_ROLE_NAME" --policy-name ${APP}-platform-deploy

step "ACM"
[[ -n "${CERT_ARN:-}" ]] && q aws acm delete-certificate --certificate-arn "$CERT_ARN"
[[ -n "${CF_CERT_ARN:-}" ]] && q aws acm delete-certificate --region us-east-1 --certificate-arn "$CF_CERT_ARN"

mv "$STATE_FILE" "$STATE_FILE.deleted.$(date +%s)" 2>/dev/null || true
echo; echo "정리 완료. 남은 리소스는 콘솔 Billing 과 'aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=$APP' 로 확인하세요."
