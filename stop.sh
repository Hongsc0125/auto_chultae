#!/bin/bash

# 출석 관리 시스템 종료 스크립트 (Watchdog 포함)

cd "$(dirname "$0")"

echo "출근 관리 종료!! (Watchdog 포함)"

# 워치독 종료 먼저
echo "워치독 종료 중..."
if [ -f "watchdog.pid" ]; then
    WATCHDOG_PID=$(cat watchdog.pid)
    if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
        kill $WATCHDOG_PID
        echo "워치독 종료 중... (PID: $WATCHDOG_PID)"
        sleep 2
        if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
            kill -9 $WATCHDOG_PID
            echo "워치독 강제 종료"
        fi
    fi
    rm -f watchdog.pid
else
    # 프로세스 이름으로 워치독 종료
    WATCHDOG_PIDS=$(pgrep -f "python.*watchdog.py")
    if [ ! -z "$WATCHDOG_PIDS" ]; then
        echo "실행 중인 워치독을 찾았습니다. 종료합니다..."
        kill $WATCHDOG_PIDS 2>/dev/null
        sleep 2
        # 강제 종료
        pkill -9 -f "python.*watchdog.py" 2>/dev/null
    fi
fi

# PID 파일 확인
if [ ! -f "auto_chultae.pid" ]; then
    echo "PID 파일을 찾을 수 없습니다."
    echo "프로세스가 실행되지 않거나 다른 방법으로 시작되었을 수 있습니다."
    
    # auto_chultae.py 프로세스 직접 검색
    PIDS=$(pgrep -f "python.*auto_chultae.py")
    if [ ! -z "$PIDS" ]; then
        echo "실행 중인 auto_chultae.py 프로세스를 찾았습니다:"
        ps -p $PIDS -o pid,cmd
        echo "이 프로세스들을 종료하시겠습니까? (y/N)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            kill $PIDS
            sleep 2
            # 강제 종료가 필요한 경우
            REMAINING=$(pgrep -f "python.*auto_chultae.py")
            if [ ! -z "$REMAINING" ]; then
                echo "일부 프로세스가 여전히 실행 중입니다. 강제 종료합니다."
                kill -9 $REMAINING
            fi
            echo "프로세스가 종료되었습니다."
        fi
    else
        echo "실행 중인 auto_chultae.py 프로세스를 찾을 수 없습니다."
    fi
    exit 0
fi

# PID 읽기
PID=$(cat auto_chultae.pid)

# 프로세스 실행 여부 확인
if ! ps -p $PID > /dev/null 2>&1; then
    echo "PID $PID 프로세스가 실행되지 않습니다."
    rm -f auto_chultae.pid
    exit 0
fi

echo "프로세스 종료 중... (PID: $PID)"

# 정상 종료 시도
kill $PID

# 종료 확인 (최대 10초 대기)
for i in {1..10}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "프로세스가 정상적으로 종료되었습니다."
        rm -f auto_chultae.pid
        exit 0
    fi
    echo "종료 대기 중... ($i/10)"
    sleep 1
done

# 강제 종료
echo "정상 종료되지 않았습니다. 강제 종료합니다."
kill -9 $PID

# 최종 확인
sleep 1
if ps -p $PID > /dev/null 2>&1; then
    echo "프로세스 종료에 실패했습니다."
    exit 1
else
    echo "프로세스가 강제 종료되었습니다."
    rm -f auto_chultae.pid
fi