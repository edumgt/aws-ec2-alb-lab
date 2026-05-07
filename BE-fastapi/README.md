# BE FastAPI Docker 샘플

간단한 Hello World API 서버입니다.

## 엔드포인트
- `GET /` -> `{ "message": "hello world" }`
- `GET /health` -> `{ "status": "ok" }`

## 로컬 실행
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker 실행
```bash
docker build -t be-fastapi-hello .
docker run --rm -p 8000:8000 be-fastapi-hello
```

## 테스트
```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=BE+fastapi+README)
