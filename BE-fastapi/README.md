# BE FastAPI OHLCV Open API

EC2 + Docker / ECS Fargate 배포 실습용 FastAPI 서비스입니다. PostgreSQL의 `ohlcv_daily` 테이블에 수집된 국내 주식 일봉 데이터를 공개 JSON API로 제공합니다. Swagger UI는 `/docs`에서 확인할 수 있습니다.

## 엔드포인트
| 경로 | 용도 |
|---|---|
| `GET /` | 헬로 메시지 |
| `GET /health` | 컨테이너/ALB 기본 헬스체크 |
| `GET /api/v1/ohlcv/{symbol}` | 일별 OHLCV 조회. `start_date`, `end_date`, `limit`(1~1000) 지원 |
| `GET /api/v1/ohlcv/symbols` | OHLCV 데이터가 있는 종목 및 데이터 기간 조회 |
| `GET /api/stocks/list` | 국내 주식 시세 목업. 플랫폼 ALB Target Group 의 헬스체크 경로와 동일 |
| `GET /api/services` | 금융사 서비스 배포 현황 목업 (AG Grid FE 용) |
| `GET /items/{id}`, `POST /items` | CRUD 예시 |
| `GET /docs` | Swagger UI |
| `GET /openapi.json` | OpenAPI 3 명세 JSON |

## PostgreSQL 연결

앱은 `QUANT_DATABASE_URL`을 우선 사용하고, 없으면 `DATABASE_URL`을 사용합니다. 배포 스크립트가 생성하는 SQLAlchemy 형식(`postgresql+psycopg://...`)과 일반 PostgreSQL 형식(`postgresql://...`) 모두 지원합니다.

```bash
export QUANT_DATABASE_URL='postgresql://stock:password@localhost:5432/ohlcv'
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Swagger UI: http://127.0.0.1:8000/docs
curl 'http://127.0.0.1:8000/api/v1/ohlcv/005930?start_date=2026-01-01&limit=30'
```

조회 대상 테이블은 [`../ohlcv-crawler/ohlcv_crawler.py`](../ohlcv-crawler/ohlcv_crawler.py)의 크롤러가 생성·갱신하는 `ohlcv_daily`입니다. 데이터베이스가 설정되지 않았거나 연결할 수 없으면 API는 `503`을 반환합니다.

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
