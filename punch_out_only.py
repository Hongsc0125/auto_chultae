import os
import sys
import time
import random
import logging
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# .env 파일 로드
load_dotenv()

# 로깅 설정
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"punch_out_only_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logger = logging.getLogger('punch_out_only')
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
LOGIN_URL = os.getenv("LOGIN_URL")
ATTEND_PAGE_URL = os.getenv("ATTEND_PAGE_URL")

if not LOGIN_URL or not ATTEND_PAGE_URL:
    raise ValueError("LOGIN_URL과 ATTEND_PAGE_URL 환경변수가 필수입니다.")
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
            page.wait_for_selector(button_selector, timeout=30000, state="attached")
            
            # 버튼이 보이는지 확인
            if not page.is_visible(button_selector, timeout=15000):
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
                page.click(button_selector, timeout=15000, force=True)
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
            logger.info(f"[{user_id}] [{action_name}] Playwright 초기화 완료")
            logger.info(f"[{user_id}] [{action_name}] 브라우저 실행 시작...")
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
                    '--disable-features=VizDisplayCompositor',
                    '--lang=ko-KR',
                    '--font-render-hinting=none',
                    '--disable-font-subpixel-positioning'
                ]
            )
            logger.info(f"[{user_id}] [{action_name}] 브라우저 실행 완료")
            logger.info(f"[{user_id}] [{action_name}] 브라우저 컨텍스트 생성 시작...")
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                proxy=PROXY_CONFIG
            )
            logger.info(f"[{user_id}] [{action_name}] 브라우저 컨텍스트 생성 완료")
            
            # 컨텍스트 타임아웃 설정
            context.set_default_timeout(600000)  # 600초 타임아웃
            context.set_default_navigation_timeout(600000)  # 네비게이션 600초 타임아웃
            
            logger.info(f"[{user_id}] [{action_name}] 새 페이지 생성...")
            page_created = False
            
            for attempt in range(5):  # 최대 5번 시도
                try:
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 시도 {attempt + 1}/5")
                    
                    # 페이지 생성 (Playwright 기본 동작 사용)
                    page = context.new_page()
                    page_created = True
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 완료")
                    break
                except Exception as e:
                    logger.warning(f"[{user_id}] [{action_name}] 페이지 생성 시도 {attempt + 1}/5 실패: {e}")
                    if attempt < 4:  # 마지막 시도가 아니면 대기 후 재시도
                        logger.info(f"[{user_id}] [{action_name}] 3초 대기 후 재시도...")
                        time.sleep(3)
                        
                        # 컨텍스트를 새로 만들어서 재시도
                        if attempt >= 2:  # 3번째 시도부터는 컨텍스트 재생성
                            try:
                                logger.info(f"[{user_id}] [{action_name}] 컨텍스트 재생성 시도")
                                context.close()
                                context = browser.new_context(
                                    viewport={'width': 1920, 'height': 1080},
                                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                    locale='ko-KR',
                                    timezone_id='Asia/Seoul',
                                    proxy=PROXY_CONFIG
                                )
                                context.set_default_timeout(600000)
                                context.set_default_navigation_timeout(600000)
                                logger.info(f"[{user_id}] [{action_name}] 컨텍스트 재생성 완료")
                            except Exception as ctx_err:
                                logger.warning(f"[{user_id}] [{action_name}] 컨텍스트 재생성 실패: {ctx_err}")
                        continue
                    else:
                        raise Exception(f"페이지 생성 최대 재시도 횟수 초과: {e}")
            
            if not page_created:
                raise Exception("페이지 생성에 실패했습니다")
            
            try:
                # 로그인
                logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 시작...")
                page.goto(LOGIN_URL, timeout=600000, wait_until="load")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 완료")
                
                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 시작...")
                page.fill("#userId", user_id)
                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 완료")
                
                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 시작...")
                page.fill("#password", password)
                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 완료")
                
                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 시작...")
                page.click("button[type=submit]")
                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 완료")
                
                # 로그인 완료 대기
                logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 대기 중...")
                
                # 메인 페이지 이동 대기 (Playwright 자체 타임아웃 사용)
                try:
                    page.wait_for_url("**/homGwMain", timeout=120000)  # 120초 타임아웃
                    logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 완료")
                except Exception as e:
                    logger.error(f"[{user_id}] [{action_name}] 메인 페이지 이동 타임아웃: {e}")
                    raise e
                
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 상태 대기 중...")
                page.wait_for_load_state("load", timeout=600000)
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 완료")
                
                logger.info(f"[{user_id}] [{action_name}] 로그인 성공")
                
            except Exception as e:
                logger.error(f"[{user_id}] [{action_name}] 로그인 중 오류 발생: {e}")
                raise

            # 페이지 완전 로드 대기
            time.sleep(3)
            
            # 모든 팝업 닫기
            close_all_popups(page, user_id, action_name)
            time.sleep(2)

            # 근태 관리 테이블 로드 대기
            try:
                page.wait_for_selector("table", timeout=45000)
                page.wait_for_selector("td#ptlAttendRegist_punch_in", timeout=45000)
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

def process_users():
    for u in USERS:
        uid = u["user_id"]
        pwd = u["password"]
        logger.info(f"=== 사용자 처리 시작: {uid}, 작업: punch_out ===")
        try:
            delay = random.randint(0, 60)
            logger.info(f"[{uid}] [punch_out] 랜덤 딜레이: {delay}s")
            time.sleep(delay)
            login_and_click_button(uid, pwd, PUNCH_OUT_BUTTON_IDS, "punch_out")
        except Exception as e:
            if "이미 처리 완료" in str(e):
                logger.info(f"[{uid}] [punch_out] {e}")
            else:
                logger.error(f"[{uid}] [punch_out] 처리 중 오류: {e}")
        logger.info(f"=== {uid} 처리 완료 ===\n")

def main():
    logger.info("=" * 50)
    logger.info("퇴근 처리 전용 스크립트 시작")
    logger.info("===== 퇴근 처리 시작 =====")
    process_users()
    logger.info("===== 퇴근 처리 완료 =====")

if __name__ == '__main__':
    main()