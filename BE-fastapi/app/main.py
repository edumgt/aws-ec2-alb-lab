from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="BE FastAPI Hello",
    version="1.0.0",
    description="""
## BE FastAPI Hello API

EC2 + Docker 배포 실습용 FastAPI 서비스입니다.

### 엔드포인트
- **GET /** — 헬로 메시지
- **GET /health** — ALB 헬스체크
- **GET /items/{item_id}** — 아이템 조회
- **POST /items** — 아이템 생성
""",
    contact={"name": "kdy", "email": "kimdypm@gmail.com"},
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Response / Request 모델 ────────────────────────────────────────────

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
