# AWS CLI 기반 배포 샘플 3종

이 폴더는 동일한 ECS(Fargate) 배포 흐름을 다음 3가지 방식으로 제공합니다.

1. Shell Script (`deploy/shell/deploy_ecs_cli.sh`)
2. Ansible Playbook (`deploy/ansible/deploy_ecs_cli.yml`)
3. GitHub Actions (`.github/workflows/deploy-ecs-aws-cli.yml`)

공통 흐름:
1. ECR 리포지토리 확인/생성
2. Docker 이미지 빌드
3. ECR 푸시
4. Task Definition 등록
5. ECS Service 업데이트
6. 서비스 안정화 대기

## 1) Shell 방식
파일:
- `deploy/shell/deploy_ecs_cli.sh`
- `deploy/shell/deploy.env.example`

실행 예시:
```bash
cp deploy/shell/deploy.env.example .env.deploy
set -a
source .env.deploy
set +a

./deploy/shell/deploy_ecs_cli.sh
```

## 2) Ansible 방식
필요:
- ansible
- aws cli
- docker

변수 파일:
- `deploy/ansible/group_vars/all.yml`

실행:
```bash
ansible-playbook -i deploy/ansible/inventory.ini deploy/ansible/deploy_ecs_cli.yml
```

## 3) GitHub Actions 방식
워크플로우:
- `.github/workflows/deploy-ecs-aws-cli.yml`

필수 설정:
- GitHub `Secrets`
  - `AWS_ROLE_TO_ASSUME` (OIDC로 Assume할 Role ARN)
- GitHub `Variables`
  - `AWS_REGION`, `ECS_CLUSTER`, `ECS_SERVICE`, `TASK_FAMILY`, `ECR_REPO`, `CONTAINER_NAME`
  - 선택: `CONTAINER_PORT`, `CPU`, `MEMORY`

권장:
- 장기 Access Key 대신 OIDC + IAM Role 사용
- 배포 전후 헬스체크 알람(CloudWatch Alarm) 연동

## 4) 실습: `deploy-ecr-ec2.yml`용 AWS CLI 인프라 구성

아래 실습은 `https://github.com/edumgt/investment-analysis/blob/main/.github/workflows/deploy-ecr-ec2.yml` 기준으로,
GitHub Actions가 ECR 빌드/푸시 후 EC2에 `docker compose` 배포할 수 있는 최소 인프라를 AWS CLI로 준비하는 예시입니다.

### 4-1. 환경변수 준비
```bash
export AWS_REGION="ap-northeast-2"
export LAB_NAME="investment-analysis"
export VPC_ID="<기존 VPC ID>"
export PUBLIC_SUBNET_ID="<퍼블릭 서브넷 ID>"
export MY_IP_CIDR="<내 공인IP>/32"              # 예: 1.2.3.4/32
export INSTANCE_TYPE="t3.small"
export AMI_ID="<Amazon Linux 2023 AMI ID>"
```

> VPC/Subnet이 없다면 `EC2/001.md` 순서대로 먼저 생성합니다.

### 4-2. 보안그룹 생성 (SSH + 앱 포트)
```bash
EC2_SG_ID=$(aws ec2 create-security-group \
  --group-name "${LAB_NAME}-ec2-sg" \
  --description "EC2 SG for ${LAB_NAME}" \
  --vpc-id "$VPC_ID" \
  --query 'GroupId' --output text --region "$AWS_REGION")

aws ec2 authorize-security-group-ingress \
  --group-id "$EC2_SG_ID" \
  --ip-permissions \
  "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MY_IP_CIDR,Description=ssh-from-admin}]" \
  "IpProtocol=tcp,FromPort=8000,ToPort=8000,IpRanges=[{CidrIp=0.0.0.0/0,Description=webapp-http}]" \
  --region "$AWS_REGION"
```

### 4-3. GitHub Actions Assume Role 생성 (OIDC)
신뢰 정책 파일(`trust-policy.json`)을 만든 뒤 Role을 생성합니다.
```bash
cat > trust-policy.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
        "StringLike": { "token.actions.githubusercontent.com:sub": "repo:edumgt/investment-analysis:*" }
      }
    }
  ]
}
JSON

aws iam create-role \
  --role-name "${LAB_NAME}-github-actions-role" \
  --assume-role-policy-document file://trust-policy.json
```

권한 정책 파일(`gha-deploy-policy.json`)을 연결합니다.
```bash
cat > gha-deploy-policy.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage",
        "ecr:DescribeRepositories",
        "ecr:CreateRepository"
      ],
      "Resource": "*"
    }
  ]
}
JSON

aws iam put-role-policy \
  --role-name "${LAB_NAME}-github-actions-role" \
  --policy-name "${LAB_NAME}-gha-deploy-policy" \
  --policy-document file://gha-deploy-policy.json
```

### 4-4. EC2 접속용 Key Pair와 인스턴스 생성
```bash
aws ec2 create-key-pair \
  --key-name "${LAB_NAME}-key" \
  --query 'KeyMaterial' --output text \
  --region "$AWS_REGION" > "${LAB_NAME}-key.pem"
chmod 400 "${LAB_NAME}-key.pem"

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "${LAB_NAME}-key" \
  --security-group-ids "$EC2_SG_ID" \
  --subnet-id "$PUBLIC_SUBNET_ID" \
  --associate-public-ip-address \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${LAB_NAME}-ec2}]" \
  --query 'Instances[0].InstanceId' --output text \
  --region "$AWS_REGION")

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"

EC2_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text --region "$AWS_REGION")
echo "$EC2_PUBLIC_IP"
```

### 4-5. EC2에 Docker / Compose 설치
```bash
ssh -i "${LAB_NAME}-key.pem" ec2-user@"$EC2_PUBLIC_IP" <<'EOF'
set -euo pipefail
sudo dnf -y update
sudo dnf -y install docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
sudo mkdir -p /home/ec2-user/investment-analysis
EOF
```

### 4-6. GitHub 저장소 Secrets / Variables 매핑
`deploy-ecr-ec2.yml` 기준 필수값은 다음과 같습니다.

- **Secrets**
  - `AWS_ROLE_ARN`: `arn:aws:iam::<AWS_ACCOUNT_ID>:role/${LAB_NAME}-github-actions-role`
  - `EC2_HOST`: `EC2_PUBLIC_IP`
  - `EC2_USERNAME`: `ec2-user` (Ubuntu AMI면 `ubuntu`)
  - `EC2_SSH_KEY`: `${LAB_NAME}-key.pem` 전체 내용
  - `BACKEND_ENV_FILE`: 애플리케이션 `.env` 내용
- **Variables**
  - `AWS_REGION`
  - `WEBAPP_ECR_REPOSITORY` (예: `investment-analysis-webapp`)
  - `MONGODB_ECR_REPOSITORY` (예: `investment-analysis-mongodb`)
  - `MONGODB_SOURCE_IMAGE` (기본 `mongo:7`)
  - `EC2_DEPLOY_PATH` (예: `/home/ec2-user/investment-analysis`)
  - `WEBAPP_PORT` (예: `8000`)

### 4-7. 검증 및 정리
```bash
# EC2 상태 확인
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION" \
  --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress,SecurityGroups[*].GroupId]'

# 롤 삭제(실습 종료 시)
aws iam delete-role-policy \
  --role-name "${LAB_NAME}-github-actions-role" \
  --policy-name "${LAB_NAME}-gha-deploy-policy"
aws iam delete-role --role-name "${LAB_NAME}-github-actions-role"

# 인스턴스/SG 정리(실습 종료 시)
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" --region "$AWS_REGION"
aws ec2 delete-security-group --group-id "$EC2_SG_ID" --region "$AWS_REGION"
```

> OIDC Provider(`token.actions.githubusercontent.com`)가 계정에 없다면 먼저 생성해야 합니다.
> 기존 계정에 이미 설정된 경우 Role 생성 단계부터 진행하면 됩니다.


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=deploy+README)
