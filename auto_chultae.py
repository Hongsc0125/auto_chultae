import os
import time
import random
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from playwright.sync_api import sync_playwright

# 로깅 설정
def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"auto_chultae_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 로거 생성
    logger = logging.getLogger('auto_chultae')
    logger.setLevel(logging.INFO)
    
    # 로그 포맷 설정
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가 (기존 핸들러가 없을 때만)
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# 전역 로거 생성
logger = setup_logging()


USER_ID = "hc0125"
PASSWORD = "Wkwkd119!!"

LOGIN_URL = "https://gw.metabuild.co.kr/ekp/view/login/userLogin"
ATTEND_PAGE_URL = "https://gw.metabuild.co.kr/ekp/main/home/homGwMain"
BUTTON_ID = "#ptlAttendRegist_btn_lvof3"
PUNCH_IN_BUTTON_ID = "#ptlAttendRegist_btn_attn"


def login_and_click_button(button_id, action_name):
    start_time = time.time()
    logger.info(f"[{action_name}] 프로세스 시작")
    
    try:
        with sync_playwright() as p:
            logger.info(f"[{action_name}] 브라우저 실행 중...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 로그인 시도
            logger.info(f"[{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
            page.goto(LOGIN_URL, timeout=30000)
            
            logger.info(f"[{action_name}] 로그인 정보 입력 중...")
            page.fill("#userId", USER_ID)
            page.fill("#password", PASSWORD)
            
            logger.info(f"[{action_name}] 로그인 시도 중...")
            page.click("button[type=submit]")
            logger.info(f"[{action_name}] 로그인 성공")

            # 버튼 클릭 대기 및 실행
            logger.info(f"[{action_name}] 버튼 대기 중: {button_id}")
            try:
                page.wait_for_selector(button_id, timeout=20000, state="visible")
                logger.info(f"[{action_name}] 버튼을 클릭합니다.")
                page.click(button_id)
                logger.info(f"[{action_name}] 버튼 클릭 완료")
            except Exception as btn_error:
                logger.error(f"[{action_name}] 버튼 클릭 중 오류 발생: {btn_error}")
                # 오류 스크린샷 저장
                screenshot_dir = "screenshots"
                if not os.path.exists(screenshot_dir):
                    os.makedirs(screenshot_dir)
                screenshot_path = os.path.join(screenshot_dir, f"error_{action_name}_{int(time.time())}.png")
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"[{action_name}] 오류 스크린샷 저장됨: {screenshot_path}")
                raise btn_error

            # 브라우저 종료 전에 잠시 대기
            time.sleep(2)
            browser.close()
            
            elapsed_time = time.time() - start_time
            logger.info(f"[{action_name}] 프로세스 완료 (소요시간: {elapsed_time:.2f}초)")
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{action_name}] 처리 중 오류 발생 (소요시간: {elapsed_time:.2f}초): {str(e)}", exc_info=True)
        raise

def punch_in():
    delay = random.randint(0, 0)  # 0~5분 랜덤 딜레이
    logger.info(f"[punch_in] 출근 처리 시작 (랜덤 딜레이: {delay}초)")
    time.sleep(delay)
    logger.info("[punch_in] 딜레이 완료, 출근 처리 진행 중...")
    login_and_click_button(PUNCH_IN_BUTTON_ID, "punch_in")
    logger.info("[punch_in] 출근 처리 완료")

# def punch_out():
#     delay = random.randint(0, 300)  # 0~5분 랜덤 딜레이
#     logger.info(f"[punch_out] 퇴근 처리 시작 (랜덤 딜레이: {delay}초)")
#     time.sleep(delay)
#     logger.info("[punch_out] 딜레이 완료, 퇴근 처리 진행 중...")
#     login_and_click_button(BUTTON_ID, "punch_out")
#     logger.info("[punch_out] 퇴근 처리 완료")

# 스캐줄러
def main():
    try:
        logger.info("=" * 50)
        logger.info(f"사용자: {USER_ID}")
        
        scheduler = BlockingScheduler(timezone="Asia/Seoul")
        # 퇴근 스케줄러 (평일 오후 6시 5분)
        # scheduler.add_job(punch_out, 'cron', hour=18, minute=5, day_of_week='mon-fri')
        # scheduler.add_job(punch_out, 'cron', minute=1, day_of_week='mon-fri')
        # 출근 스케줄러 (평일 오전 8시 50분)
        # scheduler.add_job(punch_in, 'cron', hour=8, minute=50, day_of_week='mon-fri')
        scheduler.add_job(punch_in, 'cron', minute='*/1')
        
        logger.info("스케줄러가 시작되었습니다.")
        logger.info(" - 출근: 평일 오전 8시 50분 (0~5분 랜덤 딜레이 포함)")
        logger.info(" - 퇴근: 평일 오후 6시 5분 (0~5분 랜덤 딜레이 포함)")
        logger.info("=" * 50)
        
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}", exc_info=True)
    finally:
        logging.shutdown()

if __name__ == '__main__':
    main()
