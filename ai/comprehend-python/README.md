# Lab: Amazon Comprehend — 감성 분석 / 개체명 인식 / 언어 감지

Amazon Comprehend는 별도 ML 지식 없이 텍스트 분석 기능을 API로 제공하는 완전 관리형 NLP 서비스입니다.

## 포함 파일
- `comprehend_example.py`: 감성 분석, 개체명 인식, 언어 감지 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `comprehend:DetectSentiment`, `comprehend:DetectEntities`, `comprehend:DetectDominantLanguage` |
| 패키지 | `pip install boto3` |
| 리전 | `us-east-1` (기본값, 대부분 리전 지원) |

## 실행 방법

```bash
python3 ai/comprehend-python/comprehend_example.py
```

별도 인자 없이 실행하면 영어/한국어 샘플 텍스트 2건을 자동으로 분석합니다.

## 실행 예시

```
============================================================
[입력 텍스트]
AWS re:Invent is an amazing conference held in Las Vegas every year. I love the keynote sessions!

[언어 감지] en

[감성 분석]
  결과: POSITIVE
  Positive: 0.9987
  Negative: 0.0002
  Neutral: 0.0009
  Mixed: 0.0002

[개체명 인식]
  [EVENT] re:Invent (신뢰도: 0.9912)
  [ORGANIZATION] AWS (신뢰도: 0.9843)
  [LOCATION] Las Vegas (신뢰도: 0.9998)
============================================================

============================================================
[입력 텍스트]
아마존 웹 서비스는 클라우드 컴퓨팅 분야에서 매우 뛰어난 서비스를 제공합니다. 정말 훌륭한 플랫폼입니다.

[언어 감지] ko

[감성 분석]
  결과: POSITIVE
  Positive: 0.9921
  Negative: 0.0008
  ...

[개체명 인식]
  [ORGANIZATION] 아마존 웹 서비스 (신뢰도: 0.9775)
============================================================
```

## 참고
- 지원 언어: 한국어(`ko`), 영어(`en`) 포함 100개 이상
- 요금: 100자 단위 과금 (최소 3유닛). 월 50,000유닛까지 무료 티어 제공
- 개인정보(이름, 주소, 카드번호 등) 감지는 `detect_pii_entities` API 사용
