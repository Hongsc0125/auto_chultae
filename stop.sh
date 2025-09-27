#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시스템 종료!! (독립 서버 모드)"
echo ""

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

# 기타 관련 파일 정리
rm -f auto_chultae.pid 2>/dev/null
rm -f heartbeat.txt 2>/dev/null

echo ""
echo "✅ 출근 관리 시스템 종료 완료"
echo ""