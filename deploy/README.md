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


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
