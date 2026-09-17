FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir "psycopg[binary]==3.2.10"
COPY ohlcv_crawler.py /app/ohlcv_crawler.py

CMD ["python", "/app/ohlcv_crawler.py"]
