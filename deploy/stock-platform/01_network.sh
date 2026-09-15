#!/usr/bin/env bash
# Phase A. VPC / 서브넷 2AZ / IGW / 라우팅 / 보안그룹 3계층
source "$(dirname "$0")/00_common.sh"

step "[1/5] VPC"
if ! nz "${VPC_ID:-}"; then
  save VPC_ID "$(aws ec2 create-vpc --cidr-block "$VPC_CIDR" --tag-specifications "$(tags vpc ${APP}-vpc)" --query Vpc.VpcId --output text)"
  aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames
  aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support
fi

step "[2/5] 서브넷"
mk_subnet() { aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$1" --availability-zone "${AWS_REGION}$2" \
  --tag-specifications "$(tags subnet $3)" --query Subnet.SubnetId --output text; }
nz "${PUB_A:-}" || save PUB_A "$(mk_subnet "$PUB_A_CIDR" a ${APP}-public-a)"
nz "${PUB_C:-}" || save PUB_C "$(mk_subnet "$PUB_C_CIDR" c ${APP}-public-c)"
nz "${PRI_A:-}" || save PRI_A "$(mk_subnet "$PRI_A_CIDR" a ${APP}-private-a)"
nz "${PRI_C:-}" || save PRI_C "$(mk_subnet "$PRI_C_CIDR" c ${APP}-private-c)"
for s in "$PUB_A" "$PUB_C"; do aws ec2 modify-subnet-attribute --subnet-id "$s" --map-public-ip-on-launch; done

step "[3/5] IGW + 퍼블릭 라우트"
if ! nz "${IGW_ID:-}"; then
  save IGW_ID "$(aws ec2 create-internet-gateway --tag-specifications "$(tags internet-gateway ${APP}-igw)" --query InternetGateway.InternetGatewayId --output text)"
  aws ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
fi
if ! nz "${RTB_PUB:-}"; then
  save RTB_PUB "$(aws ec2 create-route-table --vpc-id "$VPC_ID" --tag-specifications "$(tags route-table ${APP}-rtb-public)" --query RouteTable.RouteTableId --output text)"
  aws ec2 create-route --route-table-id "$RTB_PUB" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" >/dev/null
  for s in "$PUB_A" "$PUB_C"; do aws ec2 associate-route-table --route-table-id "$RTB_PUB" --subnet-id "$s" >/dev/null; done
fi

step "[4/5] 보안그룹 (ALB → APP → DB)"
mk_sg() { aws ec2 create-security-group --group-name "$1" --description "$2" --vpc-id "$VPC_ID" \
  --tag-specifications "$(tags security-group $1)" --query GroupId --output text; }
nz "${SG_ALB:-}" || save SG_ALB "$(mk_sg ${APP}-alb-sg "public http/https")"
nz "${SG_APP:-}" || save SG_APP "$(mk_sg ${APP}-app-sg "app from alb")"
nz "${SG_DB:-}"  || save SG_DB  "$(mk_sg ${APP}-db-sg  "db from app")"

step "[5/5] 인바운드 규칙"
MY_IP="$(curl -s https://checkip.amazonaws.com)/32"
auth() { aws ec2 authorize-security-group-ingress --group-id "$1" --ip-permissions "$2" >/dev/null 2>&1 || echo "  (이미 존재) $2"; }
auth "$SG_ALB" "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http}]"
auth "$SG_ALB" "IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description=https}]"
auth "$SG_APP" "IpProtocol=tcp,FromPort=${APP_PORT},ToPort=${APP_PORT},UserIdGroupPairs=[{GroupId=$SG_ALB,Description=alb}]"
auth "$SG_APP" "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MY_IP,Description=admin}]"
auth "$SG_DB"  "IpProtocol=tcp,FromPort=3306,ToPort=3306,UserIdGroupPairs=[{GroupId=$SG_APP,Description=mariadb}]"
auth "$SG_DB"  "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$SG_APP,Description=postgres}]"

echo; echo "네트워크 완료: VPC=$VPC_ID PUB=[$PUB_A,$PUB_C] PRI=[$PRI_A,$PRI_C] SG=[$SG_ALB,$SG_APP,$SG_DB]"
