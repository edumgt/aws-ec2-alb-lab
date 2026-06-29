# EC2 실습 10 - AMI 저장 · 검색 · 사용 가이드

---

## 1. AMI(Amazon Machine Image) 개요

```
AMI = OS + 소프트웨어 + 설정 + EBS 스냅샷의 묶음

인스턴스 ──► [이미지 생성] ──► AMI (스냅샷 포함)
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              새 인스턴스    Launch Template    다른 리전 복사
```

### AMI 구성 요소

| 구성 | 설명 |
|------|------|
| **루트 디바이스** | EBS 기반(권장) 또는 Instance Store |
| **EBS 스냅샷** | 각 볼륨의 시점 스냅샷 |
| **블록 디바이스 매핑** | 볼륨 크기·유형·암호화 설정 |
| **아키텍처** | x86_64 또는 arm64 |
| **가상화** | HVM (현재 표준) |
| **권한** | Private · Public · 계정 공유 |

---

## 2. AMI 저장 (현재 인스턴스 → AMI 생성)

### 2-1. 콘솔

```
EC2 콘솔 → Instances → 인스턴스 선택
→ Actions → Image and templates → Create image
→ Image name 입력 → No reboot 체크(서비스 중단 방지) → Create image
```

### 2-2. CLI

```bash
# 인스턴스에서 AMI 생성 (EC2: 43.203.255.251 기준)
INSTANCE_ID=$(aws ec2 describe-instances \
  --region ap-northeast-2 \
  --filters "Name=ip-address,Values=43.203.255.251" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

aws ec2 create-image \
  --region ap-northeast-2 \
  --instance-id "$INSTANCE_ID" \
  --name "be-fastapi-ami-$(date +%Y%m%d)" \
  --description "FastAPI + Docker + AWS CLI 설치 완료 이미지" \
  --no-reboot \
  --tag-specifications \
    'ResourceType=image,Tags=[{Key=Name,Value=be-fastapi-base},{Key=Env,Value=prod}]' \
    'ResourceType=snapshot,Tags=[{Key=Name,Value=be-fastapi-base-snap}]'
```

> `--no-reboot`: 인스턴스 재부팅 없이 AMI 생성 (파일시스템 일관성 보장 안 됨, 서비스 중에 사용).  
> 재부팅이 가능하면 `--no-reboot` 제거 → 일관성 보장.

### 2-3. AMI 생성 완료 대기

```bash
AMI_ID=$(aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters "Name=name,Values=be-fastapi-ami-*" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

# available 상태까지 대기
aws ec2 wait image-available \
  --region ap-northeast-2 \
  --image-ids "$AMI_ID"

echo "AMI 준비 완료: $AMI_ID"
```

---

## 3. AMI 검색

### 3-1. 내 AMI 검색

```bash
# 보유 AMI 전체 목록
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --query 'sort_by(Images, &CreationDate)[*].{
    AMI:ImageId,
    Name:Name,
    State:State,
    Created:CreationDate,
    Root:RootDeviceType
  }' \
  --output table

# 이름 패턴으로 필터
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters "Name=name,Values=be-fastapi-*" \
  --query 'Images[*].{AMI:ImageId,Name:Name,State:State}' \
  --output table

# 태그로 필터
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --filters \
    "Name=tag:Env,Values=prod" \
    "Name=state,Values=available" \
  --query 'Images[*].{AMI:ImageId,Name:Name}' \
  --output table
```

### 3-2. AWS 공식 AMI 검색 (Amazon Linux · Ubuntu)

```bash
# Ubuntu 22.04 LTS 최신 (ap-northeast-2)
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].{AMI:ImageId,Name:Name,Created:CreationDate}' \
  --output table

# Amazon Linux 2023 최신
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners amazon \
  --filters \
    "Name=name,Values=al2023-ami-2023*-x86_64" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].{AMI:ImageId,Name:Name}' \
  --output table
```

### 3-3. AMI 상세 정보 조회

```bash
# 스냅샷·볼륨 정보 포함
aws ec2 describe-images \
  --region ap-northeast-2 \
  --image-ids "$AMI_ID" \
  --query 'Images[0].{
    AMI:ImageId,
    Name:Name,
    State:State,
    Arch:Architecture,
    Root:RootDeviceType,
    Virtualization:VirtualizationType,
    Snapshots:BlockDeviceMappings[].Ebs.SnapshotId
  }'
```

---

## 4. AMI 사용

### 4-1. AMI로 인스턴스 직접 시작

```bash
aws ec2 run-instances \
  --region ap-northeast-2 \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --key-name kdy-test \
  --security-group-ids sg-098feef73ffc423f0 \
  --iam-instance-profile Name=EC2ECRPullProfile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=be-fastapi-from-ami}]' \
  --count 1
```

### 4-2. Launch Template에 AMI 등록

```bash
# 신규 버전으로 AMI 업데이트
aws ec2 create-launch-template-version \
  --launch-template-name be-fastapi-lt \
  --source-version '$Latest' \
  --version-description "AMI updated $(date +%Y%m%d)" \
  --launch-template-data "{\"ImageId\":\"$AMI_ID\"}"

# 기본 버전으로 설정
LATEST_VERSION=$(aws ec2 describe-launch-template-versions \
  --launch-template-name be-fastapi-lt \
  --query 'sort_by(LaunchTemplateVersions, &VersionNumber)[-1].VersionNumber' \
  --output text)

aws ec2 modify-launch-template \
  --launch-template-name be-fastapi-lt \
  --default-version "$LATEST_VERSION"
```

### 4-3. ASG에서 새 AMI 자동 반영 (Instance Refresh)

```bash
# Launch Template 새 버전 → ASG 롤링 교체
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name be-fastapi-asg \
  --strategy Rolling \
  --preferences '{
    "MinHealthyPercentage": 50,
    "InstanceWarmup": 120,
    "SkipMatching": true
  }'
```

---

## 5. AMI 복사 (리전 간 · 계정 간)

### 5-1. 다른 리전으로 복사

```bash
# ap-northeast-2 → ap-southeast-1 (싱가포르)
aws ec2 copy-image \
  --region ap-southeast-1 \
  --source-region ap-northeast-2 \
  --source-image-id "$AMI_ID" \
  --name "be-fastapi-ami-sg-copy" \
  --encrypted
```

### 5-2. 다른 계정과 공유

```bash
# 특정 계정에 공유
aws ec2 modify-image-attribute \
  --region ap-northeast-2 \
  --image-id "$AMI_ID" \
  --launch-permission "Add=[{UserId=<TARGET_ACCOUNT_ID>}]"

# 공유 해제
aws ec2 modify-image-attribute \
  --region ap-northeast-2 \
  --image-id "$AMI_ID" \
  --launch-permission "Remove=[{UserId=<TARGET_ACCOUNT_ID>}]"

# 현재 공유 대상 확인
aws ec2 describe-image-attribute \
  --region ap-northeast-2 \
  --image-id "$AMI_ID" \
  --attribute launchPermission
```

---

## 6. AMI 수명주기 관리

### 6-1. 오래된 AMI 삭제

```bash
# AMI 등록 해제 + 스냅샷 삭제
AMI_ID="ami-xxxxxxxxxxxxxxxxx"

# 연결된 스냅샷 ID 수집
SNAPSHOT_IDS=$(aws ec2 describe-images \
  --region ap-northeast-2 \
  --image-ids "$AMI_ID" \
  --query 'Images[0].BlockDeviceMappings[].Ebs.SnapshotId' \
  --output text)

# AMI 등록 해제
aws ec2 deregister-image \
  --region ap-northeast-2 \
  --image-id "$AMI_ID"

# 스냅샷 삭제
for snap in $SNAPSHOT_IDS; do
  aws ec2 delete-snapshot \
    --region ap-northeast-2 \
    --snapshot-id "$snap"
  echo "Deleted snapshot: $snap"
done
```

### 6-2. EC2 Image Builder (자동화)

대규모 환경에서는 EC2 Image Builder를 사용해 AMI 빌드 파이프라인을 자동화합니다.

```
Source AMI (Ubuntu 22.04)
      │
      ▼ Image Builder Pipeline
  Build Component (Docker 설치, AWS CLI 설치, 앱 패키징)
      │
      ▼ Test Component (헬스체크, 포트 확인)
      │
      ▼
  완성 AMI (be-fastapi-base) → 자동 Launch Template 업데이트
```

---

## 7. 이 프로젝트 AMI 권장 워크플로우

```
[1] EC2 (43.203.255.251) 에 기본 환경 구성
    └── Docker 설치, AWS CLI 설치, ECR 인증 설정

[2] AMI 생성 (스냅샷 저장)
    └── aws ec2 create-image --name "base-$(date +%Y%m%d)" --no-reboot

[3] Launch Template 에 AMI 등록
    └── aws ec2 create-launch-template-version --image-id <NEW_AMI>

[4] ASG 에서 Instance Refresh
    └── 새 AMI 기반 인스턴스로 롤링 교체

[5] 구 AMI 정리 (1세대 이전 삭제)
    └── aws ec2 deregister-image + delete-snapshot
```

### 빠른 참조 명령

```bash
# 현재 EC2의 AMI ID 확인
aws ec2 describe-instances \
  --region ap-northeast-2 \
  --filters "Name=ip-address,Values=43.203.255.251" \
  --query 'Reservations[0].Instances[0].ImageId' \
  --output text

# 내 AMI 목록 (최신순)
aws ec2 describe-images \
  --region ap-northeast-2 \
  --owners self \
  --query 'sort_by(Images, &CreationDate)[*].{AMI:ImageId,Name:Name,Date:CreationDate}' \
  --output table
```
