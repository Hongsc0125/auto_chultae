#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시스템 시작!! (독립 서버 모드)"

# 환경변수에서 포트 정보 가져오기
source .env 2>/dev/null || true
MAIN_SERVER_URL=${MAIN_SERVER_URL:-"http://127.0.0.1:9000"}
MAIN_PORT=$(echo $MAIN_SERVER_URL | sed -n 's/.*:\([0-9]*\).*/\1/p')
MAIN_PORT=${MAIN_PORT:-9000}

echo "🔍 포트 충돌 및 기존 프로세스 검사 중..."

# 포트 점유 프로세스 확인 및 정리
check_and_kill_port_processes() {
    local port=$1
    local port_pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -o 'pid=[0-9]*' | cut -d= -f2)

    if [ ! -z "$port_pids" ]; then
        echo "⚠️  포트 $port 점유 프로세스 발견: $port_pids"
        for pid in $port_pids; do
            if ps -p $pid > /dev/null 2>&1; then
                echo "   포트 $port 점유 프로세스 종료 중... (PID: $pid)"
                kill $pid 2>/dev/null
                sleep 2
                if ps -p $pid > /dev/null 2>&1; then
                    echo "   강제 종료 중... (PID: $pid)"
                    kill -9 $pid 2>/dev/null
                fi
            fi
        done
        sleep 1
    fi
}

# 관련 프로세스들 정리
cleanup_related_processes() {
    echo "🧹 관련 프로세스 정리 중..."

    # main_server 관련 프로세스
    local main_pids=$(pgrep -f "main_server\|gunicorn.*main_server" 2>/dev/null)
    if [ ! -z "$main_pids" ]; then
        echo "   main_server 관련 프로세스 종료 중: $main_pids"
        kill $main_pids 2>/dev/null
        sleep 2
        pkill -9 -f "main_server\|gunicorn.*main_server" 2>/dev/null
    fi

    # watchdog 관련 프로세스
    local watchdog_pids=$(pgrep -f "python.*watchdog.py" 2>/dev/null)
    if [ ! -z "$watchdog_pids" ]; then
        echo "   watchdog 관련 프로세스 종료 중: $watchdog_pids"
        kill $watchdog_pids 2>/dev/null
        sleep 2
        pkill -9 -f "python.*watchdog.py" 2>/dev/null
    fi
}

# 포트 및 프로세스 정리 실행
check_and_kill_port_processes $MAIN_PORT
cleanup_related_processes

# 기존 PID 파일 정리
rm -f main_server.pid watchdog.pid auto_chultae.pid heartbeat.txt 2>/dev/null

echo "✅ 환경 정리 완료"

# 로그 디렉토리 생성
mkdir -p logs

# 가상환경 활성화 및 의존성 설치
if [ -d ".venv" ]; then
    echo "가상환경 활성화 중..."
    source .venv/bin/activate
    echo "🔧 의존성 설치/업데이트 중..."
    pip3 install -r requirements.txt
elif [ -d "venv" ]; then
    echo "가상환경 활성화 중..."
    source venv/bin/activate
    echo "🔧 의존성 설치/업데이트 중..."
    pip3 install -r requirements.txt
else
    echo "가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다."
    echo "⚠️  주의: 가상환경 없이 의존성 설치 중..."
    pip3 install -r requirements.txt
fi

# Playwright 브라우저 설치 확인
echo "🌐 Playwright 브라우저 설치 확인 중..."
playwright install chromium --with-deps 2>/dev/null || echo "   Playwright 설치 완료 또는 이미 설치됨"

echo ""
echo "🚀 메인 서버 시작 중..."
echo "   - 크롤링 및 출퇴근 처리 담당"
echo "   - Gunicorn WSGI 서버로 실행 (프로덕션)"

# 메인 서버 백그라운드 실행 (Gunicorn 사용)
nohup gunicorn -c gunicorn.conf.py main_server:app > main_server.out 2>&1 &
MAIN_PID=$!
echo $MAIN_PID > main_server.pid

# 메인 서버 시작 검증
echo "⏳ 메인 서버 시작 검증 중..."
for i in {1..15}; do
    if curl -s http://localhost:$MAIN_PORT/api/health > /dev/null 2>&1; then
        echo "✅ 메인 서버 헬스체크 성공"
        break
    elif [ $i -eq 15 ]; then
        echo "❌ 메인 서버 시작 실패 - 헬스체크 타임아웃"
        echo "로그 확인: tail -f main_server.out"
        exit 1
    else
        echo "   대기 중... ($i/15)"
        sleep 2
    fi
done

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
echo "🔗 헬스체크: curl http://localhost:9000/api/health"
echo "🛑 종료 방법: ./stop.sh 실행"
echo ""