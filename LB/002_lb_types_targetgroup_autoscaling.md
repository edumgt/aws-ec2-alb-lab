# LB 실습 02 - 로드밸런서 종류 · 타겟그룹 · 오토스케일러

---

## 1. AWS 로드밸런서 종류 비교

| 항목 | ALB | NLB | GLB | CLB |
|------|-----|-----|-----|-----|
| 계층 | L7 (HTTP/HTTPS/gRPC) | L4 (TCP/UDP/TLS) | L3+L4 | L4/L7 혼합 |
| 라우팅 | Host · Path · Header · Query · IP | 포트/프로토콜 | 투명 프록시 | 포트 기반 |
| 고정 IP | ❌ (DNS) | ✅ (EIP 할당 가능) | ❌ | ❌ |
| 성능 | 고성능 (자동 확장) | 초고성능 (수백만 req/s) | 어플라이언스 전용 | 레거시 |
| WebSocket | ✅ | ✅ | ❌ | ❌ |
| gRPC | ✅ | ❌ | ❌ | ❌ |
| 주요 용도 | 웹/API/마이크로서비스 | 게임·금융·고정IP 필요 | IDS/IPS·방화벽 체이닝 | 마이그레이션 전환 |
| 권장 | ✅ (웹 기본) | ✅ (TCP 전용) | 보안 어플라이언스 | ❌ 신규 사용 금지 |

### 1-1. ALB (Application Load Balancer)

```
클라이언트
    │
    ▼ HTTP/HTTPS
┌──────────────────────────────────────────┐
│  ALB                                      │
│  Listener :443 (HTTPS)                   │
│  ├── Rule 1: Host = api.example.com       │── TG: api-servers
│  ├── Rule 2: Path = /admin/*              │── TG: admin-servers
│  └── Default: forward                    │── TG: web-servers
└──────────────────────────────────────────┘
```

**핵심 라우팅 조건**
```bash
# Host 기반
aws elbv2 create-rule \
  --listener-arn <LISTENER_ARN> \
  --conditions '[{"Field":"host-header","Values":["api.example.com"]}]' \
  --actions '[{"Type":"forward","TargetGroupArn":"<TG_ARN>"}]' \
  --priority 10

# Path 기반
--conditions '[{"Field":"path-pattern","Values":["/api/*"]}]'

# Header 기반
--conditions '[{"Field":"http-header","HttpHeaderConfig":{"HttpHeaderName":"X-Role","Values":["admin"]}}]'
```

### 1-2. NLB (Network Load Balancer)

```
클라이언트 ──TCP:443──► NLB (EIP 고정) ──TCP──► Target (EC2/ECS)
                         └── TLS 종료 가능 (리스너에서)
```

- 연결당 지연 < 1ms
- 클라이언트 IP 보존 (`proxy-protocol-v2` 없이도 가능)
- 헬스체크: TCP Ping 또는 HTTP

### 1-3. GLB (Gateway Load Balancer)

```
인터넷 트래픽
    │
    ▼ (VPC Route Table 조작으로 트래픽 강제 경유)
┌──────────────────────────┐
│  GLB Endpoint (GWLBE)    │
│  ↕ GENEVE 6081           │
│  방화벽/IDS 어플라이언스  │
└──────────────────────────┘
    │
    ▼ 정상 트래픽만 통과
   실제 서비스 EC2
```

---

## 2. Target Group 상세

### 2-1. 타겟 유형 3가지

| 타겟 유형 | 설명 | 주요 사용처 |
|-----------|------|-------------|
| `instance` | EC2 인스턴스 ID 기반 | ASG와 자동 연동 |
| `ip` | 프라이빗 IP 기반 | ECS Fargate, On-Prem, Lambda VPC |
| `lambda` | Lambda ARN 기반 | 서버리스 API (ALB 전용) |

### 2-2. 헬스체크 설정

```bash
# 헬스체크 경로·주기·임계값 설정
aws elbv2 create-target-group \
  --name be-fastapi-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxxxxx \
  --target-type ip \
  --health-check-protocol HTTP \
  --health-check-path /health \
  --health-check-interval-seconds 15 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --matcher HttpCode=200

# 헬스 상태 확인
aws elbv2 describe-target-health \
  --target-group-arn <TG_ARN> \
  --query 'TargetHealthDescriptions[].{Target:Target.Id,State:TargetHealth.State,Reason:TargetHealth.Reason}' \
  --output table
```

**헬스체크 상태값**

| 상태 | 의미 |
|------|------|
| `healthy` | 정상, 트래픽 수신 중 |
| `unhealthy` | 임계값 초과 실패 → 트래픽 제외 |
| `initial` | 등록 직후 첫 번째 체크 대기 |
| `draining` | Deregistration 진행 중 (`deregistration_delay`) |
| `unused` | TG에 LB가 연결되지 않음 |

### 2-3. Deregistration Delay (연결 드레이닝)

```bash
# 기본값 300초 → 빠른 배포를 위해 단축
aws elbv2 modify-target-group-attributes \
  --target-group-arn <TG_ARN> \
  --attributes Key=deregistration_delay.timeout_seconds,Value=30
```

### 2-4. Sticky Session (세션 고정)

```bash
# Duration 기반 (ALB 쿠키)
aws elbv2 modify-target-group-attributes \
  --target-group-arn <TG_ARN> \
  --attributes \
    Key=stickiness.enabled,Value=true \
    Key=stickiness.type,Value=lb_cookie \
    Key=stickiness.lb_cookie.duration_seconds,Value=86400
```

### 2-5. 현재 프로젝트 Target Group 구성 예시

```bash
# BE FastAPI (포트 8000, /health 체크)
aws elbv2 create-target-group \
  --name be-fastapi-tg \
  --protocol HTTP --port 8000 \
  --vpc-id <VPC_ID> \
  --target-type instance \
  --health-check-path /health

# FE Nginx (포트 80, / 체크)
aws elbv2 create-target-group \
  --name fe-ag-grid-tg \
  --protocol HTTP --port 80 \
  --vpc-id <VPC_ID> \
  --target-type instance \
  --health-check-path /

# EC2 인스턴스 등록
aws elbv2 register-targets \
  --target-group-arn <BE_TG_ARN> \
  --targets Id=<INSTANCE_ID>,Port=8000
```

---

## 3. Auto Scaling Group (ASG)

### 3-1. 구성 요소

```
Launch Template (인스턴스 설정 청사진)
    │
    ▼
Auto Scaling Group
    ├── min: 1  (최소 인스턴스 수)
    ├── desired: 2  (현재 목표 수)
    ├── max: 4  (최대 인스턴스 수)
    │
    ├── Target Group 연결 → ALB에서 자동 등록/해제
    ├── Health Check: EC2 또는 ELB
    └── Scaling Policy
```

### 3-2. Launch Template 생성

```bash
aws ec2 create-launch-template \
  --launch-template-name be-fastapi-lt \
  --version-description "v1-docker-ecr" \
  --launch-template-data '{
    "ImageId": "ami-0d3fb6fb6c746f131",
    "InstanceType": "t3.micro",
    "KeyName": "kdy-test",
    "SecurityGroupIds": ["sg-098feef73ffc423f0"],
    "IamInstanceProfile": {
      "Name": "EC2ECRPullProfile"
    },
    "UserData": "'"$(base64 -w0 <<'EOF'
#!/bin/bash
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com
docker pull 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest
docker run -d --name fastapi-app --restart unless-stopped \
  -p 8000:8000 \
  086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/be-test:latest
EOF
)"'"
  }'
```

### 3-3. ASG 생성 및 ALB 연결

```bash
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name be-fastapi-asg \
  --launch-template LaunchTemplateName=be-fastapi-lt,Version='$Latest' \
  --min-size 1 \
  --desired-capacity 2 \
  --max-size 4 \
  --target-group-arns <BE_TG_ARN> \
  --health-check-type ELB \
  --health-check-grace-period 120 \
  --vpc-zone-identifier "<SUBNET_ID_AZ1>,<SUBNET_ID_AZ2>"
```

### 3-4. Scaling Policy 종류

| 정책 유형 | 트리거 | 적합한 상황 |
|-----------|--------|-------------|
| **Target Tracking** | 목표 지표(CPU 50%) 자동 유지 | 가장 단순·권장 |
| **Step Scaling** | 임계값 단계별 인스턴스 증감 | 세밀한 제어 필요 시 |
| **Scheduled** | 특정 시간(크론) | 예측 가능한 트래픽 패턴 |
| **Predictive** | ML 기반 사전 확장 | 대규모·주기적 트래픽 |

```bash
# Target Tracking — CPU 50% 유지
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name be-fastapi-asg \
  --policy-name cpu-target-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ASGAverageCPUUtilization"
    },
    "TargetValue": 50.0,
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'

# ALB 요청 수 기반 (RequestCountPerTarget)
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name be-fastapi-asg \
  --policy-name alb-requests-tracking \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ALBRequestCountPerTarget",
      "ResourceLabel": "<ALB_ARN_SUFFIX>/<TG_ARN_SUFFIX>"
    },
    "TargetValue": 100.0
  }'
```

### 3-5. ASG 점검 명령

```bash
# ASG 전체 상태
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names be-fastapi-asg \
  --query 'AutoScalingGroups[0].{
    Min:MinSize, Desired:DesiredCapacity, Max:MaxSize,
    HealthCheck:HealthCheckType,
    Instances:Instances[].{Id:InstanceId,State:LifecycleState,Health:HealthStatus}
  }'

# 스케일링 활동 이력
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name be-fastapi-asg \
  --max-items 10 \
  --query 'Activities[].{Time:StartTime,Status:StatusCode,Desc:Description}' \
  --output table

# 인스턴스 수 수동 조정
aws autoscaling set-desired-capacity \
  --auto-scaling-group-name be-fastapi-asg \
  --desired-capacity 3
```

### 3-6. Instance Refresh (무중단 롤링 업데이트)

```bash
# Launch Template 새 버전 배포 시 롤링 교체
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name be-fastapi-asg \
  --strategy Rolling \
  --preferences '{
    "MinHealthyPercentage": 50,
    "InstanceWarmup": 120
  }'

# 진행 상태 확인
aws autoscaling describe-instance-refreshes \
  --auto-scaling-group-name be-fastapi-asg
```

---

## 4. ALB + ASG + ECS 연동 아키텍처

```
인터넷
  │
  ▼ HTTPS:443
┌──────────────────────────────────────┐
│  ALB (ap-northeast-2a / 2b)          │
│  Listener :443                        │
│  ├── /api/* → BE Target Group        │
│  └── /*     → FE Target Group        │
└───────────────────┬──────────────────┘
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│ BE ASG          │  │ FE ASG          │
│ t3.micro × 2   │  │ t3.micro × 2   │
│ fastapi :8000  │  │ nginx :80       │
│ CPU 트래킹 50% │  │ CPU 트래킹 50% │
└─────────────────┘  └─────────────────┘
        │
        ▼ (ECR Pull — IAM Instance Profile)
086015456585.dkr.ecr.ap-northeast-2.amazonaws.com
  ├── be-test:latest
  └── fe-test:latest
```

---

## 5. 자주 발생하는 문제 진단

| 증상 | 원인 | 해결 |
|------|------|------|
| `504 Gateway Timeout` | Target 응답 없음 또는 헬스체크 실패 | SG·앱 로그 확인 |
| `503 Service Unavailable` | 건강한 Target 없음 | `describe-target-health` 확인 |
| ASG Scale-out 없음 | CloudWatch Alarm 미설정 / Cooldown 중 | Scaling Activity 이력 확인 |
| 배포 후 구 버전 응답 | Sticky Session 또는 구 인스턴스 잔존 | Instance Refresh 또는 드레이닝 확인 |
| ALB → EC2 연결 불가 | SG Source 미설정 | EC2 SG 인바운드에 ALB SG 추가 |
