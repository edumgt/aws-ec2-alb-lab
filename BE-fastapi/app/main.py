from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(
    title="BE FastAPI Hello",
    version="1.0.0",
    description="""
## BE FastAPI Hello API

EC2 + Docker 배포 실습용 FastAPI 서비스입니다.

### 엔드포인트
- **GET /** — 헬로 메시지
- **GET /health** — ALB 헬스체크
- **GET /api/services** — 서비스 배포 현황 목록 (AG Grid 목업)
- **GET /items/{item_id}** — 아이템 조회
- **POST /items** — 아이템 생성
""",
    contact={"name": "kdy", "email": "kimdypm@gmail.com"},
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response / Request 모델 ────────────────────────────────────────────

class ServiceRow(BaseModel):
    service: str
    region: str
    owner: str
    status: str
    progress: int
    instances: int
    traffic: int
    updatedAt: str


class MessageResponse(BaseModel):
    message: str = Field(..., example="hello world")


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")


class Item(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="노트북")
    price: float = Field(..., gt=0, example=1_200_000)
    in_stock: bool = Field(default=True, example=True)


class ItemResponse(Item):
    id: int = Field(..., example=1)


# ── 엔드포인트 ────────────────────────────────────────────────────────

_services: List[dict] = [
    {"service": "edge-auth",        "region": "ap-northeast-2", "owner": "Platform",   "status": "Healthy",  "progress": 96, "instances": 4, "traffic": 18420, "updatedAt": "2026-04-02 09:12"},
    {"service": "billing-api",      "region": "ap-northeast-2", "owner": "Payments",   "status": "Warning",  "progress": 72, "instances": 2, "traffic": 9480,  "updatedAt": "2026-04-02 09:08"},
    {"service": "ops-admin",        "region": "ap-northeast-2", "owner": "Core Web",   "status": "Healthy",  "progress": 88, "instances": 3, "traffic": 5260,  "updatedAt": "2026-04-02 08:55"},
    {"service": "report-sync",      "region": "ap-northeast-2", "owner": "Data",       "status": "Critical", "progress": 41, "instances": 1, "traffic": 1120,  "updatedAt": "2026-04-02 08:47"},
    {"service": "cdn-warmup",       "region": "ap-northeast-2", "owner": "SRE",        "status": "Healthy",  "progress": 91, "instances": 2, "traffic": 15110, "updatedAt": "2026-04-02 08:21"},
    {"service": "partner-gateway",  "region": "ap-northeast-2", "owner": "B2B",        "status": "Warning",  "progress": 67, "instances": 2, "traffic": 6820,  "updatedAt": "2026-04-02 08:03"},
    {"service": "media-catalog",    "region": "ap-northeast-2", "owner": "Content",    "status": "Healthy",  "progress": 93, "instances": 5, "traffic": 20140, "updatedAt": "2026-04-02 07:50"},
    {"service": "batch-router",     "region": "ap-northeast-2", "owner": "Automation", "status": "Critical", "progress": 38, "instances": 1, "traffic": 440,   "updatedAt": "2026-04-02 07:32"},
]


@app.get("/api/services", response_model=List[ServiceRow], tags=["Services"])
def get_services():
    """AG Grid FE용 서비스 배포 현황 목업 데이터"""
    return _services


@app.get("/", response_model=MessageResponse, tags=["General"])
def hello_world():
    """서비스 기본 응답"""
    return {"message": "hello world"}


@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check():
    """ALB / 컨테이너 헬스체크용 엔드포인트"""
    return {"status": "ok"}


_items: dict[int, dict] = {
    1: {"id": 1, "name": "노트북", "price": 1_200_000, "in_stock": True},
    2: {"id": 2, "name": "마우스", "price": 35_000,   "in_stock": False},
}


@app.get("/items/{item_id}", response_model=ItemResponse, tags=["Items"])
def get_item(item_id: int):
    """ID로 아이템 조회"""
    if item_id not in _items:
        return JSONResponse(status_code=404, content={"detail": "Item not found"})
    return _items[item_id]


@app.post("/items", response_model=ItemResponse, status_code=201, tags=["Items"])
def create_item(item: Item):
    """새 아이템 생성"""
    new_id = max(_items.keys()) + 1
    _items[new_id] = {"id": new_id, **item.model_dump()}
    return _items[new_id]
