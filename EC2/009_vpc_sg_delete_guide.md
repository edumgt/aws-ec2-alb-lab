# VPC · 보안그룹 삭제 불가 해결 가이드

---
# AWS VPC, Security Group, Subnet 삭제 불가 문제 해결 가이드

AWS에서 **VPC, Security Group(SG), Subnet**이 서로 얽혀 있어서 삭제가 안 되는 경우는 의존성(Dependency) 때문입니다.  
삭제하려면 의존성을 하나씩 끊어줘야 합니다.

---

## 🔑 주요 원인
- **Subnet**: VPC에 속해 있으며 Route Table, NAT Gateway, Network ACL 등과 연결되어 있으면 삭제 불가
- **Security Group**: EC2 인스턴스, ENI(Network Interface), Load Balancer 등에 연결되어 있으면 삭제 불가
- **VPC**: Subnet, Internet Gateway, Route Table, SG 등이 남아 있으면 삭제 불가

---

## 🛠️ 해결 순서
1. **EC2 인스턴스 종료**  
   Subnet과 SG가 연결된 인스턴스를 먼저 종료 및 삭제

2. **ENI(Network Interface) 삭제**  
   EC2 종료 후에도 ENI가 남아 있으면 SG와 Subnet 삭제가 막힘

3. **Security Group 삭제**  
   다른 리소스와 연결이 없는지 확인 후 제거

4. **Subnet 삭제**  
   Route Table, NAT Gateway, Elastic IP 연결 해제 후 삭제

5. **Internet Gateway Detach & 삭제**  
   VPC에 붙어 있는 IGW를 먼저 Detach한 뒤 삭제

6. **VPC 삭제**  
   모든 의존성이 제거된 후 최종적으로 VPC 삭제 가능

---

## 💡 팁
- AWS 콘솔에서 **Dependencies 에러 메시지**를 확인하면 어떤 리소스가 막고 있는지 바로 알 수 있음
- CLI를 활용하면 추적이 편리함:
  ```bash
  aws ec2 describe-network-interfaces
  aws ec2 describe-security-groups
  aws ec2 describe-subnets

---

## 문제 상황

커스텀 VPC 를 삭제하려 할 때 아래 세 리소스가 서로 맞물려 삭제가 되지 않는 경우입니다.

```
vpc-043c4f8e25ef17ecd  (커스텀 VPC)
 ├── sg-0ca9fab790df712a8  default SG        ← VPC 삭제 전까지 삭제 불가 (default SG)
 │     └─ 인바운드 규칙: tcp 20-1024  from  sg-0d4f02b696b295f4a  ← SG 간 참조
 └── sg-0d4f02b696b295f4a  nginx-alb-sg      ← default SG 가 참조 중이라 삭제 불가
```

### 왜 삭제가 안 되는가?

| 리소스 | 삭제 시도 결과 | 이유 |
|---|---|---|
| `nginx-alb-sg` | `DependencyViolation` | default SG 인바운드 규칙이 이 SG를 source 로 참조 중 |
| `default SG` | `CannotDelete` | VPC 의 default SG 는 VPC 가 살아있는 한 삭제 불가 |
| `VPC` | `DependencyViolation` | nginx-alb-sg (non-default SG) 가 아직 존재 |

→ **세 리소스가 순환 참조 형태**로 잠겨 있음

---

## 해결 원칙

> **SG 간 참조 규칙만 먼저 제거하면 순환이 풀린다.**

```
① default SG 의 인바운드 규칙 중 nginx-alb-sg 를 source 로 쓰는 규칙 삭제
   → nginx-alb-sg 를 아무도 참조하지 않는 상태가 됨

② nginx-alb-sg 삭제
   → VPC 내 non-default SG 가 모두 제거됨

③ VPC 삭제
   → default SG, 라우팅 테이블 자동 삭제
```

---

## 단계별 실행 명령

### 사전 확인 - 참조 규칙 조회

```bash
REGION=ap-northeast-2

# default SG 의 인바운드 규칙 확인
aws ec2 describe-security-groups \
  --group-ids sg-0ca9fab790df712a8 \
  --region $REGION \
  --query 'SecurityGroups[0].IpPermissions'
```

출력 예시 (삭제 대상 규칙):
```json
{
  "IpProtocol": "tcp",
  "FromPort": 20,
  "ToPort": 1024,
  "UserIdGroupPairs": [
    {
      "Description": "sg-1",
      "UserId": "086015456585",
      "GroupId": "sg-0d4f02b696b295f4a"
    }
  ]
}
```

---

### 1단계 - default SG 의 SG 참조 인바운드 규칙 제거

```bash
aws ec2 revoke-security-group-ingress \
  --group-id sg-0ca9fab790df712a8 \
  --ip-permissions '[{
    "IpProtocol": "tcp",
    "FromPort": 20,
    "ToPort": 1024,
    "UserIdGroupPairs": [{
      "UserId": "086015456585",
      "GroupId": "sg-0d4f02b696b295f4a"
    }]
  }]' \
  --region ap-northeast-2
```

> **포인트**: CIDR(`IpRanges`) 이 아니라 `UserIdGroupPairs` 로 지정해야 정확히 해당 규칙만 삭제됩니다.

확인:
```bash
aws ec2 describe-security-groups \
  --group-ids sg-0ca9fab790df712a8 \
  --region ap-northeast-2 \
  --query 'SecurityGroups[0].IpPermissions[?UserIdGroupPairs[0].GroupId==`sg-0d4f02b696b295f4a`]'
# 빈 배열 [] 이면 참조 제거 완료
```

---

### 2단계 - nginx-alb-sg 삭제

```bash
aws ec2 delete-security-group \
  --group-id sg-0d4f02b696b295f4a \
  --region ap-northeast-2
```

오류 없이 완료되면 성공입니다.

---

### 3단계 - VPC 삭제

```bash
aws ec2 delete-vpc \
  --vpc-id vpc-043c4f8e25ef17ecd \
  --region ap-northeast-2
```

VPC 삭제 시 **자동으로 함께 삭제**되는 리소스:
- default SG (`sg-0ca9fab790df712a8`)
- 메인 라우팅 테이블 (`rtb-063fae0e8f79e8d6f`)
- DHCP 옵션 세트 연결

---

### 4단계 - default VPC 내 커스텀 서브넷 삭제 (선택)

커스텀 서브넷이 default VPC 에 남아 있는 경우 별도 삭제합니다.

```bash
# test-svnet
aws ec2 delete-subnet \
  --subnet-id subnet-0e23866dad8a8ebc3 \
  --region ap-northeast-2

# daegu-2
aws ec2 delete-subnet \
  --subnet-id subnet-0f92e122ce4579a81 \
  --region ap-northeast-2
```

---

## 자주 발생하는 오류 메시지

| 오류 | 원인 | 해결 |
|---|---|---|
| `DependencyViolation: resource sg-xxx has a dependent object` | 다른 SG 규칙이 이 SG 를 source 로 참조 중 | 참조하는 SG 의 인바운드/아웃바운드 규칙 먼저 제거 |
| `CannotDelete: the specified group cannot be deleted` | default SG 직접 삭제 시도 | VPC 삭제로 함께 제거 — 직접 삭제 불가 |
| `DependencyViolation` (VPC 삭제 시) | non-default SG, 서브넷, ENI, IGW 등이 잔존 | 각 리소스를 순서대로 먼저 삭제 |
| `InvalidGroup.NotFound` | 이미 삭제된 SG ID 지정 | 리소스 재조회 후 진행 |

---

## 삭제 전 의존관계 파악 명령 모음

```bash
REGION=ap-northeast-2
VPC_ID=vpc-043c4f8e25ef17ecd

# 커스텀 VPC 내 전체 리소스 한번에 확인
echo "-- 인스턴스 --"
aws ec2 describe-instances --region $REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name]' --output table

echo "-- 서브넷 --"
aws ec2 describe-subnets --region $REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[*].[SubnetId,CidrBlock]' --output table

echo "-- 보안그룹 --"
aws ec2 describe-security-groups --region $REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[*].[GroupId,GroupName]' --output table

echo "-- 네트워크 인터페이스 --"
aws ec2 describe-network-interfaces --region $REGION \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'NetworkInterfaces[*].[NetworkInterfaceId,Status,Description]' --output table

echo "-- 인터넷 게이트웨이 --"
aws ec2 describe-internet-gateways --region $REGION \
  --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
  --query 'InternetGateways[*].[InternetGatewayId]' --output table

echo "-- NAT 게이트웨이 --"
aws ec2 describe-nat-gateways --region $REGION \
  --filter "Name=vpc-id,Values=$VPC_ID" \
  --query 'NatGateways[*].[NatGatewayId,State]' --output table

echo "-- ALB --"
aws elbv2 describe-load-balancers --region $REGION \
  --query "LoadBalancers[?VpcId=='$VPC_ID'].[LoadBalancerName,LoadBalancerArn]" --output table
```

---

## 일반적인 VPC 삭제 순서 (참고)

복잡한 환경에서 VPC 를 완전히 삭제할 때의 권장 순서입니다.

```
1. EC2 인스턴스 종료 (terminate)
2. ECS 서비스/태스크 중지 및 삭제
3. ALB/NLB 삭제
4. Target Group 삭제
5. RDS / ElastiCache 삭제
6. NAT 게이트웨이 삭제 → Elastic IP 해제
7. 네트워크 인터페이스(ENI) 삭제
8. VPC 엔드포인트 삭제
9. SG 간 참조 규칙 제거
10. non-default 보안그룹 삭제
11. 서브넷 삭제
12. 인터넷 게이트웨이 분리(detach) → 삭제
13. 라우팅 테이블(non-main) 삭제
14. VPC 삭제 (main RT, default SG 자동 삭제)
```
