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

# 사용자 계정 정보 (여러 계정 추가 가능)
USERS = [
    {"user_id": "hc0125", "password": "Wkwkd119!!"},
    # {"user_id": "user2", "password": "password2"},
    # {"user_id": "user3", "password": "password3"},
]

# 상수 정의
LOGIN_URL = "https://gw.metabuild.co.kr/ekp/view/login/userLogin"
ATTEND_PAGE_URL = "https://gw.metabuild.co.kr/ekp/main/home/homGwMain"
PUNCH_OUT_BUTTON_ID = "#ptlAttendRegist_btn_lvof3"
PUNCH_OUT_BUTTON_ID2 = "#ptlAttendRegist_btn_lvof2"
PUNCH_IN_BUTTON_ID = "#ptlAttendRegist_btn_attn"

def login_and_click_button(user_id, password, button_ids, action_name):
    start_time = time.time()
    logger.info(f"[{user_id}] [{action_name}] 프로세스 시작")
    
    try:
        with sync_playwright() as p:
            logger.info(f"[{user_id}] [{action_name}] 브라우저 실행 중...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 로그인 시도
            logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
            page.goto(LOGIN_URL, timeout=30000)
            
            logger.info(f"[{user_id}] [{action_name}] 로그인 정보 입력 중...")
            page.fill("#userId", user_id)
            page.fill("#password", password)
            
            logger.info(f"[{user_id}] [{action_name}] 로그인 시도 중...")
            page.click("button[type=submit]")
            logger.info(f"[{user_id}] [{action_name}] 로그인 성공")

            # 2) 리다이렉트된 홈 화면 대기
            page.wait_for_url("**/homGwMain", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # 출근 버튼 클릭 시에만 div_punch 확인
            if action_name == "punch_in":
                try:
                    # div_punch 요소가 있는지 확인 (출근 완료 상태)
                    if page.is_visible("div.div_punch", timeout=3000):
                        logger.info(f"[{user_id}] [{action_name}] 이미 출근이 완료된 상태입니다.")
                        return
                except Exception as e:
                    logger.info(f"[{user_id}] [{action_name}] 출근 상태 확인 중: {str(e)}")
            
            # 출근/퇴근 버튼이 있는 테이블 대기
            page.wait_for_selector("td#ptlAttendRegist_punch_in", timeout=30000)
            
            # 버튼 클릭 시도
            clicked = False
            button_ids = button_ids if isinstance(button_ids, list) else [button_ids]
            
            for btn_id in button_ids:
                try:
                    logger.info(f"[{user_id}] [{action_name}] 버튼 대기 중: {btn_id}")
                    page.wait_for_selector(btn_id, timeout=5000, state="visible")
                    logger.info(f"[{user_id}] [{action_name}] 버튼을 클릭합니다: {btn_id}")
                    page.click(btn_id)
                    logger.info(f"[{user_id}] [{action_name}] 버튼 클릭 완료: {btn_id}")
                    clicked = True
                    break
                except Exception as btn_error:
                    logger.warning(f"[{user_id}] [{action_name}] 버튼 클릭 실패 ({btn_id}): {str(btn_error)}")
            
            if not clicked and action_name == "punch_in":  # 출근 버튼이 없으면 이미 출근한 것으로 간주
                try:
                    if page.is_visible("div.div_punch", timeout=3000):
                        logger.info(f"[{user_id}] [{action_name}] 출근 버튼이 없지만 이미 출근이 완료된 상태입니다.")
                        return
                except:
                    pass
            
            if not clicked:
                error_msg = f"[{user_id}] [{action_name}] 사용 가능한 버튼을 찾을 수 없습니다."
                logger.error(error_msg)
                # 오류 스크린샷 저장
                screenshot_dir = "screenshots"
                if not os.path.exists(screenshot_dir):
                    os.makedirs(screenshot_dir)
                screenshot_path = os.path.join(screenshot_dir, f"error_{user_id}_{action_name}_{int(time.time())}.png")
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"[{user_id}] [{action_name}] 오류 스크린샷 저장됨: {screenshot_path}")
                raise Exception(error_msg)

            # 브라우저 종료 전에 잠시 대기
            time.sleep(2)
            browser.close()
            
            elapsed_time = time.time() - start_time
            logger.info(f"[{user_id}] [{action_name}] 프로세스 완료 (소요시간: {elapsed_time:.2f}초)")
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{user_id}] [{action_name}] 처리 중 오류 발생 (소요시간: {elapsed_time:.2f}초): {str(e)}", exc_info=True)
        raise

def process_users(action_func, button_ids, action_name):
    """여러 사용자에 대한 출퇴근 처리를 수행하는 공통 함수"""
    for user in USERS:
        user_id = user["user_id"]
        password = user["password"]
        
        logger.info(f"[사용자 처리 시작] ID: {user_id}, 작업: {action_name}")
        
        try:
            # 각 사용자별로 랜덤 딜레이 적용 (0~60초)
            delay = random.randint(0, 60)
            logger.info(f"[{user_id}] [{action_name}] 대기 시간: {delay}초")
            time.sleep(delay)
            
            # 출퇴근 처리
            login_and_click_button(user_id, password, button_ids, action_name)
            logger.info(f"[{user_id}] [{action_name}] 처리 완료")
            
        except Exception as e:
            if "이미 출근이 완료된 상태" in str(e):
                logger.info(f"[{user_id}] [{action_name}] {str(e)}")
            else:
                logger.error(f"[{user_id}] [{action_name}] 처리 중 오류 발생: {str(e)}")
            continue  # 다음 사용자 계속 처리

def punch_in():
    """모든 사용자에 대한 출근 처리"""
    logger.info("===== 출근 처리 시작 =====")
    process_users(login_and_click_button, [PUNCH_IN_BUTTON_ID], "punch_in")
    logger.info("===== 출근 처리 완료 =====")

def punch_out():
    """모든 사용자에 대한 퇴근 처리"""
    logger.info("===== 퇴근 처리 시작 =====")
    process_users(login_and_click_button, [PUNCH_OUT_BUTTON_ID, PUNCH_OUT_BUTTON_ID2], "punch_out")
    logger.info("===== 퇴근 처리 완료 =====")

# 스캐줄러
def main():
    try:
        logger.info("=" * 50)
        logger.info(f"총 {len(USERS)}명의 사용자에 대한 근태 관리 시스템을 시작합니다.")
        
        # 프로그램 시작 시 출근 체크
        logger.info("프로그램 시작 시 출근 체크를 진행합니다.")
        punch_in()
        
        scheduler = BlockingScheduler(timezone="Asia/Seoul")
        
        # 퇴근 스케줄러
        scheduler.add_job(punch_out, 'cron', hour=18, minute=5, day_of_week='mon-fri')
        # scheduler.add_job(punch_out, 'cron', minute='*/1')
        
        # 출근 스케줄러
        scheduler.add_job(punch_in, 'cron', hour=8, minute=00, day_of_week='mon-fri')
        # scheduler.add_job(punch_in, 'cron', minute='*/1')
        
        logger.info("스케줄러가 시작되었습니다.")
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
