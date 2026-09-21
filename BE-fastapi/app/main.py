import os
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

app = FastAPI(
    title="Korea Stock OHLCV Open API",
    version="1.1.0",
    description="""
## Korea Stock OHLCV Open API

PostgreSQL에 수집된 국내 주식 일봉 OHLCV 데이터를 JSON으로 제공하는 공개 조회 API입니다.

`QUANT_DATABASE_URL`을 우선 사용하며, 없으면 `DATABASE_URL` 환경 변수를 사용합니다.
두 환경 변수 모두 PostgreSQL 연결 문자열이어야 합니다.

### 엔드포인트
- **GET /api/v1/ohlcv/{symbol}** — 종목의 일별 시가·고가·저가·종가·거래량 조회
- **GET /api/v1/ohlcv/symbols** — OHLCV 데이터가 있는 종목 목록 조회
- **GET /api** — 헬로 메시지
- **GET /api/health** — 컨테이너/프록시 헬스체크
- **GET /api/services** — 국내외 금융사 서비스 배포 현황 목록 (AG Grid 목업)
- **GET /api/stocks/list** — 국내 주식 시세 목업 (주식투자 플랫폼 ALB 헬스체크 경로와 동일)
- **GET /api/items/{item_id}** — 아이템 조회
- **POST /api/items** — 아이템 생성
""",
    contact={"name": "kdy", "email": "kimdypm@gmail.com"},
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rag.edumgt.co.kr",
        "https://rf.edumgt.co.kr",
        "http://rf.edumgt.co.kr",
    ],
    allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$",
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


class StockRow(BaseModel):
    symbol: str
    name: str
    market: str
    price: int
    change: float
    volume: int


class MessageResponse(BaseModel):
    message: str = Field(..., example="hello world")


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")


class OhlcvDaily(BaseModel):
    """PostgreSQL `ohlcv_daily` 테이블의 일봉 레코드."""

    symbol: str = Field(..., examples=["005930"], description="KRX 종목코드")
    company_name: str = Field(..., examples=["삼성전자"])
    trade_date: date = Field(..., examples=["2026-09-18"])
    open_price: Decimal = Field(..., examples=[71000])
    high_price: Decimal = Field(..., examples=[72500])
    low_price: Decimal = Field(..., examples=[70800])
    close_price: Decimal = Field(..., examples=[72000])
    volume: int = Field(..., examples=[12345678])
    foreign_ownership_pct: Optional[Decimal] = Field(None, examples=[51.23])
    change_rate_pct: Optional[Decimal] = Field(None, examples=[1.41])
    data_source: str = Field(..., examples=["naver_finance"])
    collected_at: datetime = Field(..., examples=["2026-09-18T10:30:00+00:00"])


class OhlcvSymbol(BaseModel):
    symbol: str = Field(..., examples=["005930"])
    company_name: str = Field(..., examples=["삼성전자"])
    first_trade_date: date
    last_trade_date: date


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


_stocks: List[dict] = [
    {"symbol": "005930", "name": "삼성전자",     "market": "KOSPI",  "price": 71_200,  "change": 0.85,  "volume": 12_345_678},
    {"symbol": "000660", "name": "SK하이닉스",   "market": "KOSPI",  "price": 182_500, "change": -1.24, "volume": 3_210_456},
    {"symbol": "035420", "name": "NAVER",        "market": "KOSPI",  "price": 168_000, "change": 0.30,  "volume": 812_340},
    {"symbol": "035720", "name": "카카오",       "market": "KOSPI",  "price": 41_950,  "change": -0.59, "volume": 2_945_120},
    {"symbol": "005380", "name": "현대차",       "market": "KOSPI",  "price": 236_000, "change": 1.72,  "volume": 654_210},
    {"symbol": "247540", "name": "에코프로비엠", "market": "KOSDAQ", "price": 158_700, "change": 2.91,  "volume": 1_120_034},
    {"symbol": "086520", "name": "에코프로",     "market": "KOSDAQ", "price": 93_400,  "change": -2.10, "volume": 1_530_990},
    {"symbol": "196170", "name": "알테오젠",     "market": "KOSDAQ", "price": 312_000, "change": 0.97,  "volume": 402_311},
]


@app.get("/api/stocks/list", response_model=List[StockRow], tags=["Stocks"])
def list_stocks():
    """주식투자 플랫폼 샘플 시세. ALB Target Group 헬스체크 경로(/api/stocks/list)로도 사용"""
    return _stocks


@app.get("/api", response_model=MessageResponse, tags=["General"])
def hello_world():
    """서비스 기본 응답"""
    return {"message": "hello world"}


@app.get("/api/health", response_model=HealthResponse, tags=["General"])
def health_check():
    """ALB / 컨테이너 헬스체크용 엔드포인트"""
    return {"status": "ok"}


# ── PostgreSQL OHLCV Open API ─────────────────────────────────────────

def _database_url() -> str:
    """Return a psycopg-compatible URL without exposing credentials in errors."""
    database_url = os.getenv("QUANT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="OHLCV database is not configured. Set QUANT_DATABASE_URL or DATABASE_URL.",
        )
    # The deployment scripts store SQLAlchemy-form URLs (postgresql+psycopg://).
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _database_unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="OHLCV database is temporarily unavailable.")


@app.get(
    "/api/v1/ohlcv/symbols",
    response_model=List[OhlcvSymbol],
    tags=["OHLCV"],
    summary="OHLCV 제공 종목 목록",
    responses={503: {"description": "데이터베이스 연결 불가"}},
)
def list_ohlcv_symbols():
    """수집된 종목과 보유 데이터의 첫/마지막 거래일을 반환합니다."""
    query = """
        SELECT symbol, MAX(company_name) AS company_name,
               MIN(trade_date) AS first_trade_date, MAX(trade_date) AS last_trade_date
        FROM ohlcv_daily
        GROUP BY symbol
        ORDER BY symbol
    """
    try:
        with psycopg.connect(_database_url(), connect_timeout=5) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except HTTPException:
        raise
    except psycopg.Error:
        raise _database_unavailable() from None


@app.get(
    "/api/v1/ohlcv/{symbol}",
    response_model=List[OhlcvDaily],
    tags=["OHLCV"],
    summary="일별 OHLCV 조회",
    responses={404: {"description": "해당 종목의 OHLCV 데이터가 없습니다."}, 503: {"description": "데이터베이스 연결 불가"}},
)
def get_ohlcv(
    symbol: str,
    start_date: Optional[date] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="반환할 최대 행 수"),
):
    """종목코드별 일봉을 오래된 날짜 순으로 반환합니다."""
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise HTTPException(status_code=422, detail="symbol must not be blank")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")

    clauses = ["symbol = %s"]
    parameters: list = [normalized_symbol]
    if start_date:
        clauses.append("trade_date >= %s")
        parameters.append(start_date)
    if end_date:
        clauses.append("trade_date <= %s")
        parameters.append(end_date)
    parameters.append(limit)
    query = f"""
        SELECT symbol, company_name, trade_date, open_price, high_price, low_price,
               close_price, volume, foreign_ownership_pct, change_rate_pct,
               data_source, collected_at
        FROM ohlcv_daily
        WHERE {' AND '.join(clauses)}
        ORDER BY trade_date DESC
        LIMIT %s
    """

    try:
        with psycopg.connect(_database_url(), connect_timeout=5) as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, parameters)
                rows = cursor.fetchall()
    except HTTPException:
        raise
    except psycopg.Error:
        raise _database_unavailable() from None

    if not rows:
        raise HTTPException(status_code=404, detail=f"No OHLCV data found for symbol '{normalized_symbol}'.")
    return list(reversed(rows))


_items: dict[int, dict] = {
    1: {"id": 1, "name": "노트북", "price": 1_200_000, "in_stock": True},
    2: {"id": 2, "name": "마우스", "price": 35_000,   "in_stock": False},
}


@app.get("/api/items/{item_id}", response_model=ItemResponse, tags=["Items"])
def get_item(item_id: int):
    """ID로 아이템 조회"""
    if item_id not in _items:
        return JSONResponse(status_code=404, content={"detail": "Item not found"})
    return _items[item_id]


@app.post("/api/items", response_model=ItemResponse, status_code=201, tags=["Items"])
def create_item(item: Item):
    """새 아이템 생성"""
    new_id = max(_items.keys()) + 1
    _items[new_id] = {"id": new_id, **item.model_dump()}
    return _items[new_id]
