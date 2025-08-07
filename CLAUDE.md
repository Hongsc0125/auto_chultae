# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is an **automated attendance management system** that uses Playwright to automate punch-in/punch-out operations on a company's internal attendance system. The system runs scheduled tasks to automatically handle attendance for multiple user accounts.

## Running the Application

### Start the Attendance System
```bash
python auto_chultae.py
```
The system will:
- Perform an initial punch-in check at startup
- Schedule automated punch-in at 8:00 AM (Monday-Friday)
- Schedule automated punch-out at 6:05 PM (Monday-Friday)

### Install Dependencies
```bash
pip install -r requirements.txt
```

Note: After installing Playwright, you may need to install browser dependencies:
```bash
playwright install chromium
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