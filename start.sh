#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시스템 시작!! (독립 서버 모드)"

# 기존 프로세스 확인
MAIN_SERVER_RUNNING=false
WATCHDOG_RUNNING=false

if [ -f "main_server.pid" ]; then
    PID=$(cat main_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        MAIN_SERVER_RUNNING=true
    fi
fi

if [ -f "watchdog.pid" ]; then
    PID=$(cat watchdog.pid)
    if ps -p $PID > /dev/null 2>&1; then
        WATCHDOG_RUNNING=true
    fi
fi

if [ "$MAIN_SERVER_RUNNING" = true ] || [ "$WATCHDOG_RUNNING" = true ]; then
    echo "이미 실행 중입니다:"
    [ "$MAIN_SERVER_RUNNING" = true ] && echo "  - 메인 서버 (PID: $(cat main_server.pid))"
    [ "$WATCHDOG_RUNNING" = true ] && echo "  - 워치독 서버 (PID: $(cat watchdog.pid))"
    echo "종료하려면 ./stop.sh를 실행하세요"
    exit 1
fi

# 기존 PID 파일 정리
rm -f main_server.pid watchdog.pid

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

echo ""
echo "🚀 메인 서버 시작 중..."
echo "   - 크롤링 및 출퇴근 처리 담당"
echo "   - HTTP API 서버로 실행"

# 메인 서버 백그라운드 실행
nohup python3 main_server.py > main_server.out 2>&1 &
MAIN_PID=$!
echo $MAIN_PID > main_server.pid

# 메인 서버 시작 대기
sleep 3

echo ""
echo "🕐 워치독 서버 시작 중..."
echo "   - 스케줄링 및 명령 전송 담당"
echo "   - 메인 서버와 HTTP 통신"

# 워치독 서버 백그라운드 실행
nohup python3 watchdog.py > watchdog.out 2>&1 &
WATCHDOG_PID=$!
echo $WATCHDOG_PID > watchdog.pid

echo ""
echo "✅ 출근 관리 시스템 시작 완료"
echo "   📡 메인 서버 (PID: $MAIN_PID) - 크롤링 담당"
echo "   ⏰ 워치독 서버 (PID: $WATCHDOG_PID) - 스케줄링 담당"
echo ""
echo "📁 로그 확인: logs/ 디렉토리"
echo "🔗 헬스체크: curl http://localhost:8080/api/health"
echo "🛑 종료 방법: ./stop.sh 실행"
echo ""