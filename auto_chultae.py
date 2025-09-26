import os
import sys
import time
import random
import logging
import signal
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# .env 파일 로드
load_dotenv()


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

# 하트비트 함수
def update_heartbeat(stage="unknown", user_id=None, action=None):
    """워치독을 위한 하트비트 파일 업데이트"""
    try:
        timestamp = datetime.now().isoformat()
        heartbeat_data = {
            "timestamp": timestamp,
            "stage": stage,
            "user_id": user_id,
            "action": action,
            "pid": os.getpid()
        }

        with open("heartbeat.txt", "w") as f:
            import json
            f.write(json.dumps(heartbeat_data, ensure_ascii=False) + "\n")

        # 상세 로그
        if user_id and action:
            logger.info(f"💓 HEARTBEAT: [{user_id}] [{action}] {stage}")
        else:
            logger.info(f"💓 HEARTBEAT: {stage}")

    except Exception as e:
        logger.warning(f"하트비트 업데이트 실패: {e}")

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

    # 시작 하트비트
    update_heartbeat("process_start", user_id, action_name)
    
    browser = None
    context = None
    
    try:
        with sync_playwright() as p:
            logger.info(f"[{user_id}] [{action_name}] Playwright 초기화 완료")

            # Playwright 초기화 하트비트
            update_heartbeat("playwright_init", user_id, action_name)

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

            # 브라우저 실행 완료 하트비트
            update_heartbeat("browser_started", user_id, action_name)

            logger.info(f"[{user_id}] [{action_name}] 브라우저 컨텍스트 생성 시작...")
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                proxy=PROXY_CONFIG
            )
            logger.info(f"[{user_id}] [{action_name}] 브라우저 컨텍스트 생성 완료")

            # 컨텍스트 생성 완료 하트비트
            update_heartbeat("context_created", user_id, action_name)

            # 컨텍스트 타임아웃 설정 (짧게)
            context.set_default_timeout(30000)  # 30초 타임아웃
            context.set_default_navigation_timeout(60000)  # 네비게이션 60초 타임아웃

            logger.info(f"[{user_id}] [{action_name}] 새 페이지 생성...")

            # 페이지 생성 시작 하트비트
            update_heartbeat("page_creation_start", user_id, action_name)

            # 페이지 생성 재시도 (최대 3번)
            page = None
            max_attempts = 3

            for attempt in range(max_attempts):
                try:
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 시도 {attempt + 1}/{max_attempts}")

                    # 페이지 생성 시도 하트비트
                    update_heartbeat(f"page_creation_attempt_{attempt + 1}", user_id, action_name)

                    page = context.new_page()
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 완료")

                    # 페이지 생성 성공 하트비트
                    update_heartbeat("page_created", user_id, action_name)
                    break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        logger.warning(f"[{user_id}] [{action_name}] 페이지 생성 실패: {e}, 2초 후 재시도...")
                        time.sleep(2)
                        continue
                    else:
                        logger.error(f"[{user_id}] [{action_name}] 모든 페이지 생성 시도 실패: {e}")
                        raise e

            if not page:
                raise Exception("페이지 생성에 실패했습니다")
            
            try:
                # 로그인 시작 하트비트
                update_heartbeat("login_start", user_id, action_name)

                # 로그인
                logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 시작...")

                # 페이지 이동 하트비트
                update_heartbeat("page_navigation", user_id, action_name)

                page.goto(LOGIN_URL, timeout=600000, wait_until="load")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 완료")

                # 페이지 이동 완료 하트비트
                update_heartbeat("page_loaded", user_id, action_name)

                # 로그인 폼 요소들이 로드될 때까지 대기
                logger.info(f"[{user_id}] [{action_name}] 로그인 폼 로드 대기 중...")

                try:
                    page.wait_for_selector("#userId", timeout=60000)  # 60초 대기
                    page.wait_for_selector("#password", timeout=30000)  # 30초 대기
                    page.wait_for_selector("button[type=submit]", timeout=30000)  # 30초 대기
                    logger.info(f"[{user_id}] [{action_name}] 로그인 폼 로드 완료")
                except Exception as selector_error:
                    # 로그인 폼 로드 실패 시 디버깅 정보 수집
                    logger.error(f"[{user_id}] [{action_name}] 로그인 폼 로드 실패: {selector_error}")

                    # 현재 페이지 URL과 제목 확인
                    current_url = page.url
                    page_title = page.title()
                    logger.error(f"[{user_id}] [{action_name}] 현재 URL: {current_url}")
                    logger.error(f"[{user_id}] [{action_name}] 페이지 제목: {page_title}")

                    # 디버깅용 스크린샷 저장
                    os.makedirs("screenshots", exist_ok=True)
                    debug_path = f"screenshots/login_form_error_{user_id}_{int(time.time())}.png"
                    page.screenshot(path=debug_path, full_page=True)
                    logger.error(f"[{user_id}] [{action_name}] 디버깅 스크린샷 저장: {debug_path}")

                    # HTML 내용도 저장
                    html_debug_path = f"screenshots/login_form_error_{user_id}_{int(time.time())}.html"
                    with open(html_debug_path, 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    logger.error(f"[{user_id}] [{action_name}] HTML 내용 저장: {html_debug_path}")

                    raise selector_error

                # 폼 로드 완료 하트비트
                update_heartbeat("login_form_loaded", user_id, action_name)

                # 추가 안정화 대기
                time.sleep(2)

                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 시작...")
                page.fill("#userId", user_id)
                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 완료")

                # 아이디 입력 완료 하트비트
                update_heartbeat("userid_filled", user_id, action_name)

                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 시작...")
                page.fill("#password", password)
                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 완료")

                # 비밀번호 입력 완료 하트비트
                update_heartbeat("password_filled", user_id, action_name)

                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 시작...")

                # 로그인 버튼 클릭 시작 하트비트
                update_heartbeat("login_button_click", user_id, action_name)

                page.click("button[type=submit]")
                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 완료")
                
                # 로그인 완료 대기
                logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 대기 중...")

                # 메인 페이지 이동 대기 시작 하트비트
                update_heartbeat("main_page_wait", user_id, action_name)

                # 메인 페이지 이동 대기 (Playwright 자체 타임아웃 사용)
                try:
                    page.wait_for_url("**/homGwMain", timeout=120000)  # 120초 타임아웃
                    logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 완료")

                    # 메인 페이지 이동 완료 하트비트
                    update_heartbeat("main_page_loaded", user_id, action_name)

                except Exception as e:
                    logger.error(f"[{user_id}] [{action_name}] 메인 페이지 이동 타임아웃: {e}")
                    raise e
                
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 상태 대기 중...")

                # 페이지 로드 상태 대기 하트비트
                update_heartbeat("page_load_wait", user_id, action_name)

                page.wait_for_load_state("load", timeout=600000)
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 완료")

                # 페이지 로드 완료 하트비트
                update_heartbeat("page_load_complete", user_id, action_name)

                logger.info(f"[{user_id}] [{action_name}] 로그인 성공")

                # 로그인 성공 하트비트
                update_heartbeat("login_success", user_id, action_name)
                
            except Exception as e:
                logger.error(f"[{user_id}] [{action_name}] 로그인 중 오류 발생: {e}")
                raise

            # 페이지 완전 로드 대기
            update_heartbeat("page_stabilize_wait", user_id, action_name)
            time.sleep(3)

            # 모든 팝업 닫기
            update_heartbeat("popup_close_start", user_id, action_name)
            close_all_popups(page, user_id, action_name)
            time.sleep(2)
            update_heartbeat("popup_close_complete", user_id, action_name)

            # 바로 버튼 클릭 시도 (테이블 로드 대기 제거)
            update_heartbeat("button_click_start", user_id, action_name)
            clicked = False
            for btn in button_ids:
                if wait_and_click_button(page, btn, user_id, action_name):
                    clicked = True
                    break

            if not clicked:
                # 마지막으로 이미 처리된 상태인지 다시 확인
                # 출근완료/퇴근완료 상태 확인
                try:
                    completion_status = page.evaluate("""() => {
                        // div.div_punch에서 "출근완료" 또는 "퇴근완료" 텍스트 확인
                        const punchDiv = document.querySelector('div.div_punch');
                        if (punchDiv) {
                            const text = punchDiv.textContent.trim();
                            if (text === '출근완료' || text === '퇴근완료') {
                                return text;
                            }
                        }

                        // 추가적인 완료 상태 확인
                        const indicators = [
                            '#ptlAttendRegist_time2 div.div_punch',
                            'td#ptlAttendRegist_punch_in',
                            '.attendance-complete'
                        ];

                        for (const selector of indicators) {
                            const el = document.querySelector(selector);
                            if (el && el.textContent) {
                                const text = el.textContent.trim();
                                if (text.includes('완료')) {
                                    return text;
                                }
                            }
                        }

                        return null;
                    }""")

                    if completion_status:
                        logger.info(f"[{user_id}] [{action_name}] 이미 {completion_status} 상태임")
                        raise Exception(f"이미 {completion_status}")
                except Exception as e:
                    if "이미" in str(e):
                        raise e

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
            update_heartbeat("button_clicked_success", user_id, action_name)
            time.sleep(3)

            # 완료 시 하트비트 업데이트
            update_heartbeat("process_complete", user_id, action_name)

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

# 종료 시그널 핸들러
def shutdown_handler(signum, frame):
    logging.getLogger('auto_chultae').info("종료 신호를 수신했습니다.")
    sys.exit(0)

def process_users(button_ids, action_name):
    """사용자 처리 함수 (단순 실행)"""
    for user_info in USERS:
        user_id = user_info["user_id"]
        password = user_info["password"]

        logger.info(f"=== 사용자 처리 시작: {user_id}, 작업: {action_name} ===")

        try:
            delay = random.randint(0, 60)
            logger.info(f"[{user_id}] [{action_name}] 랜덤 딜레이: {delay}s")
            time.sleep(delay)

            login_and_click_button(user_id, password, button_ids, action_name)
            logger.info(f"[{user_id}] [{action_name}] 성공")

        except Exception as e:
            if "이미 출근 완료" in str(e) or "이미 처리 완료" in str(e):
                logger.info(f"[{user_id}] [{action_name}] {e}")
            else:
                logger.error(f"[{user_id}] [{action_name}] 처리 중 오류: {e}")

        logger.info(f"=== {user_id} 처리 완료 ===\n")

def punch_in():
    """출근 처리"""
    logger.info("===== 출근 처리 시작 =====")
    process_users([PUNCH_IN_BUTTON_ID], "punch_in")
    logger.info("===== 출근 처리 완료 =====")

def punch_out():
    """퇴근 처리"""
    logger.info("===== 퇴근 처리 시작 =====")
    process_users(PUNCH_OUT_BUTTON_IDS, "punch_out")
    logger.info("===== 퇴근 처리 완료 =====")

def main():
    """크롤링 전용 메인 함수 (직접 호출용)"""

    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("=" * 50)
    logger.info("크롤링 시스템 직접 실행")

    # 초기 하트비트
    update_heartbeat("system_startup")

    logger.info("테스트용 출근 처리 실행")
    punch_in()

    logger.info("테스트용 퇴근 처리 실행")
    punch_out()

    logger.info("크롤링 테스트 완료")

if __name__ == '__main__':
    main()