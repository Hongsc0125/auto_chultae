#!/bin/bash

cd "$(dirname "$0")"

echo "출근 관리 시작!!"

# 기존 프로세스 확인
if [ -f "auto_chultae.pid" ]; then
    PID=$(cat auto_chultae.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "이미 실행 중입니다 (PID: $PID)"
        echo "종료하려면 ./stop.sh를 실행하세요"
        exit 1
    else
        echo "PID 파일이 존재하지만 프로세스가 실행되지 않습니다. PID 파일을 삭제합니다."
        rm -f auto_chultae.pid
    fi
fi

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

# nohup으로 백그라운드 실행
nohup python3 auto_chultae.py > logs/nohup.out 2>&1 &

# PID 저장
echo $! > auto_chultae.pid

echo "출근 관리 시스템 시작 완료 (PID: $!)"