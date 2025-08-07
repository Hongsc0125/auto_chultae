import os
import sys
import time
import random
import logging
import signal
import json
from datetime import datetime, time as dt_time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from playwright.sync_api import sync_playwright

# .env 파일 로드
load_dotenv()

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
users_str = os.getenv("USERS", "")
USERS = []
if users_str:
    for user in users_str.split(','):
        user_id, password = user.split(':')
        USERS.append({"user_id": user_id, "password": password})

# 프록시 설정
PROXY_CONFIG = {
    "server": os.getenv("PROXY_SERVER"),
    "username": os.getenv("PROXY_USERNAME"),
    "password": os.getenv("PROXY_PASSWORD")
}

# 상수 정의
LOGIN_URL            = os.getenv("LOGIN_URL", "https://gw.metabuild.co.kr/ekp/view/login/userLogin")
ATTEND_PAGE_URL      = os.getenv("ATTEND_PAGE_URL", "https://gw.metabuild.co.kr/ekp/main/home/homGwMain")
PUNCH_IN_BUTTON_ID   = "#ptlAttendRegist_btn_attn"
PUNCH_OUT_BUTTON_IDS = ["#ptlAttendRegist_btn_lvof3", "#ptlAttendRegist_btn_lvof2"]

def close_all_popups(page, user_id, action_name):
    """모든 팝업을 강제로 닫는 함수"""
    try:
        logger.info(f"[{user_id}] [{action_name}] 팝업 처리 시작")
        
        # 1. 모든 팝업 대화상자를 강제로 닫기
        page.evaluate("""() => {
            // jQuery UI 다이얼로그 모두 닫기
            if (window.$ && $.ui && $.ui.dialog) {
                $('.ui-dialog').each(function() {
                    const dialog = $(this);
                    if (dialog.is(':visible')) {
                        dialog.hide();
                        dialog.remove();
                    }
                });
            }
            
            // 일반 팝업 레이어들 숨기기
            const popupSelectors = [
                '.popnoti_lyr',
                '.ui-dialog',
                '.popup',
                '.modal',
                '.layer-popup',
                '[class*="popup"]',
                '[class*="modal"]',
                '[class*="dialog"]'
            ];
            
            popupSelectors.forEach(selector => {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    if (el.style.display !== 'none') {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.zIndex = '-9999';
                    }
                });
            });
            
            // 오버레이 제거
            const overlays = document.querySelectorAll('.ui-widget-overlay, .modal-backdrop, [class*="overlay"]');
            overlays.forEach(overlay => overlay.remove());
        }""")
        
        # 2. 닫기 버튼이 있다면 클릭 시도
        close_button_selectors = [
            ".ui-dialog-titlebar-close",
            ".btn-close",
            ".close",
            "[aria-label='Close']",
            "[data-dismiss='modal']"
        ]
        
        for selector in close_button_selectors:
            try:
                if page.is_visible(selector, timeout=1000):
                    page.click(selector, timeout=2000)
                    logger.info(f"[{user_id}] [{action_name}] 닫기 버튼 클릭: {selector}")
                    time.sleep(0.5)
            except:
                continue
        
        # 3. ESC 키로 팝업 닫기 시도
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except:
            pass
            
        logger.info(f"[{user_id}] [{action_name}] 팝업 처리 완료")
        
    except Exception as e:
        logger.warning(f"[{user_id}] [{action_name}] 팝업 처리 중 오류: {e}")

def wait_and_click_button(page, button_selector, user_id, action_name, max_attempts=5):
    """버튼 클릭을 재시도하는 함수"""
    for attempt in range(max_attempts):
        try:
            logger.info(f"[{user_id}] [{action_name}] 버튼 클릭 시도 {attempt + 1}/{max_attempts}: {button_selector}")
            
            # 팝업 재정리
            if attempt > 0:
                close_all_popups(page, user_id, action_name)
                time.sleep(1)
            
            # 버튼이 존재하는지 확인
            page.wait_for_selector(button_selector, timeout=10000, state="attached")
            
            # 버튼이 보이는지 확인
            if not page.is_visible(button_selector, timeout=5000):
                logger.warning(f"[{user_id}] [{action_name}] 버튼이 보이지 않음: {button_selector}")
                continue
            
            # 스크롤해서 버튼을 화면에 보이게 하기
            page.evaluate(f"""() => {{
                const btn = document.querySelector('{button_selector}');
                if (btn) {{
                    btn.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }}""")
            time.sleep(1)
            
            # 강제로 클릭 (JavaScript 사용)
            success = page.evaluate(f"""() => {{
                const btn = document.querySelector('{button_selector}');
                if (btn && !btn.disabled) {{
                    btn.click();
                    return true;
                }}
                return false;
            }}""")
            
            if success:
                logger.info(f"[{user_id}] [{action_name}] 버튼 클릭 성공 (JavaScript): {button_selector}")
                return True
            else:
                # 일반 클릭 시도
                page.click(button_selector, timeout=5000, force=True)
                logger.info(f"[{user_id}] [{action_name}] 버튼 클릭 성공 (Playwright): {button_selector}")
                return True
                
        except Exception as e:
            logger.warning(f"[{user_id}] [{action_name}] 버튼 클릭 실패 시도 {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)
            continue
    
    return False

def login_and_click_button(user_id, password, button_ids, action_name):
    start_time = time.time()
    logger.info(f"[{user_id}] [{action_name}] 프로세스 시작")
    
    browser = None
    context = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-web-security',
                    '--ignore-certificate-errors-spki-list',
                    '--ignore-certificate-errors',
                    '--ignore-ssl-errors',
                    '--proxy-bypass-list=<-loopback>',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                proxy=PROXY_CONFIG
            )
            page = context.new_page()
            
            try:
                # 로그인
                logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
                page.goto(LOGIN_URL, timeout=120000, wait_until="load")
                
                page.fill("#userId", user_id)
                page.fill("#password", password)
                page.click("button[type=submit]")
                
                # 로그인 완료 대기
                page.wait_for_url("**/homGwMain", timeout=120000)
                page.wait_for_load_state("load", timeout=60000)
                
                logger.info(f"[{user_id}] [{action_name}] 로그인 성공")
                
            except Exception as e:
                logger.error(f"[{user_id}] [{action_name}] 로그인 중 오류 발생: {e}")
                raise

            # 페이지 완전 로드 대기
            time.sleep(3)
            
            # 모든 팝업 닫기
            close_all_popups(page, user_id, action_name)
            time.sleep(2)

            # 출근 상태 미리 체크 (출근인 경우)
            # if action_name == "punch_in":
            #     try:
            #         # 이미 출근한 상태인지 확인
            #         already_punched = page.evaluate("""() => {
            #             const punchDiv = document.querySelector('div.div_punch');
            #             const punchText = document.querySelector('td#ptlAttendRegist_punch_in');
                        
            #             if (punchDiv && punchDiv.style.display !== 'none') {
            #                 return true;
            #             }
                        
            #             if (punchText && punchText.textContent && punchText.textContent.trim() !== '') {
            #                 return true;
            #             }
                        
            #             return false;
            #         }""")
                    
            #         if already_punched:
            #             logger.info(f"[{user_id}] [{action_name}] 이미 출근 완료 상태입니다.")
            #             return
                        
            #     except Exception as e:
            #         logger.debug(f"[{user_id}] [{action_name}] 출근 상태 체크 중 오류: {e}")

            # 근태 관리 테이블 로드 대기
            try:
                page.wait_for_selector("table", timeout=15000)
                page.wait_for_selector("td#ptlAttendRegist_punch_in", timeout=15000)
                logger.info(f"[{user_id}] [{action_name}] 근태 관리 테이블 로드 완료")
            except Exception as e:
                logger.warning(f"[{user_id}] [{action_name}] 테이블 로드 대기 실패: {e}")

            # 버튼 클릭 시도
            clicked = False
            for btn in button_ids:
                if wait_and_click_button(page, btn, user_id, action_name):
                    clicked = True
                    break

            if not clicked:
                # 마지막으로 이미 처리된 상태인지 다시 확인
                if action_name == "punch_in":
                    try:
                        already_done = page.evaluate("""() => {
                            const indicators = [
                                'div.div_punch',
                                'td#ptlAttendRegist_punch_in',
                                '.attendance-complete',
                                '[class*="punch"]'
                            ];
                            
                            return indicators.some(selector => {
                                const el = document.querySelector(selector);
                                return el && (
                                    el.style.display !== 'none' || 
                                    (el.textContent && el.textContent.trim() !== '')
                                );
                            });
                        }""")
                        
                        if already_done:
                            logger.info(f"[{user_id}] [{action_name}] 이미 처리 완료된 상태로 확인됨")
                            return
                    except:
                        pass

                # 스크린샷 저장
                error_msg = f"[{user_id}] [{action_name}] 사용할 수 있는 버튼을 찾을 수 없습니다."
                logger.error(error_msg)
                os.makedirs("screenshots", exist_ok=True)
                path = f"screenshots/error_{user_id}_{action_name}_{int(time.time())}.png"
                page.screenshot(path=path, full_page=True)
                logger.info(f"[{user_id}] [{action_name}] 오류 스크린샷 저장: {path}")
                
                # 페이지 HTML도 저장
                html_path = f"screenshots/error_{user_id}_{action_name}_{int(time.time())}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.content())
                logger.info(f"[{user_id}] [{action_name}] 페이지 HTML 저장: {html_path}")
                
                raise Exception(error_msg)

            # 클릭 후 처리 대기
            time.sleep(3)
            elapsed = time.time() - start_time
            logger.info(f"[{user_id}] [{action_name}] 완료 (소요시간: {elapsed:.2f}s)")

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{user_id}] [{action_name}] 오류 발생 (소요시간: {elapsed:.2f}s): {e}")
        raise
    finally:
        try:
            if context:
                context.close()
            if browser:
                browser.close()
        except:
            pass

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
            if "이미 출근 완료" in str(e) or "이미 처리 완료" in str(e):
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