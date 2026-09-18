CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol                 VARCHAR(12) NOT NULL,
    company_name           VARCHAR(100) NOT NULL,
    trade_date             DATE NOT NULL,
    open_price             NUMERIC(18, 2) NOT NULL,
    high_price             NUMERIC(18, 2) NOT NULL,
    low_price              NUMERIC(18, 2) NOT NULL,
    close_price            NUMERIC(18, 2) NOT NULL,
    volume                 BIGINT NOT NULL,
    foreign_ownership_pct  NUMERIC(7, 4),
    change_rate_pct        NUMERIC(10, 4),
    data_source            VARCHAR(50) NOT NULL DEFAULT 'naver_finance',
    collected_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);
