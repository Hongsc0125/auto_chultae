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
import hashlib
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
from db_manager import db_manager
from sqlalchemy import text

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

# CORS 설정 (Vue.js 프론트엔드와 통신용)
CORS(app,
     origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True)

# CORS Preflight 요청 처리
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

# JWT 설정
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

# 전역 변수
shutdown_flag = threading.Event()

# 웹 API 헬퍼 함수들
def hash_password(password):
    """비밀번호 해시화"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """비밀번호 검증"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

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

# 웹 API 라우트들
@app.route('/api/web/auth/register', methods=['POST'])
def register():
    """회원가입"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        password = data.get('password')
        email = data.get('email')

        if not all([user_id, password, email]):
            return jsonify({'error': '모든 필드를 입력해주세요'}), 400

        # 사용자 중복 체크
        session = db_manager.get_session()
        try:
            result = session.execute(
                text("SELECT COUNT(*) as count FROM users WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            if result.fetchone().count > 0:
                return jsonify({'error': '이미 존재하는 사용자 ID입니다'}), 400

            # 사용자 생성 (비밀번호 평문 저장 - 기존 시스템과 호환)
            session.execute(
                text("INSERT INTO users (user_id, password, email, is_active, created_at, updated_at) VALUES (:user_id, :password, :email, :is_active, :created_at, :updated_at)"),
                {
                    "user_id": user_id,
                    "password": password,  # 평문 저장 (기존 시스템과 호환)
                    "email": email,
                    "is_active": True,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            )
            session.commit()
            return jsonify({'success': True, 'message': '회원가입이 완료되었습니다'})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"회원가입 오류: {e}")
        return jsonify({'error': '회원가입 중 오류가 발생했습니다'}), 500

@app.route('/api/web/auth/login', methods=['POST'])
def login():
    """로그인"""
    try:
        # 요청 헤더 확인
        if not request.is_json:
            logger.error(f"로그인 요청 헤더 문제: Content-Type = {request.content_type}")
            return jsonify({'error': 'Content-Type은 application/json이어야 합니다'}), 400

        data = request.get_json(force=True)  # force=True로 강제 파싱
        if not data:
            logger.error("로그인 요청 데이터가 비어있음")
            return jsonify({'error': 'JSON 데이터가 필요합니다'}), 400

        user_id = data.get('user_id')
        password = data.get('password')

        logger.info(f"로그인 시도: user_id={user_id}")

        if not all([user_id, password]):
            logger.error(f"로그인 필드 누락: user_id={user_id}, password={'있음' if password else '없음'}")
            return jsonify({'error': '사용자 ID와 비밀번호를 입력해주세요'}), 400

        # 사용자 인증 (기존 users 테이블 사용)
        session = db_manager.get_session()
        try:
            result = session.execute(
                text("SELECT user_id, password, email FROM users WHERE user_id = :user_id AND is_active = true"),
                {"user_id": user_id}
            )
            user = result.fetchone()

            if not user or user.password != password:  # 평문 비교 (기존 시스템과 호환)
                return jsonify({'error': '사용자 ID 또는 비밀번호가 잘못되었습니다'}), 401

            # JWT 토큰 생성
            access_token = create_access_token(identity=user_id)

            return jsonify({
                'success': True,
                'access_token': access_token,
                'user': {
                    'id': user.user_id,
                    'username': user.user_id,
                    'email': user.email
                }
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"로그인 오류: {e}")
        return jsonify({'error': '로그인 중 오류가 발생했습니다'}), 500

@app.route('/api/web/server/status', methods=['GET'])
@jwt_required()
def get_server_status():
    """서버 상태 조회"""
    try:
        session = db_manager.get_session()
        try:
            # 최근 하트비트 상태 조회 (5분 이내)
            five_minutes_ago = datetime.now() - timedelta(minutes=5)

            result = session.execute(
                text("""
                    SELECT stage, COUNT(*) as count
                    FROM heartbeat_status
                    WHERE timestamp > :five_minutes_ago
                    GROUP BY stage
                """),
                {"five_minutes_ago": five_minutes_ago}
            )
            statuses = result.fetchall()

            status = {
                'main': False,
                'watchdog': False
            }

            # 최근 활동이 있으면 온라인으로 간주
            for s in statuses:
                if 'main' in s.stage.lower() or 'server' in s.stage.lower():
                    status['main'] = True
                elif 'watchdog' in s.stage.lower():
                    status['watchdog'] = True

            # 기본적으로 현재 요청이 성공하면 메인 서버는 온라인
            status['main'] = True

            return jsonify({'success': True, 'status': status})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"서버 상태 조회 오류: {e}")
        return jsonify({'error': '서버 상태 조회 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/summary', methods=['GET'])
@jwt_required()
def get_today_status():
    """오늘의 출근 상태 조회"""
    try:
        current_user = get_jwt_identity()
        session = db_manager.get_session()
        try:
            today = datetime.now().strftime('%Y-%m-%d')

            result = session.execute(
                text("""
                    SELECT action_type, status, attempt_time
                    FROM attendance_logs
                    WHERE user_id = :user_id AND DATE(attempt_time) = :today
                    AND status IN ('success', 'already_done')
                    ORDER BY attempt_time DESC
                """),
                {"user_id": current_user, "today": today}
            )
            logs = result.fetchall()

            status = {
                'punchIn': '',
                'punchOut': ''
            }

            for log in logs:
                if log.action_type == 'punch_in' and not status['punchIn']:
                    status['punchIn'] = log.attempt_time.strftime('%H:%M')
                elif log.action_type == 'punch_out' and not status['punchOut']:
                    status['punchOut'] = log.attempt_time.strftime('%H:%M')

            return jsonify({'success': True, 'status': status})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"오늘 상태 조회 오류: {e}")
        return jsonify({'error': '오늘 상태 조회 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/attendance', methods=['GET'])
@jwt_required()
def get_logs():
    """로그 조회"""
    try:
        current_user = get_jwt_identity()
        limit = request.args.get('limit', 50, type=int)

        session = db_manager.get_session()
        try:
            result = session.execute(
                text("""
                    SELECT id, user_id, action_type, status, error_message, attempt_time
                    FROM attendance_logs
                    WHERE user_id = :user_id
                    ORDER BY attempt_time DESC
                    LIMIT :limit
                """),
                {"user_id": current_user, "limit": limit}
            )
            logs = result.fetchall()

            log_list = []
            for log in logs:
                log_list.append({
                    'id': log.id,
                    'user_id': log.user_id,
                    'action_type': log.action_type,
                    'status': log.status,
                    'message': log.error_message or '',
                    'timestamp': log.attempt_time.isoformat()
                })

            return jsonify({'success': True, 'logs': log_list})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"로그 조회 오류: {e}")
        return jsonify({'error': '로그 조회 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/attendance/<int:attendance_id>/heartbeat', methods=['GET'])
@jwt_required()
def get_heartbeats(attendance_id):
    """특정 attendance_log_id에 연결된 heartbeat 로그 조회"""
    try:
        log_id = attendance_id

        if not log_id:
            return jsonify({'error': 'attendance_id가 필요합니다'}), 400

        session = db_manager.get_session()
        try:
            result = session.execute(
                text("""
                    SELECT id, stage, user_id, action_type, pid, timestamp, attendance_log_id
                    FROM heartbeat_status
                    WHERE attendance_log_id = :log_id
                    ORDER BY timestamp ASC
                """),
                {"log_id": log_id}
            )
            heartbeats = result.fetchall()

            heartbeat_list = []
            for heartbeat in heartbeats:
                heartbeat_list.append({
                    'id': heartbeat.id,
                    'stage': heartbeat.stage,
                    'user_id': heartbeat.user_id,
                    'action_type': heartbeat.action_type,
                    'pid': heartbeat.pid,
                    'timestamp': heartbeat.timestamp.isoformat(),
                    'attendance_log_id': heartbeat.attendance_log_id
                })

            return jsonify({'success': True, 'heartbeats': heartbeat_list})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"하트비트 조회 오류: {e}")
        return jsonify({'error': '하트비트 조회 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/status', methods=['GET'])
@jwt_required()
def get_user_status():
    """사용자 활성화 상태 조회"""
    try:
        current_user = get_jwt_identity()
        session = db_manager.get_session()
        try:
            result = session.execute(
                text("SELECT is_active FROM users WHERE user_id = :user_id"),
                {"user_id": current_user}
            )
            user = result.fetchone()

            if not user:
                return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404

            return jsonify({'success': True, 'is_active': user.is_active})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"사용자 상태 조회 오류: {e}")
        return jsonify({'error': '사용자 상태 조회 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/status', methods=['PUT'])
@jwt_required()
def update_user_status():
    """사용자 활성화 상태 변경"""
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        is_active = data.get('is_active')

        if is_active is None:
            return jsonify({'error': 'is_active 값이 필요합니다'}), 400

        session = db_manager.get_session()
        try:
            result = session.execute(
                text("UPDATE users SET is_active = :is_active WHERE user_id = :user_id"),
                {"is_active": is_active, "user_id": current_user}
            )

            if result.rowcount == 0:
                return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404

            session.commit()
            logger.info(f"사용자 {current_user} 활성화 상태 변경: {is_active}")
            return jsonify({'success': True, 'message': '상태가 변경되었습니다'})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"사용자 상태 변경 오류: {e}")
        return jsonify({'error': '사용자 상태 변경 중 오류가 발생했습니다'}), 500

@app.route('/api/web/user/delete', methods=['DELETE'])
@jwt_required()
def delete_user_account():
    """사용자 계정 완전 삭제"""
    try:
        current_user = get_jwt_identity()
        session = db_manager.get_session()
        try:
            # 1. 하트비트 로그 삭제
            session.execute(
                text("DELETE FROM heartbeat_status WHERE user_id = :user_id"),
                {"user_id": current_user}
            )

            # 2. 출석 로그 삭제
            session.execute(
                text("DELETE FROM attendance_logs WHERE user_id = :user_id"),
                {"user_id": current_user}
            )

            # 3. 사용자 계정 삭제
            result = session.execute(
                text("DELETE FROM users WHERE user_id = :user_id"),
                {"user_id": current_user}
            )

            if result.rowcount == 0:
                return jsonify({'error': '사용자를 찾을 수 없습니다'}), 404

            session.commit()
            logger.info(f"사용자 {current_user} 계정 완전 삭제 완료")
            return jsonify({'success': True, 'message': '계정이 완전히 삭제되었습니다'})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"계정 삭제 오류: {e}")
        return jsonify({'error': '계정 삭제 중 오류가 발생했습니다'}), 500

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