# AG Grid Static App

Nginx 나 S3 에 그대로 올릴 수 있는 바닐라 HTML/CSS/JS 기반 AG Grid 대시보드입니다.  
**주식투자 웹앱 플랫폼 구성**(루트 README) 에서는 S3 + CloudFront 로 서비스되는 정적 프론트엔드 자리에 들어가는 샘플입니다.

## 파일 구성
- `index.html`: CDN 으로 AG Grid 를 불러오는 진입점
- `config.js`: **런타임 설정** — API 기본 주소(`apiBase`). 빌드 없이 환경별로 교체
- `app.js`: OHLCV 그리드, 종목명/종목코드 검색, 기간 조회 로직
- `styles.css`: 대시보드 스타일
- `Dockerfile`: `nginx:alpine` 에 정적 파일 복사 (ECR `fe-test` 이미지)

## API 주소 설정 (`config.js`)

| 배포 형태 | `apiBase` | 이유 |
|---|---|---|
| 현재 공개 OHLCV API | `"https://rag.edumgt.co.kr"` | HTTPS로 종목 목록과 OHLCV 일봉을 직접 조회 |
| CloudFront 동일 도메인 (플랫폼 구성) | `""` | CloudFront 가 API 경로를 ALB 로 넘기는 경우 |
| 로컬 개발 | `"http://127.0.0.1:8000"` | `uvicorn` 로컬 백엔드 |

## 로컬 확인
```bash
cd ag-grid-app
python3 -m http.server 8080      # http://127.0.0.1:8080
```

## 배포 방법 3가지

```bash
# 1) S3 + CloudFront (플랫폼 구성, deploy/stock-platform/06_frontend_cdn.sh 가 수행)
aws s3 sync . "s3://${FE_BUCKET}/" --delete --exclude Dockerfile --exclude README.md --cache-control "max-age=300"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*"

# 2) ECR 이미지 (Nginx 컨테이너, EC2/ECS 용)
docker build -t fe-test:latest . && bash ../deploy/ecr-push-be.sh

# 3) EC2 Nginx 에 직접 복사
sudo cp -r . /var/www/html/ag-grid-app/ && sudo systemctl reload nginx
```

## 관련 문서
- 루트 README → "AWS 기반 주식투자 웹앱 플랫폼 시스템 구성" Phase E (S3 + CloudFront 오리진 2개)
- [deploy/stock-platform/README.md](../deploy/stock-platform/README.md)
