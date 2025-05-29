import os
import sys
import time
import random
import logging
import signal
from datetime import datetime, time as dt_time
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from playwright.sync_api import sync_playwright

# 전역 스케줄러 선언 (signal 핸들러에서 접근하기 위해)
scheduler = None

# 종료 시그널 핸들러
def shutdown_handler(signum, frame):
    logging.getLogger('auto_chultae').info("종료 신호를 수신했습니다. 스케줄러 종료 중...")
    if scheduler:
        scheduler.shutdown(wait=True)
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, shutdown_handler)  # kill

# 로깅 설정
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"auto_chultae_{datetime.now().strftime('%Y%m%d')}.log")
    logger = logging.getLogger('auto_chultae')
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger

logger = setup_logging()

# 사용자 계정 정보
USERS = [
    {"user_id": "hc0125", "password": "Wkwkd119!!"},
    # {"user_id": "user2", "password": "password2"},
]

# 상수 정의
LOGIN_URL            = "https://gw.metabuild.co.kr/ekp/view/login/userLogin"
ATTEND_PAGE_URL      = "https://gw.metabuild.co.kr/ekp/main/home/homGwMain"
PUNCH_IN_BUTTON_ID   = "#ptlAttendRegist_btn_attn"
PUNCH_OUT_BUTTON_IDS = ["#ptlAttendRegist_btn_lvof3", "#ptlAttendRegist_btn_lvof2"]

def login_and_click_button(user_id, password, button_ids, action_name):
    start_time = time.time()
    logger.info(f"[{user_id}] [{action_name}] 프로세스 시작")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                # 로그인
                logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
                page.goto(LOGIN_URL, timeout=30000)
                page.fill("#userId", user_id)
                page.fill("#password", password)
                page.click("button[type=submit]")
                logger.info(f"[{user_id}] [{action_name}] 로그인 성공")
            except Exception as e:
                logger.error(f"[{user_id}] [{action_name}] 로그인 중 오류 발생: {e}")
                raise

            # 홈 화면 로드 대기
            page.wait_for_url("**/homGwMain", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)

            # 출근 상태 체크
            if action_name == "punch_in":
                try:
                    if page.is_visible("div.div_punch", timeout=3000):
                        logger.info(f"[{user_id}] [{action_name}] 이미 출근 완료 상태입니다.")
                        return
                except:
                    pass

            # 버튼 클릭
            clicked = False
            # 공통 테이블 로드 대기
            page.wait_for_selector("td#ptlAttendRegist_punch_in", timeout=30000)
            for btn in button_ids:
                try:
                    logger.info(f"[{user_id}] [{action_name}] 버튼 대기 중: {btn}")
                    page.wait_for_selector(btn, timeout=5000, state="visible")
                    page.click(btn)
                    logger.info(f"[{user_id}] [{action_name}] 버튼 클릭 완료: {btn}")
                    clicked = True
                    break
                except Exception as btn_err:
                    logger.warning(f"[{user_id}] [{action_name}] 버튼 클릭 실패 ({btn}): {btn_err}")

            # 이미 처리된 경우
            if not clicked and action_name == "punch_in":
                try:
                    if page.is_visible("div.div_punch", timeout=3000):
                        logger.info(f"[{user_id}] [{action_name}] 이미 출근 완료 상태입니다.")
                        return
                except:
                    pass

            if not clicked:
                error_msg = f"[{user_id}] [{action_name}] 사용할 수 있는 버튼을 찾을 수 없습니다."
                logger.error(error_msg)
                os.makedirs("screenshots", exist_ok=True)
                path = f"screenshots/error_{user_id}_{action_name}_{int(time.time())}.png"
                page.screenshot(path=path, full_page=True)
                logger.info(f"[{user_id}] [{action_name}] 오류 스크린샷 저장: {path}")
                raise Exception(error_msg)

            # 마무리
            time.sleep(2)
            elapsed = time.time() - start_time
            logger.info(f"[{user_id}] [{action_name}] 완료 (소요시간: {elapsed:.2f}s)")
            context.close()
            browser.close()

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{user_id}] [{action_name}] 오류 발생 (소요시간: {elapsed:.2f}s): {e}", exc_info=True)
        raise

def process_users(button_ids, action_name):
    for u in USERS:
        uid = u["user_id"]; pwd = u["password"]
        logger.info(f"=== 사용자 처리 시작: {uid}, 작업: {action_name} ===")
        try:
            delay = random.randint(0, 60)
            logger.info(f"[{uid}] [{action_name}] 랜덤 딜레이: {delay}s")
            time.sleep(delay)
            login_and_click_button(uid, pwd, button_ids, action_name)
        except Exception as e:
            if "이미 출근 완료" in str(e):
                logger.info(f"[{uid}] [{action_name}] {e}")
            else:
                logger.error(f"[{uid}] [{action_name}] 처리 중 오류: {e}")
        logger.info(f"=== {uid} 처리 완료 ===\n")

def punch_in():
    logger.info("===== 출근 처리 시작 =====")
    process_users([PUNCH_IN_BUTTON_ID], "punch_in")
    logger.info("===== 출근 처리 완료 =====")

def punch_out():
    logger.info("===== 퇴근 처리 시작 =====")
    process_users(PUNCH_OUT_BUTTON_IDS, "punch_out")
    logger.info("===== 퇴근 처리 완료 =====")

def main():
    global scheduler

    logger.info("=" * 50)
    logger.info("근태 관리 시스템 시작")
    logger.info("시작 시 출근 체크 수행")
    punch_in()

    scheduler = BlockingScheduler(
        jobstores={'default': MemoryJobStore()},
        executors={'default': ThreadPoolExecutor(10)},
        job_defaults={
            'coalesce': False,
            'max_instances': 5,
            'misfire_grace_time': 3600
        },
        timezone="Asia/Seoul"
    )
    scheduler.add_job(punch_in, 'cron', hour=8,  minute=0,  day_of_week='mon-fri')
    scheduler.add_job(punch_out,'cron', hour=18, minute=5,  day_of_week='mon-fri')

    logger.info("스케줄러 시작")
    scheduler.start()

if __name__ == '__main__':
    main()
