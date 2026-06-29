# ECS 실습 04 - Docker → ECR → ECS 배포 파이프라인

---

## 1. 전체 파이프라인 구조

```
로컬 / GitHub Actions
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  [1] docker build                                           │
│       ↓                                                      │
│  [2] aws ecr get-login-password | docker login (ECR 인증)  │
│       ↓                                                      │
│  [3] docker push → ECR (be-test:latest, fe-test:latest)    │
│       ↓                                                      │
│  [4-A] EC2 배포 (docker pull + docker run)                 │
│  [4-B] ECS 배포 (Task Definition 업데이트 + Service 재배포) │
└─────────────────────────────────────────────────────────────┘

ECR Registry: 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com
  ├── be-test:latest   (FastAPI BE)
  └── fe-test:latest   (Nginx FE)
```

---

## 2. Docker 이미지 빌드

### 2-1. BE (FastAPI)

```bash
cd BE-fastapi

# 빌드
docker build -t be-test:latest .

# 로컬 테스트
docker run -d --name fastapi-local -p 8000:8000 be-test:latest
curl http://localhost:8000/health   # {"status":"ok"}
curl http://localhost:8000/api/services | python3 -m json.tool

# 정리
docker stop fastapi-local && docker rm fastapi-local
```

### 2-2. FE (Nginx + AG Grid)

```bash
cd ag-grid-app

docker build -t fe-test:latest .

docker run -d --name fe-local -p 80:80 fe-test:latest
curl http://localhost/

docker stop fe-local && docker rm fe-local
```

---

## 3. ECR 인증 및 Push

### 3-1. ECR 로그인

```bash
ECR_REGISTRY="086015456585.dkr.ecr.ap-northeast-2.amazonaws.com"
REGION="ap-northeast-2"

aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"
# Login Succeeded
```

### 3-2. 이미지 태깅 및 Push

```bash
# BE
docker tag be-test:latest "$ECR_REGISTRY/be-test:latest"
docker push "$ECR_REGISTRY/be-test:latest"

# FE
docker tag fe-test:latest "$ECR_REGISTRY/fe-test:latest"
docker push "$ECR_REGISTRY/fe-test:latest"
```

### 3-3. ECR 리포지토리 이미지 확인

```bash
# 최신 이미지 목록
aws ecr list-images \
  --region "$REGION" \
  --repository-name be-test \
  --query 'imageIds[*].{Tag:imageTag,Digest:imageDigest}' \
  --output table

# 이미지 상세 (사이즈·Push 시간)
aws ecr describe-images \
  --region "$REGION" \
  --repository-name be-test \
  --query 'imageDetails[*].{Tag:imageTags[0],Size:imageSizeInBytes,Pushed:imagePushedAt}' \
  --output table
```

---

## 4-A. EC2 배포 (현재 방식)

GitHub Actions `deploy-ecr-ec2.yml` 의 EC2 배포 단계 동작:

```bash
# EC2 SSH 접속 후 실행 (SSH Action이 자동 수행)

# ECR 인증
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com

# 최신 이미지 Pull
docker pull 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest
docker pull 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/fe-test:latest

# BE 컨테이너 교체
docker stop fastapi-app 2>/dev/null || true
docker rm   fastapi-app 2>/dev/null || true
docker run -d --name fastapi-app --restart unless-stopped \
  -p 8000:8000 \
  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest

# FE 컨테이너 교체
docker stop fe-ag-grid 2>/dev/null || true
docker rm   fe-ag-grid 2>/dev/null || true
docker run -d --name fe-ag-grid --restart unless-stopped \
  -p 80:80 \
  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/fe-test:latest

docker ps
```

---

## 4-B. ECS Fargate 배포

### 4-B-1. Task Definition 등록

```bash
# task-definition.json 예시 (be-test)
cat > /tmp/be-task-def.json <<'EOF'
{
  "family": "be-fastapi-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::086015456585:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "be-fastapi",
      "image": "086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest",
      "portMappings": [
        { "containerPort": 8000, "protocol": "tcp" }
      ],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/be-fastapi",
          "awslogs-region": "ap-northeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      }
    }
  ]
}
EOF

# Task Definition 등록
aws ecs register-task-definition \
  --region ap-northeast-2 \
  --cli-input-json file:///tmp/be-task-def.json
```

### 4-B-2. CloudWatch 로그 그룹 생성

```bash
aws logs create-log-group \
  --log-group-name /ecs/be-fastapi \
  --region ap-northeast-2

aws logs create-log-group \
  --log-group-name /ecs/fe-ag-grid \
  --region ap-northeast-2
```

### 4-B-3. ECS 클러스터 생성

```bash
aws ecs create-cluster \
  --cluster-name study-fargate-cluster \
  --capacity-providers FARGATE FARGATE_SPOT \
  --region ap-northeast-2
```

### 4-B-4. ECS 서비스 생성 (ALB 연결)

```bash
aws ecs create-service \
  --cluster study-fargate-cluster \
  --service-name be-fastapi-service \
  --task-definition be-fastapi-task \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[<PRIVATE_SUBNET_1>,<PRIVATE_SUBNET_2>],
    securityGroups=[<ECS_SG_ID>],
    assignPublicIp=DISABLED
  }" \
  --load-balancers "targetGroupArn=<BE_TG_ARN>,containerName=be-fastapi,containerPort=8000" \
  --health-check-grace-period-seconds 60 \
  --region ap-northeast-2
```

### 4-B-5. ECS 서비스 업데이트 (새 이미지 배포)

```bash
# 새 Task Definition 버전을 자동으로 감지해서 서비스 재배포
aws ecs update-service \
  --cluster study-fargate-cluster \
  --service be-fastapi-service \
  --task-definition be-fastapi-task \
  --force-new-deployment \
  --region ap-northeast-2

# 배포 완료 대기
aws ecs wait services-stable \
  --cluster study-fargate-cluster \
  --services be-fastapi-service \
  --region ap-northeast-2
echo "배포 완료"
```

---

## 5. GitHub Actions CI/CD 파이프라인 (deploy-ecr-ec2.yml)

```
git push (BE-fastapi/** 또는 ag-grid-app/**)
          │
          ▼
┌─────────────────────────────────────────────────┐
│  build-push job                                  │
│                                                  │
│  1. checkout                                     │
│  2. aws-actions/configure-aws-credentials@v4    │
│     (Access Key: AWS_ACCESS_KEY_ID/SECRET)       │
│  3. aws-actions/amazon-ecr-login@v2             │
│  4. docker build + push → be-test:latest        │
│  5. docker build + push → fe-test:latest        │
└─────────────────────────────┬───────────────────┘
                              │ needs: build-push
                              ▼
┌─────────────────────────────────────────────────┐
│  deploy job (EC2)                                │
│                                                  │
│  appleboy/ssh-action@v1                         │
│  host: 43.203.255.251                           │
│                                                  │
│  script:                                         │
│    ECR 로그인 → pull be-test → pull fe-test     │
│    → docker run fastapi-app (:8000)              │
│    → docker run fe-ag-grid (:80)                 │
└─────────────────────────────────────────────────┘
```

**워크플로우 파일**: [.github/workflows/deploy-ecr-ec2.yml](../.github/workflows/deploy-ecr-ec2.yml)

**수동 ECS 배포**: [.github/workflows/deploy-ecs-aws-cli.yml](../.github/workflows/deploy-ecs-aws-cli.yml) (`workflow_dispatch` 전용)

---

## 6. ECS vs EC2 직접 배포 비교

| 항목 | EC2 직접 배포 (현재) | ECS Fargate |
|------|---------------------|-------------|
| 인프라 관리 | EC2 직접 관리 | AWS가 컨테이너 인프라 관리 |
| 스케일링 | 수동 또는 ASG | ECS Service auto scaling |
| 헬스체크 | docker ps / ALB TG | ECS Task 헬스체크 + ALB |
| 롤링 배포 | 수동 stop/run | `force-new-deployment` 자동 |
| 비용 | EC2 온디맨드 | vCPU·메모리 사용량 per-second |
| 복잡도 | 낮음 | 중간 (IAM·VPC 설정 필요) |
| 권장 상황 | 실습·단일 서버 | 프로덕션·멀티 AZ |

---

## 7. ECR 이미지 정리 (라이프사이클 정책)

```bash
# untagged 이미지 7일 후 자동 삭제
aws ecr put-lifecycle-policy \
  --region ap-northeast-2 \
  --repository-name be-test \
  --lifecycle-policy '{
    "rules": [
      {
        "rulePriority": 1,
        "description": "Remove untagged images older than 7 days",
        "selection": {
          "tagStatus": "untagged",
          "countType": "sinceImagePushed",
          "countUnit": "days",
          "countNumber": 7
        },
        "action": { "type": "expire" }
      },
      {
        "rulePriority": 2,
        "description": "Keep only last 5 tagged images",
        "selection": {
          "tagStatus": "tagged",
          "tagPrefixList": ["latest"],
          "countType": "imageCountMoreThan",
          "countNumber": 5
        },
        "action": { "type": "expire" }
      }
    ]
  }'
```

---

## 8. 빠른 점검 명령

```bash
# ECR 이미지 확인
aws ecr describe-images --region ap-northeast-2 --repository-name be-test \
  --query 'imageDetails[*].{Tag:imageTags[0],Pushed:imagePushedAt}' --output table

# ECS 서비스 상태
aws ecs describe-services \
  --cluster study-fargate-cluster \
  --services be-fastapi-service \
  --region ap-northeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployments:deployments[0].status}'

# ECS Task 로그 (최근 20줄)
TASK_ARN=$(aws ecs list-tasks --cluster study-fargate-cluster --service-name be-fastapi-service \
  --query 'taskArns[0]' --output text --region ap-northeast-2)
aws logs tail /ecs/be-fastapi --follow --since 5m

# EC2 컨테이너 상태 확인 (SSH)
# docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
