#!/usr/bin/env bash
# Phase D-1~3. ECR 리포지토리, ACM 인증서(서울 + us-east-1), ALB / Target Group / 리스너
source "$(dirname "$0")/00_common.sh"
need VPC_ID PUB_A PUB_C SG_ALB

step "[1/4] ECR 리포지토리"
for repo in "$FE_REPO" "$BE_REPO"; do
  aws ecr describe-repositories --repository-names "$repo" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$repo" --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 --query repository.repositoryUri --output text
done

step "[2/4] Route 53 호스팅 존 + ACM 인증서"
save HZ_ID "$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN_NAME" --query 'HostedZones[0].Id' --output text | sed 's|/hostedzone/||')"
req_cert() { aws acm request-certificate --region "$1" --domain-name "$APP_HOST" --validation-method DNS --query CertificateArn --output text; }
nz "${CERT_ARN:-}"    || save CERT_ARN    "$(req_cert "$AWS_REGION")"
nz "${CF_CERT_ARN:-}" || save CF_CERT_ARN "$(req_cert us-east-1)"
sleep 8
read -r CN CV <<< "$(aws acm describe-certificate --certificate-arn "$CERT_ARN" \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord.[Name,Value]' --output text)"
aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$CN\",\"Type\":\"CNAME\",\"TTL\":300,\"ResourceRecords\":[{\"Value\":\"$CV\"}]}}]}" >/dev/null
echo "  검증 레코드 등록, 발급 대기..."
aws acm wait certificate-validated --certificate-arn "$CERT_ARN"
aws acm wait certificate-validated --region us-east-1 --certificate-arn "$CF_CERT_ARN"

step "[3/4] ALB + Target Group"
if ! nz "${ALB_ARN:-}"; then
  save ALB_ARN "$(aws elbv2 create-load-balancer --name ${APP}-alb --subnets "$PUB_A" "$PUB_C" --security-groups "$SG_ALB" \
    --scheme internet-facing --type application --tags Key=Project,Value="$APP" --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
fi
save ALB_DNS "$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --query 'LoadBalancers[0].DNSName' --output text)"
save ALB_HZ  "$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" --query 'LoadBalancers[0].CanonicalHostedZoneId' --output text)"
if ! nz "${TG_ARN:-}"; then
  save TG_ARN "$(aws elbv2 create-target-group --name ${APP}-tg --protocol HTTP --port "$APP_PORT" --vpc-id "$VPC_ID" --target-type instance \
    --health-check-path "$HEALTH_PATH" --health-check-interval-seconds 30 --healthy-threshold-count 2 --unhealthy-threshold-count 3 \
    --matcher HttpCode=200-399 --query 'TargetGroups[0].TargetGroupArn' --output text)"
fi

step "[4/4] 리스너 443(forward) / 80(redirect)"
if [[ -z "$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[?Port==`443`].ListenerArn' --output text)" ]]; then
  aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTPS --port 443 \
    --certificates CertificateArn="$CERT_ARN" --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
    --default-actions Type=forward,TargetGroupArn="$TG_ARN" >/dev/null
fi
if [[ -z "$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[?Port==`80`].ListenerArn' --output text)" ]]; then
  aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
    --default-actions 'Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}' >/dev/null
fi
echo; echo "ALB 완료: https://$ALB_DNS (인증서는 $APP_HOST 기준이므로 도메인 연결 후 정상)"
