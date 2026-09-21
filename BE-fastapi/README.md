# BE FastAPI OHLCV Open API

EC2 + Docker / ECS Fargate 배포 실습용 FastAPI 서비스입니다. PostgreSQL의 `ohlcv_daily` 테이블에 수집된 국내 주식 일봉 데이터를 공개 JSON API로 제공합니다. 모든 API 경로는 `/api`로 시작하며 Swagger UI는 `/api/docs`에서 확인할 수 있습니다.

## 엔드포인트
| 경로 | 용도 |
|---|---|
| `GET /api` | 헬로 메시지 |
| `GET /api/health` | 컨테이너/프록시 기본 헬스체크 |
| `GET /api/v1/ohlcv/{symbol}` | 일별 OHLCV 조회. `start_date`, `end_date`, `limit`(1~1000) 지원 |
| `GET /api/v1/ohlcv/symbols` | OHLCV 데이터가 있는 종목 및 데이터 기간 조회 |
| `GET /api/stocks/list` | 국내 주식 시세 목업. 플랫폼 ALB Target Group 의 헬스체크 경로와 동일 |
| `GET /api/services` | 금융사 서비스 배포 현황 목업 (AG Grid FE 용) |
| `GET /api/items/{id}`, `POST /api/items` | CRUD 예시 |
| `GET /api/docs` | Swagger UI |
| `GET /api/openapi.json` | OpenAPI 3 명세 JSON |

## PostgreSQL 연결

앱은 `QUANT_DATABASE_URL`을 우선 사용하고, 없으면 `DATABASE_URL`을 사용합니다. 배포 스크립트가 생성하는 SQLAlchemy 형식(`postgresql+psycopg://...`)과 일반 PostgreSQL 형식(`postgresql://...`) 모두 지원합니다.

```bash
export QUANT_DATABASE_URL='postgresql://stock:password@localhost:5432/ohlcv'
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Swagger UI: http://127.0.0.1:8000/api/docs
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
rf.edumgt.co.kr (S3/CloudFront 정적 FE) ── API 요청 ──► rag.edumgt.co.kr (EC2 Docker:443/TLS) ─► Nginx 프록시 ─► 이 컨테이너 (:8000, Docker 내부 전용)
```

- EC2에는 이 백엔드 컨테이너만 실행합니다. 프론트엔드는 `rf.edumgt.co.kr`의 S3/CloudFront 정적 호스팅으로 제공합니다.
- 호스트에는 HTTPS 포트 `443`만 공개합니다. FastAPI의 `8000`은 Docker 네트워크 내부에서만 사용합니다. `rag.edumgt.co.kr/api/docs`에서 Swagger UI를 제공합니다.
- ECR 푸시: `bash deploy/ecr-push-be.sh` 또는 `IMAGE_TAG=v1 bash deploy/ecr-push-be.sh`
- 실제 서비스 백엔드(Flask, MariaDB/PostgreSQL 연동)는 `stock-coin-trade` 저장소의 `python-stock-backend` 이며, 동일한 `/api/stocks/list` 계약을 제공합니다.

## 관련 문서
- 루트 README → "AWS 기반 주식투자 웹앱 플랫폼 시스템 구성 (AWS CLI)"
- [ECS/004_docker_ecr_ecs_pipeline.md](../ECS/004_docker_ecr_ecs_pipeline.md) — Docker → ECR → ECS
- [ECS/005_stock_platform_fargate.md](../ECS/005_stock_platform_fargate.md) — 백엔드를 Fargate 로 옮기기
