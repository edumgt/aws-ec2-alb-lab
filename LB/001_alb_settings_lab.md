# LB 실습 01 - ALB 설정과 점검

## 1. ALB vs NLB 선택 기준
| 항목 | ALB | NLB |
|---|---|---|
| 계층 | L7 (HTTP/HTTPS) | L4 (TCP/UDP/TLS) |
| 라우팅 | Host/Path 기반 | 포트/프로토콜 기반 |
| 주요 용도 | 웹/API | 고성능 TCP, 고정 IP 필요 |

## 2. ALB 기본 구성 요소
- Listener: 80/443 포트에서 요청 수신
- Rule: host/path 조건 기반 분기
- Target Group: 실제 백엔드(EC2 IP/Task IP)

## 3. 실습 체크리스트
1. ALB를 Public Subnet 2개 이상에 배치
2. ALB SG에 80/443 인바운드 허용
3. Target Group 헬스체크 경로 지정 (`/health`)
4. EC2/ECS SG에서 ALB SG Source 허용

## 4. 점검 명령
```bash
aws elbv2 describe-load-balancers --names <ALB_NAME>
aws elbv2 describe-listeners --load-balancer-arn <ALB_ARN>
aws elbv2 describe-rules --listener-arn <LISTENER_ARN>
aws elbv2 describe-target-health --target-group-arn <TG_ARN>
```

## 5. 자주 발생하는 문제
- 503: Target 불건강 또는 등록 없음
- Timeout: 보안그룹, NACL, 라우팅 미설정
- 잘못된 라우팅: Listener Rule 우선순위 충돌

## 6. 권장 운영 규칙
- 헬스체크 엔드포인트는 앱 비즈니스 로직과 분리
- `deregistration_delay`를 워크로드에 맞춰 조정
- 배포 전/후 Target Health를 자동 확인하도록 스크립트화


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
