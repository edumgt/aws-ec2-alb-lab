#!/usr/bin/env bash
set -euo pipefail

docker run --rm \
  --network stock-network \
  -e DATABASE_URL='postgresql://stock:stock1234!!@stock-postgres:5432/ohlcv' \
  ohlcv-crawler:1.1
