# Lab: Amazon Textract — 문서/이미지 텍스트 추출

Amazon Textract는 이미지·PDF에서 텍스트, 표, 양식(KEY-VALUE) 데이터를 자동으로 추출하는 완전 관리형 서비스입니다.

## 포함 파일
- `textract_example.py`: 텍스트 추출, 폼 필드 분석 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `textract:DetectDocumentText`, `textract:AnalyzeDocument` |
| 패키지 | `pip install boto3` |
| 입력 파일 | JPEG, PNG, PDF (로컬 또는 S3) |

## 실행 방법

### 로컬 이미지 텍스트 추출
```bash
python3 ai/textract-python/textract_example.py --file sample.png
```

### S3 문서 텍스트 추출
```bash
python3 ai/textract-python/textract_example.py \
  --s3-bucket my-bucket \
  --s3-key docs/invoice.pdf
```

### 폼 필드(KEY-VALUE) 분석
```bash
python3 ai/textract-python/textract_example.py --file form.png --forms
```

## 실행 예시

```
============================================================
[파일] invoice.png

[추출된 텍스트 라인 (12개)]
  01. INVOICE
  02. Invoice Number: INV-2024-001
  03. Date: 2024-01-15
  04. Bill To:
  05. John Doe
  ...

[폼 필드 분석 (KEY-VALUE)]
  Invoice Number: INV-2024-001
  Date: 2024-01-15
  Total Amount: $1,250.00
============================================================
```

## 참고
- 동기 API(`detect_document_text`)는 최대 10MB, 3,000페이지 제한
- 대용량·비동기 처리는 `start_document_text_detection` → `get_document_text_detection` 사용
- 요금: 1,000페이지당 $1.50 (텍스트 감지 기준), 표/폼 분석은 별도 과금
