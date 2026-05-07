# Lab: Amazon Polly — 텍스트 → 음성(MP3) 변환

Amazon Polly는 텍스트를 자연스러운 음성으로 변환하는 완전 관리형 TTS(텍스트 음성 변환) 서비스입니다.  
한국어(Neural 음성 Seoyeon 포함) 등 30개 이상 언어, 90개 이상 음성을 지원합니다.

## 포함 파일
- `polly_example.py`: 텍스트/SSML → MP3 변환, 음성 목록 조회 샘플

## 사전 조건
| 항목 | 내용 |
|---|---|
| AWS 자격 증명 | `aws configure` 또는 IAM Role |
| IAM 권한 | `polly:SynthesizeSpeech`, `polly:DescribeVoices` |
| 패키지 | `pip install boto3` |

## 실행 방법

### 기본 (한국어, Seoyeon Neural 음성)
```bash
python3 ai/polly-python/polly_example.py \
  --text "안녕하세요. 아마존 폴리입니다."
```

### 영어 음성 지정
```bash
python3 ai/polly-python/polly_example.py \
  --text "Hello, this is Amazon Polly." \
  --voice Joanna
```

### SSML로 강조·속도 조절
```bash
python3 ai/polly-python/polly_example.py --ssml \
  "<speak>안녕하세요. <emphasis level='strong'>중요한</emphasis> 내용입니다. <break time='500ms'/> 감사합니다.</speak>"
```

### 출력 파일 경로 지정
```bash
python3 ai/polly-python/polly_example.py \
  --text "테스트 음성입니다." \
  --output /tmp/test.mp3
```

### 사용 가능한 한국어 음성 목록
```bash
python3 ai/polly-python/polly_example.py --list-voices --lang ko-KR
```

## 실행 예시

### 텍스트 변환
```
============================================================
[입력 텍스트] 안녕하세요. 아마존 폴리입니다.
[음성] Seoyeon  [포맷] MP3  [SSML] 아니오

[변환 완료]
  저장 경로: /home/ubuntu/aws-ec2-alb-lab/ai/polly-python/output.mp3
  파일 크기: 24,832 bytes
============================================================
```

### 음성 목록 조회
```
============================================================
[사용 가능한 음성 목록] (ko-KR)
  Seoyeon      Female  Korean (South Korea)  [neural, standard]
============================================================
```

## 주요 SSML 태그
| 태그 | 설명 | 예시 |
|---|---|---|
| `<emphasis>` | 강조 | `<emphasis level="strong">중요</emphasis>` |
| `<break>` | 멈춤 | `<break time="500ms"/>` |
| `<prosody>` | 속도/음량/음높이 | `<prosody rate="slow">천천히</prosody>` |
| `<say-as>` | 읽기 방식 지정 | `<say-as interpret-as="digits">1234</say-as>` |

## 참고
- Neural 음성(`Seoyeon`)은 standard보다 자연스럽지만 요금이 약 4배 높음
- 요금: 100만 자당 표준 $4.00 / Neural $16.00, 처음 500만 자/월 무료 티어 제공
- 5분 이상 긴 텍스트는 `start_speech_synthesis_task` (비동기 S3 저장) 사용


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=ai+polly+python+README)
