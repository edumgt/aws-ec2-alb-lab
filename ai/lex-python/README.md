# Lab: Amazon Lex v2 — 챗봇 대화 세션

Amazon Lex v2는 Alexa와 동일한 엔진을 기반으로 한 완전 관리형 대화형 AI 서비스입니다.  
음성·텍스트 입력을 인텐트(Intent)와 슬롯(Slot)으로 파싱합니다.

## 포함 파일
- `lex_example.py`: 단일 발화 테스트 및 대화형 세션 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `lex:RecognizeText` |
| 패키지 | `pip install boto3` |
| Lex 봇 | 콘솔에서 봇 생성 후 Bot ID / Alias ID 필요 |

### Lex 봇 준비 (콘솔)
1. [Amazon Lex 콘솔](https://console.aws.amazon.com/lex/) 접속
2. **Create bot** → 봇 이름 입력, 언어 `Korean (Korea)` 선택
3. 인텐트 추가 (예: `OrderIntent`, 샘플 발화 등록)
4. **Build** → **Test** 확인
5. 봇 ID(`LEX_BOT_ID`)와 별칭 ID(`LEX_BOT_ALIAS_ID`) 복사

## 실행 방법

### 환경 변수 설정
```bash
export LEX_BOT_ID=ABCDE12345
export LEX_BOT_ALIAS_ID=TSTALIASID     # 테스트 별칭
export AWS_REGION=ap-northeast-2
```

### 단일 발화 테스트
```bash
python3 ai/lex-python/lex_example.py --text "피자 주문하고 싶어요"
```

### 대화형 모드
```bash
python3 ai/lex-python/lex_example.py
```

## 실행 예시

### 단일 발화
```
============================================================
[단일 발화 테스트]
  입력: 피자 주문하고 싶어요
  봇 응답: 어떤 사이즈로 드릴까요?
  인텐트: OrderPizzaIntent [InProgress]
  다음 액션: ElicitSlot
============================================================
```

### 대화형 모드
```
============================================================
[대화형 Lex 세션] session_id=3f2a1b...

나: 피자 주문하고 싶어요
  봇 응답: 어떤 사이즈로 드릴까요?
  인텐트: OrderPizzaIntent [InProgress]
  다음 액션: ElicitSlot

나: 라지로 주세요
  봇 응답: 주문이 완료되었습니다. 라지 피자 1판 주문되었습니다.
  인텐트: OrderPizzaIntent [Fulfilled]
  슬롯: {'Size': '라지'}
  다음 액션: Close

[인텐트 완료 — 세션 종료]
============================================================
```

## 참고
- 테스트 별칭 ID는 `TSTALIASID` (콘솔에서 확인)
- 프로덕션 배포 시 별도 별칭 생성 후 ID 교체
- 요금: 텍스트 요청 1,000건당 $0.75, 음성 요청 1,000건당 $4.00
