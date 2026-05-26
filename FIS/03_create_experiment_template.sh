#!/bin/bash
# AWS FIS - Experiment Template 생성
# 다이어그램의 "Experiment template" 박스에 해당
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"
ROLE_ARN_FILE="/tmp/fis-lab/role_arn.txt"
STOP_ALARM_FILE="/tmp/fis-lab/stop_condition_alarm_arn.txt"

# 이전 단계에서 저장된 ARN 읽기
if [ -f "$ROLE_ARN_FILE" ]; then
  ROLE_ARN=$(cat "$ROLE_ARN_FILE")
else
  echo "[ERROR] IAM Role ARN을 찾을 수 없습니다. 01_setup_iam.sh 를 먼저 실행하세요."
  exit 1
fi

if [ -f "$STOP_ALARM_FILE" ]; then
  STOP_ALARM_ARN=$(cat "$STOP_ALARM_FILE")
else
  echo "[ERROR] Stop Condition 알람 ARN을 찾을 수 없습니다. 02_create_cloudwatch_alarms.sh 를 먼저 실행하세요."
  exit 1
fi

echo "======================================"
echo " FIS Experiment Templates 생성"
echo "======================================"
echo "  Role ARN        : $ROLE_ARN"
echo "  Stop Alarm ARN  : $STOP_ALARM_ARN"
echo ""

# 대상 EC2 인스턴스 조회
INSTANCE_ID=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text 2>/dev/null)

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo "[WARN] 실행 중인 EC2 인스턴스가 없습니다."
  echo "       인스턴스 ID를 직접 설정합니다 (예: i-0123456789abcdef0)"
  INSTANCE_ID="i-REPLACE_WITH_YOUR_INSTANCE_ID"
fi
echo "  Target EC2      : $INSTANCE_ID"
echo ""

# ──────────────────────────────────────────────
# Template 1: EC2 인스턴스 중단 실험
# ──────────────────────────────────────────────
echo "[1/3] Experiment Template: EC2 인스턴스 강제 중단..."

cat > /tmp/fis-template-ec2-stop.json << EOF
{
  "description": "EC2 인스턴스 강제 중단 실험 - 서비스 복원력 검증",
  "targets": {
    "targetInstances": {
      "resourceType": "aws:ec2:instance",
      "resourceArns": [
        "arn:aws:ec2:${REGION}:$(aws sts get-caller-identity --query Account --output text):instance/${INSTANCE_ID}"
      ],
      "selectionMode": "ALL"
    }
  },
  "actions": {
    "stopInstances": {
      "actionId": "aws:ec2:stop-instances",
      "parameters": {
        "startInstancesAfterDuration": "PT5M"
      },
      "targets": {
        "Instances": "targetInstances"
      }
    }
  },
  "stopConditions": [
    {
      "source": "aws:cloudwatch:alarm",
      "value": "${STOP_ALARM_ARN}"
    }
  ],
  "roleArn": "${ROLE_ARN}",
  "tags": {
    "Name": "fis-ec2-stop-experiment",
    "Environment": "lab",
    "Purpose": "chaos-engineering"
  },
  "logConfiguration": {
    "cloudWatchLogsConfiguration": {
      "logGroupArn": "arn:aws:logs:${REGION}:$(aws sts get-caller-identity --query Account --output text):log-group:/aws/fis/experiments:*"
    },
    "logSchemaVersion": 2
  }
}
EOF

TEMPLATE1_ID=$(aws fis create-experiment-template \
  --region "$REGION" \
  --cli-input-json file:///tmp/fis-template-ec2-stop.json \
  --query 'experimentTemplate.id' \
  --output text)
echo "[OK] Template 생성 완료: $TEMPLATE1_ID (EC2 Stop)"

# ──────────────────────────────────────────────
# Template 2: EC2 CPU 스트레스 실험 (SSM 기반)
# ──────────────────────────────────────────────
echo ""
echo "[2/3] Experiment Template: EC2 CPU 스트레스 주입..."

cat > /tmp/fis-template-cpu-stress.json << EOF
{
  "description": "EC2 CPU 스트레스 실험 - 고부하 상황에서의 동작 검증",
  "targets": {
    "targetInstances": {
      "resourceType": "aws:ec2:instance",
      "resourceArns": [
        "arn:aws:ec2:${REGION}:$(aws sts get-caller-identity --query Account --output text):instance/${INSTANCE_ID}"
      ],
      "selectionMode": "ALL"
    }
  },
  "actions": {
    "cpuStress": {
      "actionId": "aws:ssm:send-command",
      "parameters": {
        "documentArn": "arn:aws:ssm:${REGION}::document/AWSFIS-Run-CPU-Stress",
        "documentParameters": "{\"DurationSeconds\": \"120\", \"CPU\": \"0\", \"InstallDependencies\": \"True\"}",
        "duration": "PT3M"
      },
      "targets": {
        "Instances": "targetInstances"
      }
    }
  },
  "stopConditions": [
    {
      "source": "aws:cloudwatch:alarm",
      "value": "${STOP_ALARM_ARN}"
    }
  ],
  "roleArn": "${ROLE_ARN}",
  "tags": {
    "Name": "fis-cpu-stress-experiment",
    "Environment": "lab",
    "Purpose": "chaos-engineering"
  }
}
EOF

TEMPLATE2_ID=$(aws fis create-experiment-template \
  --region "$REGION" \
  --cli-input-json file:///tmp/fis-template-cpu-stress.json \
  --query 'experimentTemplate.id' \
  --output text)
echo "[OK] Template 생성 완료: $TEMPLATE2_ID (CPU Stress)"

# ──────────────────────────────────────────────
# Template 3: 네트워크 지연 실험
# ──────────────────────────────────────────────
echo ""
echo "[3/3] Experiment Template: 네트워크 지연 주입..."

cat > /tmp/fis-template-network-latency.json << EOF
{
  "description": "네트워크 지연 실험 - 고지연 상황에서의 서비스 응답성 검증",
  "targets": {
    "targetInstances": {
      "resourceType": "aws:ec2:instance",
      "resourceArns": [
        "arn:aws:ec2:${REGION}:$(aws sts get-caller-identity --query Account --output text):instance/${INSTANCE_ID}"
      ],
      "selectionMode": "ALL"
    }
  },
  "actions": {
    "networkLatency": {
      "actionId": "aws:ssm:send-command",
      "parameters": {
        "documentArn": "arn:aws:ssm:${REGION}::document/AWSFIS-Run-Network-Latency",
        "documentParameters": "{\"DelayMilliseconds\": \"200\", \"JitterMilliseconds\": \"10\", \"DurationSeconds\": \"120\", \"InstallDependencies\": \"True\", \"Interface\": \"eth0\"}",
        "duration": "PT3M"
      },
      "targets": {
        "Instances": "targetInstances"
      }
    }
  },
  "stopConditions": [
    {
      "source": "aws:cloudwatch:alarm",
      "value": "${STOP_ALARM_ARN}"
    }
  ],
  "roleArn": "${ROLE_ARN}",
  "tags": {
    "Name": "fis-network-latency-experiment",
    "Environment": "lab",
    "Purpose": "chaos-engineering"
  }
}
EOF

TEMPLATE3_ID=$(aws fis create-experiment-template \
  --region "$REGION" \
  --cli-input-json file:///tmp/fis-template-network-latency.json \
  --query 'experimentTemplate.id' \
  --output text)
echo "[OK] Template 생성 완료: $TEMPLATE3_ID (Network Latency)"

# Template ID 저장
mkdir -p /tmp/fis-lab
echo "$TEMPLATE1_ID" > /tmp/fis-lab/template_ec2_stop.txt
echo "$TEMPLATE2_ID" > /tmp/fis-lab/template_cpu_stress.txt
echo "$TEMPLATE3_ID" > /tmp/fis-lab/template_network_latency.txt

echo ""
echo "======================================"
echo " 생성된 Experiment Templates"
echo "======================================"
aws fis list-experiment-templates \
  --region "$REGION" \
  --query 'experimentTemplates[].{ID:id, Description:description, CreatedTime:creationTime}' \
  --output table

echo ""
echo "다음 단계: 04_run_experiment.sh 를 실행하세요."
