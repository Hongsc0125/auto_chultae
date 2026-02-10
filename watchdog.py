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
from sqlalchemy import text
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
last_command_start_time = None
current_command = None

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
    """메인 서버 프로세스 찾기 (main_server.py 직접 실행 또는 Gunicorn으로 실행)"""
    try:
        found_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue

                cmdline_str = ' '.join(cmdline)

                # 1. main_server.py 직접 실행 감지
                if 'main_server.py' in cmdline_str:
                    found_processes.append(proc.pid)
                    logger.debug(f"메인 서버 프로세스 발견 (직접실행): PID {proc.pid} - {cmdline_str}")

                # 2. Gunicorn으로 main_server 실행 감지
                elif 'gunicorn' in cmdline_str and 'main_server' in cmdline_str:
                    # master 프로세스가 아닌 worker 프로세스 선택
                    if '--worker-class' not in cmdline_str and 'main_server:app' in cmdline_str:
                        found_processes.append(proc.pid)
                        logger.debug(f"메인 서버 프로세스 발견 (Gunicorn): PID {proc.pid} - {cmdline_str}")

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if found_processes:
            # 여러 프로세스가 있으면 첫 번째 것 반환
            selected_pid = found_processes[0]
            logger.info(f"메인 서버 프로세스 선택: PID {selected_pid} (총 {len(found_processes)}개 발견)")
            return selected_pid

        return None
    except Exception as e:
        logger.error(f"메인 서버 프로세스 찾기 실패: {e}")
        return None

def start_main_server():
    """메인 서버 시작"""
    global main_server_process, restart_count
    try:
        # 기존 프로세스가 있으면 종료
        if main_server_process:
            try:
                # psutil.Process 객체인지 확인
                if hasattr(main_server_process, 'is_running'):
                    if main_server_process.is_running():
                        main_server_process.terminate()
                        time.sleep(2)
                        if main_server_process.is_running():
                            main_server_process.kill()
                # subprocess.Popen 객체인지 확인
                elif hasattr(main_server_process, 'poll'):
                    if main_server_process.poll() is None:
                        main_server_process.terminate()
                        time.sleep(2)
                        if main_server_process.poll() is None:
                            main_server_process.kill()
            except (psutil.NoSuchProcess, AttributeError, OSError):
                # 프로세스가 이미 없거나 접근할 수 없는 경우 무시
                pass

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

def check_stuck_process():
    """모든 프로세스 단계에서 멈춤 상황 감지"""
    try:
        from datetime import datetime, timedelta

        # 최근 10분 내 server_heartbeat에서 main_server 관련 로그 확인
        with db_manager.safe_session() as session:
            ten_minutes_ago = datetime.now() - timedelta(minutes=10)

            result = session.execute(
                text("""
                    SELECT stage, timestamp, action, status
                    FROM server_heartbeat
                    WHERE component = 'main_server'
                    AND timestamp > :threshold
                    ORDER BY timestamp DESC
                    LIMIT 50
                """),
                {"threshold": ten_minutes_ago}
            )

            recent_logs = result.fetchall()

            if not recent_logs:
                logger.debug("최근 10분간 메인 서버 로그 없음")
                return False

            # 멈춤을 의심할 수 있는 단계들 정의
            stuck_indicators = [
                'page_creation_start',
                'page_creation_attempt',
                'playwright_init',
                'browser_started',
                'context_created',
                'login_attempt',
                'button_search',
                'popup_handling',
                'processing'
            ]

            # 완료를 나타내는 단계들
            completion_indicators = [
                'success',
                'complete',
                'finished',
                'process_start',  # 새로운 프로세스 시작
                'execution_result',
                'punch_in_success',
                'punch_out_success',
                'error',  # 에러도 완료로 간주 (다음 단계로 진행됨)
                'failure'
            ]

            now = datetime.now()

            # 각 stuck_indicator에 대해 멈춤 상황 확인
            for indicator in stuck_indicators:
                stuck_start_time = None
                has_completion_after = False

                for log in recent_logs:
                    stage, timestamp, action, status = log

                    # 해당 indicator로 시작된 로그 찾기
                    if indicator in stage and stuck_start_time is None:
                        stuck_start_time = timestamp

                        # 3분 이상 된 경우만 체크
                        if now - timestamp > timedelta(minutes=3):
                            # 그 이후에 완료 indicator가 있는지 확인
                            for other_log in recent_logs:
                                other_stage, other_timestamp, _, _ = other_log

                                if other_timestamp > timestamp:
                                    # 완료 indicator가 있거나, 새로운 프로세스가 시작된 경우
                                    for completion in completion_indicators:
                                        if completion in other_stage.lower():
                                            has_completion_after = True
                                            break

                                    if has_completion_after:
                                        break

                            # 완료 indicator가 없으면 멈춤으로 판단
                            if not has_completion_after:
                                elapsed = now - timestamp
                                logger.warning(f"프로세스 멈춤 감지: {indicator} - 시작: {timestamp}, 경과: {elapsed}")
                                db_manager.log_system("WARNING", "watchdog",
                                    f"프로세스 멈춤 감지: {indicator}, 경과시간: {elapsed}",
                                    stage="stuck_detection")
                                return True

            # 추가 체크: 최근 5분간 아무런 활동이 없는 경우
            five_minutes_ago = now - timedelta(minutes=5)
            recent_activity = [log for log in recent_logs if log[1] > five_minutes_ago]

            if not recent_activity:
                logger.warning("최근 5분간 메인 서버 활동 없음 - 멈춤 의심")
                db_manager.log_system("WARNING", "watchdog",
                    "최근 5분간 메인 서버 활동 없음",
                    stage="no_activity_detected")
                return True

            return False

    except Exception as e:
        logger.error(f"프로세스 멈춤 감지 실패: {e}")
        return False

def check_crawling_progress():
    """크롤링 진행 상태 확인 - 5분 이상 진행되지 않으면 True 반환"""
    global last_command_start_time, current_command

    try:
        from datetime import datetime, timedelta

        # 현재 실행 중인 명령이 없으면 체크하지 않음
        if not current_command or not last_command_start_time:
            return False

        now = datetime.now()
        elapsed = now - last_command_start_time

        # 5분 이상 경과했는지 확인
        if elapsed > timedelta(minutes=5):
            logger.warning(f"크롤링 진행 없음 감지: {current_command}, 경과시간: {elapsed}")
            db_manager.log_system("WARNING", "watchdog",
                f"크롤링 진행 없음 감지: {current_command}, 경과시간: {elapsed}",
                stage="crawling_stuck_detection", action_type=current_command)

            # 데이터베이스에서 최근 진행 상황 확인
            with db_manager.safe_session() as session:
                five_minutes_ago = now - timedelta(minutes=5)

                # 최근 5분간 크롤링 진행 로그 확인
                result = session.execute(
                    text("""
                        SELECT stage, timestamp, action
                        FROM server_heartbeat
                        WHERE component = 'main_server'
                        AND timestamp > :threshold
                        AND (stage LIKE '%success%' OR stage LIKE '%complete%' OR stage LIKE '%finished%')
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """),
                    {"threshold": five_minutes_ago}
                )

                recent_progress = result.fetchone()

                if not recent_progress:
                    logger.warning(f"최근 5분간 크롤링 진행 없음 - 강제 재시작 필요")
                    db_manager.log_system("WARNING", "watchdog",
                        "최근 5분간 크롤링 진행 없음 - 강제 재시작 필요",
                        stage="no_crawling_progress", action_type=current_command)
                    return True
                else:
                    logger.info(f"최근 크롤링 진행 확인됨: {recent_progress[0]} at {recent_progress[1]}")

        return False

    except Exception as e:
        logger.error(f"크롤링 진행 상태 확인 중 오류: {e}")
        return False

def force_restart_main_server():
    """메인 서버 강제 재시작 (프로세스 kill 후 재시작)"""
    global main_server_process, restart_count

    try:
        logger.warning("메인 서버 강제 재시작 시작")
        db_manager.log_server_heartbeat(
            component="watchdog",
            status="force_restart",
            stage="kill_attempt"
        )

        # 1. 기존 프로세스들 모두 찾아서 종료
        killed_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline:
                    continue

                cmdline_str = ' '.join(cmdline)

                # main_server 관련 프로세스 모두 종료
                if ('main_server.py' in cmdline_str or
                    ('gunicorn' in cmdline_str and 'main_server' in cmdline_str)):

                    proc_obj = psutil.Process(proc.info['pid'])
                    proc_obj.terminate()
                    killed_pids.append(proc.info['pid'])
                    logger.info(f"메인 서버 프로세스 종료 - PID: {proc.info['pid']}")

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 2. 종료 대기
        time.sleep(3)

        # 3. 강제 종료가 필요한 프로세스 확인
        for pid in killed_pids:
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    proc.kill()
                    logger.warning(f"메인 서버 프로세스 강제 종료 - PID: {pid}")
            except psutil.NoSuchProcess:
                pass

        # 4. 기존 변수 초기화
        main_server_process = None

        # 5. 새로 시작
        time.sleep(2)
        success = start_main_server()

        if success:
            logger.info("메인 서버 강제 재시작 성공")
            db_manager.log_server_heartbeat(
                component="watchdog",
                status="force_restart_success",
                stage="restart_complete"
            )
            return True
        else:
            logger.error("메인 서버 강제 재시작 실패")
            db_manager.log_server_heartbeat(
                component="watchdog",
                status="force_restart_failed",
                stage="restart_failed"
            )
            return False

    except Exception as e:
        logger.error(f"메인 서버 강제 재시작 중 오류: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"메인 서버 강제 재시작 중 오류: {e}",
            stage="force_restart_error")
        return False

def monitor_main_server():
    """메인 서버 모니터링 및 재시작"""
    global main_server_process

    # 1. 크롤링 진행 상태 먼저 확인
    if check_crawling_progress():
        logger.warning("크롤링 진행 없음 감지 - 메인 서버 강제 재시작 수행")
        db_manager.log_system("WARNING", "watchdog",
            "크롤링 진행 없음 감지로 인한 강제 재시작",
            stage="crawling_stuck_restart")

        if force_restart_main_server():
            # 강제 재시작 성공 후 잠시 대기하고 리턴
            time.sleep(10)
            return
        # 강제 재시작 실패 시 일반 로직 계속 진행

    # 2. 프로세스 멈춤 상황 확인
    if check_stuck_process():
        logger.warning("프로세스 멈춤 감지 - 메인 서버 강제 재시작 수행")
        db_manager.log_system("WARNING", "watchdog",
            "프로세스 멈춤 감지로 인한 강제 재시작",
            stage="stuck_detection")

        if force_restart_main_server():
            # 강제 재시작 성공 후 잠시 대기하고 리턴
            time.sleep(10)
            return
        # 강제 재시작 실패 시 일반 로직 계속 진행

    # 2. 일반 헬스체크 수행
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
        except (psutil.NoSuchProcess, AttributeError, OSError):
            process_running = False
            main_server_process = None  # 유효하지 않은 프로세스 객체 제거

    # main_server_process가 없거나 유효하지 않으면 기존 프로세스 찾기
    if not main_server_process:
        pid = find_main_server_process()
        if pid:
            try:
                # 찾은 프로세스는 참조용으로만 사용하고 main_server_process에 할당하지 않음
                found_process = psutil.Process(pid)
                process_running = found_process.is_running()
                logger.info(f"기존 메인 서버 프로세스 발견 - PID: {pid}")
            except psutil.NoSuchProcess:
                process_running = False

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
    global last_command_start_time, current_command

    try:
        import requests
        from datetime import datetime

        main_server_url = os.getenv('MAIN_SERVER_URL')
        if not main_server_url:
            raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

        # 명령 시작 시간 기록
        last_command_start_time = datetime.now()
        current_command = command

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

            # 성공 시 명령 완료 기록
            current_command = None
            last_command_start_time = None
            return True
        else:
            logger.error(f"{command} 명령 전송 실패: {response.status_code}")
            db_manager.log_system("ERROR", "watchdog",
                f"{command} 명령 전송 실패 - 상태코드: {response.status_code}",
                stage="command_failure", action_type=command)

            # HTTP 오류 시 메인 서버 재시작 시도
            logger.warning(f"HTTP 오류로 인한 메인 서버 재시작 시도")
            if force_restart_main_server():
                logger.info("메인 서버 재시작 성공 - 명령 재시도")
                # 재시작 후 잠시 대기하고 명령 재시도
                time.sleep(5)
                try:
                    response = requests.post(f"{main_server_url}/api/command",
                                           json={"command": command},
                                           timeout=300)
                    if response.status_code == 200:
                        logger.info(f"{command} 명령 재시도 성공")
                        # 성공 시 명령 완료 기록
                        current_command = None
                        last_command_start_time = None
                        return True
                    else:
                        logger.error(f"{command} 명령 재시도 실패: {response.status_code}")
                        # 실패 시 명령 완료 기록
                        current_command = None
                        last_command_start_time = None
                        return False
                except Exception as retry_e:
                    logger.error(f"{command} 명령 재시도 중 오류: {retry_e}")
                    # 실패 시 명령 완료 기록
                    current_command = None
                    last_command_start_time = None
                    return False
            else:
                logger.error("메인 서버 재시작 실패")
                # 실패 시 명령 완료 기록
                current_command = None
                last_command_start_time = None
                return False

    except requests.exceptions.RequestException as e:
        logger.error(f"{command} 명령 전송 오류 (메인 서버 연결 실패): {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 전송 네트워크 오류 (메인 서버 연결 실패): {e}",
            stage="network_error", action_type=command)

        # 네트워크 오류 시 메인 서버 재시작 시도
        logger.warning(f"네트워크 오류로 인한 메인 서버 재시작 시도")
        if force_restart_main_server():
            logger.info("메인 서버 재시작 성공 - 명령 재시도")
            # 재시작 후 잠시 대기하고 명령 재시도
            time.sleep(5)
            try:
                main_server_url = os.getenv('MAIN_SERVER_URL')
                response = requests.post(f"{main_server_url}/api/command",
                                       json={"command": command},
                                       timeout=300)
                if response.status_code == 200:
                    logger.info(f"{command} 명령 재시도 성공")
                    # 성공 시 명령 완료 기록
                    current_command = None
                    last_command_start_time = None
                    return True
                else:
                    logger.error(f"{command} 명령 재시도 실패: {response.status_code}")
                    # 실패 시 명령 완료 기록
                    current_command = None
                    last_command_start_time = None
                    return False
            except Exception as retry_e:
                logger.error(f"{command} 명령 재시도 중 오류: {retry_e}")
                # 실패 시 명령 완료 기록
                current_command = None
                last_command_start_time = None
                return False
        else:
            logger.error("메인 서버 재시작 실패")
            # 실패 시 명령 완료 기록
            current_command = None
            last_command_start_time = None
            return False

    except Exception as e:
        logger.error(f"{command} 명령 전송 오류: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"{command} 명령 전송 예외 오류: {e}",
            stage="exception_error", action_type=command)
        # 실패 시 명령 완료 기록
        current_command = None
        last_command_start_time = None
        return False

def execute_punch_in_parallel():
    """출근 처리 실행 (사용자별 병렬 프로세스)"""
    logger.info("출근 처리 시작 - 사용자별 병렬 실행")

    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return False

    # 처리가 필요한 사용자 필터링
    users_to_process = []
    for user in users:
        user_id = user["user_id"]
        is_workday = db_manager.is_workday_scheduled(user_id)
        has_success_today = db_manager.has_today_success(user_id, "punch_in")

        if is_workday and not has_success_today:
            users_to_process.append(user)
            logger.info(f"[{user_id}] 출근 처리 대상에 추가")

    if not users_to_process:
        logger.info("출근 처리가 필요한 사용자 없음")
        return True

    # 각 사용자별로 독립 프로세스 실행 (Flask 서버 포함)
    processes = []
    base_port = 9001  # 메인 백엔드(9000) 다음부터 시작

    for idx, user in enumerate(users_to_process):
        user_id = user["user_id"]
        port = base_port + idx

        cmd = [
            sys.executable,
            "main_server.py",
            "--user", user_id,
            "--action", "punch_in",
            "--port", str(port)
        ]

        logger.info(f"[{user_id}] 출근 프로세스 시작 (포트: {port})")
        proc = subprocess.Popen(cmd, cwd=os.getcwd())
        processes.append((user_id, proc))

    # 모든 프로세스 완료 대기
    all_success = True
    for user_id, proc in processes:
        returncode = proc.wait()
        if returncode == 0:
            logger.info(f"[{user_id}] 출근 처리 완료 (성공)")
        else:
            logger.error(f"[{user_id}] 출근 처리 완료 (실패: exit code {returncode})")
            all_success = False

    return all_success

def execute_punch_out_parallel():
    """퇴근 처리 실행 (사용자별 병렬 프로세스)"""
    logger.info("퇴근 처리 시작 - 사용자별 병렬 실행")

    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return False

    # 처리가 필요한 사용자 필터링
    users_to_process = []
    for user in users:
        user_id = user["user_id"]
        has_punch_in = db_manager.has_today_success(user_id, "punch_in")
        has_punch_out = db_manager.has_today_success(user_id, "punch_out")

        if has_punch_in and not has_punch_out:
            users_to_process.append(user)
            logger.info(f"[{user_id}] 퇴근 처리 대상에 추가")

    if not users_to_process:
        logger.info("퇴근 처리가 필요한 사용자 없음")
        return True

    # 각 사용자별로 독립 프로세스 실행 (Flask 서버 포함)
    processes = []
    base_port = 9001  # 메인 백엔드(9000) 다음부터 시작

    for idx, user in enumerate(users_to_process):
        user_id = user["user_id"]
        port = base_port + idx

        cmd = [
            sys.executable,
            "main_server.py",
            "--user", user_id,
            "--action", "punch_out",
            "--port", str(port)
        ]

        logger.info(f"[{user_id}] 퇴근 프로세스 시작 (포트: {port})")
        proc = subprocess.Popen(cmd, cwd=os.getcwd())
        processes.append((user_id, proc))

    # 모든 프로세스 완료 대기
    all_success = True
    for user_id, proc in processes:
        returncode = proc.wait()
        if returncode == 0:
            logger.info(f"[{user_id}] 퇴근 처리 완료 (성공)")
        else:
            logger.error(f"[{user_id}] 퇴근 처리 완료 (실패: exit code {returncode})")
            all_success = False

    return all_success

def execute_punch_in():
    """출근 처리 실행 (병렬 모드 사용)"""
    return execute_punch_in_parallel()

def execute_punch_out():
    """퇴근 처리 실행 (병렬 모드 사용)"""
    return execute_punch_out_parallel()

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

def check_missed_schedules():
    """재시작 시 놓친 스케줄 확인 및 처리"""
    now = datetime.now()
    current_time = now.time()
    current_weekday = now.weekday()  # 0=월요일, 6=일요일

    # 평일이 아니면 체크하지 않음
    if current_weekday >= 5:  # 토요일(5), 일요일(6)
        logger.info("주말이므로 놓친 스케줄 체크 생략")
        return

    logger.info(f"놓친 스케줄 체크 시작 - 현재시간: {current_time}")
    db_manager.log_system("INFO", "watchdog",
        f"놓친 스케줄 체크 시작 - 현재시간: {current_time}",
        stage="missed_schedule_check")

    # 1. 출근 시간대 놓쳤는지 체크 (8:40 이후)
    if current_time > dt_time(8, 40):
        logger.info("출근 시간대(08:00-08:40) 경과 - 놓친 출근 확인")
        db_manager.log_system("INFO", "watchdog",
            "출근 시간대 경과 - 놓친 출근 확인 및 처리",
            stage="missed_punch_in_check")

        # 출근 이력이 없는 사용자들에게 출근 처리
        users = get_users()
        users_needing_punch_in = []

        for user in users:
            user_id = user["user_id"]
            is_workday = db_manager.is_workday_scheduled(user_id)
            has_success_today = db_manager.has_today_success(user_id, "punch_in")

            if is_workday and not has_success_today:
                users_needing_punch_in.append(user_id)
                db_manager.log_system("INFO", "watchdog",
                    f"[{user_id}] 놓친 출근 처리 대상에 추가",
                    stage="missed_punch_in_target", user_id=user_id, action_type="punch_in")

        if users_needing_punch_in:
            logger.info(f"놓친 출근 처리 시도 - 대상 사용자: {users_needing_punch_in}")
            db_manager.log_system("WARNING", "watchdog",
                f"놓친 출근 처리 시도 - 대상 사용자: {users_needing_punch_in}",
                stage="missed_punch_in_execute", action_type="punch_in")

            success = execute_punch_in_parallel()
            if success:
                logger.info("✅ 놓친 출근 처리 성공")
                db_manager.log_system("INFO", "watchdog",
                    "놓친 출근 처리 성공",
                    stage="missed_punch_in_success", action_type="punch_in")
            else:
                logger.warning("⚠️ 놓친 출근 처리 실패")
                db_manager.log_system("WARNING", "watchdog",
                    "놓친 출근 처리 실패",
                    stage="missed_punch_in_failure", action_type="punch_in")

    # 2. 퇴근 시간대 놓쳤는지 체크 (19:00 이후)
    if current_time > dt_time(19, 0):
        logger.info("퇴근 시간대(18:00-19:00) 경과 - 놓친 퇴근 확인")
        db_manager.log_system("INFO", "watchdog",
            "퇴근 시간대 경과 - 놓친 퇴근 확인 및 처리",
            stage="missed_punch_out_check")

        # 출근은 했지만 퇴근 이력이 없는 사용자들에게 퇴근 처리
        users = get_users()
        users_needing_punch_out = []

        for user in users:
            user_id = user["user_id"]
            has_punch_in_success = db_manager.has_today_success(user_id, "punch_in")
            has_punch_out_success = db_manager.has_today_success(user_id, "punch_out")

            if has_punch_in_success and not has_punch_out_success:
                users_needing_punch_out.append(user_id)
                db_manager.log_system("INFO", "watchdog",
                    f"[{user_id}] 놓친 퇴근 처리 대상에 추가",
                    stage="missed_punch_out_target", user_id=user_id, action_type="punch_out")

        if users_needing_punch_out:
            logger.info(f"놓친 퇴근 처리 시도 - 대상 사용자: {users_needing_punch_out}")
            db_manager.log_system("WARNING", "watchdog",
                f"놓친 퇴근 처리 시도 - 대상 사용자: {users_needing_punch_out}",
                stage="missed_punch_out_execute", action_type="punch_out")

            success = execute_punch_out_parallel()
            if success:
                logger.info("✅ 놓친 퇴근 처리 성공")
                db_manager.log_system("INFO", "watchdog",
                    "놓친 퇴근 처리 성공",
                    stage="missed_punch_out_success", action_type="punch_out")
            else:
                logger.warning("⚠️ 놓친 퇴근 처리 실패")
                db_manager.log_system("WARNING", "watchdog",
                    "놓친 퇴근 처리 실패",
                    stage="missed_punch_out_failure", action_type="punch_out")

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

    # 워치독 시작 시 놓친 스케줄 확인
    logger.info("🕐 워치독 시작 - 놓친 스케줄 확인")
    db_manager.log_system("INFO", "watchdog",
        "워치독 시작 - 놓친 스케줄 확인 수행",
        stage="startup_missed_check")

    try:
        check_missed_schedules()
    except Exception as e:
        logger.error(f"❌ 놓친 스케줄 확인 실패: {e}")
        db_manager.log_system("ERROR", "watchdog",
            f"놓친 스케줄 확인 예외 발생: {e}",
            stage="startup_missed_check_error")

    # 워치독 시작 시 초기 출근 체크 수행 (병렬 실행)
    logger.info("🚀 워치독 시작 - 초기 출근 체크 수행 (병렬)")
    db_manager.log_system("INFO", "watchdog",
        "워치독 시작 - 초기 출근 체크 수행 (병렬 실행)",
        stage="initial_startup")

    try:
        logger.info("초기 출근 처리 시도 시작 (병렬 실행)")
        db_manager.log_system("INFO", "watchdog",
            "초기 출근 처리 시도 - 사용자별 병렬 프로세스 실행",
            stage="parallel_execution", action_type="punch_in")

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

    # 메인 서버 모니터링: 60초마다 체크
    scheduler.add_job(monitor_main_server, 'interval', seconds=60)

    logger.info("스케줄러 시작")
    logger.info("출근 스케줄: 월-금 08:00-08:40 (5분간격)")
    logger.info("퇴근 스케줄: 월-금 18:00-19:00 (5분간격)")
    logger.info("메인 서버 모니터링: 60초마다")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("스케줄러 종료")

if __name__ == '__main__':
    main()