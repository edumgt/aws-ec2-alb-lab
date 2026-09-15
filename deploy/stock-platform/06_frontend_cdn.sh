#!/usr/bin/env bash
# Phase E. S3 정적 프론트엔드 + CloudFront(오리진 2개: S3 / ALB) + Route 53
#   FRONTEND_DIR: 업로드할 정적 파일 디렉터리 (기본: 저장소의 ag-grid-app)
source "$(dirname "$0")/00_common.sh"
need ALB_DNS CF_CERT_ARN HZ_ID
FRONTEND_DIR="${FRONTEND_DIR:-$REPO_ROOT/ag-grid-app}"
FE_BUCKET="${APP}-frontend-${ACCOUNT_ID}"; save FE_BUCKET "$FE_BUCKET"

step "[1/4] S3 버킷 + 업로드"
aws s3api head-bucket --bucket "$FE_BUCKET" 2>/dev/null || \
aws s3api create-bucket --bucket "$FE_BUCKET" --region "$AWS_REGION" --create-bucket-configuration LocationConstraint="$AWS_REGION" >/dev/null
aws s3 sync "$FRONTEND_DIR/" "s3://${FE_BUCKET}/" --delete --exclude "Dockerfile" --exclude "README.md" --cache-control "max-age=300"

step "[2/4] OAC + CloudFront 배포"
if ! nz "${OAC_ID:-}"; then
  save OAC_ID "$(aws cloudfront create-origin-access-control --origin-access-control-config \
    "Name=${APP}-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" --query OriginAccessControl.Id --output text)"
fi
if ! nz "${DIST_ID:-}"; then
  CFG=$(mktemp)
  sed -e "s|__APP__|$APP|g" -e "s|__APP_HOST__|$APP_HOST|g" -e "s|__CF_CERT_ARN__|$CF_CERT_ARN|g" \
      -e "s|__FE_BUCKET__|$FE_BUCKET|g" -e "s|__REGION__|$AWS_REGION|g" -e "s|__OAC_ID__|$OAC_ID|g" \
      -e "s|__ALB_DNS__|$ALB_DNS|g" -e "s|__REF__|$(date +%s)|g" "$SP_DIR/templates/cloudfront-distribution.json" > "$CFG"
  save DIST_ID "$(aws cloudfront create-distribution --distribution-config "file://$CFG" --query Distribution.Id --output text)"
  rm -f "$CFG"
fi
save CF_DOMAIN "$(aws cloudfront get-distribution --id "$DIST_ID" --query Distribution.DomainName --output text)"

step "[3/4] 버킷 정책 (이 배포만 읽기)"
aws s3api put-bucket-policy --bucket "$FE_BUCKET" --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Principal\":{\"Service\":\"cloudfront.amazonaws.com\"},\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::${FE_BUCKET}/*\",\"Condition\":{\"StringEquals\":{\"AWS:SourceArn\":\"arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}\"}}}]}"

step "[4/4] Route 53 별칭 → CloudFront"
aws route53 change-resource-record-sets --hosted-zone-id "$HZ_ID" --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"${APP_HOST}\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"Z2FDTNDATAQYW2\",\"DNSName\":\"${CF_DOMAIN}\",\"EvaluateTargetHealth\":false}}}]}" >/dev/null
echo "  배포 전파 대기..."
aws cloudfront wait distribution-deployed --id "$DIST_ID"
echo; echo "프론트엔드 완료: https://${APP_HOST}  (FE: S3, /api/* /openapi/*: ALB)"
curl -s -o /dev/null -w "  FE  %{http_code}\n" "https://${APP_HOST}/index.html" || true
curl -s -o /dev/null -w "  API %{http_code}\n" "https://${APP_HOST}${HEALTH_PATH}" || true
