# AWS AI Resource 예시: Amazon Bedrock + Python LLM

이 예시는 **Amazon Bedrock**를 Python(`boto3`)으로 호출해 LLM 응답을 받는 최소 예시입니다.

## 포함 파일
- `bedrock_claude_example.py`: Claude 모델 호출 샘플 코드

## 실행 방법
1. AWS 자격 증명 설정(아래 중 하나)
   - 로컬 개발: `aws configure`
   - EC2/ECS: IAM Role 연결(권장)
   - 환경 변수: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
   - SSO: `aws configure sso`
2. 필요 시 환경 변수 설정
   - `export AWS_REGION=us-east-1`
   - `export BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0`
3. 실행
   - `python ai/bedrock-python-llm/bedrock_claude_example.py`

## 참고
- Bedrock 모델 접근 권한(IAM + 모델 액세스)이 있어야 동작합니다.
- 과금이 발생할 수 있으므로 테스트 시 토큰/호출량을 제한하세요.
