#!/bin/bash
# AWS FIS - 실험 시작/모니터링/중단
# 다이어그램의 "FIS Engine: Start experiment / Stop experiment" 에 해당
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"

usage() {
  cat << EOF
사용법: $0 <command> [options]

Commands:
  start <template_type>   실험 시작 (ec2-stop | cpu-stress | network-latency)
  stop  <experiment_id>   실험 강제 중단
  status <experiment_id>  실험 상태 조회
  list                    전체 실험 목록 조회
  watch <experiment_id>   실험 실시간 모니터링

예시:
  $0 start ec2-stop
  $0 start cpu-stress
  $0 status EXPxxxxxxxxxxx
  $0 stop EXPxxxxxxxxxxx
  $0 list
  $0 watch EXPxxxxxxxxxxx
EOF
  exit 1
}

# ──────────────────────────────────────────────
# 실험 시작
# ──────────────────────────────────────────────
start_experiment() {
  local TYPE="$1"
  local TEMPLATE_FILE

  case "$TYPE" in
    ec2-stop)
      TEMPLATE_FILE="/tmp/fis-lab/template_ec2_stop.txt"
      ;;
    cpu-stress)
      TEMPLATE_FILE="/tmp/fis-lab/template_cpu_stress.txt"
      ;;
    network-latency)
      TEMPLATE_FILE="/tmp/fis-lab/template_network_latency.txt"
      ;;
    *)
      echo "[ERROR] 알 수 없는 실험 유형: $TYPE"
      echo "       사용 가능: ec2-stop | cpu-stress | network-latency"
      exit 1
      ;;
  esac

  if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "[ERROR] Template ID 파일을 찾을 수 없습니다: $TEMPLATE_FILE"
    echo "        03_create_experiment_template.sh 를 먼저 실행하세요."
    exit 1
  fi

  TEMPLATE_ID=$(cat "$TEMPLATE_FILE")

  echo "======================================"
  echo " 실험 시작: $TYPE"
  echo " Template ID: $TEMPLATE_ID"
  echo "======================================"
  echo ""
  echo "[!] 주의: 실제 AWS 리소스에 장애를 주입합니다."
  read -r -p "    계속 진행하시겠습니까? (yes/no): " CONFIRM

  if [ "$CONFIRM" != "yes" ]; then
    echo "[ABORT] 실험을 취소했습니다."
    exit 0
  fi

  echo ""
  echo "[START] 실험 시작 중..."
  EXPERIMENT_ID=$(aws fis start-experiment \
    --region "$REGION" \
    --experiment-template-id "$TEMPLATE_ID" \
    --tags "RunBy=cli-script,Type=$TYPE" \
    --query 'experiment.id' \
    --output text)

  echo "[OK] 실험 시작됨: $EXPERIMENT_ID"
  echo ""

  # 실험 ID 저장
  mkdir -p /tmp/fis-lab
  echo "$EXPERIMENT_ID" > /tmp/fis-lab/last_experiment_id.txt

  echo "실험 상태 확인:"
  get_status "$EXPERIMENT_ID"

  echo ""
  echo "실시간 모니터링: $0 watch $EXPERIMENT_ID"
  echo "실험 중단:       $0 stop $EXPERIMENT_ID"
}

# ──────────────────────────────────────────────
# 실험 상태 조회
# ──────────────────────────────────────────────
get_status() {
  local EXPERIMENT_ID="$1"

  aws fis get-experiment \
    --region "$REGION" \
    --id "$EXPERIMENT_ID" \
    --query '{
      ID: experiment.id,
      State: experiment.state.status,
      Reason: experiment.state.reason,
      StartTime: experiment.startTime,
      EndTime: experiment.endTime,
      TemplateID: experiment.experimentTemplateId
    }' \
    --output table
}

# ──────────────────────────────────────────────
# 실험 강제 중단 (Stop Experiment)
# ──────────────────────────────────────────────
stop_experiment() {
  local EXPERIMENT_ID="$1"

  echo "======================================"
  echo " 실험 중단: $EXPERIMENT_ID"
  echo "======================================"

  CURRENT_STATE=$(aws fis get-experiment \
    --region "$REGION" \
    --id "$EXPERIMENT_ID" \
    --query 'experiment.state.status' \
    --output text)

  echo "현재 상태: $CURRENT_STATE"

  if [ "$CURRENT_STATE" = "completed" ] || [ "$CURRENT_STATE" = "stopped" ] || [ "$CURRENT_STATE" = "failed" ]; then
    echo "[INFO] 실험이 이미 종료 상태입니다: $CURRENT_STATE"
    exit 0
  fi

  echo ""
  echo "[STOP] 실험 중단 요청 중..."
  aws fis stop-experiment \
    --region "$REGION" \
    --id "$EXPERIMENT_ID" \
    --query 'experiment.state.{Status:status, Reason:reason}' \
    --output table

  echo "[OK] 중단 요청 완료"

  # 중단 완료 대기
  echo ""
  echo "중단 완료 대기 중..."
  for i in {1..12}; do
    sleep 5
    STATE=$(aws fis get-experiment \
      --region "$REGION" \
      --id "$EXPERIMENT_ID" \
      --query 'experiment.state.status' \
      --output text)
    echo "  [$i] 상태: $STATE"
    if [ "$STATE" = "stopped" ] || [ "$STATE" = "completed" ] || [ "$STATE" = "failed" ]; then
      echo "[OK] 실험이 중단되었습니다: $STATE"
      break
    fi
  done
}

# ──────────────────────────────────────────────
# 전체 실험 목록
# ──────────────────────────────────────────────
list_experiments() {
  echo "======================================"
  echo " 실험 목록"
  echo "======================================"
  aws fis list-experiments \
    --region "$REGION" \
    --query 'experiments[].{
      ID: id,
      State: state.status,
      TemplateID: experimentTemplateId,
      StartTime: startTime
    }' \
    --output table
}

# ──────────────────────────────────────────────
# 실험 실시간 모니터링
# ──────────────────────────────────────────────
watch_experiment() {
  local EXPERIMENT_ID="$1"

  echo "======================================"
  echo " 실험 실시간 모니터링: $EXPERIMENT_ID"
  echo " (종료: Ctrl+C)"
  echo "======================================"

  while true; do
    clear
    echo "======================================"
    echo " AWS FIS 실험 모니터링"
    echo " ID: $EXPERIMENT_ID"
    echo " 시각: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================"

    RESULT=$(aws fis get-experiment \
      --region "$REGION" \
      --id "$EXPERIMENT_ID" \
      --query 'experiment.{
        Status: state.status,
        Reason: state.reason,
        StartTime: startTime,
        EndTime: endTime
      }' \
      --output table 2>&1)

    echo "$RESULT"

    STATE=$(aws fis get-experiment \
      --region "$REGION" \
      --id "$EXPERIMENT_ID" \
      --query 'experiment.state.status' \
      --output text 2>/dev/null)

    echo ""
    echo "--- Actions 상태 ---"
    aws fis get-experiment \
      --region "$REGION" \
      --id "$EXPERIMENT_ID" \
      --query 'experiment.actions' \
      --output table 2>/dev/null || echo "(액션 정보 없음)"

    if [ "$STATE" = "completed" ] || [ "$STATE" = "stopped" ] || [ "$STATE" = "failed" ]; then
      echo ""
      echo "[완료] 실험 종료 상태: $STATE"
      break
    fi

    echo ""
    echo "다음 갱신까지 15초 대기..."
    sleep 15
  done
}

# ──────────────────────────────────────────────
# main
# ──────────────────────────────────────────────
[ $# -lt 1 ] && usage

COMMAND="$1"
shift

case "$COMMAND" in
  start)
    [ $# -lt 1 ] && { echo "[ERROR] 실험 유형을 지정하세요."; usage; }
    start_experiment "$1"
    ;;
  stop)
    [ $# -lt 1 ] && { echo "[ERROR] 실험 ID를 지정하세요."; usage; }
    stop_experiment "$1"
    ;;
  status)
    [ $# -lt 1 ] && { echo "[ERROR] 실험 ID를 지정하세요."; usage; }
    get_status "$1"
    ;;
  list)
    list_experiments
    ;;
  watch)
    [ $# -lt 1 ] && { echo "[ERROR] 실험 ID를 지정하세요."; usage; }
    watch_experiment "$1"
    ;;
  *)
    echo "[ERROR] 알 수 없는 명령: $COMMAND"
    usage
    ;;
esac
