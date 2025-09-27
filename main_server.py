#!/usr/bin/env python3
"""
Auto Chultae Main Server - 크롤링 전용 서버
HTTP API를 통해 출퇴근 명령을 받아 처리하는 독립 서버
"""

import os
import sys
import logging
import signal
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from db_manager import db_manager

# .env 파일 로드
load_dotenv()

# 로깅 설정
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"main_server_{datetime.now().strftime('%Y%m%d')}.log")

    logger = logging.getLogger('main_server')
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - [MAIN] %(message)s')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(fmt)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# Flask 앱 생성
app = Flask(__name__)

# 전역 변수
shutdown_flag = threading.Event()

def update_server_heartbeat():
    """서버 하트비트 업데이트"""
    try:
        db_manager.update_heartbeat(
            component="main_server",
            status="running",
            pid=os.getpid(),
            stage="waiting",
            user_id=None,
            action=None
        )
    except Exception as e:
        logger.warning(f"하트비트 업데이트 실패: {e}")

def heartbeat_worker():
    """하트비트 워커 스레드"""
    while not shutdown_flag.is_set():
        update_server_heartbeat()
        time.sleep(30)  # 30초마다 하트비트 업데이트

@app.route('/api/health', methods=['GET'])
def health_check():
    """헬스체크 엔드포인트"""
    try:
        db_connected = db_manager.test_connection()
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected' if db_connected else 'disconnected',
            'pid': os.getpid()
        }
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"헬스체크 오류: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/command', methods=['POST'])
def handle_command():
    """워치독에서 오는 명령 처리"""
    try:
        data = request.get_json()
        command = data.get('command')

        if command == 'punch_in':
            logger.info("출근 명령 수신")
            db_manager.update_heartbeat(
                component="main_server",
                status="processing",
                pid=os.getpid(),
                stage="punch_in_start",
                user_id=None,
                action="punch_in"
            )

            # auto_chultae 모듈에서 punch_in 실행
            from auto_chultae import punch_in
            punch_in()

            db_manager.update_heartbeat(
                component="main_server",
                status="completed",
                pid=os.getpid(),
                stage="punch_in_complete",
                user_id=None,
                action="punch_in"
            )

            logger.info("출근 처리 완료")
            return jsonify({'status': 'success', 'message': '출근 처리 완료'}), 200

        elif command == 'punch_out':
            logger.info("퇴근 명령 수신")
            db_manager.update_heartbeat(
                component="main_server",
                status="processing",
                pid=os.getpid(),
                stage="punch_out_start",
                user_id=None,
                action="punch_out"
            )

            # auto_chultae 모듈에서 punch_out 실행
            from auto_chultae import punch_out
            punch_out()

            db_manager.update_heartbeat(
                component="main_server",
                status="completed",
                pid=os.getpid(),
                stage="punch_out_complete",
                user_id=None,
                action="punch_out"
            )

            logger.info("퇴근 처리 완료")
            return jsonify({'status': 'success', 'message': '퇴근 처리 완료'}), 200

        else:
            logger.warning(f"알 수 없는 명령: {command}")
            return jsonify({'status': 'error', 'message': f'알 수 없는 명령: {command}'}), 400

    except Exception as e:
        logger.error(f"명령 처리 오류: {e}")
        db_manager.update_heartbeat(
            component="main_server",
            status="error",
            pid=os.getpid(),
            stage="error",
            user_id=None,
            action=None
        )
        return jsonify({'status': 'error', 'message': str(e)}), 500

def signal_handler(signum, frame):
    """시그널 핸들러"""
    logger.info("종료 신호 수신")
    shutdown_flag.set()

    # 데이터베이스에 종료 상태 기록
    try:
        db_manager.update_heartbeat(
            component="main_server",
            status="shutting_down",
            pid=os.getpid(),
            stage="shutdown",
            user_id=None,
            action=None
        )
    except Exception as e:
        logger.warning(f"종료 시 하트비트 업데이트 실패: {e}")

    sys.exit(0)

def main():
    """메인 서버 시작"""
    # 시그널 핸들러 설정
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("메인 서버 시작 (크롤링 전용)")

    # 데이터베이스 연결 테스트
    if not db_manager.test_connection():
        logger.error("데이터베이스 연결 실패! 계속 진행하지만 로그는 DB에 저장되지 않습니다.")
    else:
        logger.info("데이터베이스 연결 성공")
        db_manager.log_system("INFO", "main_server", "메인 서버 시작")

    # 하트비트 워커 스레드 시작
    heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
    heartbeat_thread.start()
    logger.info("하트비트 워커 스레드 시작")

    # Flask 서버 설정 - MAIN_SERVER_URL에서 파싱 (필수)
    main_server_url = os.getenv('MAIN_SERVER_URL')
    if not main_server_url:
        raise ValueError("MAIN_SERVER_URL 환경변수가 필수입니다.")

    from urllib.parse import urlparse
    parsed = urlparse(main_server_url)
    host = parsed.hostname
    port = parsed.port

    if not host:
        raise ValueError("MAIN_SERVER_URL에서 호스트를 파싱할 수 없습니다.")
    if not port:
        raise ValueError("MAIN_SERVER_URL에서 포트를 파싱할 수 없습니다.")

    logger.info(f"Flask 서버 시작: {host}:{port}")
    logger.info("API 엔드포인트:")
    logger.info("  - GET /api/health : 헬스체크")
    logger.info("  - POST /api/command : 명령 실행 (punch_in, punch_out)")

    # 초기 하트비트
    update_server_heartbeat()

    # 서버 시작 시 초기 출근 체크 수행
    def initial_punch_check():
        """서버 시작 시 초기 출근 체크"""
        try:
            logger.info("🚀 서버 시작 - 초기 출근 체크 수행")
            from auto_chultae import punch_in
            punch_in()
            logger.info("✅ 초기 출근 체크 완료")
        except Exception as e:
            logger.error(f"❌ 초기 출근 체크 실패: {e}")

    # 별도 스레드에서 초기 출근 체크 실행 (Flask 서버 시작과 병렬)
    initial_check_thread = threading.Thread(target=initial_punch_check, daemon=True)
    initial_check_thread.start()

    try:
        # 개발 모드와 프로덕션 모드 구분
        if os.getenv('FLASK_ENV') == 'development':
            # 개발 모드: Flask 내장 서버 사용
            logger.info("개발 모드로 Flask 내장 서버 실행")
            app.run(host=host, port=port, debug=True, use_reloader=False)
        else:
            # 프로덕션 모드: gunicorn으로 실행되어야 함
            logger.info("프로덕션 모드 - gunicorn으로 실행해야 합니다")
            logger.info(f"명령어: gunicorn -c gunicorn.conf.py main_server:app")

            # gunicorn이 이 앱을 로드할 때는 여기서 실행하지 않음
            # 하지만 직접 실행된 경우에는 경고 후 기본 서버로 실행
            if __name__ == '__main__':
                logger.warning("프로덕션 환경에서는 gunicorn 사용을 권장합니다")
                app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("메인 서버 종료")
    except Exception as e:
        logger.error(f"서버 실행 오류: {e}")
    finally:
        shutdown_flag.set()

if __name__ == '__main__':
    main()