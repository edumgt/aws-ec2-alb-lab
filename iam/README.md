# AWS IAM 구성 가이드

이 프로젝트에서 사용하는 IAM 리소스 전체를 정리합니다.

```
iam/
├── policies/                      # 권한 정책 (Permission Policy) JSON
│   ├── ecr-push-policy.json       # info-pro 유저용 — ECR push/pull
│   ├── ec2-ecr-pull-policy.json   # EC2 인스턴스 역할용 — ECR pull 전용
│   ├── github-oidc-deploy-policy.json  # GitHub OIDC Role용 — ECR push/pull
│   ├── ecs-task-execution-policy.json  # ECS Task Execution Role — ECR + CW + SSM
│   ├── stock-platform-ec2-app-policy.json       # [주식 플랫폼] 앱 EC2 — SSM 읽기 + ECR pull (플레이스홀더)
│   ├── stock-platform-lambda-policy.json        # [주식 플랫폼] 시세 수집 Lambda — SSM 읽기
│   └── stock-platform-github-deploy-policy.json # [주식 플랫폼] GitHub OIDC 역할 추가 권한 (S3/CF/Lambda/SSM RunCommand)
├── trust-policies/                # 신뢰 관계 (Trust Policy) JSON
│   ├── github-oidc-trust.json     # GitHub Actions OIDC → AssumeRoleWithWebIdentity
│   ├── ec2-instance-trust.json    # EC2 서비스 → AssumeRole
│   ├── ecs-task-execution-trust.json  # ECS Tasks 서비스 → AssumeRole
│   ├── lambda-trust.json          # [주식 플랫폼] Lambda 서비스 → AssumeRole
│   └── scheduler-trust.json       # [주식 플랫폼] EventBridge Scheduler → AssumeRole
└── setup/                         # IAM 리소스 생성 셸 스크립트
    ├── 01_setup_iam_user_policy.sh
    ├── 02_setup_ec2_role.sh
    ├── 03_setup_github_oidc.sh
    ├── 04_setup_ecs_role.sh
    └── 05_setup_stock_platform_roles.sh   # [주식 플랫폼] EC2/Lambda/Scheduler 역할 3종 (--delete 지원)
```

---

## 1. IAM 개요 — 이 프로젝트의 인증 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Actions                                                  │
│  (deploy-ecr-ec2.yml)                                           │
│                                                                  │
│  방식 A: Access Key  ──────────────────────────► ECR Push/Pull  │
│  (현재 사용)          secrets.AWS_ACCESS_KEY_ID                  │
│                       secrets.AWS_SECRET_ACCESS_KEY             │
│                                                                  │
│  방식 B: OIDC        ─── AssumeRoleWithWebIdentity ──► Role    │
│  (권장, 03번 스크립트)   GitHubActionsECRRole                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  EC2 (43.203.255.251)                                           │
│  방식 A: Access Key 직접 설정 (현재 사용)                        │
│         ~/.aws/credentials                                       │
│                                                                  │
│  방식 B: Instance Profile (권장, 02번 스크립트)                  │
│         EC2ECRPullRole → ECR Pull Only                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ECS Fargate (deploy-ecs-aws-cli.yml)                           │
│  ecsTaskExecutionRole ─────────────────────────► ECR Pull       │
│                                                ► CloudWatch Logs│
│                                                ► SSM Parameters │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. IAM 주요 개념

### 2-1. 정책(Policy) 종류

| 구분 | 설명 | 이 프로젝트에서 |
|------|------|----------------|
| **AWS 관리형 정책** | AWS가 제공·관리 | `AmazonECSTaskExecutionRolePolicy` |
| **고객 관리형 정책** | 직접 생성·관리 | `ECRPushPolicy`, `EC2ECRPullPolicy` 등 |
| **인라인 정책** | 특정 엔티티에만 종속 | 사용 안 함 (관리 어려움) |

### 2-2. 신뢰 관계(Trust Policy)

Role이 **누구에게 AssumeRole을 허용하는지** 정의합니다.

```json
// EC2 인스턴스 신뢰 관계 예시
{
  "Principal": { "Service": "ec2.amazonaws.com" },
  "Action": "sts:AssumeRole"
}

// GitHub OIDC 신뢰 관계 예시
{
  "Principal": { "Federated": "arn:aws:iam::086015456585:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringLike": { "token.actions.githubusercontent.com:sub": "repo:edumgt/aws-ec2-alb-lab:ref:refs/heads/main" }
  }
}
```

### 2-3. 권한 경계(Permission Boundary)

Role이나 User에 부여된 최대 권한 상한선. 이 프로젝트에서는 별도 설정 없음.

---

## 3. IAM 리소스 목록

### 3-1. IAM User

| User | 용도 | 연결 정책 |
|------|------|-----------|
| `info-pro` | GitHub Actions CI/CD (Access Key 방식) | `ECRPushPolicy` (커스텀) |

**설정 스크립트**: `setup/01_setup_iam_user_policy.sh`

```bash
bash iam/setup/01_setup_iam_user_policy.sh
```

---

### 3-2. IAM Role — EC2 Instance Profile

| 항목 | 값 |
|------|----|
| Role 이름 | `EC2ECRPullRole` |
| Instance Profile | `EC2ECRPullProfile` |
| 신뢰 주체 | `ec2.amazonaws.com` |
| 권한 | ECR pull (`be-test`, `fe-test`) |

**신뢰 관계** (`trust-policies/ec2-instance-trust.json`):
```json
{
  "Principal": { "Service": "ec2.amazonaws.com" },
  "Action": "sts:AssumeRole"
}
```

**설정 스크립트**: `setup/02_setup_ec2_role.sh`

```bash
bash iam/setup/02_setup_ec2_role.sh
```

> 설정 후 EC2에서 `aws ecr get-login-password` 명령 시 자격증명이 자동으로 인스턴스 메타데이터(IMDS)에서 조회됩니다.

---

### 3-3. IAM Role — GitHub Actions OIDC

OIDC(OpenID Connect)를 사용하면 장기 Access Key 없이 GitHub Actions에서 AWS에 인증할 수 있습니다.

#### OIDC 동작 원리

```
GitHub Actions Runner
  │
  ├─ 1. GitHub OIDC 토큰 발급 (JWT)
  │       sub: "repo:edumgt/aws-ec2-alb-lab:ref:refs/heads/main"
  │       aud: "sts.amazonaws.com"
  │
  ├─ 2. AWS STS AssumeRoleWithWebIdentity 호출
  │       → OIDC Provider가 JWT 서명 검증
  │       → Condition(sub, aud) 일치 확인
  │
  └─ 3. 임시 자격증명 반환 (Access Key + Session Token, 1시간 유효)
         → ECR Login, Docker Build/Push 수행
```

| 항목 | 값 |
|------|----|
| OIDC Provider | `token.actions.githubusercontent.com` |
| Role 이름 | `GitHubActionsECRRole` |
| 신뢰 주체 | `token.actions.githubusercontent.com` (Federated) |
| Condition | `sub: repo:edumgt/aws-ec2-alb-lab:ref:refs/heads/main` |
| 권한 | ECR push/pull (`be-test`, `fe-test`) |

**설정 스크립트**: `setup/03_setup_github_oidc.sh`

```bash
bash iam/setup/03_setup_github_oidc.sh
```

**OIDC 방식으로 워크플로우 전환 시** (`deploy-ecr-ec2.yml` 수정):
```yaml
permissions:
  id-token: write   # OIDC 토큰 발급 권한 필수
  contents: read

- name: AWS 자격 증명 설정
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
    aws-region: ap-northeast-2
```

GitHub Secret 추가:
- `AWS_ROLE_TO_ASSUME` : `arn:aws:iam::086015456585:role/GitHubActionsECRRole`

---

### 3-4. IAM Role — ECS Task Execution

| 항목 | 값 |
|------|----|
| Role 이름 | `ecsTaskExecutionRole` |
| 신뢰 주체 | `ecs-tasks.amazonaws.com` |
| AWS 관리형 정책 | `AmazonECSTaskExecutionRolePolicy` |
| 커스텀 정책 | `ECSTaskExecutionCustomPolicy` (SSM, Secrets Manager, CloudWatch) |

**설정 스크립트**: `setup/04_setup_ecs_role.sh`

```bash
bash iam/setup/04_setup_ecs_role.sh
```

---

## 4. 정책(Permission Policy) 상세

### ecr-push-policy.json (info-pro 유저 / GitHub OIDC Role)

```
ECRAuth     : ecr:GetAuthorizationToken          (Resource: *)
ECRPushPull : ecr:BatchCheckLayerAvailability    (Resource: be-test, fe-test)
              ecr:PutImage
              ecr:InitiateLayerUpload
              ecr:UploadLayerPart
              ecr:CompleteLayerUpload
              ecr:GetDownloadUrlForLayer
              ecr:BatchGetImage
              ecr:DescribeRepositories
              ecr:CreateRepository
              ecr:ListImages
              ecr:DescribeImages
```

> `ecr:GetAuthorizationToken`은 리포지토리 ARN이 아닌 `*`에만 적용됩니다 (AWS 제약).

### ec2-ecr-pull-policy.json (EC2 Instance Role)

push 권한 없이 pull만 허용하여 최소 권한(Least Privilege) 원칙 적용:

```
ECRAuth : ecr:GetAuthorizationToken   (Resource: *)
ECRPull : ecr:BatchCheckLayerAvailability
          ecr:GetDownloadUrlForLayer
          ecr:BatchGetImage
          ecr:DescribeRepositories
          ecr:ListImages
          ecr:DescribeImages
```

---

## 5. CLI로 정책 직접 적용하기

### IAM User에 정책 연결
```bash
# 정책 생성
aws iam create-policy \
  --policy-name ECRPushPolicy \
  --policy-document file://iam/policies/ecr-push-policy.json

# User에 연결
aws iam attach-user-policy \
  --user-name info-pro \
  --policy-arn arn:aws:iam::086015456585:policy/ECRPushPolicy
```

### IAM Role 생성 및 정책 연결
```bash
# Role 생성 (신뢰 관계 포함)
aws iam create-role \
  --role-name EC2ECRPullRole \
  --assume-role-policy-document file://iam/trust-policies/ec2-instance-trust.json

# 정책 연결
aws iam attach-role-policy \
  --role-name EC2ECRPullRole \
  --policy-arn arn:aws:iam::086015456585:policy/EC2ECRPullPolicy
```

### 현재 연결된 정책 확인
```bash
# User 정책
aws iam list-attached-user-policies --user-name info-pro

# Role 정책
aws iam list-attached-role-policies --role-name EC2ECRPullRole

# 정책 JSON 내용 확인
aws iam get-policy-version \
  --policy-arn arn:aws:iam::086015456585:policy/ECRPushPolicy \
  --version-id v1
```

---

## 6. Access Key vs OIDC 비교

| 항목 | Access Key (현재) | OIDC (권장) |
|------|-------------------|-------------|
| 자격증명 수명 | 영구 (만료 없음) | 임시 (1시간) |
| Secret 관리 | GitHub Secret에 저장 | Secret 불필요 |
| 보안 수준 | 낮음 (유출 시 위험) | 높음 |
| 설정 복잡도 | 낮음 | 중간 |
| 자격증명 교체 | 수동 | 자동 |
| 권장 여부 | 실습·개발 환경 | 프로덕션 환경 |

---

## 7. 주식투자 웹앱 플랫폼용 IAM 구성

루트 README 의 "AWS 기반 주식투자 웹앱 플랫폼 시스템 구성" 과 `deploy/stock-platform/` 스크립트가 사용하는 역할입니다.  
정책 JSON 은 계정·리전에 독립적으로 두기 위해 `__ACCOUNT_ID__`, `__REGION__`, `__SSM_PREFIX__`, `__APP__` 플레이스홀더를 쓰며, `05_setup_stock_platform_roles.sh` 가 실행 시 치환합니다.

### 7-1. 인증 흐름

```
GitHub Actions ── OIDC ──► GitHubActionsECRRole
                              ├─ (기존) ECR push: be-test, fe-test
                              └─ (+ 인라인 ${APP}-platform-deploy)
                                   S3 sync → CloudFront invalidation
                                   ECR push: stock-coin-trade-*
                                   Lambda UpdateFunctionCode
                                   SSM SendCommand → 앱 EC2 (SSH 키 불필요)

앱 EC2 ── 인스턴스 프로파일 ${APP}-ec2-profile ──► ${APP}-ec2-role
                              ├─ SSM GetParameter*  : /stock-coin-trade/*  (증권사 키, DB URL)
                              ├─ KMS Decrypt        : ssm 경유만
                              ├─ ECR pull           : stock-coin-trade-*
                              ├─ AmazonSSMManagedInstanceCore (Session Manager, Run Command)
                              └─ CloudWatchAgentServerPolicy

EventBridge Scheduler ── ${APP}-scheduler-role ──► lambda:InvokeFunction (${APP}-*)
Lambda ── ${APP}-lambda-role ──► CloudWatch Logs + SSM GetParameter* (/stock-coin-trade/*)
```

### 7-2. 역할 목록

| 역할 | 신뢰 주체 | 권한 | 정책 파일 |
|---|---|---|---|
| `${APP}-ec2-role` (+ `${APP}-ec2-profile`) | `ec2.amazonaws.com` | SSM 읽기, KMS 복호화(ssm 경유), ECR pull, SSM Core, CW Agent | `policies/stock-platform-ec2-app-policy.json` |
| `${APP}-lambda-role` | `lambda.amazonaws.com` | 기본 로그 + SSM 읽기 | `policies/stock-platform-lambda-policy.json` |
| `${APP}-scheduler-role` | `scheduler.amazonaws.com` | `lambda:InvokeFunction` (`${APP}-*`) | 인라인 (스크립트 내 생성) |
| `GitHubActionsECRRole` (기존) | GitHub OIDC | + S3/CloudFront/Lambda/ECR/SSM RunCommand | `policies/stock-platform-github-deploy-policy.json` |

### 7-3. 실행

```bash
# 생성 (APP, SSM_PREFIX, AWS_REGION 환경변수로 조정 가능)
APP=stock-trade SSM_PREFIX=/stock-coin-trade bash iam/setup/05_setup_stock_platform_roles.sh

# 기존 EC2 에 프로파일 붙이기
aws ec2 associate-iam-instance-profile --instance-id <INSTANCE_ID> --iam-instance-profile Name=stock-trade-ec2-profile

# GitHub OIDC 역할 권한 확장 (deploy/stock-platform/09_github_actions.sh 가 수행)
sed -e "s|__ACCOUNT_ID__|$ACCOUNT_ID|g" -e "s|__REGION__|ap-northeast-2|g" -e "s|__APP__|stock-trade|g" \
    -e "s|__FE_BUCKET__|$FE_BUCKET|g" -e "s|__DIST_ID__|$DIST_ID|g" -e "s|__INSTANCE_ID__|$INSTANCE_ID|g" \
    iam/policies/stock-platform-github-deploy-policy.json > /tmp/gha.json
aws iam put-role-policy --role-name GitHubActionsECRRole --policy-name stock-trade-platform-deploy --policy-document file:///tmp/gha.json

# 삭제
bash iam/setup/05_setup_stock_platform_roles.sh --delete
```

### 7-4. 최소 권한 원칙 적용 포인트

- SSM 파라미터는 `${SSM_PREFIX}/*` 경로에만 접근. `kms:Decrypt` 는 `kms:ViaService = ssm.<region>.amazonaws.com` 조건으로 SSM 경유만 허용.
- 앱 EC2 는 ECR **pull 만**, `stock-coin-trade-*` 리포지토리만.
- GitHub 역할의 `ssm:SendCommand` 는 특정 인스턴스 ARN + `AWS-RunShellScript` 문서로 제한 → SSH 프라이빗 키를 GitHub Secret 에 두지 않아도 됨.
- Scheduler 역할은 `${APP}-*` 함수만 호출 가능.
