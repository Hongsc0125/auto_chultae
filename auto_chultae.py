import os
import sys
import time
import random
import logging
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from db_manager import db_manager

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
def update_heartbeat(stage="unknown", user_id=None, action=None, attendance_log_id=None):
    """하트비트 업데이트 - heartbeat_status 테이블에 저장"""
    try:
        # heartbeat_status 테이블에 저장
        session = db_manager.get_session()
        try:
            from sqlalchemy import text
            from datetime import datetime
            import os

            session.execute(
                text("""
                    INSERT INTO heartbeat_status
                    (stage, user_id, action_type, pid, timestamp, attendance_log_id)
                    VALUES (:stage, :user_id, :action_type, :pid, :timestamp, :attendance_log_id)
                """),
                {
                    "stage": stage,
                    "user_id": user_id,
                    "action_type": action,
                    "pid": os.getpid(),
                    "timestamp": datetime.now(),
                    "attendance_log_id": attendance_log_id
                }
            )
            session.commit()

            # 상세 로그
            if user_id and action:
                logger.debug(f"💓 HEARTBEAT: [{user_id}] [{action}] {stage}")
            else:
                logger.debug(f"💓 HEARTBEAT: {stage}")

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    except Exception as e:
        logger.warning(f"하트비트 업데이트 실패: {e}")

# 사용자 계정 정보는 데이터베이스에서 동적으로 로드
def get_users():
    """데이터베이스에서 활성 사용자 목록 조회"""
    try:
        return db_manager.get_active_users()
    except Exception as e:
        logger.error(f"사용자 목록 조회 실패: {e}")
        return []

def create_attendance_record(user_id, action_type):
    """출석 기록을 사전에 생성하고 ID 반환"""
    try:
        session = db_manager.get_session()
        try:
            from sqlalchemy import text
            from datetime import datetime

            now = datetime.now()
            result = session.execute(
                text("""
                    INSERT INTO attendance_logs (user_id, action_type, status, attempt_time, created_at)
                    VALUES (:user_id, :action_type, 'in_progress', :attempt_time, :created_at)
                    RETURNING id
                """),
                {
                    "user_id": user_id,
                    "action_type": action_type,
                    "attempt_time": now,
                    "created_at": now
                }
            )
            attendance_id = result.fetchone()[0]
            session.commit()
            return attendance_id
        finally:
            session.close()
    except Exception as e:
        logger.error(f"출석 기록 생성 실패: {e}")
        return None

def update_attendance_record(attendance_id, status, error_message=None):
    """출석 기록 상태 업데이트"""
    try:
        session = db_manager.get_session()
        try:
            from sqlalchemy import text
            from datetime import datetime

            session.execute(
                text("""
                    UPDATE attendance_logs
                    SET status = :status, error_message = :error_message
                    WHERE id = :attendance_id
                """),
                {
                    "attendance_id": attendance_id,
                    "status": status,
                    "error_message": error_message
                }
            )
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"출석 기록 업데이트 실패: {e}")

# 프록시 설정
PROXY_CONFIG = {
    "server": os.getenv("PROXY_SERVER"),
    "username": os.getenv("PROXY_USERNAME"),
    "password": os.getenv("PROXY_PASSWORD")
}

# 상수 정의 - 환경변수에서 로드
LOGIN_URL = os.getenv("LOGIN_URL")
ATTEND_PAGE_URL = os.getenv("ATTEND_PAGE_URL")

if not LOGIN_URL or not ATTEND_PAGE_URL:
    raise ValueError("LOGIN_URL과 ATTEND_PAGE_URL 환경변수가 필수입니다. .env 파일에 설정해주세요.")

# 버튼 셀렉터 - 환경변수에서 로드 (필수)
PUNCH_IN_BUTTON_ID = os.getenv("PUNCH_IN_BUTTON_ID")
PUNCH_OUT_BUTTON_IDS_STR = os.getenv("PUNCH_OUT_BUTTON_IDS")
POPUP_PUNCH_IN_BUTTON_ID = os.getenv("POPUP_PUNCH_IN_BUTTON_ID")
POPUP_PUNCH_OUT_BUTTON_ID = os.getenv("POPUP_PUNCH_OUT_BUTTON_ID")

if not PUNCH_IN_BUTTON_ID:
    raise ValueError("PUNCH_IN_BUTTON_ID 환경변수가 필수입니다.")
if not PUNCH_OUT_BUTTON_IDS_STR:
    raise ValueError("PUNCH_OUT_BUTTON_IDS 환경변수가 필수입니다.")
if not POPUP_PUNCH_IN_BUTTON_ID:
    raise ValueError("POPUP_PUNCH_IN_BUTTON_ID 환경변수가 필수입니다.")
if not POPUP_PUNCH_OUT_BUTTON_ID:
    raise ValueError("POPUP_PUNCH_OUT_BUTTON_ID 환경변수가 필수입니다.")

PUNCH_OUT_BUTTON_IDS = PUNCH_OUT_BUTTON_IDS_STR.split(",")

# 타임아웃 설정 - 환경변수에서 로드 (필수, 밀리초)
DEFAULT_TIMEOUT_STR = os.getenv("DEFAULT_TIMEOUT")
NAVIGATION_TIMEOUT_STR = os.getenv("NAVIGATION_TIMEOUT")
PAGE_LOAD_TIMEOUT_STR = os.getenv("PAGE_LOAD_TIMEOUT")
POPUP_CHECK_TIMEOUT_STR = os.getenv("POPUP_CHECK_TIMEOUT")

if not DEFAULT_TIMEOUT_STR:
    raise ValueError("DEFAULT_TIMEOUT 환경변수가 필수입니다.")
if not NAVIGATION_TIMEOUT_STR:
    raise ValueError("NAVIGATION_TIMEOUT 환경변수가 필수입니다.")
if not PAGE_LOAD_TIMEOUT_STR:
    raise ValueError("PAGE_LOAD_TIMEOUT 환경변수가 필수입니다.")
if not POPUP_CHECK_TIMEOUT_STR:
    raise ValueError("POPUP_CHECK_TIMEOUT 환경변수가 필수입니다.")

DEFAULT_TIMEOUT = int(DEFAULT_TIMEOUT_STR)
NAVIGATION_TIMEOUT = int(NAVIGATION_TIMEOUT_STR)
PAGE_LOAD_TIMEOUT = int(PAGE_LOAD_TIMEOUT_STR)
POPUP_CHECK_TIMEOUT = int(POPUP_CHECK_TIMEOUT_STR)

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

def check_punch_in_completed(page, user_id, action_name, attendance_log_id=None):
    """출근 완료 상태 확인 함수 - button_click_start 내부 로직과 동일"""
    try:
        update_heartbeat("checking_punch_in_status", user_id, action_name, attendance_log_id)
        logger.info(f"[{user_id}] [{action_name}] 출근 완료 상태 확인 중...")

        # JavaScript로 출근 완료 상태 확인 (788-833행 로직과 동일)
        completion_status = page.evaluate("""() => {
            const selectors = [
                '#ptlAttendRegist_punch_in',
                '#ptlAttendRegist_time2 .div_punch',
                'td#ptlAttendRegist_punch_in',
                '#ptlAttendRegist_punch_in .div_punch',
                'div.div_punch'
            ];

            for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (!el) {
                    continue;
                }

                // 1. class에 'complete'가 있는지 확인
                if (el.classList && el.classList.contains('complete')) {
                    if (el.id && el.id.includes('punch_in')) {
                        return '출근완료';
                    }
                }

                // 2. textContent에 '완료'가 포함되어 있는지 확인
                if (el.textContent) {
                    const text = el.textContent.trim();
                    if (text.includes('완료')) {
                        return text;
                    }
                }
            }

            return null;
        }""")

        if completion_status:
            logger.info(f"[{user_id}] [{action_name}] ✅ 출근이 이미 완료되어 있습니다! (상태: {completion_status})")
            update_heartbeat("punch_in_already_completed", user_id, action_name, attendance_log_id)
            return True

        logger.info(f"[{user_id}] [{action_name}] 출근 완료 표시를 찾지 못했거나 아직 완료되지 않음")
        update_heartbeat("punch_in_not_completed_yet", user_id, action_name, attendance_log_id)
        return False

    except Exception as e:
        logger.warning(f"[{user_id}] [{action_name}] 출근 완료 상태 확인 실패: {e}")
        update_heartbeat("punch_in_status_check_failed", user_id, action_name, attendance_log_id)
        return False

def check_punch_out_completed(page, user_id, action_name, attendance_log_id=None):
    """퇴근 완료 상태 확인 함수 - button_click_start 내부 로직과 동일"""
    try:
        update_heartbeat("checking_punch_out_status", user_id, action_name, attendance_log_id)
        logger.info(f"[{user_id}] [{action_name}] 퇴근 완료 상태 확인 중...")

        # JavaScript로 퇴근 완료 상태 확인 (788-833행 로직과 동일)
        completion_status = page.evaluate("""() => {
            const selectors = [
                '#ptlAttendRegist_punch_out',
                '#ptlAttendRegist_time3 .div_punch',
                'button[class*="btn_punch_on"][id*="ptlAttendRegist_btn_lvof2"]',
                '#ptlAttendRegist_punch_out .div_punch',
                '#ptlAttendRegist_time3 .btn_punch_on',
                'div.div_punch'
            ];

            for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (!el) {
                    continue;
                }

                // 1. class에 'complete'가 있는지 확인
                if (el.classList && el.classList.contains('complete')) {
                    if (el.id && el.id.includes('punch_out')) {
                        return '퇴근완료';
                    }
                }

                // 2. textContent에 '완료'가 포함되어 있는지 확인
                if (el.textContent) {
                    const text = el.textContent.trim();
                    if (text.includes('완료')) {
                        return text;
                    }
                }
            }

            return null;
        }""")

        if completion_status:
            logger.info(f"[{user_id}] [{action_name}] ✅ 퇴근이 이미 완료되어 있습니다! (상태: {completion_status})")
            update_heartbeat("punch_out_already_completed", user_id, action_name, attendance_log_id)
            return True

        logger.info(f"[{user_id}] [{action_name}] 퇴근 완료 표시를 찾지 못했거나 아직 완료되지 않음")
        update_heartbeat("punch_out_not_completed_yet", user_id, action_name, attendance_log_id)
        return False

    except Exception as e:
        logger.warning(f"[{user_id}] [{action_name}] 퇴근 완료 상태 확인 실패: {e}")
        update_heartbeat("punch_out_status_check_failed", user_id, action_name, attendance_log_id)
        return False

def wait_and_click_button(page, button_selector, user_id, action_name, max_attempts=5):
    """버튼 클릭을 재시도하는 함수 - 날짜 선택 팝업 우선 확인"""

    # Step 1: 먼저 날짜 선택 팝업 버튼이 있는지 확인
    logger.info(f"[{user_id}] [{action_name}] 1단계: 날짜 선택 팝업 버튼 확인 중...")

    try:
        # 출근인 경우 팝업 출근 버튼 확인
        if action_name == "punch_in":
            popup_button = POPUP_PUNCH_IN_BUTTON_ID
            button_name = "출근"
        else:
            popup_button = POPUP_PUNCH_OUT_BUTTON_ID
            button_name = "퇴근"

        # 날짜 선택 팝업 버튼이 있는지 확인
        if page.is_visible(popup_button, timeout=POPUP_CHECK_TIMEOUT):
            logger.info(f"[{user_id}] [{action_name}] 날짜 선택 팝업 {button_name} 버튼 발견: {popup_button}")

            # 팝업 버튼 클릭 시도
            success = page.evaluate(f"""() => {{
                const btn = document.querySelector('{popup_button}');
                if (btn && !btn.disabled) {{
                    btn.click();
                    return true;
                }}
                return false;
            }}""")

            if success:
                logger.info(f"[{user_id}] [{action_name}] 날짜 선택 팝업 {button_name} 버튼 클릭 성공!")

                # 팝업 버튼 클릭 후 잠시 대기 후 기본 출근/퇴근 버튼 클릭 시도
                time.sleep(2)
                logger.info(f"[{user_id}] [{action_name}] 팝업 클릭 후 기본 {button_name} 버튼 찾는 중...")

                # 이제 기본 버튼이 나타났는지 확인하고 클릭
                for attempt in range(3):
                    try:
                        if page.is_visible(button_selector, timeout=5000):
                            # 기본 버튼 클릭 시도
                            basic_success = page.evaluate(f"""() => {{
                                const btn = document.querySelector('{button_selector}');
                                if (btn && !btn.disabled) {{
                                    btn.click();
                                    return true;
                                }}
                                return false;
                            }}""")

                            if basic_success:
                                logger.info(f"[{user_id}] [{action_name}] 팝업 후 기본 {button_name} 버튼 클릭 성공!")
                                return True
                            else:
                                # Playwright 클릭 시도
                                page.click(button_selector, timeout=5000, force=True)
                                logger.info(f"[{user_id}] [{action_name}] 팝업 후 기본 {button_name} 버튼 클릭 성공! (Playwright)")
                                return True
                        else:
                            logger.info(f"[{user_id}] [{action_name}] 팝업 클릭 후 기본 버튼 대기 중... ({attempt+1}/3)")
                            time.sleep(1)
                    except Exception as basic_error:
                        logger.warning(f"[{user_id}] [{action_name}] 팝업 후 기본 버튼 클릭 실패 시도 {attempt+1}: {basic_error}")
                        time.sleep(1)

                logger.warning(f"[{user_id}] [{action_name}] 팝업 클릭 후 기본 버튼을 찾을 수 없음")
                return False
            else:
                # 일반 클릭 시도
                page.click(popup_button, timeout=5000, force=True)
                logger.info(f"[{user_id}] [{action_name}] 날짜 선택 팝업 {button_name} 버튼 클릭 성공! (Playwright)")
                time.sleep(2)
                return True
        else:
            logger.info(f"[{user_id}] [{action_name}] 날짜 선택 팝업 버튼 없음, 기본 버튼으로 진행")

    except Exception as popup_error:
        logger.warning(f"[{user_id}] [{action_name}] 날짜 선택 팝업 버튼 확인 실패: {popup_error}")

    # Step 2: 날짜 선택 팝업이 없으면 기본 출근/퇴근 버튼 클릭 시도
    logger.info(f"[{user_id}] [{action_name}] 2단계: 기본 버튼 클릭 시도")

    for attempt in range(max_attempts):
        try:
            logger.info(f"[{user_id}] [{action_name}] 기본 버튼 클릭 시도 {attempt + 1}/{max_attempts}: {button_selector}")

            # 팝업 재정리
            if attempt > 0:
                close_all_popups(page, user_id, action_name)
                time.sleep(1)

            # 버튼이 존재하는지 확인
            page.wait_for_selector(button_selector, timeout=DEFAULT_TIMEOUT, state="attached")

            # 버튼이 보이는지 확인
            if not page.is_visible(button_selector, timeout=15000):
                logger.warning(f"[{user_id}] [{action_name}] 기본 버튼이 보이지 않음: {button_selector}")
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
                logger.info(f"[{user_id}] [{action_name}] 기본 버튼 클릭 성공 (JavaScript): {button_selector}")
                return True
            else:
                # 일반 클릭 시도
                page.click(button_selector, timeout=15000, force=True)
                logger.info(f"[{user_id}] [{action_name}] 기본 버튼 클릭 성공 (Playwright): {button_selector}")
                return True

        except Exception as e:
            logger.warning(f"[{user_id}] [{action_name}] 기본 버튼 클릭 실패 시도 {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(2)
            continue

    return False

def login_and_click_button(user_id, password, button_ids, action_name, attendance_log_id=None):
    start_time = time.time()
    logger.info(f"[{user_id}] [{action_name}] 프로세스 시작")

    # 로컬 하트비트 함수 (attendance_log_id가 자동으로 포함됨)
    def heartbeat(stage):
        update_heartbeat(stage, user_id, action_name, attendance_log_id)

    # 시작 하트비트
    heartbeat("process_start")
    
    browser = None
    context = None
    
    try:
        with sync_playwright() as p:
            logger.info(f"[{user_id}] [{action_name}] Playwright 초기화 완료")

            # Playwright 초기화 하트비트
            heartbeat("playwright_init")

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
            heartbeat("browser_started")

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
            heartbeat("context_created")

            # 컨텍스트 타임아웃 설정 (짧게)
            context.set_default_timeout(DEFAULT_TIMEOUT)
            context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

            logger.info(f"[{user_id}] [{action_name}] 새 페이지 생성...")

            # 페이지 생성 시작 하트비트
            heartbeat("page_creation_start")

            # 페이지 생성 재시도 (최대 3번)
            page = None
            max_attempts = 3

            for attempt in range(max_attempts):
                try:
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 시도 {attempt + 1}/{max_attempts}")

                    # 페이지 생성 시도 하트비트
                    heartbeat(f"page_creation_attempt_{attempt + 1}")

                    page = context.new_page()
                    logger.info(f"[{user_id}] [{action_name}] 페이지 생성 완료")

                    # 페이지 생성 성공 하트비트
                    heartbeat("page_created")
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
                heartbeat("login_start")

                # 로그인
                logger.info(f"[{user_id}] [{action_name}] 로그인 페이지로 이동: {LOGIN_URL}")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 시작...")

                # 페이지 이동 하트비트
                heartbeat("page_navigation")

                page.goto(LOGIN_URL, timeout=PAGE_LOAD_TIMEOUT, wait_until="load")
                logger.info(f"[{user_id}] [{action_name}] 페이지 이동 완료")

                # 페이지 이동 완료 하트비트
                heartbeat("page_loaded")

                # 로그인 폼 요소들이 로드될 때까지 대기
                logger.info(f"[{user_id}] [{action_name}] 로그인 폼 로드 대기 중...")

                try:
                    page.wait_for_selector("#userId", timeout=NAVIGATION_TIMEOUT)
                    page.wait_for_selector("#password", timeout=DEFAULT_TIMEOUT)
                    page.wait_for_selector("button[type=submit]", timeout=DEFAULT_TIMEOUT)
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
                heartbeat("login_form_loaded")

                # 추가 안정화 대기
                time.sleep(2)

                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 시작...")
                page.fill("#userId", user_id)
                logger.info(f"[{user_id}] [{action_name}] 아이디 입력 완료")

                # 아이디 입력 완료 하트비트
                heartbeat("userid_filled")

                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 시작...")
                page.fill("#password", password)
                logger.info(f"[{user_id}] [{action_name}] 비밀번호 입력 완료")

                # 비밀번호 입력 완료 하트비트
                heartbeat("password_filled")

                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 시작...")

                # 로그인 버튼 클릭 시작 하트비트
                heartbeat("login_button_click")

                page.click("button[type=submit]")
                logger.info(f"[{user_id}] [{action_name}] 로그인 버튼 클릭 완료")
                
                # 로그인 완료 대기
                logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 대기 중...")

                # 메인 페이지 이동 대기 시작 하트비트
                heartbeat("main_page_wait")

                # 메인 페이지 이동 대기 (Playwright 자체 타임아웃 사용)
                try:
                    page.wait_for_url("**/homGwMain", timeout=120000)  # 120초 타임아웃
                    logger.info(f"[{user_id}] [{action_name}] 메인 페이지 이동 완료")

                    # 메인 페이지 이동 완료 하트비트
                    heartbeat("main_page_loaded")

                except Exception as e:
                    logger.error(f"[{user_id}] [{action_name}] 메인 페이지 이동 타임아웃: {e}")
                    raise e
                
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 상태 대기 중...")

                # 페이지 로드 상태 대기 하트비트
                heartbeat("page_load_wait")

                page.wait_for_load_state("load", timeout=PAGE_LOAD_TIMEOUT)
                logger.info(f"[{user_id}] [{action_name}] 페이지 로드 완료")

                # 페이지 로드 완료 하트비트
                heartbeat("page_load_complete")

                logger.info(f"[{user_id}] [{action_name}] 로그인 성공")

                # 로그인 성공 하트비트
                heartbeat("login_success")
                
            except Exception as e:
                logger.error(f"[{user_id}] [{action_name}] 로그인 중 오류 발생: {e}")
                raise

            # 페이지 완전 로드 대기
            heartbeat("page_stabilize_wait")
            time.sleep(3)

            # 출근의 경우 먼저 완료 상태 확인
            if action_name == "punch_in":
                if check_punch_in_completed(page, user_id, action_name, attendance_log_id):
                    logger.info(f"[{user_id}] [{action_name}] ✅ 출근이 이미 완료되어 있어 작업을 종료합니다")
                    heartbeat("process_complete")
                    return True

            # 퇴근의 경우 먼저 완료 상태 확인
            if action_name == "punch_out":
                if check_punch_out_completed(page, user_id, action_name, attendance_log_id):
                    logger.info(f"[{user_id}] [{action_name}] ✅ 퇴근이 이미 완료되어 있어 작업을 종료합니다")
                    heartbeat("process_complete")
                    return True

            # 모든 팝업 닫기
            heartbeat("popup_close_start")
            close_all_popups(page, user_id, action_name)
            time.sleep(2)
            heartbeat("popup_close_complete")

            # 바로 버튼 클릭 시도 (테이블 로드 대기 제거)
            heartbeat("button_click_start")
            clicked = False
            for btn in button_ids:
                if wait_and_click_button(page, btn, user_id, action_name):
                    clicked = True

                    # 버튼 클릭 후 출근 완료 상태 재확인
                    if action_name == "punch_in":
                        time.sleep(2)  # 상태 변경 대기
                        if check_punch_in_completed(page, user_id, action_name, attendance_log_id):
                            logger.info(f"[{user_id}] [{action_name}] ✅ 버튼 클릭 후 출근 완료 확인됨")
                            heartbeat("button_clicked_success")
                            heartbeat("process_complete")
                            return True
                        else:
                            # 출근 완료가 확인되지 않으면 실패 처리
                            logger.error(f"[{user_id}] [{action_name}] ❌ 버튼 클릭 후 출근 완료 확인 실패")

                            # 스크린샷 저장
                            os.makedirs("screenshots", exist_ok=True)
                            path = f"screenshots/punch_in_verify_failed_{user_id}_{int(time.time())}.png"
                            page.screenshot(path=path, full_page=True)
                            logger.error(f"[{user_id}] [{action_name}] 검증 실패 스크린샷 저장: {path}")

                            # 페이지 HTML도 저장
                            html_path = f"screenshots/punch_in_verify_failed_{user_id}_{int(time.time())}.html"
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(page.content())
                            logger.error(f"[{user_id}] [{action_name}] 페이지 HTML 저장: {html_path}")

                            raise Exception("출근 버튼 클릭 후 출근 완료 상태가 확인되지 않음")

                    # 버튼 클릭 후 퇴근 완료 상태 재확인
                    if action_name == "punch_out":
                        time.sleep(2)  # 상태 변경 대기
                        if check_punch_out_completed(page, user_id, action_name, attendance_log_id):
                            logger.info(f"[{user_id}] [{action_name}] ✅ 버튼 클릭 후 퇴근 완료 확인됨")
                            heartbeat("button_clicked_success")
                            heartbeat("process_complete")
                            return True
                        else:
                            # 퇴근 완료가 확인되지 않으면 실패 처리
                            logger.error(f"[{user_id}] [{action_name}] ❌ 버튼 클릭 후 퇴근 완료 확인 실패")

                            # 스크린샷 저장
                            os.makedirs("screenshots", exist_ok=True)
                            path = f"screenshots/punch_out_verify_failed_{user_id}_{int(time.time())}.png"
                            page.screenshot(path=path, full_page=True)
                            logger.error(f"[{user_id}] [{action_name}] 검증 실패 스크린샷 저장: {path}")

                            # 페이지 HTML도 저장
                            html_path = f"screenshots/punch_out_verify_failed_{user_id}_{int(time.time())}.html"
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(page.content())
                            logger.error(f"[{user_id}] [{action_name}] 페이지 HTML 저장: {html_path}")

                            raise Exception("퇴근 버튼 클릭 후 퇴근 완료 상태가 확인되지 않음")

                    break

            if not clicked:
                # 마지막으로 이미 처리된 상태인지 다시 확인
                # 출근완료/퇴근완료 상태 확인
                try:
                    completion_status = page.evaluate("""() => {
                        const selectors = [
                            '#ptlAttendRegist_punch_in',
                            '#ptlAttendRegist_punch_out',
                            '#ptlAttendRegist_time2 .div_punch',
                            '#ptlAttendRegist_time3 .div_punch',
                            'div.div_punch',
                            '.attendance-complete'
                        ];

                        for (const selector of selectors) {
                            const el = document.querySelector(selector);
                            if (!el) {
                                continue;
                            }

                            if (el.classList && el.classList.contains('complete')) {
                                if (el.id && el.id.includes('punch_in')) {
                                    return '출근완료';
                                }
                                if (el.id && el.id.includes('punch_out')) {
                                    return '퇴근완료';
                                }
                            }

                            if (el.textContent) {
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
            heartbeat("button_clicked_success")
            time.sleep(3)

            # 완료 시 하트비트 업데이트
            heartbeat("process_complete")

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

# 크롤링 전용 모듈 - 시그널 핸들러 불필요 (워치독에서 관리)

def process_users(button_ids, action_name):
    """사용자 처리 함수 (단순 실행)"""
    users = get_users()
    if not users:
        logger.error("활성 사용자를 찾을 수 없습니다")
        return

    for user_info in users:
        user_id = user_info["user_id"]
        password = user_info["password"]

        logger.info(f"=== 사용자 처리 시작: {user_id}, 작업: {action_name} ===")

        # 스케줄 체크: 오늘이 출근일인지 확인
        is_workday = db_manager.is_workday_scheduled(user_id)
        if not is_workday:
            logger.info(f"[{user_id}] [{action_name}] 오늘은 휴무일로 스케줄되어 있음 - 스킵")
            continue

        # 사전 체크: 이미 오늘 성공한 기록이 있는지 확인
        has_success_today = db_manager.has_today_success(user_id, action_name)
        if has_success_today:
            logger.info(f"[{user_id}] [{action_name}] 오늘자 성공 이력 있음 - 스킵 (attendance_log 생성 안함)")
            continue

        # 출석 기록 사전 생성 (체크 통과한 경우만)
        attendance_id = create_attendance_record(user_id, action_name)
        if not attendance_id:
            logger.error(f"[{user_id}] [{action_name}] 출석 기록 생성 실패")
            continue

        try:
            delay = random.randint(0, 60)
            logger.info(f"[{user_id}] [{action_name}] 랜덤 딜레이: {delay}s")
            time.sleep(delay)

            login_and_click_button(user_id, password, button_ids, action_name, attendance_id)
            logger.info(f"[{user_id}] [{action_name}] 성공")
            # 성공으로 상태 업데이트
            update_attendance_record(attendance_id, "success")

        except Exception as e:
            if "이미 출근 완료" in str(e) or "이미 처리 완료" in str(e) or "이미" in str(e):
                logger.info(f"[{user_id}] [{action_name}] {e}")
                # 이미 완료된 상태로 업데이트
                update_attendance_record(attendance_id, "already_done", str(e))
            else:
                logger.error(f"[{user_id}] [{action_name}] 처리 중 오류: {e}")

                # 스크린샷과 HTML 경로 추출 (에러 메시지에서)
                screenshot_path = None
                html_path = None
                error_msg = str(e)

                # 간단한 경로 추출 (개선 가능)
                if "screenshots/" in error_msg:
                    lines = error_msg.split('\n')
                    for line in lines:
                        if "screenshots/" in line and line.endswith(".png"):
                            screenshot_path = line.split(":")[-1].strip()
                        elif "screenshots/" in line and line.endswith(".html"):
                            html_path = line.split(":")[-1].strip()

                # 실패로 상태 업데이트
                update_attendance_record(attendance_id, "failed", error_msg)

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

# 이 파일은 크롤링 함수만 제공합니다.
# 실행은 워치독(watchdog.py)에서 관리됩니다.
#
# 직접 테스트 실행:
# python -c "from auto_chultae import punch_in, punch_out; punch_in()"
# python -c "from auto_chultae import punch_in, punch_out; punch_out()"

if __name__ == '__main__':
    # 직접 실행 시에만 DB 연결 및 테스트 실행
    logger.info("=" * 50)
    logger.info("Auto Chultae 크롤링 시스템 직접 실행")

    if not db_manager.test_connection():
        logger.warning("데이터베이스 연결 실패! 로그는 DB에 저장되지 않습니다.")

    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "punch_in":
            punch_in()
        elif sys.argv[1] == "punch_out":
            punch_out()
        else:
            print("사용법: python auto_chultae.py [punch_in|punch_out]")
    else:
        print("사용법: python auto_chultae.py [punch_in|punch_out]")
        print("또는: python -c \"from auto_chultae import punch_in; punch_in()\"")