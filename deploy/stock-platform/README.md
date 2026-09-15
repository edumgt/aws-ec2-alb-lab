# 주식투자 웹앱 플랫폼 — AWS CLI 구성 스크립트

루트 README 의 **"AWS 기반 주식투자 웹앱 플랫폼 시스템 구성 (AWS CLI)"** 섹션의 Phase A~H 를 그대로 실행 가능한 스크립트로 옮긴 것입니다.  
각 스크립트는 생성한 리소스 ID 를 `.state` 파일에 기록하므로, 순서대로 실행하면 이전 단계의 값을 자동으로 이어받습니다. 중간에 실패하면 같은 스크립트를 다시 실행해도 이미 만든 리소스는 건너뜁니다.

```
deploy/stock-platform/
├── env.example.sh          # 공통 변수 → env.sh 로 복사해 수정 (git 제외)
├── 00_common.sh            # 로더: env.sh + .state, save/need 헬퍼
├── 01_network.sh           # A. VPC·서브넷 2AZ·IGW·SG 3계층
├── 02_secrets_iam.sh       # B. SSM SecureString + EC2/Lambda/Scheduler 역할
├── 03_rds.sh               # C. RDS MariaDB + PostgreSQL
├── 04_ecr_acm_alb.sh       # D-1~3. ECR, ACM(서울/us-east-1), ALB
├── 05_app_ec2.sh           # D-4. 앱 EC2 (User Data → compose 기동) + 타깃 등록
├── 06_frontend_cdn.sh      # E. S3 + CloudFront(오리진 2개) + Route 53
├── 07_serverless.sh        # F. Lambda + EventBridge Scheduler + API Gateway
├── 08_observability.sh     # G. SNS·알람 5종·WAF·Budgets
├── 09_github_actions.sh    # H. OIDC 역할 권한 + gh secrets/variables
├── 99_cleanup.sh           # 생성 역순 삭제
├── templates/              # CloudFront 배포 JSON, WAF 규칙
└── lambda/collector/       # 시세 수집 Lambda 골격
```

## 실행 순서

```bash
cp deploy/stock-platform/env.example.sh deploy/stock-platform/env.sh
vi deploy/stock-platform/env.sh            # DOMAIN_NAME, ALERT_EMAIL 등 수정

# 증권사 키 파일이 있으면 02 단계에서 SSM 에 함께 등록
export KIS_KEY_FILE=~/keys/kis.key KB_KEY_FILE=~/keys/kb.key ALPACA_KEY_FILE=~/keys/al.key

bash deploy/stock-platform/01_network.sh
bash deploy/stock-platform/02_secrets_iam.sh
bash deploy/stock-platform/03_rds.sh          # 10~15분 소요
bash deploy/stock-platform/04_ecr_acm_alb.sh  # ACM DNS 검증 대기 포함
# → 이 시점에 ECR 에 이미지가 있어야 05 가 기동됩니다 (stock-coin-trade 에서 scripts/ecr-push.sh 또는 워크플로우)
bash deploy/stock-platform/05_app_ec2.sh
bash deploy/stock-platform/06_frontend_cdn.sh # FRONTEND_DIR=<정적 파일 경로> 지정 가능
bash deploy/stock-platform/07_serverless.sh
bash deploy/stock-platform/08_observability.sh
bash deploy/stock-platform/09_github_actions.sh
```

현재까지 만들어진 값 확인: `cat deploy/stock-platform/.state`

## 전제 조건

- 루트 README 로드맵 0~3단계 완료 (`aws sts get-caller-identity` 성공)
- Route 53 에 `DOMAIN_NAME` 호스팅 존 존재
- `iam/setup/03_setup_github_oidc.sh` 로 GitHub OIDC 역할 생성 (09 단계에서 권한 확장)
- 로컬 도구: `aws`, `jq`, `zip`, `openssl`, `gh`(09 단계만)

## 이 저장소 샘플로 먼저 검증하기

실제 주식 앱 이미지 없이 구조만 확인하려면:

- 프론트엔드: `06_frontend_cdn.sh` 기본값이 [`ag-grid-app/`](../../ag-grid-app/) 을 업로드합니다.
- 백엔드: [`BE-fastapi`](../../BE-fastapi/) 가 `/api/stocks/list` 헬스체크 경로를 제공하므로, `env.sh` 에서 `APP_PORT=8000`, `BE_REPO=be-test` 로 바꾸고 `05_app_ec2.sh` 의 compose 대신 `docker run -p 8000:8000` 으로 기동하면 ALB 헬스체크가 통과합니다.

## 관련 문서

| 주제 | 문서 |
|---|---|
| 전체 설계·명령 설명 | 루트 README → "AWS 기반 주식투자 웹앱 플랫폼 시스템 구성" |
| IAM 역할·정책 파일 | [iam/README.md](../../iam/README.md) §7 |
| 배포 워크플로우 | [.github/workflows/deploy-stock-platform.yml](../../.github/workflows/deploy-stock-platform.yml) |
| 백엔드를 Fargate 로 옮길 때 | [ECS/005_stock_platform_fargate.md](../../ECS/005_stock_platform_fargate.md) |
