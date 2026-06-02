#!/bin/bash
set -e

REGION="ap-northeast-2"
KEY_NAME="kdy-test"
INSTANCE_TYPE="t3.micro"
INSTANCE_NAME="ubuntu-docker-nginx"

# ---------------------------------------------------------------------------
# AMI: Ubuntu 22.04 LTS (최신)
# ---------------------------------------------------------------------------
echo "[1/6] AMI 조회 중..."
AMI_ID=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "  AMI: $AMI_ID"

# ---------------------------------------------------------------------------
# VPC: 비-default 우선, 없으면 default
# ---------------------------------------------------------------------------
echo "[2/6] VPC 조회 중..."
VPC_ID=$(aws ec2 describe-vpcs \
  --region "$REGION" \
  --filters "Name=state,Values=available" \
  --query 'Vpcs[?IsDefault==`false`].VpcId | [0]' \
  --output text)

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
  VPC_ID=$(aws ec2 describe-vpcs \
    --region "$REGION" \
    --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' \
    --output text)
fi

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
  echo "ERROR: 사용 가능한 VPC가 없습니다." >&2
  exit 1
fi
echo "  VPC: $VPC_ID"

# ---------------------------------------------------------------------------
# 퍼블릭 서브넷: map-public-ip-on-launch=true 우선, 없으면 신규 생성
# ---------------------------------------------------------------------------
echo "[3/6] 퍼블릭 서브넷 조회 중..."
SUBNET_ID=$(aws ec2 describe-subnets \
  --region "$REGION" \
  --filters \
    "Name=vpc-id,Values=$VPC_ID" \
    "Name=map-public-ip-on-launch,Values=true" \
  --query 'Subnets[0].SubnetId' \
  --output text)

if [ "$SUBNET_ID" = "None" ] || [ -z "$SUBNET_ID" ]; then
  SUBNET_ID=$(aws ec2 describe-subnets \
    --region "$REGION" \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'Subnets[0].SubnetId' \
    --output text)
fi

if [ "$SUBNET_ID" = "None" ] || [ -z "$SUBNET_ID" ]; then
  echo "  서브넷 없음 → 퍼블릭 서브넷 생성 중..."

  # VPC CIDR 에서 /24 서브넷 CIDR 계산 (예: 172.31.0.0/16 → 172.31.0.0/24)
  VPC_CIDR=$(aws ec2 describe-vpcs \
    --region "$REGION" \
    --vpc-ids "$VPC_ID" \
    --query 'Vpcs[0].CidrBlock' \
    --output text)
  SUBNET_CIDR=$(echo "$VPC_CIDR" | sed 's|\([0-9]*\.[0-9]*\)\.[0-9]*\.[0-9]*/[0-9]*|\1.0.0/24|')

  # 첫 번째 AZ 선택
  AZ=$(aws ec2 describe-availability-zones \
    --region "$REGION" \
    --query 'AvailabilityZones[0].ZoneName' \
    --output text)

  SUBNET_ID=$(aws ec2 create-subnet \
    --region "$REGION" \
    --vpc-id "$VPC_ID" \
    --cidr-block "$SUBNET_CIDR" \
    --availability-zone "$AZ" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=public-subnet-auto}]" \
    --query 'Subnet.SubnetId' \
    --output text)
  echo "  서브넷 생성: $SUBNET_ID ($SUBNET_CIDR, $AZ)"

  # 퍼블릭 IP 자동 할당 활성화
  aws ec2 modify-subnet-attribute \
    --region "$REGION" \
    --subnet-id "$SUBNET_ID" \
    --map-public-ip-on-launch

  # Internet Gateway: 기존 것 재사용 또는 신규 생성 후 VPC에 연결
  IGW_ID=$(aws ec2 describe-internet-gateways \
    --region "$REGION" \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --query 'InternetGateways[0].InternetGatewayId' \
    --output text)

  if [ "$IGW_ID" = "None" ] || [ -z "$IGW_ID" ]; then
    IGW_ID=$(aws ec2 create-internet-gateway \
      --region "$REGION" \
      --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=igw-auto}]" \
      --query 'InternetGateway.InternetGatewayId' \
      --output text)
    aws ec2 attach-internet-gateway \
      --region "$REGION" \
      --internet-gateway-id "$IGW_ID" \
      --vpc-id "$VPC_ID"
    echo "  Internet Gateway 생성 및 연결: $IGW_ID"
  else
    echo "  Internet Gateway 재사용: $IGW_ID"
  fi

  # 라우트 테이블: 메인 라우트 테이블에 0.0.0.0/0 → IGW 경로 추가
  RTB_ID=$(aws ec2 describe-route-tables \
    --region "$REGION" \
    --filters \
      "Name=vpc-id,Values=$VPC_ID" \
      "Name=association.main,Values=true" \
    --query 'RouteTables[0].RouteTableId' \
    --output text)

  # 기존 default route 없을 때만 추가
  EXISTING_ROUTE=$(aws ec2 describe-route-tables \
    --region "$REGION" \
    --route-table-ids "$RTB_ID" \
    --query "RouteTables[0].Routes[?DestinationCidrBlock=='0.0.0.0/0'].GatewayId" \
    --output text)

  if [ -z "$EXISTING_ROUTE" ] || [ "$EXISTING_ROUTE" = "None" ]; then
    aws ec2 create-route \
      --region "$REGION" \
      --route-table-id "$RTB_ID" \
      --destination-cidr-block 0.0.0.0/0 \
      --gateway-id "$IGW_ID" > /dev/null
    echo "  기본 경로 추가: 0.0.0.0/0 → $IGW_ID (라우트 테이블: $RTB_ID)"
  fi

  # 서브넷을 라우트 테이블에 연결
  aws ec2 associate-route-table \
    --region "$REGION" \
    --subnet-id "$SUBNET_ID" \
    --route-table-id "$RTB_ID" > /dev/null
  echo "  서브넷 ↔ 라우트 테이블 연결 완료"
fi
echo "  Subnet: $SUBNET_ID"

# ---------------------------------------------------------------------------
# Security Group: VPC 내 첫 번째 SG
# ---------------------------------------------------------------------------
echo "[4/6] 보안 그룹 조회 중..."
SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo "ERROR: VPC $VPC_ID 에 보안 그룹이 없습니다." >&2
  exit 1
fi
echo "  Security Group: $SG_ID"

# ---------------------------------------------------------------------------
# User Data: 패키지 업데이트 → Docker 설치 → 이미지 pull
# ---------------------------------------------------------------------------
USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
exec > /var/log/user-data.log 2>&1

# 패키지 업데이트
apt-get update -y
apt-get upgrade -y

# Docker 공식 GPG 키 & 저장소 추가
apt-get install -y ca-certificates curl gnupg lsb-release
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker 설치
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io \
                   docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

# ubuntu 유저가 docker 명령 사용 가능하도록
usermod -aG docker ubuntu

# 이미지 pull
docker pull edumgt/platform-nginx:1.27-alpine

echo "--- user-data 완료 ---"
USERDATA
)

# ---------------------------------------------------------------------------
# EC2 인스턴스 생성
# ---------------------------------------------------------------------------
echo "[6/6] EC2 인스턴스 생성 중..."
INSTANCE_ID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SG_ID" \
  --associate-public-ip-address \
  --user-data "$USER_DATA" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "  Instance ID: $INSTANCE_ID"
echo "  Running 상태 대기 중..."
aws ec2 wait instance-running \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID"

PUBLIC_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo ""
echo "=============================="
echo " EC2 인스턴스 생성 완료!"
echo "=============================="
echo "  Instance ID : $INSTANCE_ID"
echo "  Public IP   : $PUBLIC_IP"
echo "  SSH 접속    : ssh -i ~/.ssh/kdy-test.pem ubuntu@$PUBLIC_IP"
echo ""
echo "  User Data 로그 확인 (접속 후):"
echo "    sudo tail -f /var/log/user-data.log"
echo "=============================="
