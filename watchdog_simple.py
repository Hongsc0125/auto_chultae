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
        # 상세 로깅: 사용자 목록 조회 시작
        db_manager.log_system("DEBUG", "watchdog",
            "데이터베이스에서 활성 사용자 목록 조회 시작",
            stage="user_query")

        users = db_manager.get_active_users()

        # 상세 로깅: 조회 결과
        db_manager.log_system("INFO", "watchdog",
            f"활성 사용자 {len(users)}명 조회 성공: {[u['user_id'] for u in users]}",
            stage="user_query_success")

        logger.info(f"활성 사용자 {len(users)}명 조회: {[u['user_id'] for u in users]}")
        return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"사용자 목록 조회 실패: {e}",
            stage="user_query_error")
        return []

def send_command_to_main_server(command):
    """메인 서버에 명령 전송"""
    try:
        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

        # 상세 로깅: 메인 서버 통신 시작
        db_manager.log_system("INFO", "watchdog",
            f"메인 서버에 {command} 명령 전송 시작 - URL: {main_server_url}",
            stage="server_communication", action_type=command)

        logger.info(f"메인 서버에 {command} 명령 전송 시작")

        response = requests.post(
            f"{main_server_url}/api/command",
            json={"command": command},
            timeout=300  # 5분 타임아웃
        )

        # 상세 로깅: 응답 결과
        db_manager.log_system("INFO", "watchdog",
            f"메인 서버 응답 - 상태코드: {response.status_code}, 명령: {command}",
            stage="server_response", action_type=command)

        if response.status_code == 200:
            logger.info(f"✅ {command} 명령 전송 성공")
            db_manager.log_system("INFO", "watchdog",
                f"{command} 명령 전송 성공 - 상태코드: {response.status_code}",
                stage="command_success", action_type=command)
            return True
        else:
            logger.error(f"❌ {command} 명령 전송 실패: HTTP {response.status_code}")
            db_manager.log_system("ERROR", "watchdog",
                f"{command} 명령 전송 실패 - 상태코드: {response.status_code}",
                stage="command_failure", action_type=command)
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ {command} 명령 타임아웃 (5분 초과)")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 타임아웃 (5분 초과)",
            stage="timeout_error", action_type=command)
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ {command} 명령 전송 오류: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 전송 네트워크 오류: {e}",
            stage="network_error", action_type=command)
        return False
    except Exception as e:
        logger.error(f"❌ {command} 명령 예외 발생: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 예외 발생: {e}",
            stage="exception_error", action_type=command)
        return False

def check_punch_in_needed():
    """출근 처리가 필요한 사용자 확인"""
    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return []

    users_needing_punch_in = []

    # 상세 로깅: 사용자 목록 조회
    db_manager.log_system("INFO", "watchdog",
        f"활성 사용자 {len(users)}명 조회완료: {[u['user_id'] for u in users]}",
        stage="user_check")

    for user in users:
        user_id = user["user_id"]

        # 1. 스케줄 확인: 오늘이 출근일인지
        is_workday = db_manager.is_workday_scheduled(user_id)

        # 상세 로깅: 스케줄 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 스케줄 확인 결과: is_workday={is_workday}",
            stage="schedule_check", user_id=user_id, action_type="punch_in")

        if not is_workday:
            logger.info(f"[{user_id}] 오늘은 휴무일 - 스킵")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 휴무일로 스케줄되어 있어 출근 처리 스킵",
                stage="schedule_skip", user_id=user_id, action_type="punch_in")
            continue

        # 2. 출근 성공 이력 확인
        has_success_today = db_manager.has_today_success(user_id, "punch_in")

        # 상세 로깅: 출근 이력 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 오늘자 출근 성공 이력: {has_success_today}",
            stage="history_check", user_id=user_id, action_type="punch_in")

        if has_success_today:
            logger.info(f"[{user_id}] 오늘 이미 출근 완료 - 스킵")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 오늘자 출근 성공 이력 있어 스킵",
                stage="history_skip", user_id=user_id, action_type="punch_in")
        else:
            users_needing_punch_in.append(user_id)
            logger.info(f"[{user_id}] 출근 처리 대상")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 출근 처리 대상에 추가",
                stage="target_add", user_id=user_id, action_type="punch_in")

    return users_needing_punch_in

def check_punch_out_needed():
    """퇴근 처리가 필요한 사용자 확인"""
    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return []

    users_needing_punch_out = []

    # 상세 로깅: 사용자 목록 조회
    db_manager.log_system("INFO", "watchdog",
        f"활성 사용자 {len(users)}명 조회완료: {[u['user_id'] for u in users]}",
        stage="user_check")

    for user in users:
        user_id = user["user_id"]

        # 1. 퇴근 성공 이력 확인
        has_punch_out_success = db_manager.has_today_success(user_id, "punch_out")

        # 상세 로깅: 퇴근 이력 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 오늘자 퇴근 성공 이력: {has_punch_out_success}",
            stage="punch_out_history_check", user_id=user_id, action_type="punch_out")

        if has_punch_out_success:
            logger.info(f"[{user_id}] 오늘 이미 퇴근 완료 - 스킵")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 오늘자 퇴근 성공 이력 있어 스킵",
                stage="punch_out_skip", user_id=user_id, action_type="punch_out")
            continue

        # 2. 출근 이력 확인 (출근이 있어야 퇴근 가능)
        has_punch_in_success = db_manager.has_today_success(user_id, "punch_in")

        # 상세 로깅: 출근 이력 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 오늘자 출근 성공 이력: {has_punch_in_success}",
            stage="punch_in_history_check", user_id=user_id, action_type="punch_out")

        if not has_punch_in_success:
            logger.info(f"[{user_id}] 오늘 출근 이력 없음 - 퇴근 불필요")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 오늘자 출근 이력 없어 퇴근 불필요",
                stage="punch_in_missing", user_id=user_id, action_type="punch_out")
            continue

        # 퇴근 필요
        users_needing_punch_out.append(user_id)
        logger.info(f"[{user_id}] 퇴근 처리 대상")
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 퇴근 처리 대상에 추가",
            stage="target_add", user_id=user_id, action_type="punch_out")

    return users_needing_punch_out

def punch_in():
    """출근 처리 (1회 실행)"""
    logger.info("=" * 60)
    logger.info("출근 명령 실행 시작")
    logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    db_manager.log_system("INFO", "watchdog",
        f"출근 명령 실행 시작 - 실행시간: {datetime.now()}",
        stage="punch_in_start", action_type="punch_in")

    # 출근이 필요한 사용자 확인
    users_needing_punch_in = check_punch_in_needed()

    if not users_needing_punch_in:
        logger.info("✅ 모든 사용자가 이미 출근 완료 또는 휴무일 - 실행 불필요")
        db_manager.log_system("INFO", "watchdog",
            "모든 사용자가 이미 출근 완료 또는 휴무일 - 실행하지 않음",
            stage="no_action", action_type="punch_in")
        logger.info("=" * 60)
        return True

    logger.info(f"출근 처리 대상 사용자: {users_needing_punch_in}")
    db_manager.log_system("INFO", "watchdog",
        f"출근 처리 시도 시작 - 대상 사용자: {users_needing_punch_in}",
        stage="execution_start", action_type="punch_in")

    # 메인 서버에 명령 전송
    success = send_command_to_main_server("punch_in")

    # 상세 로깅: 실행 결과
    db_manager.log_system("INFO" if success else "ERROR", "watchdog",
        f"출근 처리 결과: {'성공' if success else '실패'} - 대상 사용자: {users_needing_punch_in}",
        stage="execution_result", action_type="punch_in")

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

    db_manager.log_system("INFO", "watchdog",
        f"퇴근 명령 실행 시작 - 실행시간: {datetime.now()}",
        stage="punch_out_start", action_type="punch_out")

    # 퇴근이 필요한 사용자 확인
    users_needing_punch_out = check_punch_out_needed()

    if not users_needing_punch_out:
        logger.info("✅ 모든 사용자가 이미 퇴근 완료 또는 출근 이력 없음 - 실행 불필요")
        db_manager.log_system("INFO", "watchdog",
            "모든 사용자가 이미 퇴근 완료 또는 출근 이력 없음 - 실행하지 않음",
            stage="no_action", action_type="punch_out")
        logger.info("=" * 60)
        return True

    logger.info(f"퇴근 처리 대상 사용자: {users_needing_punch_out}")
    db_manager.log_system("INFO", "watchdog",
        f"퇴근 처리 시도 시작 - 대상 사용자: {users_needing_punch_out}",
        stage="execution_start", action_type="punch_out")

    # 메인 서버에 명령 전송
    success = send_command_to_main_server("punch_out")

    # 상세 로깅: 실행 결과
    db_manager.log_system("INFO" if success else "ERROR", "watchdog",
        f"퇴근 처리 결과: {'성공' if success else '실패'} - 대상 사용자: {users_needing_punch_out}",
        stage="execution_result", action_type="punch_out")

    if success:
        logger.info(f"✅ 퇴근 명령 완료 - 대상: {users_needing_punch_out}")
    else:
        logger.error(f"❌ 퇴근 명령 실패 - 대상: {users_needing_punch_out}")

    logger.info("=" * 60)
    return success

def main():
    """메인 함수 - 현재 시간에 따라 출근/퇴근 자동 판단"""

    # 데이터베이스 연결 테스트
    if not db_manager.test_connection():
        logger.error("❌ 데이터베이스 연결 실패!")
        db_manager.log_system("ERROR", "watchdog", "데이터베이스 연결 실패", stage="db_connection_failed")
        sys.exit(1)

    logger.info("✅ 데이터베이스 연결 성공")
    db_manager.log_system("INFO", "watchdog", "워치독 시스템 시작 - 데이터베이스 연결 성공", stage="startup")

    # 현재 시간 확인
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    weekday = now.weekday()  # 0=월요일, 6=일요일

    logger.info(f"현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')} (요일: {weekday})")
    db_manager.log_system("INFO", "watchdog",
        f"현재 시간 확인 - {now.strftime('%Y-%m-%d %H:%M:%S')} (요일: {weekday})",
        stage="time_check")

    # 주말 체크 (토요일=5, 일요일=6)
    if weekday >= 5:
        logger.info("주말이므로 실행하지 않음")
        db_manager.log_system("INFO", "watchdog", "주말이므로 실행하지 않음", stage="weekend_skip")
        sys.exit(0)

    # 출근 시간: 08:00 ~ 08:40
    if current_hour == 8 and current_minute <= 40:
        logger.info("출근 시간대 감지 - 출근 처리 시작")
        db_manager.log_system("INFO", "watchdog", "출근 시간대 감지", stage="schedule_match", action_type="punch_in")
        success = punch_in()
        sys.exit(0 if success else 1)

    # 퇴근 시간: 18:00 ~ 19:00
    elif current_hour == 18 or (current_hour == 19 and current_minute == 0):
        logger.info("퇴근 시간대 감지 - 퇴근 처리 시작")
        db_manager.log_system("INFO", "watchdog", "퇴근 시간대 감지", stage="schedule_match", action_type="punch_out")
        success = punch_out()
        sys.exit(0 if success else 1)

    # 스케줄 외 시간
    else:
        logger.info(f"스케줄 외 시간 (현재: {current_hour:02d}:{current_minute:02d}) - 실행하지 않음")
        db_manager.log_system("INFO", "watchdog",
            f"스케줄 외 시간 ({current_hour:02d}:{current_minute:02d}) - 실행하지 않음",
            stage="schedule_skip")
        sys.exit(0)

if __name__ == '__main__':
    main()
