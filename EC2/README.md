# EC2 실습 가이드

EC2 + VPC + ALB + Auto Scaling 실습을 단계별로 수행할 수 있도록 문서를 재정리했습니다.

## 문서 구성
1. [000_aws_onboarding_lab.md](000_aws_onboarding_lab.md): 회원가입/IAM/MFA/AWS CLI 온보딩
2. [001.md](001.md): VPC/서브넷/IGW/라우팅 기초 (CLI)
3. [002.md](002.md): ALB/Target Group/Listener 구성 (CLI)
4. [003.md](003.md): Launch Template + ASG 운용 점검
5. [004.md](004.md): 콘솔 중심 AMI/Template/ASG 체크리스트
6. [005.md](005.md): 애플리케이션 런타임 준비(JDK/전송)
7. [008.md](008.md): 운영 점검용 조회 명령 모음
8. [010_ami_guide.md](010_ami_guide.md): AMI 저장·검색·사용 가이드

## 실습 전 체크
- AWS 계정 생성 및 결제/본인 인증 완료
- 루트 계정 + IAM 사용자 MFA 활성화 완료
- AWS CLI 인증 완료 (`aws configure`)
- 기본 리전 확정 (예: `ap-northeast-2`)
- 비용 발생 리소스(ALB, NAT, EIP, ECS 서비스) 생성/삭제 계획 수립

## 학습 포인트
- 왜 ALB는 2개 이상의 Subnet(AZ 분산)이 필요한가
- 라우팅(`0.0.0.0/0`)과 IGW 연결 관계
- ASG와 Launch Template 버전 관리 방식
- 보안그룹을 ALB/EC2 역할별로 분리하는 이유

## 주식투자 웹앱 플랫폼 구성에서의 역할

이 폴더의 실습은 루트 README **"AWS 기반 주식투자 웹앱 플랫폼 시스템 구성 (AWS CLI)"** 의 네트워크·앱 계층을 손으로 만들어 보는 단계입니다. 아래 표의 스크립트가 같은 작업을 자동화합니다.

| 실습 문서 | 플랫폼에서 대응되는 것 | 자동화 스크립트 |
|---|---|---|
| [000](000_aws_onboarding_lab.md) 온보딩 | 로드맵 0~3단계 (WSL, CLI, IAM, configure) | — (1회 수동) |
| [001](001.md) VPC/서브넷/IGW | Phase A: `10.20.0.0/16`, 퍼블릭(앱·ALB)/프라이빗(RDS) 2AZ | `deploy/stock-platform/01_network.sh` |
| [002](002.md) ALB/Target Group | Phase D-3: 443 리스너 + 80→443, 헬스체크 `/api/stocks/list` | `deploy/stock-platform/04_ecr_acm_alb.sh` |
| [003](003.md) ASG 운용·Docker 설치 | Phase D-4 의 User Data (Docker + compose 자동 기동), 2대 이상 확장 시 ASG | `deploy/stock-platform/05_app_ec2.sh` |
| [004](004.md) AMI/Template/ASG | Docker 세팅 완료 인스턴스를 AMI 로 저장해 ASG Launch Template 에 사용 | [010_ami_guide.md](010_ami_guide.md) |
| [008](008.md) 운영 점검 CLI | 런북: 타깃 헬스, 인스턴스 상태, SSM 세션 | 루트 README "운영 런북 요약" |
| [009](009_vpc_sg_delete_guide.md) VPC/SG 삭제 | 정리 순서 (DB SG → APP SG → ALB SG) | `deploy/stock-platform/99_cleanup.sh` |

플랫폼 구성에서 EC2 실습과 달라지는 점:
- **SSH 대신 SSM Session Manager / Run Command** — 인스턴스 프로파일에 `AmazonSSMManagedInstanceCore` 가 있어 22번 포트를 닫아도 접속·배포 가능
- **보안그룹은 3계층 참조 규칙** — 앱 SG 의 3000 포트는 ALB SG 에서만, DB SG 의 3306/5432 는 앱 SG 에서만
- **EIP 불필요** — ALB 뒤에 있으므로 고정 IP 가 필요 없음 (직접 노출 실습에서만 EIP 사용)
- **비밀은 인스턴스 안에 두지 않음** — User Data 가 SSM Parameter Store 에서 `.env` 를 생성

## 보안 주의
- 본 폴더의 이미지(`*.png`)는 민감정보 보호를 위해 마스킹 처리되었습니다.
- 문서 예시는 `vpc-xxxxxxxx`, `subnet-xxxxxxxx` 등 마스킹 표기를 사용합니다.


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=EC2+README)
