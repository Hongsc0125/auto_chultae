#!/usr/bin/env python3
"""
Auto Chultae Watchdog - 단순 버전 (크론탭용)
- 크론탭에서 호출되어 1회만 출근/퇴근 명령 전송
- DB 체크: 이미 출근했는지, 스케줄 확인 등 모든 검증 로직 포함
- 스케줄러 없음, 재시도 없음, 프로세스 모니터링 없음
"""

import os
import sys
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
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

def get_users():
    """데이터베이스에서 활성 사용자 목록 조회"""
    try:
        users = db_manager.get_active_users()
        logger.info(f"활성 사용자 {len(users)}명 조회: {[u['user_id'] for u in users]}")
        return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {e}")
        return []

def send_command_to_main_server(command):
    """메인 서버에 명령 전송"""
    try:
        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

        logger.info(f"메인 서버에 {command} 명령 전송 시작")

        response = requests.post(
            f"{main_server_url}/api/command",
            json={"command": command},
            timeout=300  # 5분 타임아웃
        )

        if response.status_code == 200:
            logger.info(f"✅ {command} 명령 전송 성공")
            return True
        else:
            logger.error(f"❌ {command} 명령 전송 실패: HTTP {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ {command} 명령 타임아웃 (5분 초과)")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ {command} 명령 전송 오류: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {command} 명령 예외 발생: {e}")
        return False

def check_punch_in_needed():
    """출근 처리가 필요한 사용자 확인"""
    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return []

    users_needing_punch_in = []

    for user in users:
        user_id = user["user_id"]

        # 1. 스케줄 확인: 오늘이 출근일인지
        is_workday = db_manager.is_workday_scheduled(user_id)
        if not is_workday:
            logger.info(f"[{user_id}] 오늘은 휴무일 - 스킵")
            continue

        # 2. 출근 성공 이력 확인
        has_success_today = db_manager.has_today_success(user_id, "punch_in")
        if has_success_today:
            logger.info(f"[{user_id}] 오늘 이미 출근 완료 - 스킵")
            continue

        # 출근 필요 (성공 이력 없음 = 미시도 or 실패 or 진행중)
        users_needing_punch_in.append(user_id)
        logger.info(f"[{user_id}] 출근 처리 대상")

    return users_needing_punch_in

def check_punch_out_needed():
    """퇴근 처리가 필요한 사용자 확인"""
    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return []

    users_needing_punch_out = []

    for user in users:
        user_id = user["user_id"]

        # 1. 퇴근 성공 이력 확인
        has_punch_out_success = db_manager.has_today_success(user_id, "punch_out")
        if has_punch_out_success:
            logger.info(f"[{user_id}] 오늘 이미 퇴근 완료 - 스킵")
            continue

        # 2. 출근 이력 확인 (출근이 있어야 퇴근 가능)
        has_punch_in_success = db_manager.has_today_success(user_id, "punch_in")
        if not has_punch_in_success:
            logger.info(f"[{user_id}] 오늘 출근 이력 없음 - 퇴근 불필요")
            continue

        # 퇴근 필요 (출근은 있고 퇴근 성공 이력 없음 = 미시도 or 실패 or 진행중)
        users_needing_punch_out.append(user_id)
        logger.info(f"[{user_id}] 퇴근 처리 대상")

    return users_needing_punch_out

def punch_in():
    """출근 처리 (1회 실행)"""
    logger.info("=" * 60)
    logger.info("출근 명령 실행 시작")
    logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 출근이 필요한 사용자 확인
    users_needing_punch_in = check_punch_in_needed()

    if not users_needing_punch_in:
        logger.info("✅ 모든 사용자가 이미 출근 완료 또는 휴무일 - 실행 불필요")
        logger.info("=" * 60)
        return True

    logger.info(f"출근 처리 대상 사용자: {users_needing_punch_in}")

    # 메인 서버에 명령 전송
    success = send_command_to_main_server("punch_in")

    if success:
        logger.info(f"✅ 출근 명령 완료 - 대상: {users_needing_punch_in}")
    else:
        logger.error(f"❌ 출근 명령 실패 - 대상: {users_needing_punch_in}")

    logger.info("=" * 60)
    return success

def punch_out():
    """퇴근 처리 (1회 실행)"""
    logger.info("=" * 60)
    logger.info("퇴근 명령 실행 시작")
    logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 퇴근이 필요한 사용자 확인
    users_needing_punch_out = check_punch_out_needed()

    if not users_needing_punch_out:
        logger.info("✅ 모든 사용자가 이미 퇴근 완료 또는 출근 이력 없음 - 실행 불필요")
        logger.info("=" * 60)
        return True

    logger.info(f"퇴근 처리 대상 사용자: {users_needing_punch_out}")

    # 메인 서버에 명령 전송
    success = send_command_to_main_server("punch_out")

    if success:
        logger.info(f"✅ 퇴근 명령 완료 - 대상: {users_needing_punch_out}")
    else:
        logger.error(f"❌ 퇴근 명령 실패 - 대상: {users_needing_punch_out}")

    logger.info("=" * 60)
    return success

def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("사용법: python watchdog_simple.py [punch_in|punch_out]")
        sys.exit(1)

    command = sys.argv[1]

    # 데이터베이스 연결 테스트
    if not db_manager.test_connection():
        logger.error("❌ 데이터베이스 연결 실패!")
        sys.exit(1)

    logger.info("✅ 데이터베이스 연결 성공")

    if command == "punch_in":
        success = punch_in()
        sys.exit(0 if success else 1)
    elif command == "punch_out":
        success = punch_out()
        sys.exit(0 if success else 1)
    else:
        logger.error(f"알 수 없는 명령: {command}")
        print("사용법: python watchdog_simple.py [punch_in|punch_out]")
        sys.exit(1)

if __name__ == '__main__':
    main()
