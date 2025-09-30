#!/usr/bin/env python3
"""
Auto Chultae Watchdog - 스케줄링 전용
출퇴근 시간에 맞춰서 서브프로세스로 크롤링 함수 실행
"""

import os
import sys
import logging
import subprocess
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from db_manager import db_manager

# .env 파일 로드
load_dotenv()

# 로깅 설정
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"watchdog_{datetime.now().strftime('%Y%m%d')}.log")

    logger = logging.getLogger('watchdog')
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - [WATCHDOG] %(message)s')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# 사용자 목록 조회
def get_users():
    """데이터베이스에서 활성 사용자 목록 조회"""
    try:
        return db_manager.get_active_users()
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {e}")
        return []

# 메인 서버 통신 함수들
def send_command_to_main_server(command):
    """메인 서버에 명령 전송"""
    try:
        import requests

        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")
        response = requests.post(f"{main_server_url}/api/command",
                               json={"command": command},
                               timeout=300)  # 5분 타임아웃 (크롤링 작업 고려)

        if response.status_code == 200:
            logger.info(f"{command} 명령 전송 성공")
            db_manager.log_system("INFO", "watchdog", f"{command} 명령 전송 성공")
            return True
        else:
            logger.error(f"{command} 명령 전송 실패: {response.status_code}")
            db_manager.log_system("ERROR", "watchdog", f"{command} 명령 전송 실패: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"{command} 명령 전송 오류 (메인 서버 연결 실패): {e}")
        db_manager.log_system("ERROR", "watchdog", f"{command} 명령 전송 오류: {e}")
        return False
    except Exception as e:
        logger.error(f"{command} 명령 전송 오류: {e}")
        db_manager.log_system("ERROR", "watchdog", f"{command} 명령 전송 오류: {e}")
        return False

def execute_punch_in():
    """출근 처리 실행 (메인 서버에 명령 전송)"""
    logger.info("출근 처리 시작 - 메인 서버에 명령 전송")
    return send_command_to_main_server("punch_in")

def execute_punch_out():
    """퇴근 처리 실행 (메인 서버에 명령 전송)"""
    logger.info("퇴근 처리 시작 - 메인 서버에 명령 전송")
    return send_command_to_main_server("punch_out")

# 스케줄링 함수들
def punch_in_with_retry():
    """출근 시간대 재시도 로직 (08:00-08:40) - 오늘자 성공 이력 확인"""
    now = datetime.now()
    current_time = now.time()

    # 08:00-08:40 시간대가 아니면 실행하지 않음
    if not (dt_time(8, 0) <= current_time <= dt_time(8, 40)):
        logger.debug(f"출근 시간대가 아님: {current_time}")
        return

    # 모든 활성 사용자의 오늘자 출근 성공 이력 확인
    users = get_users()
    users_needing_punch_in = []

    for user in users:
        user_id = user["user_id"]
        has_success_today = db_manager.has_today_success(user_id, "punch_in")

        if has_success_today:
            logger.info(f"[{user_id}] 오늘자 출근 성공 이력 있음 - 스킵")
        else:
            users_needing_punch_in.append(user_id)

    if not users_needing_punch_in:
        logger.info("모든 사용자가 오늘 이미 출근 완료 - 실행하지 않음")
        return

    logger.info(f"출근 처리 시도 시작 ({current_time}) - 대상 사용자: {users_needing_punch_in}")
    success = execute_punch_in()

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(8, 35):
            logger.warning(f"출근 처리 실패 - 대상 사용자: {users_needing_punch_in}")

def punch_out_with_retry():
    """퇴근 시간대 재시도 로직 (18:00-19:00) - 오늘자 성공 이력 확인"""
    now = datetime.now()
    current_time = now.time()

    # 18:00-19:00 시간대가 아니면 실행하지 않음
    if not (dt_time(18, 0) <= current_time <= dt_time(19, 0)):
        logger.debug(f"퇴근 시간대가 아님: {current_time}")
        return

    # 모든 활성 사용자의 오늘자 퇴근 성공 이력 확인
    users = get_users()
    users_needing_punch_out = []

    for user in users:
        user_id = user["user_id"]
        has_success_today = db_manager.has_today_success(user_id, "punch_out")

        if has_success_today:
            logger.info(f"[{user_id}] 오늘자 퇴근 성공 이력 있음 - 스킵")
        else:
            users_needing_punch_out.append(user_id)

    if not users_needing_punch_out:
        logger.info("모든 사용자가 오늘 이미 퇴근 완료 - 실행하지 않음")
        return

    logger.info(f"퇴근 처리 시도 시작 ({current_time}) - 대상 사용자: {users_needing_punch_out}")
    success = execute_punch_out()

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(18, 55):
            logger.warning(f"퇴근 처리 실패 - 대상 사용자: {users_needing_punch_out}")

def main():
    """워치독 메인 함수 - 스케줄링만 담당"""
    import signal

    # 시그널 핸들러 설정
    def signal_handler(signum, frame):
        logger.info("종료 신호 수신")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("워치독 시스템 시작 (스케줄링 전용)")

    # 데이터베이스 연결 테스트
    if not db_manager.test_connection():
        logger.error("데이터베이스 연결 실패! 계속 진행하지만 로그는 DB에 저장되지 않습니다.")
    else:
        logger.info("데이터베이스 연결 성공")
        db_manager.log_system("INFO", "watchdog", "워치독 시스템 시작")

    # 워치독 시작 시 초기 출근 체크 수행 (강제 실행)
    logger.info("🚀 워치독 시작 - 초기 출근 체크 수행 (강제)")
    try:
        # 초기 실행 시에는 사전 체크 무시하고 강제로 Main Server 호출
        logger.info("초기 출근 처리 시도 시작 (강제 실행)")
        success = execute_punch_in()
        if success:
            logger.info("✅ 워치독 초기 출근 체크 완료")
        else:
            logger.warning("⚠️ 워치독 초기 출근 체크 실패했지만 계속 진행")
    except Exception as e:
        logger.error(f"❌ 워치독 초기 출근 체크 실패: {e}")

    # 스케줄러 설정
    scheduler = BlockingScheduler(
        jobstores={'default': MemoryJobStore()},
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        },
        timezone="Asia/Seoul"
    )

    # 출근: 08:00-08:40 동안 5분마다 체크
    for minute in range(0, 41, 5):  # 0, 5, 10, 15, 20, 25, 30, 35, 40
        scheduler.add_job(punch_in_with_retry, 'cron', hour=8, minute=minute, day_of_week='mon-fri')

    # 퇴근: 18:00-19:00 동안 5분마다 체크
    for minute in range(0, 60, 5):  # 0, 5, 10, ..., 55
        scheduler.add_job(punch_out_with_retry, 'cron', hour=18, minute=minute, day_of_week='mon-fri')

    # 19:00에도 한 번 더
    scheduler.add_job(punch_out_with_retry, 'cron', hour=19, minute=0, day_of_week='mon-fri')

    logger.info("스케줄러 시작")
    logger.info("출근 스케줄: 월-금 08:00-08:40 (5분간격)")
    logger.info("퇴근 스케줄: 월-금 18:00-19:00 (5분간격)")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")

if __name__ == '__main__':
    main()