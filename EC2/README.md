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

## 보안 주의
- 본 폴더의 이미지(`*.png`)는 민감정보 보호를 위해 마스킹 처리되었습니다.
- 문서 예시는 `vpc-xxxxxxxx`, `subnet-xxxxxxxx` 등 마스킹 표기를 사용합니다.


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
