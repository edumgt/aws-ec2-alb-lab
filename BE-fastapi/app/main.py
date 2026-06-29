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
- **GET /api/services** — 국내외 금융사 서비스 배포 현황 목록 (AG Grid 목업)
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
    # 국내 금융사
    {"service": "kb-payment-gateway",    "region": "ap-northeast-2", "owner": "KB국민은행",     "status": "Healthy",  "progress": 97, "instances": 6, "traffic": 52340, "updatedAt": "2026-06-29 09:14"},
    {"service": "shinhan-account-api",   "region": "ap-northeast-2", "owner": "신한은행",       "status": "Healthy",  "progress": 91, "instances": 4, "traffic": 38720, "updatedAt": "2026-06-29 09:10"},
    {"service": "kakaobank-loan-engine", "region": "ap-northeast-2", "owner": "카카오뱅크",     "status": "Warning",  "progress": 74, "instances": 3, "traffic": 29480, "updatedAt": "2026-06-29 09:07"},
    {"service": "toss-remittance",       "region": "ap-northeast-2", "owner": "토스",           "status": "Healthy",  "progress": 99, "instances": 8, "traffic": 71560, "updatedAt": "2026-06-29 09:05"},
    {"service": "hana-fx-trading",       "region": "ap-northeast-2", "owner": "하나은행",       "status": "Healthy",  "progress": 88, "instances": 4, "traffic": 31200, "updatedAt": "2026-06-29 08:58"},
    {"service": "nh-credit-scoring",     "region": "ap-northeast-2", "owner": "NH농협은행",     "status": "Critical", "progress": 43, "instances": 2, "traffic": 8940,  "updatedAt": "2026-06-29 08:51"},
    {"service": "samsung-sec-trading",   "region": "ap-northeast-2", "owner": "삼성증권",       "status": "Healthy",  "progress": 95, "instances": 5, "traffic": 44870, "updatedAt": "2026-06-29 08:44"},
    {"service": "mirae-portfolio-api",   "region": "ap-northeast-2", "owner": "미래에셋증권",   "status": "Healthy",  "progress": 93, "instances": 4, "traffic": 39510, "updatedAt": "2026-06-29 08:40"},
    {"service": "hyundai-card-auth",     "region": "ap-northeast-2", "owner": "현대카드",       "status": "Warning",  "progress": 68, "instances": 3, "traffic": 22140, "updatedAt": "2026-06-29 08:35"},
    {"service": "woori-kyc-verify",      "region": "ap-northeast-2", "owner": "우리은행",       "status": "Healthy",  "progress": 86, "instances": 3, "traffic": 18630, "updatedAt": "2026-06-29 08:28"},
    # 해외 금융사
    {"service": "jpmorgan-risk-monitor", "region": "us-east-1",      "owner": "JPMorgan Chase", "status": "Healthy",  "progress": 98, "instances": 10, "traffic": 93200, "updatedAt": "2026-06-29 08:22"},
    {"service": "goldman-algo-trader",   "region": "us-east-1",      "owner": "Goldman Sachs",  "status": "Warning",  "progress": 71, "instances": 6,  "traffic": 61480, "updatedAt": "2026-06-29 08:15"},
    {"service": "hsbc-swift-gateway",    "region": "eu-west-1",      "owner": "HSBC",           "status": "Healthy",  "progress": 94, "instances": 7,  "traffic": 47320, "updatedAt": "2026-06-29 08:10"},
    {"service": "ubs-compliance-api",    "region": "eu-west-1",      "owner": "UBS",            "status": "Critical", "progress": 37, "instances": 2,  "traffic": 5610,  "updatedAt": "2026-06-29 08:03"},
    {"service": "dbs-open-banking",      "region": "ap-southeast-1", "owner": "DBS Bank",       "status": "Healthy",  "progress": 89, "instances": 5,  "traffic": 33740, "updatedAt": "2026-06-29 07:55"},
    {"service": "stripe-payment-core",   "region": "us-east-1",      "owner": "Stripe",         "status": "Healthy",  "progress": 100, "instances": 12, "traffic": 128500, "updatedAt": "2026-06-29 07:48"},
]


@app.get("/api/services", response_model=List[ServiceRow], tags=["Services"])
def get_services():
    """AG Grid FE용 국내외 금융사 서비스 배포 현황 목업 데이터"""
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
