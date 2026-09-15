#!/usr/bin/env bash
# Phase B. SSM Parameter Store 비밀 등록 + 앱/람다/스케줄러 IAM 역할
#   증권사 키 파일 경로(선택): KIS_KEY_FILE, KB_KEY_FILE, ALPACA_KEY_FILE (1행 key, 2행 secret)
source "$(dirname "$0")/00_common.sh"

step "[1/3] DB 비밀번호·앱 시크릿 생성 → SSM"
gen() { openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | cut -c1-24; }
if ! aws ssm get-parameter --name "${SSM_PREFIX}/db/mariadb/password" >/dev/null 2>&1; then ssm_put db/mariadb/password "$(gen)"; fi
if ! aws ssm get-parameter --name "${SSM_PREFIX}/db/postgres/password" >/dev/null 2>&1; then ssm_put db/postgres/password "$(gen)"; fi
if ! aws ssm get-parameter --name "${SSM_PREFIX}/app/secret_key" >/dev/null 2>&1; then ssm_put app/secret_key "$(openssl rand -hex 32)"; fi

step "[2/3] 증권사·거래소 키 → SSM (파일이 지정된 경우만)"
put_pair() { # $1 파일 $2 key경로 $3 secret경로
  [[ -n "${!1:-}" && -f "${!1}" ]] || { echo "  skip $2 (파일 없음: \$$1)"; return; }
  ssm_put "$2" "$(sed -n 1p "${!1}")"; [[ -n "$3" ]] && ssm_put "$3" "$(sed -n 2p "${!1}")"
}
put_pair KIS_KEY_FILE    kis/app_key    kis/app_secret
put_pair KB_KEY_FILE     kb/app_key     kb/app_secret
put_pair ALPACA_KEY_FILE alpaca/key_id  alpaca/secret

step "[3/3] IAM 역할 (iam/setup/05_setup_stock_platform_roles.sh)"
APP="$APP" SSM_PREFIX="$SSM_PREFIX" bash "$REPO_ROOT/iam/setup/05_setup_stock_platform_roles.sh"
save EC2_PROFILE "${APP}-ec2-profile"
save LAMBDA_ROLE_ARN "$(aws iam get-role --role-name ${APP}-lambda-role --query Role.Arn --output text)"
save SCHED_ROLE_ARN  "$(aws iam get-role --role-name ${APP}-scheduler-role --query Role.Arn --output text)"

echo; aws ssm get-parameters-by-path --path "$SSM_PREFIX" --recursive --query 'Parameters[*].Name' --output table
