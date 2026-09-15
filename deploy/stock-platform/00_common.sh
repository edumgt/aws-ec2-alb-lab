#!/usr/bin/env bash
# 모든 단계 스크립트가 source 하는 공통 로더
#  - env.sh 로드, 생성된 리소스 ID 를 .state 파일에 저장/복원
set -euo pipefail

SP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SP_DIR/../.." && pwd)"
ENV_FILE="$SP_DIR/env.sh"
STATE_FILE="$SP_DIR/.state"

[[ -f "$ENV_FILE" ]] || { echo "env.sh 가 없습니다: cp $SP_DIR/env.example.sh $ENV_FILE 후 값을 수정하세요." >&2; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"
[[ -f "$STATE_FILE" ]] && source "$STATE_FILE"

export AWS_DEFAULT_REGION="$AWS_REGION"
export ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
export ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export KEY_NAME="${APP}-key"

# save VAR VALUE : 변수 export + .state 에 기록(같은 키는 덮어씀)
save() {
  local k="$1" v="$2"
  export "$k=$v"
  touch "$STATE_FILE"
  grep -v "^export $k=" "$STATE_FILE" > "$STATE_FILE.tmp" || true
  echo "export $k=\"$v\"" >> "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
  echo "  $k=$v"
}

# need VAR... : 이전 단계에서 만든 값이 있는지 확인
need() { for k in "$@"; do [[ -n "${!k:-}" ]] || { echo "필요한 값 $k 이(가) 없습니다. 이전 단계를 먼저 실행하세요." >&2; exit 1; }; done; }

# 값이 None/빈문자열이면 실패 처리
nz() { [[ -n "$1" && "$1" != "None" ]]; }

# SSM SecureString 저장
ssm_put() { aws ssm put-parameter --name "${SSM_PREFIX}/$1" --value "$2" --type SecureString --overwrite >/dev/null; echo "  ssm ${SSM_PREFIX}/$1"; }

# 태그 스펙 헬퍼
tags() { echo "ResourceType=$1,Tags=[{Key=Name,Value=$2},{Key=Project,Value=$APP}]"; }

step() { echo; echo "── $* ──"; }
