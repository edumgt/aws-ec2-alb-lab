#!/usr/bin/env bash
# Phase H. GitHub Actions OIDC 역할 권한 확장 + gh 로 Secrets/Variables 등록
source "$(dirname "$0")/00_common.sh"
need FE_BUCKET DIST_ID INSTANCE_ID
command -v gh >/dev/null || { echo "gh CLI 가 필요합니다 (gh auth login)"; exit 1; }

step "[1/2] ${GHA_ROLE_NAME} 에 플랫폼 배포 권한 인라인 정책"
sed -e "s|__ACCOUNT_ID__|$ACCOUNT_ID|g" -e "s|__REGION__|$AWS_REGION|g" -e "s|__APP__|$APP|g" \
    -e "s|__FE_BUCKET__|$FE_BUCKET|g" -e "s|__DIST_ID__|$DIST_ID|g" -e "s|__INSTANCE_ID__|$INSTANCE_ID|g" \
    "$REPO_ROOT/iam/policies/stock-platform-github-deploy-policy.json" > /tmp/gha-platform.json
aws iam put-role-policy --role-name "$GHA_ROLE_NAME" --policy-name ${APP}-platform-deploy --policy-document file:///tmp/gha-platform.json
rm -f /tmp/gha-platform.json

step "[2/2] GitHub Secrets / Variables"
gh secret   set AWS_ROLE_TO_ASSUME --body "arn:aws:iam::${ACCOUNT_ID}:role/${GHA_ROLE_NAME}"
gh variable set AWS_REGION       --body "$AWS_REGION"
gh variable set ECR_REGISTRY     --body "$ECR_REGISTRY"
gh variable set FE_BUCKET        --body "$FE_BUCKET"
gh variable set CF_DIST_ID       --body "$DIST_ID"
gh variable set APP_INSTANCE_ID  --body "$INSTANCE_ID"
gh variable set APP_HOST         --body "$APP_HOST"
gh variable set APP_NAME         --body "$APP"
echo; echo "완료. 워크플로우: .github/workflows/deploy-stock-platform.yml  →  gh workflow run deploy-stock-platform.yml"
