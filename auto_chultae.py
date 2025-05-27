import os
import time
import random
from apscheduler.schedulers.blocking import BlockingScheduler
from playwright.sync_api import sync_playwright


USER_ID = "hc0125"
PASSWORD = "Wkwkd119!!"

LOGIN_URL = "https://gw.metabuild.co.kr/ekp/view/login/userLogin"
ATTEND_PAGE_URL = "https://gw.metabuild.co.kr/ekp/main/home/homGwMain"
BUTTON_ID = "#ptlAttendRegist_btn_lvof3"


def punch_out():
    try:
        delay = random.randint(0, 300)
        print(f"[punch_out] Waiting for {delay} seconds before punching out...")
        time.sleep(delay)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            page.goto(LOGIN_URL)

            page.fill("#userId", USER_ID)
            page.fill("#password", PASSWORD)
            page.click("button[type=submit]")

            page.wait_for_selector(BUTTON_ID, timeout=20000)

            page.click(BUTTON_ID)
            print("[punch_out] Punch-out button clicked successfully.")

            browser.close()
    except Exception as e:
        print(f"[punch_out] Error occurred: {e}")

# 스캐줄러
def main():
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(punch_out, 'cron', hour=18, minute=5, day_of_week='mon-fri')
    print("[scheduler] Scheduler started. Bot will run weekdays at 18:05 KST.")
    scheduler.start()

if __name__ == '__main__':
    main()
