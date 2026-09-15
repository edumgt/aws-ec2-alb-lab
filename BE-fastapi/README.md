# BE FastAPI Docker 샘플

EC2 + Docker / ECS Fargate 배포 실습용 FastAPI 서비스이자, **주식투자 웹앱 플랫폼 구성**(루트 README) 에서 실제 Flask 백엔드 대신 끼워 넣어 인프라를 먼저 검증할 수 있는 대역(stand-in) 백엔드입니다.

## 엔드포인트
| 경로 | 용도 |
|---|---|
| `GET /` | 헬로 메시지 |
| `GET /health` | 컨테이너/ALB 기본 헬스체크 |
| `GET /api/stocks/list` | 국내 주식 시세 목업. 플랫폼 ALB Target Group 의 헬스체크 경로와 동일 |
| `GET /api/services` | 금융사 서비스 배포 현황 목업 (AG Grid FE 용) |
| `GET /items/{id}`, `POST /items` | CRUD 예시 |
| `GET /docs` | Swagger UI |

## 로컬 실행
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker 실행
```bash
docker build -t be-test:latest .
docker run --rm -p 8000:8000 be-test:latest
curl http://127.0.0.1:8000/api/stocks/list
```

## 주식투자 플랫폼에서의 위치

```
CloudFront (/api/*) ─► ALB:443 ─► EC2:${APP_PORT} ─► 이 컨테이너 (:8000)
```

- 플랫폼 스크립트(`deploy/stock-platform/`) 로 만든 인프라에 이 이미지를 올려 검증하려면 `env.sh` 에서 `APP_PORT=8000`, `BE_REPO=be-test` 로 설정합니다.
- ECR 푸시: `bash deploy/ecr-push-be.sh` 또는 `IMAGE_TAG=v1 bash deploy/ecr-push-be.sh`
- 실제 서비스 백엔드(Flask, MariaDB/PostgreSQL 연동)는 `stock-coin-trade` 저장소의 `python-stock-backend` 이며, 동일한 `/api/stocks/list` 계약을 제공합니다.

## 관련 문서
- 루트 README → "AWS 기반 주식투자 웹앱 플랫폼 시스템 구성 (AWS CLI)"
- [ECS/004_docker_ecr_ecs_pipeline.md](../ECS/004_docker_ecr_ecs_pipeline.md) — Docker → ECR → ECS
- [ECS/005_stock_platform_fargate.md](../ECS/005_stock_platform_fargate.md) — 백엔드를 Fargate 로 옮기기
