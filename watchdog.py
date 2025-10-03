#!/usr/bin/env python3
"""
Auto Chultae Watchdog - 스케줄링 전용
출퇴근 시간에 맞춰서 서브프로세스로 크롤링 함수 실행
"""

import os
import sys
import logging
import subprocess
import psutil
import time
import requests
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

# 전역 변수
main_server_process = None
restart_count = 0

# 사용자 목록 조회
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

        return users
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"사용자 목록 조회 실패: {e}",
            stage="user_query_error")
        return []

# 메인 서버 헬스체크 및 관리 함수
def check_main_server_health():
    """메인 서버 헬스체크"""
    try:
        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            return False

        response = requests.get(f"{main_server_url}/api/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"메인 서버 헬스체크 실패: {e}")
        return False

def find_main_server_process():
    """메인 서버 프로세스 찾기"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'main_server.py' in ' '.join(cmdline):
                    return proc.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    except Exception as e:
        logger.error(f"메인 서버 프로세스 찾기 실패: {e}")
        return None

def start_main_server():
    """메인 서버 시작"""
    global main_server_process, restart_count
    try:
        # 기존 프로세스가 있으면 종료
        if main_server_process and main_server_process.poll() is None:
            main_server_process.terminate()
            time.sleep(2)
            if main_server_process.poll() is None:
                main_server_process.kill()

        # 새로 시작
        cmd = [sys.executable, "main_server.py"]
        main_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        restart_count += 1

        logger.info(f"메인 서버 시작 - PID: {main_server_process.pid} (재시작 횟수: {restart_count})")
        db_manager.log_system("INFO", "watchdog",
            f"메인 서버 시작 - PID: {main_server_process.pid} (재시작 횟수: {restart_count})",
            stage="server_start")

        # 시작 후 잠시 대기
        time.sleep(3)
        return True

    except Exception as e:
        logger.error(f"메인 서버 시작 실패: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"메인 서버 시작 실패: {e}",
            stage="server_start_error")
        return False

def monitor_main_server():
    """메인 서버 모니터링 및 재시작"""
    global main_server_process

    # 헬스체크 수행
    is_healthy = check_main_server_health()

    # 프로세스 상태 확인
    process_running = False
    if main_server_process:
        try:
            # psutil.Process 객체는 is_running() 메서드 사용
            if hasattr(main_server_process, 'is_running'):
                process_running = main_server_process.is_running()
            else:
                # subprocess.Popen 객체는 poll() 메서드 사용
                process_running = main_server_process.poll() is None
        except (psutil.NoSuchProcess, AttributeError):
            process_running = False
    else:
        # 기존 프로세스 찾기
        pid = find_main_server_process()
        if pid:
            try:
                main_server_process = psutil.Process(pid)
                process_running = main_server_process.is_running()
                logger.info(f"기존 메인 서버 프로세스 발견 - PID: {pid}")
            except psutil.NoSuchProcess:
                pass

    # 로깅 - server_heartbeat 테이블 사용
    db_manager.log_server_heartbeat(
        component="watchdog",
        status="monitoring",
        stage=f"health:{is_healthy},process:{process_running}"
    )

    # 헬스체크 우선 로직: 헬스체크가 성공하면 재시작하지 않음
    if is_healthy:
        # 서버가 정상 응답하면 프로세스 상태와 관계없이 재시작하지 않음
        logger.debug("메인 서버 헬스체크 성공 - 재시작 불필요")
        return

    # 헬스체크 실패 시에만 재시작
    if not is_healthy:
        logger.warning(f"메인 서버 다운 감지 - 헬스체크: {is_healthy}, 프로세스: {process_running}")
        db_manager.log_server_heartbeat(
            component="watchdog",
            status="server_down",
            stage="restart_attempt"
        )

        success = start_main_server()
        if success:
            # 재시작 후 헬스체크
            time.sleep(5)
            if check_main_server_health():
                logger.info("메인 서버 재시작 성공")
                db_manager.log_server_heartbeat(
                    component="watchdog",
                    status="restart_success",
                    stage="health_check_passed"
                )
            else:
                logger.error("메인 서버 재시작 후에도 헬스체크 실패")
                db_manager.log_system("ERROR", "watchdog",
                    "메인 서버 재시작 후에도 헬스체크 실패",
                    stage="server_restart_failed")

# 메인 서버 통신 함수들
def send_command_to_main_server(command):
    """메인 서버에 명령 전송"""
    try:
        import requests

        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

        # 상세 로깅: 메인 서버 통신 시작
        db_manager.log_system("INFO", "watchdog",
            f"메인 서버에 {command} 명령 전송 시작 - URL: {main_server_url}",
            stage="server_communication", action_type=command)

        response = requests.post(f"{main_server_url}/api/command",
                               json={"command": command},
                               timeout=300)  # 5분 타임아웃 (크롤링 작업 고려)

        # 상세 로깅: 응답 결과
        db_manager.log_system("INFO", "watchdog",
            f"메인 서버 응답 - 상태코드: {response.status_code}, 명령: {command}",
            stage="server_response", action_type=command)

        if response.status_code == 200:
            logger.info(f"{command} 명령 전송 성공")
            db_manager.log_system("INFO", "watchdog",
                f"{command} 명령 전송 성공 - 상태코드: {response.status_code}",
                stage="command_success", action_type=command)
            return True
        else:
            logger.error(f"{command} 명령 전송 실패: {response.status_code}")
            db_manager.log_system("ERROR", "watchdog",
                f"{command} 명령 전송 실패 - 상태코드: {response.status_code}",
                stage="command_failure", action_type=command)
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"{command} 명령 전송 오류 (메인 서버 연결 실패): {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 전송 네트워크 오류 (메인 서버 연결 실패): {e}",
            stage="network_error", action_type=command)
        return False
    except Exception as e:
        logger.error(f"{command} 명령 전송 오류: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 전송 예외 오류: {e}",
            stage="exception_error", action_type=command)
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

    # 상세 로깅: 함수 시작
    db_manager.log_system("INFO", "watchdog",
        f"punch_in_with_retry 시작 - 현재시간: {current_time}",
        stage="schedule_check")

    # 08:00-08:40 시간대가 아니면 실행하지 않음
    if not (dt_time(8, 0) <= current_time <= dt_time(8, 40)):
        logger.debug(f"출근 시간대가 아님: {current_time}")
        db_manager.log_system("DEBUG", "watchdog",
            f"출근 시간대가 아님 - 현재시간: {current_time}, 대상시간: 08:00-08:40",
            stage="time_check")
        return

    # 모든 활성 사용자의 오늘자 출근 성공 이력 확인
    users = get_users()
    users_needing_punch_in = []

    # 상세 로깅: 사용자 목록 조회
    db_manager.log_system("INFO", "watchdog",
        f"활성 사용자 {len(users)}명 조회완료: {[u['user_id'] for u in users]}",
        stage="user_check")

    for user in users:
        user_id = user["user_id"]

        # 1. 스케줄 확인: 오늘이 출근일인지 확인
        is_workday = db_manager.is_workday_scheduled(user_id)

        # 상세 로깅: 스케줄 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 스케줄 확인 결과: is_workday={is_workday}",
            stage="schedule_check", user_id=user_id, action_type="punch_in")

        if not is_workday:
            logger.info(f"[{user_id}] 오늘은 휴무일로 스케줄되어 있음 - 스킵")
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
            logger.info(f"[{user_id}] 오늘자 출근 성공 이력 있음 - 스킵")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 오늘자 출근 성공 이력 있어 스킵",
                stage="history_skip", user_id=user_id, action_type="punch_in")
        else:
            users_needing_punch_in.append(user_id)
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 출근 처리 대상에 추가",
                stage="target_add", user_id=user_id, action_type="punch_in")

    if not users_needing_punch_in:
        logger.info("모든 사용자가 오늘 이미 출근 완료 - 실행하지 않음")
        db_manager.log_system("INFO", "watchdog",
            "모든 사용자가 이미 출근 완료 또는 휴무일 - 실행하지 않음",
            stage="no_action")
        return

    logger.info(f"출근 처리 시도 시작 ({current_time}) - 대상 사용자: {users_needing_punch_in}")
    db_manager.log_system("INFO", "watchdog",
        f"출근 처리 시도 시작 - 대상 사용자: {users_needing_punch_in}, 현재시간: {current_time}",
        stage="execution_start", action_type="punch_in")

    success = execute_punch_in()

    # 상세 로깅: 실행 결과
    db_manager.log_system("INFO" if success else "ERROR", "watchdog",
        f"출근 처리 결과: {'성공' if success else '실패'} - 대상 사용자: {users_needing_punch_in}",
        stage="execution_result", action_type="punch_in")

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(8, 35):
            logger.warning(f"출근 처리 실패 - 대상 사용자: {users_needing_punch_in}")
            db_manager.log_system("WARNING", "watchdog",
                f"출근 처리 실패 (8:35 이후) - 대상 사용자: {users_needing_punch_in}",
                stage="execution_failure", action_type="punch_in")

def punch_out_with_retry():
    """퇴근 시간대 재시도 로직 (18:00-19:00) - 오늘자 성공 이력 확인"""
    now = datetime.now()
    current_time = now.time()

    # 상세 로깅: 함수 시작
    db_manager.log_system("INFO", "watchdog",
        f"punch_out_with_retry 시작 - 현재시간: {current_time}",
        stage="schedule_check")

    # 18:00-19:00 시간대가 아니면 실행하지 않음
    if not (dt_time(18, 0) <= current_time <= dt_time(19, 0)):
        logger.debug(f"퇴근 시간대가 아님: {current_time}")
        db_manager.log_system("DEBUG", "watchdog",
            f"퇴근 시간대가 아님 - 현재시간: {current_time}, 대상시간: 18:00-19:00",
            stage="time_check")
        return

    # 모든 활성 사용자의 오늘자 퇴근 성공 이력 확인
    users = get_users()
    users_needing_punch_out = []

    # 상세 로깅: 사용자 목록 조회
    db_manager.log_system("INFO", "watchdog",
        f"활성 사용자 {len(users)}명 조회완료: {[u['user_id'] for u in users]}",
        stage="user_check")

    for user in users:
        user_id = user["user_id"]

        # 1. 퇴근 성공 이력 확인 (먼저 확인)
        has_punch_out_success = db_manager.has_today_success(user_id, "punch_out")

        # 상세 로깅: 퇴근 이력 확인 결과
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 오늘자 퇴근 성공 이력: {has_punch_out_success}",
            stage="punch_out_history_check", user_id=user_id, action_type="punch_out")

        if has_punch_out_success:
            logger.info(f"[{user_id}] 오늘자 퇴근 성공 이력 있음 - 스킵")
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
            logger.info(f"[{user_id}] 오늘자 출근 이력 없음 - 퇴근 불필요")
            db_manager.log_system("INFO", "watchdog",
                f"[{user_id}] 오늘자 출근 이력 없어 퇴근 불필요",
                stage="punch_in_missing", user_id=user_id, action_type="punch_out")
            continue

        # 3. 출근 이력이 있으면 퇴근 대상에 추가 (스케줄 무관)
        users_needing_punch_out.append(user_id)
        db_manager.log_system("INFO", "watchdog",
            f"[{user_id}] 퇴근 처리 대상에 추가",
            stage="target_add", user_id=user_id, action_type="punch_out")

    if not users_needing_punch_out:
        logger.info("모든 사용자가 오늘 이미 퇴근 완료 - 실행하지 않음")
        db_manager.log_system("INFO", "watchdog",
            "모든 사용자가 이미 퇴근 완료 또는 출근 이력 없음 - 실행하지 않음",
            stage="no_action")
        return

    logger.info(f"퇴근 처리 시도 시작 ({current_time}) - 대상 사용자: {users_needing_punch_out}")
    db_manager.log_system("INFO", "watchdog",
        f"퇴근 처리 시도 시작 - 대상 사용자: {users_needing_punch_out}, 현재시간: {current_time}",
        stage="execution_start", action_type="punch_out")

    success = execute_punch_out()

    # 상세 로깅: 실행 결과
    db_manager.log_system("INFO" if success else "ERROR", "watchdog",
        f"퇴근 처리 결과: {'성공' if success else '실패'} - 대상 사용자: {users_needing_punch_out}",
        stage="execution_result", action_type="punch_out")

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(18, 55):
            logger.warning(f"퇴근 처리 실패 - 대상 사용자: {users_needing_punch_out}")
            db_manager.log_system("WARNING", "watchdog",
                f"퇴근 처리 실패 (18:55 이후) - 대상 사용자: {users_needing_punch_out}",
                stage="execution_failure", action_type="punch_out")

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
    db_manager.log_system("INFO", "watchdog",
        "워치독 시작 - 초기 출근 체크 수행 (강제 실행)",
        stage="initial_startup")

    try:
        # 초기 실행 시에는 사전 체크 무시하고 강제로 Main Server 호출
        logger.info("초기 출근 처리 시도 시작 (강제 실행)")
        db_manager.log_system("WARNING", "watchdog",
            "초기 출근 처리 시도 - 스케줄 체크 및 이력 체크 무시 (강제 실행)",
            stage="forced_execution", action_type="punch_in")

        success = execute_punch_in()

        if success:
            logger.info("✅ 워치독 초기 출근 체크 완료")
            db_manager.log_system("INFO", "watchdog",
                "워치독 초기 출근 체크 성공",
                stage="initial_success", action_type="punch_in")
        else:
            logger.warning("⚠️ 워치독 초기 출근 체크 실패했지만 계속 진행")
            db_manager.log_system("WARNING", "watchdog",
                "워치독 초기 출근 체크 실패했지만 계속 진행",
                stage="initial_failure", action_type="punch_in")
    except Exception as e:
        logger.error(f"❌ 워치독 초기 출근 체크 실패: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"워치독 초기 출근 체크 예외 발생: {e}",
            stage="initial_exception", action_type="punch_in")

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

    # 메인 서버 모니터링: 30초마다 체크
    scheduler.add_job(monitor_main_server, 'interval', seconds=30)

    logger.info("스케줄러 시작")
    logger.info("출근 스케줄: 월-금 08:00-08:40 (5분간격)")
    logger.info("퇴근 스케줄: 월-금 18:00-19:00 (5분간격)")
    logger.info("메인 서버 모니터링: 30초마다")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")

if __name__ == '__main__':
    main()