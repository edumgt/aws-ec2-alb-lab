# Lab: Amazon Rekognition — 이미지 분석 (레이블 / 얼굴 / 텍스트)

Amazon Rekognition은 이미지·영상에서 객체, 얼굴, 텍스트 등을 감지하는 완전 관리형 컴퓨터 비전 서비스입니다.

## 포함 파일
- `rekognition_example.py`: 레이블 감지, 얼굴 분석, 텍스트 감지 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `rekognition:DetectLabels`, `rekognition:DetectFaces`, `rekognition:DetectText` |
| 패키지 | `pip install boto3` |
| 입력 파일 | JPEG, PNG (로컬 최대 5MB / S3 최대 15MB) |

## 실행 방법

### 레이블 감지 (기본)
```bash
python3 ai/rekognition-python/rekognition_example.py --file photo.jpg
```

### 얼굴 분석
```bash
python3 ai/rekognition-python/rekognition_example.py --file photo.jpg --mode faces
```

### 이미지 내 텍스트 감지
```bash
python3 ai/rekognition-python/rekognition_example.py --file sign.jpg --mode text
```

### S3 이미지 분석
```bash
python3 ai/rekognition-python/rekognition_example.py \
  --s3-bucket my-bucket \
  --s3-key images/photo.jpg \
  --mode labels
```

## 실행 예시

### 레이블 감지
```
============================================================
[이미지] photo.jpg
[분석 모드] labels

[레이블 감지 (8개, 신뢰도 80.0% 이상)]
  Person       (99.12%)  카테고리: People
  Laptop       (97.43%)  카테고리: Technology, Electronics
  Desk         (92.18%)  카테고리: Furniture
  Office       (89.55%)  카테고리: Architecture, Building
============================================================
```

### 얼굴 분석
```
============================================================
[이미지] portrait.jpg
[분석 모드] faces

[얼굴 분석 (2명 감지)]
  얼굴 1: Male, 25~35세, 미소=예, 주요감정=HAPPY (신뢰도 99.87%)
  얼굴 2: Female, 30~40세, 미소=아니오, 주요감정=CALM (신뢰도 98.34%)
============================================================
```

### 텍스트 감지
```
============================================================
[이미지] sign.jpg
[분석 모드] text

[텍스트 감지 (3줄)]
  "WELCOME TO AWS" (99.21%)
  "re:Invent 2024" (97.55%)
  "Las Vegas, NV" (95.12%)
============================================================
```

## 참고
- 신뢰도 임계값은 코드 내 `CONFIDENCE_THRESHOLD = 80.0` 으로 조정 가능
- 영상 분석(비동기)은 `start_label_detection` → `get_label_detection` 사용
- 요금: 이미지 1,000건당 $1.00 (레이블 기준), 얼굴 분석은 별도 과금
