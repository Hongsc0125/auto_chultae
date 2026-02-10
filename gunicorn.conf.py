#!/usr/bin/env python3
"""
Gunicorn 설정 파일
프로덕션 환경용 WSGI 서버 설정
"""

import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# .env 파일 로드
load_dotenv()

# MAIN_SERVER_URL에서 호스트와 포트 파싱
main_server_url = os.getenv('MAIN_SERVER_URL')
if not main_server_url:
    raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

parsed = urlparse(main_server_url)
host = parsed.hostname or '127.0.0.1'
port = parsed.port or 9000

# Gunicorn 설정
bind = f"{host}:{port}"
workers = 2  # CPU 코어 수 * 2 (최소 2개)
worker_class = "sync"
worker_connections = 1000
timeout = 300  # 크롤링 작업은 최대 5분 소요될 수 있음
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
daemon = False

# 로깅 설정
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 프로세스 이름
proc_name = "auto_chultae_main_server"

# 디렉토리 생성
os.makedirs("logs", exist_ok=True)

print(f"Gunicorn 설정: {bind}, workers: {workers}")