// 런타임 설정. 빌드 없이 배포 환경별로 이 파일만 교체합니다.
//  - CloudFront 뒤에서 /api/* 가 ALB 로 라우팅되는 플랫폼 구성: apiBase = ""  (상대 경로 /api/...)
//  - HTTPS 공개 OHLCV API: apiBase = "https://rag.edumgt.co.kr"
window.APP_CONFIG = {
  apiBase: "https://rag.edumgt.co.kr",
};
