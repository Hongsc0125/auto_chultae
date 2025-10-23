#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시스템 종료!! (독립 서버 모드)"
echo ""

# 환경변수에서 포트 정보 가져오기
source .env 2>/dev/null || true
MAIN_SERVER_URL=${MAIN_SERVER_URL:-"http://127.0.0.1:9000"}
MAIN_PORT=$(echo $MAIN_SERVER_URL | sed -n 's/.*:\([0-9]*\).*/\1/p')
MAIN_PORT=${MAIN_PORT:-9000}

# 포트 정리 함수
cleanup_port() {
    local port=$1
    local port_pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -o 'pid=[0-9]*' | cut -d= -f2)

    if [ ! -z "$port_pids" ]; then
        echo "🧹 포트 $port 정리 중..."
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
    fi
}

# 완전한 프로세스 정리 함수
complete_cleanup() {
    echo "🔍 완전한 시스템 정리 중..."

    # 모든 관련 프로세스 찾기 및 종료
    local all_pids=$(pgrep -f "main_server\|gunicorn.*main_server\|python.*watchdog\.py\|auto_chultae" 2>/dev/null)

    if [ ! -z "$all_pids" ]; then
        echo "   관련 프로세스 발견: $all_pids"
        kill $all_pids 2>/dev/null
        sleep 3

        # 여전히 살아있는 프로세스 강제 종료
        local remaining_pids=$(pgrep -f "main_server\|gunicorn.*main_server\|python.*watchdog\.py\|auto_chultae" 2>/dev/null)
        if [ ! -z "$remaining_pids" ]; then
            echo "   남은 프로세스 강제 종료: $remaining_pids"
            kill -9 $remaining_pids 2>/dev/null
        fi
    fi

    # 포트 정리
    cleanup_port $MAIN_PORT
}

# 워치독 서버 종료
echo "🕐 워치독 서버 종료 중..."
if [ -f "watchdog.pid" ]; then
    WATCHDOG_PID=$(cat watchdog.pid)
    if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
        kill $WATCHDOG_PID
        echo "   워치독 서버 종료 중... (PID: $WATCHDOG_PID)"
        sleep 2
        if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
            kill -9 $WATCHDOG_PID
            echo "   워치독 서버 강제 종료"
        else
            echo "   워치독 서버 정상 종료"
        fi
    else
        echo "   워치독 서버가 실행되지 않음 (PID: $WATCHDOG_PID)"
    fi
    rm -f watchdog.pid
else
    # 프로세스 이름으로 워치독 찾기
    WATCHDOG_PIDS=$(pgrep -f "python.*watchdog.py")
    if [ ! -z "$WATCHDOG_PIDS" ]; then
        echo "   실행 중인 워치독 서버를 찾았습니다. 종료합니다..."
        kill $WATCHDOG_PIDS 2>/dev/null
        sleep 2
        pkill -9 -f "python.*watchdog.py" 2>/dev/null
        echo "   워치독 서버 종료 완료"
    else
        echo "   워치독 서버가 실행되지 않음"
    fi
fi

echo ""

# 메인 서버 종료
echo "📡 메인 서버 종료 중..."
if [ -f "main_server.pid" ]; then
    MAIN_PID=$(cat main_server.pid)
    if ps -p $MAIN_PID > /dev/null 2>&1; then
        kill $MAIN_PID
        echo "   메인 서버 종료 중... (PID: $MAIN_PID)"

        # 종료 확인 (최대 10초 대기)
        for i in {1..10}; do
            if ! ps -p $MAIN_PID > /dev/null 2>&1; then
                echo "   메인 서버 정상 종료"
                break
            fi
            echo "   종료 대기 중... ($i/10)"
            sleep 1
        done

        # 여전히 실행 중이면 강제 종료
        if ps -p $MAIN_PID > /dev/null 2>&1; then
            echo "   메인 서버 강제 종료"
            kill -9 $MAIN_PID
        fi
    else
        echo "   메인 서버가 실행되지 않음 (PID: $MAIN_PID)"
    fi
    rm -f main_server.pid
else
    # 프로세스 이름으로 메인 서버 찾기
    MAIN_PIDS=$(pgrep -f "python.*main_server.py")
    if [ ! -z "$MAIN_PIDS" ]; then
        echo "   실행 중인 메인 서버를 찾았습니다. 종료합니다..."
        kill $MAIN_PIDS 2>/dev/null
        sleep 3
        # 강제 종료
        REMAINING=$(pgrep -f "python.*main_server.py")
        if [ ! -z "$REMAINING" ]; then
            kill -9 $REMAINING
            echo "   메인 서버 강제 종료"
        else
            echo "   메인 서버 정상 종료"
        fi
    else
        echo "   메인 서버가 실행되지 않음"
    fi
fi

# 완전한 정리 수행
complete_cleanup

# 기타 관련 파일 정리
rm -f main_server.pid watchdog.pid auto_chultae.pid heartbeat.txt 2>/dev/null

# 최종 검증
echo "🔍 최종 정리 검증 중..."
remaining_processes=$(pgrep -f "main_server\|gunicorn.*main_server\|python.*watchdog\.py" 2>/dev/null)
port_check=$(ss -tlnp 2>/dev/null | grep ":$MAIN_PORT ")

if [ ! -z "$remaining_processes" ]; then
    echo "⚠️  아직 남은 프로세스: $remaining_processes"
    kill -9 $remaining_processes 2>/dev/null
fi

if [ ! -z "$port_check" ]; then
    echo "⚠️  포트 $MAIN_PORT 아직 점유 중"
    cleanup_port $MAIN_PORT
else
    echo "✅ 포트 $MAIN_PORT 정리 완료"
fi

echo ""
echo "✅ 출근 관리 시스템 종료 완료"
echo "   🧹 모든 프로세스 및 포트 정리됨"
echo ""