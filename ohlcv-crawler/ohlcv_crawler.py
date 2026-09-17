"""Fetch Samsung Electronics daily OHLCV data and upsert it into PostgreSQL."""

import ast
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal

import psycopg


DEFAULT_STOCKS = [
    {"symbol": "005930", "company_name": "삼성전자"},
    {"symbol": "000660", "company_name": "SK하이닉스"},
    {"symbol": "373220", "company_name": "LG에너지솔루션"},
    {"symbol": "207940", "company_name": "삼성바이오로직스"},
    {"symbol": "005380", "company_name": "현대차"},
    {"symbol": "000270", "company_name": "기아"},
    {"symbol": "068270", "company_name": "셀트리온"},
    {"symbol": "105560", "company_name": "KB금융"},
    {"symbol": "035420", "company_name": "NAVER"},
    {"symbol": "055550", "company_name": "신한지주"},
]
START_DATE = os.getenv("START_DATE", f"{date.today().year}0101")
END_DATE = os.getenv("END_DATE", date.today().strftime("%Y%m%d"))
DATABASE_URL = os.environ["DATABASE_URL"]

DDL = """
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol              VARCHAR(12) NOT NULL,
    company_name        VARCHAR(100) NOT NULL,
    trade_date          DATE NOT NULL,
    open_price          NUMERIC(18,2) NOT NULL,
    high_price          NUMERIC(18,2) NOT NULL,
    low_price           NUMERIC(18,2) NOT NULL,
    close_price         NUMERIC(18,2) NOT NULL,
    volume              BIGINT NOT NULL,
    foreign_ownership_pct NUMERIC(7,4),
    change_rate_pct     NUMERIC(10,4),
    data_source         VARCHAR(50) NOT NULL DEFAULT 'naver_finance',
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);
"""

UPSERT = """
INSERT INTO ohlcv_daily (
    symbol, company_name, trade_date, open_price, high_price, low_price,
    close_price, volume, foreign_ownership_pct, change_rate_pct, data_source
) VALUES (%(symbol)s, %(company_name)s, %(trade_date)s, %(open_price)s,
          %(high_price)s, %(low_price)s, %(close_price)s, %(volume)s,
          %(foreign_ownership_pct)s, %(change_rate_pct)s, 'naver_finance')
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    open_price = EXCLUDED.open_price,
    high_price = EXCLUDED.high_price,
    low_price = EXCLUDED.low_price,
    close_price = EXCLUDED.close_price,
    volume = EXCLUDED.volume,
    foreign_ownership_pct = EXCLUDED.foreign_ownership_pct,
    change_rate_pct = EXCLUDED.change_rate_pct,
    data_source = EXCLUDED.data_source,
    collected_at = NOW();
"""


def stocks_to_collect():
    """Allow the KOSPI universe to be overridden without rebuilding the image."""
    return json.loads(os.getenv("STOCKS_JSON", json.dumps(DEFAULT_STOCKS, ensure_ascii=False)))


def fetch_rows(stock):
    params = urllib.parse.urlencode(
        {
            "symbol": stock["symbol"],
            "requestType": "1",
            "startTime": START_DATE,
            "endTime": END_DATE,
            "timeframe": "day",
        }
    )
    request = urllib.request.Request(
        f"https://api.finance.naver.com/siseJson.naver?{params}",
        headers={"User-Agent": "Mozilla/5.0 (OHLCV data collector)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("euc-kr", errors="replace")

    # The endpoint returns a JavaScript-style list with whitespace/comments.
    payload = re.sub(r"^\s*//.*$", "", payload, flags=re.MULTILINE).strip()
    rows = ast.literal_eval(payload)
    if len(rows) < 2:
        raise RuntimeError("The data source returned no OHLCV rows.")

    result = []
    previous_close = None
    for raw in rows[1:]:
        trade_date = datetime.strptime(str(raw[0]), "%Y%m%d").date()
        close_price = Decimal(str(raw[4]))
        result.append(
            {
                "symbol": stock["symbol"],
                "company_name": stock["company_name"],
                "trade_date": trade_date,
                "open_price": Decimal(str(raw[1])),
                "high_price": Decimal(str(raw[2])),
                "low_price": Decimal(str(raw[3])),
                "close_price": close_price,
                "volume": int(raw[5]),
                "foreign_ownership_pct": Decimal(str(raw[6])) if raw[6] is not None else None,
                "change_rate_pct": (
                    (close_price - previous_close) / previous_close * 100
                    if previous_close not in (None, Decimal("0"))
                    else None
                ),
            }
        )
        previous_close = close_price
    return result


def main():
    rows = []
    for stock in stocks_to_collect():
        stock_rows = fetch_rows(stock)
        rows.extend(stock_rows)
        print(f"Fetched {len(stock_rows)} rows for {stock['company_name']} ({stock['symbol']}).")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)
            cursor.executemany(UPSERT, rows)
    print(f"Upserted {len(rows)} OHLCV rows for {len(stocks_to_collect())} stocks ({START_DATE}–{END_DATE}).")


if __name__ == "__main__":
    main()
