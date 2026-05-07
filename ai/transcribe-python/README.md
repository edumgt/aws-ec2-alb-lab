# Lab: Amazon Transcribe — 음성 → 텍스트 변환

Amazon Transcribe는 오디오 파일을 텍스트로 변환하는 완전 관리형 ASR(자동 음성 인식) 서비스입니다.  
한국어를 포함한 100개 이상의 언어를 지원합니다.

## 포함 파일
- `transcribe_example.py`: S3 오디오 파일 변환 및 결과 조회 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `transcribe:StartTranscriptionJob`, `transcribe:GetTranscriptionJob`, `s3:PutObject`, `s3:GetObject` |
| 패키지 | `pip install boto3` |
| 입력 파일 | S3에 저장된 오디오 (MP3, WAV, FLAC, MP4, OGG 등) |

## 실행 방법

### S3에 있는 오디오 파일 변환
```bash
python3 ai/transcribe-python/transcribe_example.py \
  --s3-uri s3://my-bucket/audio/sample.mp3 \
  --lang ko-KR
```

### 로컬 파일을 S3에 업로드 후 변환
```bash
python3 ai/transcribe-python/transcribe_example.py \
  --file sample.mp3 \
  --bucket my-bucket \
  --lang ko-KR
```

### 영어 변환
```bash
python3 ai/transcribe-python/transcribe_example.py \
  --s3-uri s3://my-bucket/audio/english.wav \
  --lang en-US
```

## 실행 예시

```
============================================================
[입력] s3://my-bucket/audio/sample.mp3
[언어] ko-KR
[작업 시작] job_name=lab-3a7f2e1b

[진행 상황]
  [  0s] 상태: IN_PROGRESS
  [  5s] 상태: IN_PROGRESS
  [ 10s] 상태: IN_PROGRESS
  [ 15s] 상태: COMPLETED

[변환 결과]
  안녕하세요. 아마존 트랜스크라이브 테스트입니다. 이 서비스는 음성을 텍스트로 변환해줍니다.
============================================================
```

## 참고
- 변환 작업은 비동기로 처리됩니다. 파일 길이에 따라 수 초~수 분 소요
- 최대 대기 시간은 코드 내 `MAX_WAIT_SECONDS = 300`으로 조정 가능
- 화자 분리 기능은 `Settings.ShowSpeakerLabels = True` 로 활성화
- 요금: 초당 $0.00004 (약 분당 $0.024), 처음 60분/월 무료 티어 제공
