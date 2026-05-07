# FastAPI 프레임워크에서 FastAPI 클래스를 임포트합니다
from fastapi import FastAPI

# FastAPI 애플리케이션 인스턴스를 생성합니다
# title: Swagger UI / OpenAPI 문서에 표시될 서비스 이름
# version: API 버전 정보 (OpenAPI 스펙에 포함됨)
app = FastAPI(title="BE FastAPI Hello", version="1.0.0")


# HTTP GET 메서드로 루트 경로("/")를 처리하는 엔드포인트를 등록합니다
@app.get("/")
def hello_world() -> dict[str, str]:  # 반환 타입: 문자열 키-값 딕셔너리 (JSON으로 자동 직렬화)
    # "hello world" 메시지를 담은 JSON 응답을 반환합니다
    return {"message": "hello world"}


# HTTP GET 메서드로 헬스체크 경로("/health")를 처리하는 엔드포인트를 등록합니다
# ALB(Application Load Balancer) 또는 컨테이너 오케스트레이터(ECS, K8s)의 헬스체크에 활용됩니다
@app.get("/health")
def health_check() -> dict[str, str]:  # 반환 타입: 문자열 키-값 딕셔너리 (JSON으로 자동 직렬화)
    # 서비스가 정상 동작 중임을 나타내는 "ok" 상태값을 반환합니다
    return {"status": "ok"}
