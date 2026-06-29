# 배포 가이드 — aws-ec2-alb-lab

이 디렉토리는 **BE-fastapi** 와 **ag-grid-app(FE)** 를 다양한 방식으로 배포하는 스크립트와 설정을 모읍니다.

---

## 배포 방식 선택 가이드

```
                    ┌──────────────────────────────────────────────────────┐
                    │  이미지 빌드 · ECR Push                              │
                    │  (ecr-push-be.sh — 로컬 수동)                        │
                    └────────────────────┬─────────────────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────────────────┐
                    │  ECR Registry                                         │
                    │  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com   │
                    │  ├── be-test:latest   (FastAPI BE :8000)              │
                    │  └── fe-test:latest   (Nginx FE  :80)                │
                    └──────────┬───────────────────┬───────────────────────┘
                               │                   │
              ┌────────────────▼──────┐   ┌────────▼───────────────────────┐
              │  방식 A: EC2 직접      │   │  방식 B: ECS Fargate            │
              │  deploy-ecr-ec2.yml  │   │  deploy-ecs-aws-cli.yml        │
              │  (Git push 자동)      │   │  (workflow_dispatch 수동)       │
              │                      │   │                                  │
              │  docker pull+run      │   │  Task Definition 등록           │
              │  EC2: 43.203.255.251  │   │  ECS Service 업데이트           │
              └──────────────────────┘   └──────────────────────────────────┘
```

| 방식 | 트리거 | 대상 | 파일 |
|------|--------|------|------|
| A-1. 로컬 ECR Push | 수동 | ECR | `deploy/ecr-push-be.sh` |
| A-2. EC2 자동 배포 | `git push` (main) | EC2 → Docker | `.github/workflows/deploy-ecr-ec2.yml` |
| A-3. EC2 수동 적용 | EC2 SSH 접속 후 | EC2 → Docker | `deploy/shell/ec2-apply.sh` |
| B-1. ECS Shell | 수동 | ECS Fargate | `deploy/shell/deploy_ecs_cli.sh` |
| B-2. ECS Ansible | 수동 | ECS Fargate | `deploy/ansible/deploy_ecs_cli.yml` |
| B-3. ECS GitHub Actions | `workflow_dispatch` | ECS Fargate | `.github/workflows/deploy-ecs-aws-cli.yml` |

---

## 사전 준비 — IAM 및 자격증명

### GitHub Actions (방식 A-2, B-3)

GitHub Secrets에 다음을 등록합니다.

```
AWS_ACCESS_KEY_ID     : info-pro IAM 유저 Access Key ID
AWS_SECRET_ACCESS_KEY : info-pro IAM 유저 Secret Access Key
EC2_SSH_KEY           : ~/.ssh/kdy-test.pem 전체 내용 (개행 포함)
```

IAM 유저 `info-pro` 에 필요한 정책이 없다면:
```bash
bash iam/setup/01_setup_iam_user_policy.sh
```

OIDC 방식으로 전환하려면 (Access Key 불필요):
```bash
bash iam/setup/03_setup_github_oidc.sh
# → Secret AWS_ROLE_TO_ASSUME 등록 후 workflow에서 role-to-assume 방식으로 교체
```

자세한 내용 → [iam/README.md](../iam/README.md)

### 로컬 스크립트 (방식 A-1, B-1, B-2)

```bash
# info-pro 키로 구성 (info-pro_accessKeys.csv 참조)
aws configure
# AWS Access Key ID     : [info-pro Access Key]
# AWS Secret Access Key : [info-pro Secret Key]
# Default region        : ap-northeast-2
```

### EC2 Instance Profile (EC2에서 직접 실행 시)

EC2가 IAM Instance Profile 없이 `aws ecr get-login-password` 를 사용하려면
`~/.aws/credentials` 를 직접 설정해야 합니다:
```bash
aws configure  # EC2 SSH 접속 후 실행
```

Instance Profile 방식(권장)으로 전환하려면:
```bash
bash iam/setup/02_setup_ec2_role.sh
```

---

## 방식 A-1. 로컬 수동 ECR Push

**파일**: `deploy/ecr-push-be.sh` (또는 루트의 `ecr-push-be.sh`)

```bash
# 기본 (latest 태그)
bash deploy/ecr-push-be.sh

# 특정 태그
IMAGE_TAG=v1.2.0 bash deploy/ecr-push-be.sh
```

수행 내용:
1. ECR 로그인 (`aws ecr get-login-password`)
2. `BE-fastapi/` → 빌드 → `be-test:latest` 푸시
3. `ag-grid-app/` → 빌드 → `fe-test:latest` 푸시

---

## 방식 A-2. GitHub Actions — ECR + EC2 자동 배포

**파일**: `.github/workflows/deploy-ecr-ec2.yml`

`main` 브랜치에 `BE-fastapi/**` 또는 `ag-grid-app/**` 파일 변경 후 push 하면 자동 실행됩니다.

```
git push origin main
→ build-push job : ECR 로그인 → be-test:latest, fe-test:latest 빌드 및 push
→ deploy job     : SSH(43.203.255.251) → pull → docker run (포트 8000, 80)
```

수동 실행 (GitHub 콘솔 또는 CLI):
```bash
gh workflow run deploy-ecr-ec2.yml
```

---

## 방식 A-3. EC2 수동 적용

**파일**: `deploy/shell/ec2-apply.sh`

EC2에 SSH 접속하지 않고 로컬에서 최신 ECR 이미지를 EC2에 적용할 때 사용합니다.

```bash
# 기본 (환경변수 기반)
EC2_HOST=43.203.255.251 \
EC2_KEY=~/.ssh/kdy-test.pem \
bash deploy/shell/ec2-apply.sh
```

EC2 직접 접속 후 실행도 가능:
```bash
ssh -i ~/.ssh/kdy-test.pem ubuntu@43.203.255.251
# 접속 후:
bash /home/ubuntu/aws-ec2-alb-lab/deploy/shell/ec2-apply.sh
```

---

## 방식 B. ECS Fargate 배포 (3가지 선택)

### 환경변수 설정 (공통)

```bash
cp deploy/shell/deploy.env.example .env.deploy
# 필요시 값 수정 후:
set -a && source .env.deploy && set +a
```

### B-1. Shell Script

```bash
set -a && source .env.deploy && set +a
bash deploy/shell/deploy_ecs_cli.sh
```

7단계 흐름: ECR 리포 확인 → ECR 로그인 → 빌드+Push → Task Definition → ECS 업데이트 → 안정화 대기

### B-2. Ansible

```bash
# 설치 확인
ansible --version
aws --version
docker --version

ansible-playbook \
  -i deploy/ansible/inventory.ini \
  deploy/ansible/deploy_ecs_cli.yml
```

변수 편집: `deploy/ansible/group_vars/all.yml`

### B-3. GitHub Actions (수동 트리거)

```bash
gh workflow run deploy-ecs-aws-cli.yml
```

워크플로우 파일: `.github/workflows/deploy-ecs-aws-cli.yml`

ECS 관련 사전 작업:
```bash
# ECS Task Execution Role 생성
bash iam/setup/04_setup_ecs_role.sh

# CloudWatch 로그 그룹 생성
aws logs create-log-group --log-group-name /ecs/be-fastapi-service --region ap-northeast-2
aws logs create-log-group --log-group-name /ecs/fe-ag-grid-service  --region ap-northeast-2

# ECS 클러스터 생성 (없는 경우)
aws ecs create-cluster --cluster-name study-fargate-cluster --region ap-northeast-2
```

자세한 Task Definition 예시 → [ECS/004_docker_ecr_ecs_pipeline.md](../ECS/004_docker_ecr_ecs_pipeline.md)

---

## EC2 인스턴스 신규 생성

Docker 및 ECR 인증이 구성된 EC2 인스턴스를 처음부터 만들 때:

```bash
# Ubuntu 22.04 + Docker 설치 + ECR 이미지 pull
bash deploy/create-ec2-docker.sh
```

생성 내용:
- Ubuntu 22.04 LTS AMI (최신 자동 조회)
- 기존 VPC/서브넷 자동 감지 (없으면 생성)
- User Data로 Docker 설치 및 이미지 pull
- 키페어: `kdy-test`

AMI 저장 및 재사용 방법 → [EC2/010_ami_guide.md](../EC2/010_ami_guide.md)

---

## 참고 리소스

| 주제 | 문서 |
|------|------|
| Docker → ECR → ECS 전체 흐름 | [ECS/004_docker_ecr_ecs_pipeline.md](../ECS/004_docker_ecr_ecs_pipeline.md) |
| IAM 정책·OIDC·설정 스크립트 | [iam/README.md](../iam/README.md) |
| LB 종류·타겟그룹·오토스케일러 | [LB/002_lb_types_targetgroup_autoscaling.md](../LB/002_lb_types_targetgroup_autoscaling.md) |
| AMI 저장·검색·사용 | [EC2/010_ami_guide.md](../EC2/010_ami_guide.md) |
| ALB 설정 기초 | [LB/001_alb_settings_lab.md](../LB/001_alb_settings_lab.md) |
| ECS Fargate 핸즈온 | [ECS/001_fargate_hands_on.md](../ECS/001_fargate_hands_on.md) |

---

## ECR 레지스트리 정보

```
Registry  : 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com
BE 리포   : 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest
FE 리포   : 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/fe-test:latest
IAM 유저  : info-pro (Access Key 방식 CI/CD)
EC2 호스트: 43.203.255.251 (ubuntu@)
```

---

## 자주 사용하는 명령 모음

```bash
# ECR 이미지 확인
aws ecr describe-images --region ap-northeast-2 --repository-name be-test \
  --query 'imageDetails[*].{Tag:imageTags[0],Pushed:imagePushedAt}' --output table

# EC2 컨테이너 상태
ssh -i ~/.ssh/kdy-test.pem ubuntu@43.203.255.251 \
  "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# BE 헬스체크
curl http://43.203.255.251:8000/health

# FE 접속 확인
curl -s -o /dev/null -w "%{http_code}" http://43.203.255.251/

# GitHub Actions 워크플로우 상태
gh run list --workflow deploy-ecr-ec2.yml --limit 5

# ECS 서비스 상태
aws ecs describe-services \
  --cluster study-fargate-cluster \
  --services be-fastapi-service \
  --region ap-northeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

---

## 리소스 정리 (실습 종료)

```bash
# EC2 컨테이너 중지
ssh -i ~/.ssh/kdy-test.pem ubuntu@43.203.255.251 \
  "docker stop fastapi-app fe-ag-grid && docker rm fastapi-app fe-ag-grid"

# ECS 서비스 중지 (desired=0)
aws ecs update-service \
  --cluster study-fargate-cluster \
  --service be-fastapi-service \
  --desired-count 0 \
  --region ap-northeast-2

# ECR 이미지 삭제
aws ecr batch-delete-image \
  --region ap-northeast-2 \
  --repository-name be-test \
  --image-ids imageTag=latest
aws ecr batch-delete-image \
  --region ap-northeast-2 \
  --repository-name fe-test \
  --image-ids imageTag=latest
```
