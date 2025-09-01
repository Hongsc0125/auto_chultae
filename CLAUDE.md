# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an **automated attendance management system** that uses Playwright to automate punch-in/punch-out operations on a company's internal attendance system. The system runs scheduled tasks to automatically handle attendance for multiple user accounts.

## Running the Application

### Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### Start the Attendance System
```bash
python auto_chultae.py
```
The system will:
- Perform an initial punch-in check at startup
- Schedule automated punch-in at 8:00 AM (Monday-Friday)
- Schedule automated punch-out at 6:05 PM (Monday-Friday)

### Environment Configuration
Create a `.env` file with:
```
USERS=user1:password1,user2:password2
LOGIN_URL=https://gw.metabuild.co.kr/ekp/view/login/userLogin
ATTEND_PAGE_URL=https://gw.metabuild.co.kr/ekp/main/home/homGwMain
PROXY_SERVER=optional_proxy_server
PROXY_USERNAME=optional_proxy_username
PROXY_PASSWORD=optional_proxy_password
```

## Core Architecture

### Main Components
- **`auto_chultae.py`** - Main automation script with scheduling and browser automation
- **`requirements.txt`** - Python dependencies (APScheduler, Playwright)

### Key Functions
- **`login_and_click_button()`** - Handles login and button clicking with retry logic
- **`close_all_popups()`** - Aggressive popup handling to clear UI obstructions
- **`wait_and_click_button()`** - Robust button clicking with multiple retry attempts
- **`process_users()`** - Processes multiple user accounts with random delays
- **`punch_in()`** and **`punch_out()`** - Main attendance functions

### Configuration
- **User Accounts**: Defined in `USERS` array with credentials
- **URLs and Selectors**: Company-specific login URL and button selectors
- **Timing**: Korean timezone (Asia/Seoul) for scheduling

### Browser Automation Architecture
- **Playwright with Chromium**: Headless browser automation
- **Popup Management**: Multi-layered popup closing using JavaScript injection
- **Error Handling**: Screenshot and HTML capture on failures
- **Retry Logic**: Multiple attempts for button clicks with exponential backoff

### Logging and Monitoring
- **Daily Log Files**: Stored in `logs/` directory with date-based naming
- **Structured Logging**: Detailed logging with user ID and action tracking
- **Error Screenshots**: Automatic screenshot capture in `screenshots/` directory on failures
- **HTML Dumps**: Page source saved alongside screenshots for debugging

### Scheduling System
- **APScheduler**: Blocking scheduler with thread pool execution
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM
- **Job Configuration**: Coalescing disabled, multiple instances allowed, misfire grace period
- **Korean Timezone**: All scheduling uses Asia/Seoul timezone

### Error Recovery
- **Popup Interference**: Comprehensive popup detection and removal
- **Button Visibility**: JavaScript-based scrolling and visibility checks  
- **Duplicate Action Prevention**: State checking to avoid redundant operations
- **Random Delays**: Anti-detection delays between user processing

## Development Commands

### Debug Mode
To troubleshoot issues, check the following directories:
- `logs/` - Daily log files with timestamp format `auto_chultae_YYYYMMDD.log`
- `screenshots/` - Error screenshots and HTML dumps for failed operations

### Testing Changes
When modifying the automation logic:
1. Test with a single user first by temporarily reducing the `USERS` list
2. Monitor logs for proper login and button detection
3. Check screenshot outputs if automation fails

### Key Configuration Points
- **Button Selectors**: `auto_chultae.py:68-69` defines punch-in/out button selectors
- **URLs**: `auto_chultae.py:66-67` defines login and attendance page URLs  
- **Scheduling**: `auto_chultae.py:405-406` sets punch times (8:00 AM in, 6:05 PM out)
- **Browser Options**: `auto_chultae.py:211-225` configures Playwright browser settings