# Load Balancer 학습 가이드

이 폴더는 ALB/NLB 설정과 점검 포인트를 정리한 학습 문서입니다.

## 문서
1. [001_alb_settings_lab.md](001_alb_settings_lab.md) — ALB 설정 기초 및 점검
2. [002_lb_types_targetgroup_autoscaling.md](002_lb_types_targetgroup_autoscaling.md) — LB 종류·타겟그룹·오토스케일러

## 주식투자 웹앱 플랫폼 구성에서의 역할

플랫폼의 ALB 는 CloudFront 뒤에서 `/api/*`, `/openapi/*` 만 받는 **API 전용 ALB** 입니다. 이 폴더의 점검 포인트를 플랫폼 기준으로 정리하면:

| 항목 | 플랫폼 설정값 | 근거 |
|---|---|---|
| 리스너 | 443 (ACM, `ELBSecurityPolicy-TLS13-1-2-2021-06`) + 80→443 리다이렉트 | CloudFront 오리진 프로토콜 `https-only` |
| 타깃 그룹 | `instance` 타입, 포트 3000(nginx), 헬스체크 `/api/stocks/list` 200-399 | 백엔드까지 관통하는 경로로 상태 판단 |
| 헬스체크 주기 | 30초, healthy 2 / unhealthy 3 | 배포 직후 오탐 방지 |
| 보안그룹 | ALB SG 80/443 공개 → 앱 SG 는 ALB SG 만 허용 | 3계층 참조 규칙 |
| Sticky Session | 사용 안 함 | 세션은 백엔드 DB/토큰 기반, 무상태 유지 |
| 오토스케일링 | Stage 1 은 단일 EC2, 확장 시 ASG Target Tracking(CPU 60%) | [002](002_lb_types_targetgroup_autoscaling.md) |
| 오리진 보호(선택) | CloudFront 커스텀 헤더 `X-Origin-Verify` → 리스너 규칙으로 헤더 없는 요청 403 | ALB 직접 호출 차단 |

리스너 규칙으로 오리진 보호를 거는 예:

```bash
# 기본 액션을 403 고정 응답으로 바꾸고, 헤더가 맞는 요청만 forward
aws elbv2 modify-listener --listener-arn "$LISTENER_443_ARN" \
  --default-actions 'Type=fixed-response,FixedResponseConfig={StatusCode=403,ContentType=text/plain,MessageBody=forbidden}'
aws elbv2 create-rule --listener-arn "$LISTENER_443_ARN" --priority 10 \
  --conditions '[{"Field":"http-header","HttpHeaderConfig":{"HttpHeaderName":"X-Origin-Verify","Values":["<랜덤 문자열>"]}}]' \
  --actions Type=forward,TargetGroupArn="$TG_ARN"
# CloudFront 오리진(alb-api)의 CustomHeaders 에 같은 값을 추가
```

## 학습 목표
- ALB/NLB/GLB 차이 및 선택 기준 이해
- Listener/Rule/Target Group 기본 구조 숙지
- 헬스체크 상태·드레이닝·Sticky Session 설정
- ASG Scaling Policy 유형 및 Instance Refresh 운용
- 헬스체크 실패 시 진단 순서 확립


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+Load+Balancer+ALB+NLB)
