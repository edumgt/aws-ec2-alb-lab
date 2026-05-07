# AWS ECS + Fargate 핵심 요약

## 1. ECS와 Fargate의 관계
- ECS: 컨테이너 오케스트레이션 서비스
- Fargate: ECS에서 서버 관리 없이 컨테이너를 실행하는 런타임

즉, ECS는 제어 평면이고 Fargate는 실행 방식입니다.

## 2. 주요 구성요소
- Cluster: 서비스가 배치되는 논리 단위
- Task Definition: CPU/Memory/Image/Port/Env 정의
- Task: 실제 실행 컨테이너
- Service: Task 개수 유지, 롤링 업데이트
- ALB/NLB: 외부 트래픽 진입점
- ECR: 이미지 저장소
- IAM Role: Task 실행 권한, 앱 권한

## 3. Fargate 필수 포인트
- `requiresCompatibilities: ["FARGATE"]`
- 네트워크 모드 `awsvpc` 필수
- Target Group은 보통 `ip` 타입 사용
- 서브넷/보안그룹 설계가 서비스 안정성에 직접 영향

## 4. ECS on EC2 vs ECS on Fargate
| 항목 | ECS on EC2 | ECS on Fargate |
|---|---|---|
| 서버 운영 | 직접 관리 | AWS 관리 |
| 제어 범위 | 높음 | 상대적으로 제한 |
| 운영 난이도 | 높음 | 낮음 |
| 비용 특성 | 상시 대규모에 유리 가능 | 변동/소규모에 유리 가능 |

## 5. 실무 배포 흐름
1. 앱 이미지 빌드
2. ECR Push
3. Task Definition 새 리비전 등록
4. ECS Service 업데이트
5. ALB 헬스체크/트래픽 전환 확인
6. CloudWatch 로그 점검 및 필요 시 롤백

## 6. 반드시 체크할 보안/운영 항목
- 최소 권한 IAM Role
- 태스크 로그 표준화(`/ecs/<service-name>`)
- 헬스체크 경로(`/health`) 분리
- 배포 실패 시 이전 리비전 롤백 절차 문서화


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
