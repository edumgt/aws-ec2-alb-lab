# AG Grid Static App

Nginx에 그대로 올릴 수 있는 바닐라 HTML/CSS/JS 기반 AG Grid 예제입니다.

## 파일 구성
- `index.html`: CDN으로 AG Grid를 불러오는 진입점
- `styles.css`: 대시보드 스타일
- `app.js`: 그리드 컬럼, 데이터, 필터 로직

## 로컬 확인
정적 파일이라 아무 웹서버에 올리면 됩니다.

예시:
```bash
cd /home/AWS-EC2-ECS-LB/ag-grid-app
python3 -m http.server 8080
```

브라우저에서 `http://127.0.0.1:8080` 접속

## Nginx 배포 예시
```bash
sudo mkdir -p /var/www/html/ag-grid-app
sudo cp -r /home/AWS-EC2-ECS-LB/ag-grid-app/* /var/www/html/ag-grid-app/
sudo systemctl reload nginx
```

접속:
`http://<EC2_PUBLIC_IP>/ag-grid-app/`


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
