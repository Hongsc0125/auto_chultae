#!/usr/bin/env python3
"""
Auto Chultae Watchdog
메인 프로그램을 모니터링하고 무한 대기 시 재시작하는 워치독
"""

import os
import sys
import time
import signal
import subprocess
import logging
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.memory import MemoryJobStore

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

# 사용자 목록 로드
users_str = os.getenv("USERS", "")
USERS = []
if users_str:
    for user in users_str.split(','):
        user_id, password = user.split(':')
        USERS.append({"user_id": user_id, "password": password})


class AutoChultaeWatchdog:
    def __init__(self):
        self.main_script = "auto_chultae.py"
        self.heartbeat_file = "heartbeat.txt"
        self.max_heartbeat_age = 300  # 5분
        self.check_interval = 30  # 30초마다 체크 (더 세밀하게)
        self.process = None
        self.restart_count = 0
        self.max_restarts_per_hour = 5
        self.restart_times = []
        self.last_heartbeat_stage = None  # 마지막 하트비트 단계 추적

    def cleanup_old_restarts(self):
        """1시간 이상 된 재시작 기록 제거"""
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.restart_times = [t for t in self.restart_times if t > cutoff_time]

    def can_restart(self):
        """시간당 재시작 횟수 제한 체크"""
        self.cleanup_old_restarts()
        return len(self.restart_times) < self.max_restarts_per_hour

    def get_heartbeat_info(self):
        """하트비트 파일의 상세 정보 반환"""
        try:
            if not os.path.exists(self.heartbeat_file):
                return {"age": float('inf'), "stage": "unknown", "user_id": None, "action": None, "pid": None}

            with open(self.heartbeat_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # JSON 형식으로 파싱 시도
            try:
                import json
                heartbeat_data = json.loads(content)

                # 시간 계산
                timestamp_str = heartbeat_data.get("timestamp", "")
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                age = (datetime.now() - timestamp).total_seconds()

                return {
                    "age": age,
                    "stage": heartbeat_data.get("stage", "unknown"),
                    "user_id": heartbeat_data.get("user_id"),
                    "action": heartbeat_data.get("action"),
                    "pid": heartbeat_data.get("pid"),
                    "timestamp": timestamp_str
                }
            except (json.JSONDecodeError, ValueError):
                # 기존 형식 (문자열)인 경우
                file_time = datetime.fromtimestamp(os.path.getmtime(self.heartbeat_file))
                age = (datetime.now() - file_time).total_seconds()
                return {"age": age, "stage": "legacy_format", "user_id": None, "action": None, "pid": None}

        except Exception as e:
            logger.warning(f"하트비트 파일 확인 실패: {e}")
            return {"age": float('inf'), "stage": "error", "user_id": None, "action": None, "pid": None}

    def is_process_running(self):
        """프로세스가 실행 중인지 확인"""
        if self.process is None:
            return False

        poll_result = self.process.poll()
        return poll_result is None

    def kill_process(self):
        """메인 프로세스 강제 종료"""
        if self.process and self.is_process_running():
            try:
                logger.info("메인 프로세스 종료 시도 (SIGTERM)")
                self.process.terminate()

                # 10초 대기
                try:
                    self.process.wait(timeout=10)
                    logger.info("메인 프로세스 정상 종료")
                except subprocess.TimeoutExpired:
                    logger.warning("SIGTERM 무시, SIGKILL 사용")
                    self.process.kill()
                    self.process.wait()
                    logger.info("메인 프로세스 강제 종료")

            except Exception as e:
                logger.error(f"프로세스 종료 실패: {e}")
            finally:
                self.process = None

    def start_main_process(self):
        """메인 프로세스 시작"""
        try:
            logger.info(f"메인 프로세스 시작: {self.main_script}")
            self.process = subprocess.Popen(
                [sys.executable, self.main_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.restart_count += 1
            self.restart_times.append(datetime.now())
            logger.info(f"메인 프로세스 시작됨 (PID: {self.process.pid})")

        except Exception as e:
            logger.error(f"메인 프로세스 시작 실패: {e}")
            self.process = None

    def restart_main_process(self):
        """메인 프로세스 재시작"""
        if not self.can_restart():
            logger.error(f"시간당 재시작 제한 초과 ({self.max_restarts_per_hour}번)")
            return False

        logger.info("=== 메인 프로세스 재시작 ===")
        self.kill_process()
        time.sleep(5)  # 5초 대기
        self.start_main_process()
        return True

    def check_health(self):
        """헬스체크 수행"""
        # 1. 프로세스 실행 상태 확인
        if not self.is_process_running():
            logger.warning("메인 프로세스가 실행되지 않음")
            return False

        # 2. 하트비트 상세 확인
        heartbeat_info = self.get_heartbeat_info()
        heartbeat_age = heartbeat_info["age"]

        if heartbeat_age > self.max_heartbeat_age:
            stage = heartbeat_info["stage"]
            user_id = heartbeat_info["user_id"]
            action = heartbeat_info["action"]
            pid = heartbeat_info["pid"]

            if user_id and action:
                logger.warning(f"하트비트 오래됨: {heartbeat_age:.1f}초 (마지막: [{user_id}] [{action}] {stage}, PID: {pid})")
            else:
                logger.warning(f"하트비트 오래됨: {heartbeat_age:.1f}초 (마지막: {stage}, PID: {pid})")

            return False

        # 3. 특정 단계에서 너무 오래 걸리는 경우 체크 (추가 모니터링)
        stage = heartbeat_info["stage"]
        critical_stages = {
            "page_creation_start": 180,  # 페이지 생성 3분
            "main_page_wait": 240,       # 메인 페이지 대기 4분
            "page_load_wait": 180,       # 페이지 로드 대기 3분
            "button_click_start": 120    # 버튼 클릭 2분
        }

        if stage in critical_stages and heartbeat_age > critical_stages[stage]:
            user_id = heartbeat_info["user_id"]
            action = heartbeat_info["action"]
            logger.warning(f"중요 단계에서 지연: {stage} ({heartbeat_age:.1f}초) - [{user_id}] [{action}]")
            return False

        # 4. 단계 변화 감지 및 로깅
        if self.last_heartbeat_stage != stage:
            user_id = heartbeat_info["user_id"]
            action = heartbeat_info["action"]
            if user_id and action:
                logger.info(f"🔄 단계 변화: [{user_id}] [{action}] {self.last_heartbeat_stage} → {stage}")
            else:
                logger.info(f"🔄 단계 변화: {self.last_heartbeat_stage} → {stage}")
            self.last_heartbeat_stage = stage

        # 5. 헬스체크 성공 (간소화된 로깅)
        if heartbeat_age < 30:  # 30초 이내는 간단히
            logger.debug(f"💓 OK: {stage} ({heartbeat_age:.0f}s)")
        else:  # 30초 이상은 상세히
            user_id = heartbeat_info["user_id"]
            action = heartbeat_info["action"]
            if user_id and action:
                logger.info(f"💓 헬스체크 OK: [{user_id}] [{action}] {stage} ({heartbeat_age:.1f}초 전)")
            else:
                logger.info(f"💓 헬스체크 OK: {stage} ({heartbeat_age:.1f}초 전)")

        return True



    def run(self):
        """워치독 메인 루프"""
        logger.info("Auto Chultae Watchdog 시작")

        # 초기 프로세스 시작
        self.start_main_process()

        try:
            while True:
                time.sleep(self.check_interval)

                if not self.check_health():
                    if not self.restart_main_process():
                        logger.error("재시작 제한으로 워치독 종료")
                        break

        except KeyboardInterrupt:
            logger.info("워치독 종료 신호 수신")
        except Exception as e:
            logger.error(f"워치독 오류: {e}")
        finally:
            self.kill_process()
            logger.info("워치독 종료")


def execute_punch_in():
    """출근 처리 실행 (서브프로세스)"""
    try:
        logger.info("출근 처리 시작 - 서브프로세스 실행")
        result = subprocess.run(
            [sys.executable, "-c", "from auto_chultae import punch_in; punch_in()"],
            capture_output=True,
            text=True,
            timeout=600  # 10분 타임아웃
        )

        if result.returncode == 0:
            logger.info("출근 처리 성공")
        else:
            logger.error(f"출근 처리 실패: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("출근 처리 타임아웃 (10분)")
        return False
    except Exception as e:
        logger.error(f"출근 처리 오류: {e}")
        return False

def execute_punch_out():
    """퇴근 처리 실행 (서브프로세스)"""
    try:
        logger.info("퇴근 처리 시작 - 서브프로세스 실행")
        result = subprocess.run(
            [sys.executable, "-c", "from auto_chultae import punch_out; punch_out()"],
            capture_output=True,
            text=True,
            timeout=600  # 10분 타임아웃
        )

        if result.returncode == 0:
            logger.info("퇴근 처리 성공")
        else:
            logger.error(f"퇴근 처리 실패: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("퇴근 처리 타임아웃 (10분)")
        return False
    except Exception as e:
        logger.error(f"퇴근 처리 오류: {e}")
        return False

def punch_in_with_retry():
    """출근 시간대 재시도 로직 (08:00-08:40)"""
    now = datetime.now()
    current_time = now.time()

    # 08:00-08:40 시간대가 아니면 실행하지 않음
    if not (dt_time(8, 0) <= current_time <= dt_time(8, 40)):
        return

    logger.info(f"출근 처리 시도 시작 ({current_time})")

    success = execute_punch_in()

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(8, 35):
            failed_users = [user["user_id"] for user in USERS]
            logger.warning(f"출근 처리 실패 - 대상 사용자: {failed_users}")

def punch_out_with_retry():
    """퇴근 시간대 재시도 로직 (18:00-19:00)"""
    now = datetime.now()
    current_time = now.time()

    # 18:00-19:00 시간대가 아니면 실행하지 않음
    if not (dt_time(18, 0) <= current_time <= dt_time(19, 0)):
        return

    logger.info(f"퇴근 처리 시도 시작 ({current_time})")

    success = execute_punch_out()

    if not success:
        # 실패 로그 기록
        if current_time > dt_time(18, 55):
            failed_users = [user["user_id"] for user in USERS]
            logger.warning(f"퇴근 처리 실패 - 대상 사용자: {failed_users}")

def main():
    # 시그널 핸들러 설정
    def signal_handler(signum, frame):
        logger.info("종료 신호 수신")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("워치독 시스템 시작 (스케줄링 + 모니터링)")

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
    for minute in range(0, 61, 5):  # 0, 5, 10, ..., 55, 60(19:00)
        scheduler.add_job(punch_out_with_retry, 'cron', hour=18, minute=minute, day_of_week='mon-fri')

    # 19:00에도 한 번 더
    scheduler.add_job(punch_out_with_retry, 'cron', hour=19, minute=0, day_of_week='mon-fri')

    # 일일 상태 리셋 (자정)
    scheduler.add_job(lambda: None, 'cron', hour=0, minute=0)  # 자정에 실행

    logger.info("스케줄러 시작")

    # 워치독과 스케줄러를 별도 스레드에서 실행
    import threading

    # 워치독 스레드
    watchdog = AutoChultaeWatchdog()
    watchdog_thread = threading.Thread(target=watchdog.run, daemon=True)
    watchdog_thread.start()

    # 메인 스레드에서 스케줄러 실행
    scheduler.start()

if __name__ == '__main__':
    main()