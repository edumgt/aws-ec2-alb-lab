# AWS AI Resource 예시: Claude LLM 호출 (Python)

이 예시는 Python에서 Claude LLM을 호출하는 방법을 다룹니다.  
**Amazon Bedrock** 경유 방식과 **Anthropic SDK 직접 호출** 방식을 모두 설명합니다.

---

## 포함 파일
- `bedrock_claude_example.py`: Anthropic SDK를 사용한 Claude 호출 샘플 코드

---

## 방법 1: Amazon Bedrock 경유

### 개요
AWS 관리형 서비스인 Bedrock을 통해 Claude를 호출합니다.  
AWS IAM 권한만으로 인증이 가능하며, API 키 없이 AWS 자격증명으로 동작합니다.

### 사전 조건
- AWS 계정에 Bedrock 액세스 활성화 (콘솔 → Amazon Bedrock → 모델 액세스 신청)
- IAM 권한: `bedrock:InvokeModel`
- `pip install boto3`

### 샘플 코드
```python
import boto3, json

client = boto3.client("bedrock-runtime", region_name="us-east-1")

body = {
    "messages": [{"role": "user", "content": [{"text": "안녕하세요"}]}],
    "inferenceConfig": {"max_new_tokens": 512},
}

response = client.invoke_model(
    modelId="amazon.nova-lite-v1:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps(body),
)
payload = json.loads(response["body"].read())
print(payload["output"]["message"]["content"][0]["text"])
```

### 알려진 제약
| 항목 | 내용 |
|---|---|
| 지역 제한 | 한국 IP에서 `anthropic.claude-*` 계열 모델 호출 불가 (`ValidationException`) |
| 계정 인증 | 개인 계정은 기업 고객 인증 필요 (`"you must provide further information..."`) |
| EOL 모델 | `amazon.titan-text-express-v1` 등 일부 모델 서비스 종료 |
| 권장 모델 | `amazon.nova-lite-v1:0` (us-east-1, 기업 인증 후 사용 가능) |

---

## 방법 2: Anthropic SDK 직접 호출 (현재 사용 방식)

### 개요
AWS를 거치지 않고 Anthropic API에 직접 접속합니다.  
AWS 계정·IAM 권한 불필요. `ANTHROPIC_API_KEY`만 있으면 동작합니다.

### 실행 방법

1. 패키지 설치
   ```bash
   pip install anthropic
   ```

2. API 키 설정
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   API 키 발급: [console.anthropic.com](https://console.anthropic.com)

3. (선택) 모델 변경
   ```bash
   export CLAUDE_MODEL_ID=claude-haiku-4-5   # 저비용
   # export CLAUDE_MODEL_ID=claude-opus-4-7  # 기본값 (고성능)
   ```

4. 실행
   ```bash
   python3 ai/bedrock-python-llm/bedrock_claude_example.py
   ```

### 지원 모델
| 모델 ID | 특징 | 입력 $/1M | 출력 $/1M |
|---|---|---|---|
| `claude-opus-4-7` | 최고 성능 (기본값) | $5.00 | $25.00 |
| `claude-sonnet-4-6` | 균형형 | $3.00 | $15.00 |
| `claude-haiku-4-5` | 저비용·고속 | $1.00 | $5.00 |

---

## 테스트 결과

### 환경
- OS: Ubuntu (WSL2, Linux 6.6.x)
- Python: 3.12.3
- anthropic: 0.100.0

### 테스트 1 — API 키 미설정 시 오류 처리
```bash
$ python3 ai/bedrock-python-llm/bedrock_claude_example.py
RuntimeError: ANTHROPIC_API_KEY environment variable is not set.
```
→ 키 누락 시 명확한 오류 메시지 출력 확인

### 테스트 2 — 정상 호출 예시 (API 키 설정 후)
```bash
$ export ANTHROPIC_API_KEY=sk-ant-...
$ python3 ai/bedrock-python-llm/bedrock_claude_example.py
```
**프롬프트:** `AWS ALB와 EC2를 사용하는 기본 아키텍처를 5줄로 설명해줘.`

**응답 예시:**
```
1. 사용자 요청은 인터넷 게이트웨이를 통해 ALB(Application Load Balancer)로 전달됩니다.
2. ALB는 리스너 규칙에 따라 트래픽을 대상 그룹(Target Group)으로 라우팅합니다.
3. 대상 그룹에 등록된 EC2 인스턴스들이 실제 요청을 처리합니다.
4. 여러 가용 영역(AZ)에 EC2를 분산 배치해 고가용성을 확보합니다.
5. Auto Scaling Group과 함께 사용하면 부하에 따라 EC2 수를 자동으로 조정할 수 있습니다.
```

### Bedrock 테스트 — 오류 이력
| 시도 | 모델 | 리전 | 오류 |
|---|---|---|---|
| 1 | `anthropic.claude-3-haiku-20240307-v1:0` | us-east-1 | `ValidationException`: 한국 IP 차단 |
| 2 | `amazon.titan-text-express-v1` | ap-northeast-2 | `ResourceNotFoundException`: 모델 EOL |
| 3 | `amazon.nova-lite-v1:0` | us-east-1 | `ValidationException`: 계정 기업 인증 필요 |

---

## 참고
- `max_tokens=512` 고정. 비용 절감 시 `128`로 낮추고 호출 빈도를 제한하세요.
- AWS Cost Explorer / 예산 알림을 함께 설정해 비용을 모니터링하세요.


---

## YouTube 참고 영상
- [YouTube에서 관련 영상 찾아보기](https://www.youtube.com/results?search_query=AWS+EC2+ECS+ALB+Lab)
