# ECS 학습 가이드

ECS/Fargate 실습과 스터디를 위한 문서 모음입니다.

## 문서 순서
1. [aws_ecs_fargate_summary.md](aws_ecs_fargate_summary.md)
2. [001_fargate_hands_on.md](001_fargate_hands_on.md)
3. [002_ecs_alb_lab.md](002_ecs_alb_lab.md)
4. [003_study_checklist.md](003_study_checklist.md)
5. [004_docker_ecr_ecs_pipeline.md](004_docker_ecr_ecs_pipeline.md) — Docker → ECR → ECS 전체 배포 파이프라인

## 주식투자 웹앱 플랫폼 구성에서의 역할

루트 README 의 플랫폼 구성은 **Stage 1~3 까지 EC2 + Docker Compose** 로 백엔드를 운영합니다. 트래픽이 늘어 인스턴스 2대 이상·무중단 배포가 필요해지면 이 폴더의 ECS Fargate 실습이 **Stage 4** 가 됩니다.

| 문서 | 플랫폼 적용 |
|---|---|
| [001](001_fargate_hands_on.md) Fargate 핸즈온 | 백엔드 컨테이너(`stock-coin-trade-python-backend`)를 Task 로 실행 |
| [002](002_ecs_alb_lab.md) ECS + ALB | 기존 플랫폼 ALB 의 `/api/*` 를 EC2 타깃 그룹에서 Fargate `ip` 타깃 그룹으로 전환 |
| [004](004_docker_ecr_ecs_pipeline.md) Docker → ECR → ECS | GitHub Actions `deploy-ecs-aws-cli.yml` 로 태스크 정의 갱신 |
| [005](005_stock_platform_fargate.md) **플랫폼 백엔드 Fargate 전환** | RDS·SSM 연동, Task Role, 서비스 오토스케일링까지 포함한 전환 절차 |

## 실습 목표
- ECS on Fargate 핵심 구성요소 이해
- ECR 이미지 기반 서비스 배포
- Docker build → ECR push → ECS 배포 파이프라인 이해
- ALB와 ECS Service 연동
- CloudWatch 로그/헬스체크 기반 점검


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=ECS+README)
