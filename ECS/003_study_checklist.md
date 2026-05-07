# ECS 스터디 체크리스트

## A. 개념 질문
1. ECS와 EKS의 가장 큰 운영 차이는 무엇인가?
2. ECS on EC2 대비 Fargate의 제약사항은 무엇인가?
3. Fargate에서 `awsvpc` 모드가 필수인 이유는 무엇인가?
4. ALB Target Group에서 ECS는 왜 `ip` 타입을 많이 사용하는가?
5. ECS Task Role과 Execution Role의 역할 차이는 무엇인가?

## B. 실습 점검 질문
1. 새 이미지 배포 시 Task Definition 리비전이 실제로 증가했는가?
2. 롤링 업데이트 중 최소 정상 태스크 수를 어떻게 보장하는가?
3. CloudWatch 로그에서 장애 시그널(재시작/타임아웃)을 어떻게 찾는가?

## C. 팀 스터디 과제
1. `BE-fastapi`에 `/version` 엔드포인트를 추가하고 태그(`v2`) 배포하기
2. ALB Listener Rule로 `/api/*`만 ECS 서비스로 전달하도록 구성하기
3. 배포 실패를 가정하고 이전 리비전으로 롤백 실습하기

## D. 완료 기준
- [ ] ECS Service 1개 이상 정상 동작
- [ ] Target Group `healthy` 확인
- [ ] CloudWatch 로그 확인 및 장애 원인 1개 이상 기록
- [ ] 롤백 절차 문서화


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
