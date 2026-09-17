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