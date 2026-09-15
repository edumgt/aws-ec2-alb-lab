#!/usr/bin/env bash
# Phase D-4. 앱 EC2 (User Data: Docker + AWS CLI + SSM→.env + ECR compose 기동) → 타깃 등록
source "$(dirname "$0")/00_common.sh"
need PUB_A SG_APP TG_ARN EC2_PROFILE

step "[1/4] 키페어"
if ! aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  aws ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 --query KeyMaterial --output text > ~/.ssh/${KEY_NAME}.pem
  chmod 400 ~/.ssh/${KEY_NAME}.pem; echo "  ~/.ssh/${KEY_NAME}.pem 저장"
fi

step "[2/4] AMI (Ubuntu 22.04 최신)"
AMI_ID=$(aws ec2 describe-images --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" "Name=state,Values=available" \
  --query 'sort_by(Images,&CreationDate)[-1].ImageId' --output text); echo "  $AMI_ID"

step "[3/4] User Data 렌더링"
UD=$(mktemp)
cat > "$UD" <<USERDATA
#!/bin/bash
exec > /var/log/user-data.log 2>&1
set -e
export AWS_DEFAULT_REGION=${AWS_REGION}
apt-get update -y && apt-get install -y ca-certificates curl gnupg unzip git jq mariadb-client postgresql-client
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable" > /etc/apt/sources.list.d/docker.list
apt-get update -y && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker && usermod -aG docker ubuntu
curl -s https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install
git clone ${APP_REPO_URL} ${APP_DIR} || true
cd ${APP_DIR}
p() { aws ssm get-parameter --with-decryption --name "${SSM_PREFIX}/\$1" --query Parameter.Value --output text; }
cat > .env <<ENV
ECR_REGISTRY=${ECR_REGISTRY}
IMAGE_TAG=latest
AWS_REGION=${AWS_REGION}
AWS_SSM_PARAMETER_PREFIX=${SSM_PREFIX}
DATABASE_URL=\$(p db/mariadb/url)
QUANT_DATABASE_URL=\$(p db/postgres/url)
SECRET_KEY=\$(p app/secret_key)
ENV
chmod 600 .env
aws ecr get-login-password | docker login --username AWS --password-stdin ${ECR_REGISTRY}
docker compose -p stock-coin-trade -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -p stock-coin-trade -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build --remove-orphans
echo "--- user-data done ---"
USERDATA

step "[4/4] 인스턴스 생성 → 타깃 등록"
if ! nz "${INSTANCE_ID:-}"; then
  save INSTANCE_ID "$(aws ec2 run-instances --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" --key-name "$KEY_NAME" \
    --subnet-id "$PUB_A" --security-group-ids "$SG_APP" --associate-public-ip-address \
    --iam-instance-profile Name="$EC2_PROFILE" \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true}' \
    --user-data "file://$UD" --tag-specifications "$(tags instance ${APP}-app-a)" \
    --query 'Instances[0].InstanceId' --output text)"
fi
rm -f "$UD"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
aws elbv2 register-targets --target-group-arn "$TG_ARN" --targets Id="$INSTANCE_ID"
echo "  타깃 healthy 대기 (User Data 완료까지 수 분)..."
aws elbv2 wait target-in-service --target-group-arn "$TG_ARN" --targets Id="$INSTANCE_ID"
echo; echo "앱 서버 완료: $INSTANCE_ID  접속: aws ssm start-session --target $INSTANCE_ID"
