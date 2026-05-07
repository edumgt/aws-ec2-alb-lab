# ECS 실습 01 - Fargate 배포 실습 (FastAPI 샘플)

## 목표
- `BE-fastapi` 샘플 이미지를 ECR에 올리고 ECS Fargate로 배포합니다.

## 준비값
```bash
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
APP_NAME="be-fastapi-hello"
ECR_REPO="${APP_NAME}"
CLUSTER_NAME="study-fargate-cluster"
SERVICE_NAME="study-fargate-service"
TASK_FAMILY="study-fargate-task"
CONTAINER_NAME="api"
CONTAINER_PORT="8000"
SUBNET_1="subnet-xxxxxxxx"
SUBNET_2="subnet-yyyyyyyy"
SECURITY_GROUP="sg-xxxxxxxx"
```

## 0) 실행 역할 확인 (`ecsTaskExecutionRole`)
```bash
aws iam get-role --role-name ecsTaskExecutionRole >/dev/null 2>&1 || \
echo "ecsTaskExecutionRole이 없으면 AWS 공식 가이드로 먼저 생성하세요."
```

## 1) ECR 리포지토리 생성
```bash
aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${AWS_REGION}" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name "${ECR_REPO}" \
  --image-scanning-configuration scanOnPush=true \
  --region "${AWS_REGION}"
```

## 2) 로컬 이미지 빌드/푸시
```bash
cd ../BE-fastapi
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t ${APP_NAME}:v1 .
docker tag ${APP_NAME}:v1 ${ECR_URI}:v1
docker push ${ECR_URI}:v1
```

## 3) CloudWatch Logs 그룹 생성
```bash
aws logs create-log-group --log-group-name "/ecs/${SERVICE_NAME}" --region "${AWS_REGION}" 2>/dev/null || true
```

## 4) ECS 클러스터 생성
```bash
aws ecs create-cluster --cluster-name "${CLUSTER_NAME}" --region "${AWS_REGION}"
```

## 5) Task Definition 등록
```bash
cat > taskdef.json <<JSON
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "${CONTAINER_NAME}",
      "image": "${ECR_URI}:v1",
      "portMappings": [{"containerPort": ${CONTAINER_PORT}, "protocol": "tcp"}],
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${SERVICE_NAME}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
JSON

aws ecs register-task-definition --cli-input-json file://taskdef.json --region "${AWS_REGION}"
```

## 6) Service 생성
```bash
aws ecs create-service \
  --cluster "${CLUSTER_NAME}" \
  --service-name "${SERVICE_NAME}" \
  --task-definition "${TASK_FAMILY}" \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_1},${SUBNET_2}],securityGroups=[${SECURITY_GROUP}],assignPublicIp=ENABLED}" \
  --region "${AWS_REGION}"
```

## 7) 상태 확인
```bash
aws ecs describe-services --cluster "${CLUSTER_NAME}" --services "${SERVICE_NAME}" --region "${AWS_REGION}"
aws ecs list-tasks --cluster "${CLUSTER_NAME}" --service-name "${SERVICE_NAME}" --region "${AWS_REGION}"
```

## 삭제(정리)
```bash
aws ecs update-service --cluster "${CLUSTER_NAME}" --service "${SERVICE_NAME}" --desired-count 0 --region "${AWS_REGION}"
aws ecs delete-service --cluster "${CLUSTER_NAME}" --service "${SERVICE_NAME}" --force --region "${AWS_REGION}"
aws ecs delete-cluster --cluster "${CLUSTER_NAME}" --region "${AWS_REGION}"
```


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
