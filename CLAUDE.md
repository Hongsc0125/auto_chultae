# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an **automated attendance management system** that uses Playwright to automate punch-in/punch-out operations on a company's internal attendance system. The system runs scheduled tasks to automatically handle attendance for multiple user accounts.

## Running the Application

### Install Dependencies
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### Start the Attendance System
```bash
# Start with watchdog (recommended)
./start.sh

# Stop the system
./stop.sh
```

The system will:
- Run watchdog that monitors and manages the main process
- Schedule automated punch-in at 8:00-8:40 AM (Monday-Friday, every 5 minutes)
- Schedule automated punch-out at 6:00-7:00 PM (Monday-Friday, every 5 minutes)
- Store all logs and attendance records in PostgreSQL database

### Environment Configuration
Create a `.env` file with:
```
# 필수 설정 - 반드시 설정해야 함
LOGIN_URL=https://your-company.com/login
ATTEND_PAGE_URL=https://your-company.com/attendance
DATABASE_URL=postgresql://user:password@host:port/database

# 프록시 설정 (선택사항)
PROXY_SERVER=your_proxy_server_url
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password

# 서버 설정
MAIN_SERVER_HOST=127.0.0.1
MAIN_SERVER_PORT=8080
MAIN_SERVER_URL=http://localhost:8080

# 버튼 셀렉터 설정 (기본값 있음, 변경 필요시에만 설정)
# PUNCH_IN_BUTTON_ID=#ptlAttendRegist_btn_attn
# PUNCH_OUT_BUTTON_IDS=#ptlAttendRegist_btn_lvof3,#ptlAttendRegist_btn_lvof2
# POPUP_PUNCH_IN_BUTTON_ID=#ptlAttendRegistLvr_div_lovfWrite_btn_attn
# POPUP_PUNCH_OUT_BUTTON_ID=#ptlAttendRegistLvr_div_lovfWrite_btn_lvof

# 타임아웃 설정 (밀리초, 기본값 있음)
# DEFAULT_TIMEOUT=30000
# NAVIGATION_TIMEOUT=60000
# PAGE_LOAD_TIMEOUT=600000
# POPUP_CHECK_TIMEOUT=3000
```

### 🔒 Security Best Practices
- **하드코딩 금지**: 모든 URL, 데이터베이스 연결정보, 도메인 정보는 환경변수로 관리
- **필수 환경변수**: LOGIN_URL, ATTEND_PAGE_URL, DATABASE_URL은 반드시 설정 필요
- **기본값 제공**: 버튼 셀렉터와 타임아웃은 기본값이 있어 필요시에만 환경변수로 오버라이드
- **민감정보 보호**: 실제 운영 환경의 URL이나 데이터베이스 정보가 코드에 노출되지 않음

### User Management
Users are managed in the PostgreSQL database:
```bash
# Add new user
python manage_users.py add username password email

# List users
python manage_users.py list

# Activate/deactivate users
python manage_users.py activate username
python manage_users.py deactivate username
```

## Core Architecture

### Main Components
- **`auto_chultae.py`** - Core browser automation for punch-in/punch-out
- **`watchdog.py`** - Scheduling server (HTTP client for main server)
- **`main_server.py`** - Crawling server (Flask HTTP API server)
- **`db_manager.py`** - Database operations and connection management
- **`manage_users.py`** - Command-line user management interface
- **`start.sh`** / **`stop.sh`** - System startup and shutdown scripts
- **`requirements.txt`** - Python dependencies

### Key Functions
- **`login_and_click_button()`** - Handles login and button clicking with retry logic
- **`close_all_popups()`** - Aggressive popup handling to clear UI obstructions
- **`wait_and_click_button()`** - Robust button clicking with multiple retry attempts
- **`process_users()`** - Processes multiple user accounts with random delays
- **`punch_in()`** and **`punch_out()`** - Main attendance functions

### Configuration
- **User Accounts**: Managed in PostgreSQL database via `manage_users.py`
- **URLs and Selectors**: Company-specific login URL and button selectors
- **Environment Variables**: All sensitive data in `.env` file
- **Timing**: Korean timezone (Asia/Seoul) for scheduling

### Independent Server Architecture
- **Watchdog Server**: Scheduling only, sends HTTP commands to main server
- **Main Server**: Flask API server for crawling operations only
- **HTTP Communication**: RESTful API between servers for complete isolation
- **Health Monitoring**: Separate health checks for each server

### Browser Automation Architecture
- **Playwright with Chromium**: Headless browser automation
- **Smart Button Detection**: Priority popup buttons, fallback to basic buttons
- **Popup Management**: Multi-layered popup closing using JavaScript injection
- **Error Handling**: Screenshot and HTML capture on failures
- **Retry Logic**: Multiple attempts for button clicks with exponential backoff

### Logging and Monitoring
- **Daily Log Files**: Stored in `logs/` directory with date-based naming
- **Real-time Logs**: `main_server.out`, `watchdog.out` for live monitoring
- **Structured Logging**: Detailed logging with user ID and action tracking
- **Error Screenshots**: Automatic screenshot capture in `screenshots/` directory on failures
- **Database Logging**: All operations logged to PostgreSQL

### Scheduling System
- **APScheduler**: Blocking scheduler in watchdog server
- **HTTP Commands**: Sends punch-in/out commands to main server
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM
- **Korean Timezone**: All scheduling uses Asia/Seoul timezone

### Error Recovery
- **Popup Interference**: Comprehensive popup detection and removal
- **Button Visibility**: JavaScript-based scrolling and visibility checks  
- **Duplicate Action Prevention**: State checking to avoid redundant operations
- **Random Delays**: Anti-detection delays between user processing

## Development Commands

### System Management
```bash
# Start both servers
./start.sh

# Stop both servers
./stop.sh

# Health check
curl http://localhost:8080/api/health

# Manual testing
curl -X POST http://localhost:8080/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "punch_in"}'
```

### User Management
```bash
# Add user
python manage_users.py add user_id password

# List users
python manage_users.py list

# Activate/deactivate user
python manage_users.py activate user_id
python manage_users.py deactivate user_id
```

### Debug Mode
Real-time monitoring:
```bash
# Main server (crawling) logs
tail -f main_server.out
tail -f logs/main_server_YYYYMMDD.log

# Watchdog (scheduling) logs
tail -f watchdog.out
tail -f logs/watchdog_YYYYMMDD.log

# Detailed crawling logs
tail -f logs/auto_chultae_YYYYMMDD.log
```

Error investigation:
- `logs/` - Daily log files with detailed progression tracking
- `screenshots/` - Error screenshots and HTML dumps for failed operations

### Testing Changes
When modifying the automation logic:
1. Test individual functions: `python -c "from auto_chultae import punch_in; punch_in()"`
2. Monitor real-time logs for proper login and button detection
3. Check screenshot outputs if automation fails
4. Test server communication: Health check and manual commands

### Key Configuration Points
- **Button Selectors**: `auto_chultae.py:74-79` defines all button selectors
- **URLs**: `auto_chultae.py:72-73` defines login and attendance page URLs
- **Server Settings**: Environment variables in `.env` file
- **Scheduling**: `watchdog.py:187-195` sets punch times (8:00-8:40 AM in, 18:00-19:00 PM out)