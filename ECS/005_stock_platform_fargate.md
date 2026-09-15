# ECS 실습 05 - 주식투자 플랫폼 백엔드를 Fargate 로 전환 (Stage 4)

루트 README 의 플랫폼 구성(Stage 1~3) 은 단일 EC2 에서 Docker Compose 로 백엔드를 실행합니다.  
이 문서는 **네트워크·RDS·SSM·ALB 는 그대로 두고 백엔드 컨테이너만 ECS Fargate 로 옮기는** 절차입니다. `deploy/stock-platform/.state` 의 값(VPC, 서브넷, SG, ALB, TG)을 재사용합니다.

---

## 1. 전환 전/후 구조

```
[전환 전] CloudFront /api/* ─► ALB ─► TG(instance:3000) ─► EC2 ─► nginx ─► flask
[전환 후] CloudFront /api/* ─► ALB ─► TG(ip:5000)       ─► Fargate Task(flask)  ×N (오토스케일링)
                                                             │ Task Role: SSM 읽기
                                                             └─► RDS MariaDB / PostgreSQL (DB SG 가 Task SG 허용)
```

정적 프론트엔드는 이미 S3 + CloudFront 이므로 nginx 컨테이너는 불필요해집니다.

---

## 2. 사전 준비

```bash
source deploy/stock-platform/00_common.sh      # env.sh + .state 로드
bash iam/setup/04_setup_ecs_role.sh            # ecsTaskExecutionRole (ECR pull + 로그 + SSM 파라미터 주입)

# Task Role: 앱 컨테이너가 런타임에 SSM 을 읽을 권한 (EC2 역할과 동일 정책 재사용)
aws iam create-role --role-name ${APP}-task-role \
  --assume-role-policy-document file://iam/trust-policies/ecs-task-execution-trust.json
aws iam put-role-policy --role-name ${APP}-task-role --policy-name app-access \
  --policy-document "$(sed -e "s|__ACCOUNT_ID__|$ACCOUNT_ID|g" -e "s|__REGION__|$AWS_REGION|g" -e "s|__SSM_PREFIX__|$SSM_PREFIX|g" iam/policies/stock-platform-ec2-app-policy.json)"

# Task 보안그룹: ALB SG 에서 5000 만 허용, DB SG 에 Task SG 추가
SG_TASK=$(aws ec2 create-security-group --group-name ${APP}-task-sg --description "fargate task" --vpc-id "$VPC_ID" --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id "$SG_TASK" --ip-permissions "IpProtocol=tcp,FromPort=5000,ToPort=5000,UserIdGroupPairs=[{GroupId=$SG_ALB}]"
aws ec2 authorize-security-group-ingress --group-id "$SG_DB" --ip-permissions \
  "IpProtocol=tcp,FromPort=3306,ToPort=3306,UserIdGroupPairs=[{GroupId=$SG_TASK}]" \
  "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_TASK}]"

aws logs create-log-group --log-group-name /ecs/${APP}-backend || true
aws ecs create-cluster --cluster-name ${APP}-cluster --capacity-providers FARGATE FARGATE_SPOT >/dev/null
```

> Fargate Task 는 퍼블릭 서브넷에 `assignPublicIp=ENABLED` 로 두면 NAT 없이 ECR/SSM/외부 시세 API 에 접근할 수 있습니다. 프라이빗 서브넷에 두려면 NAT Gateway 또는 ECR/SSM/Logs VPC 엔드포인트가 필요합니다.

---

## 3. Task Definition (SSM 파라미터를 환경변수로 주입)

```bash
cat > /tmp/taskdef.json <<JSON
{
  "family": "${APP}-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512", "memory": "1024",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${APP}-task-role",
  "containerDefinitions": [{
    "name": "backend",
    "image": "${ECR_REGISTRY}/${BE_REPO}:latest",
    "portMappings": [{ "containerPort": 5000, "protocol": "tcp" }],
    "essential": true,
    "environment": [
      { "name": "AWS_REGION", "value": "${AWS_REGION}" },
      { "name": "AWS_SSM_PARAMETER_PREFIX", "value": "${SSM_PREFIX}" }
    ],
    "secrets": [
      { "name": "DATABASE_URL",       "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/db/mariadb/url" },
      { "name": "QUANT_DATABASE_URL", "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/db/postgres/url" },
      { "name": "SECRET_KEY",         "valueFrom": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/app/secret_key" }
    ],
    "healthCheck": { "command": ["CMD-SHELL", "curl -fs http://localhost:5000/api/stocks/list || exit 1"], "interval": 30, "timeout": 5, "retries": 3, "startPeriod": 30 },
    "logConfiguration": { "logDriver": "awslogs", "options": {
      "awslogs-group": "/ecs/${APP}-backend", "awslogs-region": "${AWS_REGION}", "awslogs-stream-prefix": "backend" } }
  }]
}
JSON
aws ecs register-task-definition --cli-input-json file:///tmp/taskdef.json --query 'taskDefinition.taskDefinitionArn' --output text
```

> `secrets` 항목은 `ecsTaskExecutionRole` 이 SSM 을 읽어 컨테이너 시작 시 주입합니다. 컨테이너 안에는 키 파일이 없습니다.  
> 백엔드 컨테이너 포트가 5000 이 아니면 `containerPort`, 헬스체크, 타깃 그룹 포트를 함께 맞춥니다.

---

## 4. 타깃 그룹(ip) 생성 → ALB 리스너를 새 타깃 그룹으로 전환

```bash
TG_FARGATE=$(aws elbv2 create-target-group --name ${APP}-tg-fargate --protocol HTTP --port 5000 \
  --vpc-id "$VPC_ID" --target-type ip --health-check-path /api/stocks/list --matcher HttpCode=200-399 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)

aws ecs create-service --cluster ${APP}-cluster --service-name ${APP}-backend \
  --task-definition ${APP}-backend --desired-count 2 --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PUB_A,$PUB_C],securityGroups=[$SG_TASK],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=$TG_FARGATE,containerName=backend,containerPort=5000" \
  --health-check-grace-period-seconds 60 \
  --deployment-configuration "minimumHealthyPercent=100,maximumPercent=200,deploymentCircuitBreaker={enable=true,rollback=true}"

aws ecs wait services-stable --cluster ${APP}-cluster --services ${APP}-backend

# 리스너 기본 액션 교체 (EC2 → Fargate). 문제가 있으면 같은 명령으로 $TG_ARN 으로 되돌림
LISTENER_443=$(aws elbv2 describe-listeners --load-balancer-arn "$ALB_ARN" --query 'Listeners[?Port==`443`].ListenerArn' --output text)
aws elbv2 modify-listener --listener-arn "$LISTENER_443" --default-actions Type=forward,TargetGroupArn="$TG_FARGATE"
curl -fsS "https://${APP_HOST}/api/stocks/list" -o /dev/null -w "%{http_code}\n"
```

---

## 5. 오토스케일링 (CPU 60% 목표, 2~6 태스크)

```bash
aws application-autoscaling register-scalable-target --service-namespace ecs \
  --resource-id service/${APP}-cluster/${APP}-backend --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 --max-capacity 6
aws application-autoscaling put-scaling-policy --service-namespace ecs \
  --resource-id service/${APP}-cluster/${APP}-backend --scalable-dimension ecs:service:DesiredCount \
  --policy-name ${APP}-cpu60 --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{"TargetValue":60.0,"PredefinedMetricSpecification":{"PredefinedMetricType":"ECSServiceAverageCPUUtilization"},"ScaleOutCooldown":60,"ScaleInCooldown":300}'
```

---

## 6. 배포 파이프라인 변경

기존 `deploy/shell/deploy_ecs_cli.sh` 를 그대로 사용할 수 있습니다.

```bash
cp deploy/shell/deploy.env.stock-platform.example .env.deploy
set -a && source .env.deploy && set +a
bash deploy/shell/deploy_ecs_cli.sh        # 빌드 → ECR push → 태스크 정의 갱신 → 서비스 업데이트 → 안정화 대기
```

GitHub Actions 는 `deploy-ecs-aws-cli.yml` 의 환경변수를 위 예제 파일 값으로 바꾸면 됩니다.

---

## 7. 전환 후 정리

- EC2 의 백엔드 컨테이너 중지 후 인스턴스 종료 (또는 배치 작업용으로 축소)
- 기존 `instance` 타깃 그룹 삭제: `aws elbv2 delete-target-group --target-group-arn $TG_ARN`
- 앱 SG 의 3000 포트 규칙 제거

## 8. 체크리스트

- [ ] Task Role 로 SSM 파라미터 읽기 성공 (`aws logs tail /ecs/${APP}-backend`)
- [ ] DB SG 에 Task SG 허용 → RDS 접속 로그 정상
- [ ] `ip` 타깃 그룹 healthy 2개 이상
- [ ] 리스너 전환 후 `https://<APP_HOST>/api/stocks/list` 200
- [ ] 오토스케일링 정책 등록, 서킷 브레이커 롤백 동작 확인
