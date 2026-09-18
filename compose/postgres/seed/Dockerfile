FROM 086015456585.dkr.ecr.ap-northeast-2.amazonaws.com/stock-postgres:latest

# The build context supplies a pg_dump plain-SQL file named 001-ohlcv.sql.
# PostgreSQL's official entrypoint executes it only when a new data volume is initialized.
COPY --chmod=644 001-ohlcv.sql /docker-entrypoint-initdb.d/001-ohlcv.sql
