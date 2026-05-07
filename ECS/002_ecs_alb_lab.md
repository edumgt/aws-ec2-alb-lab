# ECS 실습 02 - ECS Service + ALB 연동

## 목표
- ECS Fargate Service를 ALB 뒤에 연결하고 경로 기반 라우팅을 구성합니다.

## 핵심 설정
- ALB: Public Subnet 2개 이상
- Target Group 타입: `ip`
- Health Check 경로: `/health`
- ECS Service: ALB Listener 규칙과 매핑

## 1) Target Group 생성 (`ip` 타입)
```bash
aws elbv2 create-target-group \
  --name fargate-api-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxxxxx \
  --target-type ip \
  --health-check-path /health
```

## 2) ALB 생성
```bash
aws elbv2 create-load-balancer \
  --name study-ecs-alb \
  --subnets subnet-xxxxxxxx subnet-yyyyyyyy \
  --security-groups sg-xxxxxxxx \
  --scheme internet-facing \
  --type application
```

## 3) Listener 생성
```bash
aws elbv2 create-listener \
  --load-balancer-arn <ALB_ARN> \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=<TG_ARN>
```

## 4) ECS Service에 ALB 연결
`create-service` 또는 `update-service`에 `--load-balancers` 옵션 사용:
```bash
aws ecs update-service \
  --cluster <CLUSTER_NAME> \
  --service <SERVICE_NAME> \
  --load-balancers targetGroupArn=<TG_ARN>,containerName=api,containerPort=8000
```

## 5) 검증
- ALB DNS로 접속: `/`, `/health`
- `describe-target-health`에서 `healthy` 확인

```bash
aws elbv2 describe-target-health --target-group-arn <TG_ARN>
```

## 트러블슈팅
- `unhealthy`: SG에서 ALB -> Task 8000 허용 확인
- `Target registration failed`: Target type이 `instance`로 되어 있지 않은지 확인
- `503`: 서비스 태스크 수 0 또는 헬스체크 실패


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=ECS+002+ecs+alb+lab)
