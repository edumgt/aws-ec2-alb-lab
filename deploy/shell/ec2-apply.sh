#!/usr/bin/env bash
# EC2(43.203.255.251)에 최신 ECR 이미지를 적용합니다.
# 로컬에서 SSH를 통해 실행하거나, EC2 접속 후 직접 실행할 수 있습니다.
#
# 사용법 (로컬에서):
#   EC2_HOST=43.203.255.251 EC2_KEY=~/.ssh/kdy-test.pem bash deploy/shell/ec2-apply.sh
#
# 사용법 (EC2 직접):
#   bash deploy/shell/ec2-apply.sh  (원격 접속 없이 로컬 실행)
set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-2}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-086015456585}"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
BE_IMAGE="${ECR_REGISTRY}/be-test:latest"
FE_IMAGE="${ECR_REGISTRY}/fe-test:latest"

EC2_HOST="${EC2_HOST:-}"
EC2_KEY="${EC2_KEY:-}"
EC2_USER="${EC2_USER:-ubuntu}"

# ──────────────────────────────────────────────
# 원격 실행용 deploy 스크립트 (EC2에서 직접 실행)
# ──────────────────────────────────────────────
DEPLOY_COMMANDS=$(cat <<REMOTE
set -euo pipefail
REGION="${REGION}"
ECR_REGISTRY="${ECR_REGISTRY}"
BE_IMAGE="${BE_IMAGE}"
FE_IMAGE="${FE_IMAGE}"

echo "[1/5] ECR 로그인"
aws ecr get-login-password --region "\$REGION" | \\
  docker login --username AWS --password-stdin "\$ECR_REGISTRY"

echo "[2/5] 최신 이미지 Pull"
docker pull "\$BE_IMAGE"
docker pull "\$FE_IMAGE"

echo "[3/5] BE 컨테이너 교체 (:8000)"
docker stop fastapi-app 2>/dev/null || true
docker rm   fastapi-app 2>/dev/null || true
docker run -d --name fastapi-app --restart unless-stopped \\
  -p 8000:8000 "\$BE_IMAGE"

echo "[4/5] FE 컨테이너 교체 (:80)"
docker stop fe-ag-grid 2>/dev/null || true
docker rm   fe-ag-grid 2>/dev/null || true
docker run -d --name fe-ag-grid --restart unless-stopped \\
  -p 80:80 "\$FE_IMAGE"

echo "[5/5] 실행 상태 확인"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ""
echo "BE 헬스체크:"
sleep 3
curl -sf http://localhost:8000/health && echo " OK" || echo " FAIL"
REMOTE
)

# ──────────────────────────────────────────────
# 실행: 원격 SSH 또는 로컬 직접
# ──────────────────────────────────────────────
if [[ -n "$EC2_HOST" && -n "$EC2_KEY" ]]; then
  echo "원격 EC2 배포: ${EC2_USER}@${EC2_HOST}"
  ssh -i "$EC2_KEY" \
      -o StrictHostKeyChecking=no \
      -o ConnectTimeout=15 \
      "${EC2_USER}@${EC2_HOST}" \
      "bash -s" <<< "$DEPLOY_COMMANDS"
else
  echo "로컬 실행 모드 (EC2 직접 접속 상태에서 실행)"
  bash -c "$DEPLOY_COMMANDS"
fi
