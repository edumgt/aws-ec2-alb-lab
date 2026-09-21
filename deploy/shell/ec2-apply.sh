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
PROXY_IMAGE="${ECR_REGISTRY}/rag-api-proxy:latest"
TLS_DIR="${TLS_DIR:-/opt/rag-tls}"

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
PROXY_IMAGE="${PROXY_IMAGE}"
TLS_DIR="${TLS_DIR}"

echo "[1/5] ECR 로그인"
aws ecr get-login-password --region "\$REGION" | \\
  docker login --username AWS --password-stdin "\$ECR_REGISTRY"

echo "[2/5] 최신 BE/HTTPS 프록시 이미지 Pull"
docker pull "\$BE_IMAGE"
docker pull "\$PROXY_IMAGE"

if [[ ! -r "\$TLS_DIR/fullchain.pem" || ! -r "\$TLS_DIR/privkey.pem" ]]; then
  echo "TLS 인증서가 없습니다: \$TLS_DIR/{fullchain.pem,privkey.pem}" >&2
  exit 1
fi

docker network create rag-api-net 2>/dev/null || true

echo "[3/5] BE 컨테이너 교체 (Docker 내부 포트 :8000, 호스트 미공개)"
docker stop fastapi-app 2>/dev/null || true
docker rm   fastapi-app 2>/dev/null || true
docker run -d --name fastapi-app --restart unless-stopped \\
  --network rag-api-net "\$BE_IMAGE"

echo "[4/5] 기존 EC2 FE 컨테이너 제거 (FE는 rf.edumgt.co.kr의 S3/CloudFront에서 제공)"
docker stop fe-ag-grid 2>/dev/null || true
docker rm   fe-ag-grid 2>/dev/null || true
docker stop rag-api-proxy 2>/dev/null || true
docker rm   rag-api-proxy 2>/dev/null || true
docker run -d --name rag-api-proxy --restart unless-stopped \\
  --network rag-api-net -p 443:443 \\
  --mount type=bind,src="\$TLS_DIR/fullchain.pem",dst=/etc/nginx/tls/fullchain.pem,readonly \\
  --mount type=bind,src="\$TLS_DIR/privkey.pem",dst=/etc/nginx/tls/privkey.pem,readonly \\
  "\$PROXY_IMAGE"

echo "[5/5] 실행 상태 확인"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo ""
echo "HTTPS 헬스체크:"
sleep 3
curl -skf --resolve rag.edumgt.co.kr:443:127.0.0.1 https://rag.edumgt.co.kr/api/health && echo " OK" || echo " FAIL"
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
