# ─────────────────────────────────────────────────────────────
# 주식투자 웹앱 플랫폼 — 공통 환경변수
#   cp deploy/stock-platform/env.example.sh deploy/stock-platform/env.sh
#   값 수정 후 각 단계 스크립트 실행 (env.sh 는 git 에 커밋하지 않음)
# ─────────────────────────────────────────────────────────────
export AWS_REGION="ap-northeast-2"
export APP="stock-trade"                       # 리소스 이름 접두어
export DOMAIN_NAME="example.co.kr"             # Route 53 호스팅 존이 있는 도메인
export APP_HOST="st.${DOMAIN_NAME}"            # 서비스 주소
export ALERT_EMAIL="you@example.com"           # SNS / Budgets 알림 수신
export MONTHLY_BUDGET_USD="100"

# 네트워크
export VPC_CIDR="10.20.0.0/16"
export PUB_A_CIDR="10.20.1.0/24";  export PUB_C_CIDR="10.20.2.0/24"
export PRI_A_CIDR="10.20.11.0/24"; export PRI_C_CIDR="10.20.12.0/24"

# 앱 서버
export INSTANCE_TYPE="t3.small"
export APP_REPO_URL="https://github.com/edumgt/stock-coin-trade.git"
export APP_DIR="/opt/stock-coin-trade"
export APP_PORT="3000"                          # nginx 컨테이너 호스트 포트
export HEALTH_PATH="/api/stocks/list"

# 컨테이너 이미지 (ECR 리포지토리 이름)
export FE_REPO="stock-coin-trade-frontend"
export BE_REPO="stock-coin-trade-python-backend"

# 비밀 저장 경로 (백엔드의 AWS_SSM_PARAMETER_PREFIX 와 동일)
export SSM_PREFIX="/stock-coin-trade"

# RDS
export DB_INSTANCE_CLASS="db.t4g.micro"
export MARIADB_NAME="mockinv";        export MARIADB_USER="mockinv"
export PG_NAME="quant_research";      export PG_USER="quant"

# GitHub Actions OIDC 역할 (iam/setup/03_setup_github_oidc.sh 로 생성)
export GHA_ROLE_NAME="GitHubActionsECRRole"
