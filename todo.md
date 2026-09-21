# AWS EC2 / KOSPI OHLCV 구축 작업 기록

## 완료 항목

- [x] AWS S3 목록 조회 명령 정리: `aws-s3-list-commands.md`
- [x] Ubuntu 24.04 EC2 생성
  - 인스턴스 ID: `i-094c4b0496cdfcb57`
  - 사양: `t3.medium` (2 vCPU, 4 GiB)
  - 루트 볼륨: gp3 SSD 30 GiB
  - 보안 그룹: `myFw2`
  - 키 페어: `test-0916`
  - SSH: `ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ubuntu@52.78.51.190`

- [x] OHLCV 수집 서버 접속 확인
  - 서버: `54.116.203.151`
  - SSH 사용자: `ec2-user`
  - SSH: `ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151`

- [x] Docker 기반 PostgreSQL 구성
  - 컨테이너: `stock-postgres`
  - 이미지: `postgres:16-alpine`
  - Docker 네트워크: `stock-network`
  - 영속 볼륨: `stock-postgres-data`
  - 데이터베이스: `ohlcv`
  - DB 사용자: `stock`
  - DB 비밀번호: `stock1234!!`
  - PostgreSQL은 외부 포트를 노출하지 않고 Docker 네트워크 내부에서만 접근

- [x] KOSPI 주요 종목 일봉 OHLCV 크롤러 구현 및 배포
  - 원본 소스: `ohlcv-crawler/ohlcv_crawler.py`
  - 서버 경로: `/home/ec2-user/ohlcv-crawler/ohlcv_crawler.py`
  - Docker 이미지: `ohlcv-crawler:1.1`
  - 데이터 소스: Naver 금융 일봉 API
  - 적재 테이블: `ohlcv_daily`
  - 적재 필드:
    - `symbol`, `company_name`, `trade_date`
    - `open_price`, `high_price`, `low_price`, `close_price`, `volume`
    - `foreign_ownership_pct`, `change_rate_pct`
    - `data_source`, `collected_at`
  - 중복 기준: `(symbol, trade_date)` primary key / upsert

- [x] 대표 KOSPI 10종목 초기 배치 실행
  - 종목: 삼성전자(005930), SK하이닉스(000660), LG에너지솔루션(373220), 삼성바이오로직스(207940), 현대차(005380), 기아(000270), 셀트리온(068270), KB금융(105560), NAVER(035420), 신한지주(055550)
  - 적재 결과: 10종목, 1,750건
  - 수집 날짜 범위: 2026-01-02 ~ 2026-09-17

- [x] 10분 주기 cron 배치 등록
  - cron 설정 원본: `ohlcv-crawler/cron.ohlcv`
  - 서버 배치 스크립트: `/home/ec2-user/ohlcv-crawler/run_kospi_batch.sh`
  - 실행 주기: `*/10 * * * *`
  - 동시 실행 방지: `/usr/bin/flock -n /tmp/ohlcv-kospi.lock`
  - 로그: `/home/ec2-user/ohlcv-crawler/logs/kospi-batch.log`
  - 서비스: `crond` 활성화 완료

- [x] PostgreSQL OHLCV Open API 및 Swagger 배포 (2026-09-18)
  - 소스: `BE-fastapi/`
  - Docker 이미지: `be-fastapi:20260918-ohlcv`
  - 실행 컨테이너: `be-fastapi` (`0.0.0.0:8000 -> 8000`)
  - Docker 네트워크: `stock-network` (`stock-postgres`와 동일 네트워크)
  - DB 연결: 컨테이너 환경 변수 `DATABASE_URL`로 `ohlcv` DB 연결
  - OpenAPI/Swagger:
    - `GET /docs` — Swagger UI
    - `GET /openapi.json` — OpenAPI 3 명세
    - `GET /api/v1/ohlcv/{symbol}` — 일봉 OHLCV 조회 (`start_date`, `end_date`, `limit` 지원)
    - `GET /api/v1/ohlcv/symbols` — 수집 종목과 데이터 보유 기간 조회
  - 검증 완료: 헬스체크, `005930` OHLCV 조회, 종목 목록, OpenAPI 명세
  - 롤백용 기존 컨테이너 보관: `be-fastapi-previous-20260918` (중지 상태)

## 2026-09-21 — API 경로·HTTPS·FE 분리 반영

- [x] FastAPI의 모든 공개 경로를 `/api` 아래로 통일
  - Swagger UI: `https://rag.edumgt.co.kr/api/docs`
  - ReDoc: `https://rag.edumgt.co.kr/api/redoc`
  - OpenAPI JSON: `https://rag.edumgt.co.kr/api/openapi.json`
  - 헬스체크: `GET /api/health`
  - 아이템: `GET /api/items/{item_id}`, `POST /api/items`
  - Swagger OAuth redirect도 `/api/docs/oauth2-redirect`로 설정
- [x] EC2의 `rag-caddy`를 Docker `stock-network`에 연결
  - Caddy가 호스트 포트 `80/443`과 TLS를 담당
  - `/api/*` 요청만 `be-fastapi:8000`으로 프록시
  - FastAPI `8000`은 Docker 내부 포트만 사용하며 호스트에 공개하지 않음
- [x] EC2 Docker의 FE 제거
  - 실행 중이던 `fe-ag-grid`와 중지된 `fe-ag-grid-http-backup` 컨테이너 제거
  - 사용하지 않는 `ohlcv-fe:20260918` 이미지 제거
  - FE는 `rf.edumgt.co.kr`의 S3/CloudFront 정적 호스팅으로만 제공
- [x] CORS 허용 Origin 설정 및 EC2 배포
  - `https://rag.edumgt.co.kr`
  - `https://rf.edumgt.co.kr`
  - `http://rf.edumgt.co.kr`
  - `http(s)://localhost:<port>`, `http(s)://127.0.0.1:<port>`
- [x] 외부 HTTPS 검증
  - `/api/docs`, `/api/openapi.json`, `/api/health`, `/api/items/1`이 `200` 응답

## rf.edumgt.co.kr CloudFront HTTPS 작업

- [ ] CloudFront·ACM·Route 53 권한이 있는 AWS 역할/프로필 준비
  - 현재 IAM 사용자 `ec2-user`는 `cloudfront:ListDistributions`, `acm:ListCertificates`, `route53:ListHostedZonesByName` 권한이 없어 작업이 차단됨
- [ ] `us-east-1`에서 `rf.edumgt.co.kr` ACM 공개 인증서 요청
- [ ] ACM DNS 검증용 CNAME 레코드를 Route 53 `edumgt.co.kr` 호스팅 존에 생성하고 인증서 발급 완료 확인
- [ ] S3 버킷 `rf.edumgt.co.kr`을 오리진으로 사용하는 CloudFront 배포를 생성하거나 기존 배포를 수정
  - Alternate domain name: `rf.edumgt.co.kr`
  - Viewer certificate: 발급된 `us-east-1` ACM 인증서
  - Viewer protocol policy: `Redirect HTTP to HTTPS`
  - 정적 파일 배포 후 CloudFront invalidation 수행
- [ ] Route 53 `rf.edumgt.co.kr` A/AAAA Alias 레코드를 CloudFront 배포로 연결
- [ ] `https://rf.edumgt.co.kr` 접속 및 `https://rag.edumgt.co.kr/api/health` CORS 호출 검증

## 운영 명령

### 배치 수동 실행

```bash
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 \
  '/home/ec2-user/ohlcv-crawler/run_kospi_batch.sh'
```

### cron 설정 확인

```bash
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 'crontab -l'
```

### 배치 로그 확인

```bash
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 \
  'tail -f /home/ec2-user/ohlcv-crawler/logs/kospi-batch.log'
```

### PostgreSQL 접속

```bash
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 \
  'docker exec -it stock-postgres psql -U stock -d ohlcv'
```

### 최근 적재 데이터 조회

```sql
SELECT symbol, company_name, trade_date, close_price, volume
FROM ohlcv_daily
ORDER BY trade_date DESC, symbol;
```

### OHLCV Open API 확인

```bash
# Swagger UI / API health (EC2의 8000 포트는 외부 비공개)
curl -I https://rag.edumgt.co.kr/api/docs
curl https://rag.edumgt.co.kr/api/health

# 삼성전자 일봉 30건 조회
curl 'https://rag.edumgt.co.kr/api/v1/ohlcv/005930?limit=30'

# 제공 종목 목록 조회
curl https://rag.edumgt.co.kr/api/v1/ohlcv/symbols
```

### API 컨테이너 상태 및 롤백

```bash
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 \
  'docker ps -a --filter name=be-fastapi'

# 현재 컨테이너를 중지하고 보관한 이전 버전을 재시작하는 롤백 절차
ssh -i /home/ubuntu/aws-ec2-alb-lab/test-0916.key ec2-user@54.116.203.151 \
  'docker stop be-fastapi && docker rename be-fastapi be-fastapi-failed && docker rename be-fastapi-previous-20260918 be-fastapi && docker start be-fastapi'
```

## 추후 작업 후보

- [ ] 종목 유니버스를 시가총액 기준으로 자동 갱신
- [ ] 수집 실패 알림 및 모니터링 추가
- [ ] 일봉 외 분봉 데이터 수집 필요 여부 검토
- [ ] DB 백업 및 보존 정책 설정


## DB 접속

Host: 54.116.203.151
Port: 5432
Database: ohlcv
User: stock
Password: stock1234!!
