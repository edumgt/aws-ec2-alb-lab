"""AWS AI Lab FastAPI 애플리케이션.

8개 AWS AI 서비스 + Financial RAG를 REST API로 노출하고,
Vanilla JS / Tailwind CSS 기반 웹 프론트엔드를 제공합니다.

실행 방법:
    uvicorn app.main:app --reload --port 8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import (
    bedrock,
    comprehend,
    financial_rag,
    lex,
    polly,
    rekognition,
    textract,
    transcribe,
)

app = FastAPI(
    title="AWS AI Lab API",
    version="1.0.0",
    description="8개 AWS AI 서비스를 웹에서 테스트하는 FastAPI 백엔드",
)

# 개발 편의를 위해 CORS를 전체 허용합니다 (프로덕션에서는 origins를 제한하세요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(bedrock.router, prefix="/api/bedrock", tags=["Bedrock"])
app.include_router(comprehend.router, prefix="/api/comprehend", tags=["Comprehend"])
app.include_router(rekognition.router, prefix="/api/rekognition", tags=["Rekognition"])
app.include_router(textract.router, prefix="/api/textract", tags=["Textract"])
app.include_router(polly.router, prefix="/api/polly", tags=["Polly"])
app.include_router(transcribe.router, prefix="/api/transcribe", tags=["Transcribe"])
app.include_router(lex.router, prefix="/api/lex", tags=["Lex"])
app.include_router(financial_rag.router, prefix="/api/rag", tags=["Financial RAG"])

# 정적 파일 서빙 (프론트엔드 assets)
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Vanilla JS / Tailwind 프론트엔드 SPA를 반환합니다."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """ALB / ECS 헬스체크용 엔드포인트."""
    return {"status": "ok"}
