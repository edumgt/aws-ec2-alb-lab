# AWS Fault Injection Simulator (FIS) Lab

다이어그램 기반 AWS FIS 카오스 엔지니어링 실습 스크립트

## 아키텍처 구성 요소

| 컴포넌트 | 역할 | 스크립트 |
|---|---|---|
| AWS IAM | FIS 실행 권한 부여 | `01_setup_iam.sh` |
| CloudWatch Alarms | FIS Safeguards (자동 중단 조건) | `02_create_cloudwatch_alarms.sh` |
| Experiment Template | 실험 시나리오 정의 | `03_create_experiment_template.sh` |
| FIS Engine | 실험 시작 / 중단 / 모니터링 | `04_run_experiment.sh` |
| Cleanup | 모든 리소스 삭제 | `05_cleanup.sh` |

## 실행 순서

```bash
# 사전 조건: AWS CLI 설정 완료
aws configure  # 또는 환경변수 설정
export AWS_DEFAULT_REGION=ap-northeast-2

# 1단계: IAM Role & Policy 생성
./01_setup_iam.sh

# 2단계: CloudWatch Alarms 생성 (FIS Safeguards)
./02_create_cloudwatch_alarms.sh

# 3단계: Experiment Templates 생성
./03_create_experiment_template.sh

# 4단계: 실험 실행
./04_run_experiment.sh start ec2-stop          # EC2 인스턴스 중단
./04_run_experiment.sh start cpu-stress        # CPU 스트레스
./04_run_experiment.sh start network-latency   # 네트워크 지연

# 실험 모니터링
./04_run_experiment.sh watch EXPxxxxxxxxxxx
./04_run_experiment.sh status EXPxxxxxxxxxxx
./04_run_experiment.sh list

# 실험 강제 중단
./04_run_experiment.sh stop EXPxxxxxxxxxxx

# 정리
./05_cleanup.sh
```

## 실험 시나리오

### 1. EC2 Stop (Compute 장애)
- EC2 인스턴스를 강제 중단 후 5분 뒤 재시작
- 검증 목표: Auto Scaling, ALB 헬스체크 동작 확인

### 2. CPU Stress (고부하 장애)
- SSM을 통해 CPU 100% 부하 120초 주입
- 검증 목표: CloudWatch 알람 → Auto Scaling 반응 시간

### 3. Network Latency (네트워크 장애)
- 네트워크 패킷에 200ms 지연 + 10ms 지터 추가
- 검증 목표: 타임아웃 설정, 재시도 로직, Circuit Breaker 동작

## FIS Safeguards (자동 중단 조건)

실험 중 CloudWatch 알람이 트리거되면 FIS가 자동으로 실험을 중단합니다:

| 알람 이름 | 조건 | 임계치 |
|---|---|---|
| fis-safeguard-ec2-cpu-high | EC2 CPU ≥ 80% (3분 지속) | 자동 중단 |
| fis-safeguard-ec2-status-check | 상태 체크 실패 | 자동 중단 |
| fis-safeguard-alb-5xx-high | ALB 5xx 오류 > 50개 | 자동 중단 |
| fis-safeguard-availability-breach | 시스템 상태 체크 실패 | 즉시 중단 |
