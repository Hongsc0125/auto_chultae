#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시작!! (with Watchdog)"

# 기존 프로세스 확인 (워치독과 메인 프로그램 모두)
MAIN_RUNNING=false
WATCHDOG_RUNNING=false

if [ -f "auto_chultae.pid" ]; then
    PID=$(cat auto_chultae.pid)
    if ps -p $PID > /dev/null 2>&1; then
        MAIN_RUNNING=true
    fi
fi

if pgrep -f "python.*watchdog.py" > /dev/null; then
    WATCHDOG_RUNNING=true
fi

if [ "$MAIN_RUNNING" = true ] || [ "$WATCHDOG_RUNNING" = true ]; then
    echo "이미 실행 중입니다:"
    [ "$MAIN_RUNNING" = true ] && echo "  - 메인 프로그램 (PID: $(cat auto_chultae.pid))"
    [ "$WATCHDOG_RUNNING" = true ] && echo "  - 워치독"
    echo "종료하려면 ./stop.sh를 실행하세요"
    exit 1
fi

# 기존 PID 파일 정리
rm -f auto_chultae.pid watchdog.pid

# 로그 디렉토리 생성
mkdir -p logs

# 가상환경 활성화 확인
if [ -d ".venv" ]; then
    echo "가상환경 활성화 중..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "가상환경 활성화 중..."
    source venv/bin/activate
else
    echo "가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다."
fi

echo "워치독 시작 중..."
echo "워치독이 메인 프로그램을 모니터링하며 무한 대기 시 자동 재시작합니다."

# nohup으로 워치독 백그라운드 실행
nohup python3 watchdog.py > watchdog.out 2>&1 &

# 워치독 PID 저장
echo $! > watchdog.pid

echo ""
echo "✅ 출근 관리 시스템 시작 완료 (Watchdog PID: $!)"
echo "📁 로그 확인: logs/ 디렉토리"
echo "🛑 종료 방법: ./stop.sh 실행"
echo ""