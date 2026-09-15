#!/usr/bin/env bash
# Phase F. Lambda(시세 수집·장마감) + EventBridge Scheduler + API Gateway(HTTP API)
source "$(dirname "$0")/00_common.sh"
need LAMBDA_ROLE_ARN SCHED_ROLE_ARN
FN="${APP}-price-collector"

step "[1/4] Lambda 패키징·배포"
ZIP=$(mktemp -u).zip; (cd "$SP_DIR/lambda/collector" && zip -qr "$ZIP" .)
if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://$ZIP" >/dev/null; echo "  코드 갱신"
else
  aws lambda create-function --function-name "$FN" --runtime python3.12 --handler handler.handler \
    --role "$LAMBDA_ROLE_ARN" --zip-file "fileb://$ZIP" --timeout 30 --memory-size 256 \
    --environment "Variables={SSM_PREFIX=${SSM_PREFIX},APP_INGEST_URL=https://${APP_HOST}/api/internal/ingest}" \
    --tags Project="$APP" >/dev/null; echo "  함수 생성"
fi
rm -f "$ZIP"
save FN_ARN "$(aws lambda get-function --function-name "$FN" --query Configuration.FunctionArn --output text)"
aws lambda wait function-active-v2 --function-name "$FN"

step "[2/4] 스케줄 (KST, 평일)"
mk_sched() { # name cron input
  local tgt="{\"Arn\":\"$FN_ARN\",\"RoleArn\":\"$SCHED_ROLE_ARN\",\"RetryPolicy\":{\"MaximumRetryAttempts\":2}${3:+,\"Input\":\"$3\"}}"
  if aws scheduler get-schedule --name "$1" >/dev/null 2>&1; then
    aws scheduler update-schedule --name "$1" --schedule-expression "$2" --schedule-expression-timezone Asia/Seoul --flexible-time-window Mode=OFF --target "$tgt" >/dev/null
  else
    aws scheduler create-schedule --name "$1" --schedule-expression "$2" --schedule-expression-timezone Asia/Seoul --flexible-time-window Mode=OFF --target "$tgt" >/dev/null
  fi; echo "  $1 : $2"
}
mk_sched ${APP}-market-hours   "cron(0/1 9-15 ? * MON-FRI *)" ""
mk_sched ${APP}-eod-settlement "cron(0 16 ? * MON-FRI *)"     '{\"job\":\"eod\"}'

step "[3/4] API Gateway HTTP API (GET /v1/quotes)"
if ! nz "${API_ID:-}"; then
  save API_ID "$(aws apigatewayv2 create-api --name ${APP}-openapi --protocol-type HTTP --target "$FN_ARN" --route-key "GET /v1/quotes" --query ApiId --output text)"
  aws lambda add-permission --function-name "$FN" --statement-id apigw-invoke --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*" >/dev/null
fi
aws apigatewayv2 update-stage --api-id "$API_ID" --stage-name '$default' --default-route-settings ThrottlingRateLimit=20,ThrottlingBurstLimit=50 >/dev/null
save API_ENDPOINT "$(aws apigatewayv2 get-api --api-id "$API_ID" --query ApiEndpoint --output text)"

step "[4/4] 테스트 호출"
aws lambda invoke --function-name "$FN" --payload '{}' --cli-binary-format raw-in-base64-out /dev/stdout | head -c 300; echo
echo "Open API: ${API_ENDPOINT}/v1/quotes"
