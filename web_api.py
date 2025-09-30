#!/usr/bin/env python3
"""
Auto Chultae Web API - 대시보드용 API 서버
Flask JWT를 사용한 인증 및 데이터 조회 API 제공
"""

import os
import hashlib
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from dotenv import load_dotenv
from db_manager import db_manager
from sqlalchemy import text

# .env 파일 로드
load_dotenv()

# Flask 앱 생성
app = Flask(__name__)

# CORS 설정 (Vue.js 프론트엔드와 통신용)
CORS(app,
     origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=True)

# JWT 설정
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-this-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
jwt = JWTManager(app)

def hash_password(password):
    """비밀번호 해시화"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """비밀번호 검증"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

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
                text("SELECT user_id FROM users WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            if result.fetchone():
                return jsonify({'error': '이미 존재하는 사용자 ID입니다'}), 400

            # 사용자 생성
            hashed_password = hash_password(password)
            session.execute(
                text("""
                    INSERT INTO users (user_id, password, email, is_active, created_at, updated_at)
                    VALUES (:user_id, :password, :email, true, :now, :now)
                """),
                {
                    "user_id": user_id,
                    "password": hashed_password,
                    "email": email,
                    "now": datetime.now()
                }
            )
            session.commit()

            return jsonify({'message': '회원가입이 완료되었습니다'}), 201

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/auth/login', methods=['POST'])
def login():
    """로그인"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        password = data.get('password')

        if not all([user_id, password]):
            return jsonify({'error': '사용자 ID와 비밀번호를 입력해주세요'}), 400

        session = db_manager.get_session()
        try:
            result = session.execute(
                text("SELECT user_id, password, email, is_active FROM users WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            user = result.fetchone()

            if not user:
                return jsonify({'error': '사용자를 찾을 수 없습니다'}), 401

            if not user[3]:  # is_active
                return jsonify({'error': '비활성화된 계정입니다'}), 401

            # 비밀번호 검증 (평문과 해시 둘 다 지원)
            stored_password = user[1]
            if stored_password.startswith('$2b$'):  # bcrypt 해시인 경우
                if not verify_password(password, stored_password):
                    return jsonify({'error': '비밀번호가 올바르지 않습니다'}), 401
            else:  # 평문인 경우
                if password != stored_password:
                    return jsonify({'error': '비밀번호가 올바르지 않습니다'}), 401

            # JWT 토큰 생성
            access_token = create_access_token(identity=user_id)

            return jsonify({
                'access_token': access_token,
                'user': {
                    'user_id': user[0],
                    'email': user[2]
                }
            }), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/server/status', methods=['GET'])
@jwt_required()
def get_server_status():
    """서버 상태 조회 (실시간)"""
    try:
        session = db_manager.get_session()
        try:
            # 메인 서버 상태
            result = session.execute(
                text("""
                    SELECT component, status, timestamp
                    FROM server_heartbeat
                    WHERE component IN ('main_server', 'watchdog')
                    ORDER BY component, timestamp DESC
                """)
            )
            heartbeats = result.fetchall()

            server_status = {
                'main_server': {'status': 'stopped', 'last_seen': None},
                'watchdog': {'status': 'stopped', 'last_seen': None}
            }

            for hb in heartbeats:
                component = hb[0]
                if component in server_status:
                    # 5분 이내면 활성 상태로 간주
                    time_diff = datetime.now() - hb[2]
                    if time_diff.total_seconds() < 300:  # 5분
                        server_status[component]['status'] = hb[1]
                    else:
                        server_status[component]['status'] = 'timeout'
                    server_status[component]['last_seen'] = hb[2].isoformat()

            return jsonify(server_status), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/user/attendance', methods=['GET'])
@jwt_required()
def get_user_attendance():
    """사용자별 출퇴근 기록 조회"""
    try:
        current_user = get_jwt_identity()

        # 쿼리 파라미터
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        session = db_manager.get_session()
        try:
            # 기본 쿼리
            query = """
                SELECT id, action_type, status, attempt_time, error_message
                FROM attendance_logs
                WHERE user_id = :user_id
            """
            params = {"user_id": current_user}

            # 날짜 필터링
            if date_from:
                query += " AND DATE(attempt_time) >= :date_from"
                params["date_from"] = date_from
            if date_to:
                query += " AND DATE(attempt_time) <= :date_to"
                params["date_to"] = date_to

            query += " ORDER BY attempt_time DESC LIMIT :limit OFFSET :offset"
            params.update({"limit": limit, "offset": offset})

            result = session.execute(text(query), params)
            records = result.fetchall()

            # 한국어 번역 맵
            status_translation = {
                'success': '성공',
                'failed': '실패',
                'already_done': '이미 완료됨'
            }

            action_translation = {
                'punch_in': '출근',
                'punch_out': '퇴근'
            }

            attendance_data = []
            for record in records:
                attendance_data.append({
                    'id': record[0],
                    'action_type': action_translation.get(record[1], record[1]),
                    'action_type_raw': record[1],
                    'status': status_translation.get(record[2], record[2]),
                    'status_raw': record[2],
                    'attempt_time': record[3].isoformat() if record[3] else None,
                    'error_message': record[4]
                })

            return jsonify({
                'attendance': attendance_data,
                'total': len(attendance_data)
            }), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/user/heartbeat', methods=['GET'])
@jwt_required()
def get_user_heartbeat():
    """사용자별 크롤링 진행상태 조회"""
    try:
        current_user = get_jwt_identity()

        # 쿼리 파라미터
        limit = request.args.get('limit', 50, type=int)
        action_type = request.args.get('action_type')  # punch_in 또는 punch_out 필터
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        session = db_manager.get_session()
        try:
            # 기본 쿼리
            query = """
                SELECT stage, action_type, timestamp
                FROM heartbeat_status
                WHERE user_id = :user_id
            """
            params = {"user_id": current_user}

            # 액션 타입 필터링
            if action_type:
                query += " AND action_type = :action_type"
                params["action_type"] = action_type

            # 날짜 필터링
            if date_from:
                query += " AND DATE(timestamp) >= :date_from"
                params["date_from"] = date_from
            if date_to:
                query += " AND DATE(timestamp) <= :date_to"
                params["date_to"] = date_to

            query += " ORDER BY timestamp DESC LIMIT :limit"
            params["limit"] = limit

            result = session.execute(text(query), params)
            heartbeats = result.fetchall()

            # 한국어 번역 맵
            stage_translation = {
                'process_start': '프로세스 시작',
                'playwright_init': 'Playwright 초기화',
                'browser_started': '브라우저 시작',
                'context_created': '브라우저 컨텍스트 생성',
                'page_creation_start': '페이지 생성 시작',
                'page_creation_attempt_1': '페이지 생성 시도 1',
                'page_creation_attempt_2': '페이지 생성 시도 2',
                'page_creation_attempt_3': '페이지 생성 시도 3',
                'page_created': '페이지 생성 완료',
                'login_start': '로그인 시작',
                'page_navigation': '페이지 이동',
                'page_loaded': '페이지 로드 완료',
                'login_form_loaded': '로그인 폼 로드',
                'userid_filled': '사용자 ID 입력',
                'password_filled': '비밀번호 입력',
                'login_button_click': '로그인 버튼 클릭',
                'main_page_wait': '메인 페이지 대기',
                'main_page_loaded': '메인 페이지 로드',
                'page_load_wait': '페이지 로드 대기',
                'page_load_complete': '페이지 로드 완료',
                'login_success': '로그인 성공',
                'page_stabilize_wait': '페이지 안정화 대기',
                'popup_close_start': '팝업 정리 시작',
                'popup_close_complete': '팝업 정리 완료',
                'button_click_start': '버튼 클릭 시작',
                'button_clicked_success': '버튼 클릭 성공',
                'process_complete': '프로세스 완료'
            }

            action_translation = {
                'punch_in': '출근',
                'punch_out': '퇴근'
            }

            heartbeat_data = []
            for hb in heartbeats:
                heartbeat_data.append({
                    'stage': stage_translation.get(hb[0], hb[0]),
                    'stage_raw': hb[0],  # 원본 단계명도 포함
                    'action_type': action_translation.get(hb[1], hb[1]),
                    'action_type_raw': hb[1],  # 원본 액션 타입도 포함
                    'timestamp': hb[2].isoformat() if hb[2] else None
                })

            return jsonify({
                'heartbeats': heartbeat_data,
                'total': len(heartbeat_data),
                'filters': {
                    'action_type': action_type,
                    'date_from': date_from,
                    'date_to': date_to,
                    'limit': limit
                }
            }), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/user/attendance/<int:attendance_id>/heartbeat', methods=['GET'])
@jwt_required()
def get_attendance_heartbeat(attendance_id):
    """특정 출석 기록의 상세 하트비트 조회"""
    try:
        current_user = get_jwt_identity()

        session = db_manager.get_session()
        try:
            # 해당 출석 기록이 현재 사용자의 것인지 확인
            attendance_result = session.execute(
                text("""
                    SELECT user_id, action_type, attempt_time, status
                    FROM attendance_logs
                    WHERE id = :attendance_id AND user_id = :user_id
                """),
                {"attendance_id": attendance_id, "user_id": current_user}
            )
            attendance = attendance_result.fetchone()

            if not attendance:
                return jsonify({'error': '출석 기록을 찾을 수 없습니다'}), 404

            # 해당 출석 기록의 시간대 기준으로 하트비트 조회
            # 출석 시도 시간 전후 30분 범위에서 해당 액션 타입의 하트비트 조회
            attempt_time = attendance[2]
            action_type = attendance[1]

            start_time = attempt_time - timedelta(minutes=30)
            end_time = attempt_time + timedelta(minutes=30)

            heartbeat_result = session.execute(
                text("""
                    SELECT stage, action_type, timestamp
                    FROM heartbeat_status
                    WHERE user_id = :user_id
                    AND action_type = :action_type
                    AND timestamp BETWEEN :start_time AND :end_time
                    ORDER BY timestamp ASC
                """),
                {
                    "user_id": current_user,
                    "action_type": action_type,
                    "start_time": start_time,
                    "end_time": end_time
                }
            )
            heartbeats = heartbeat_result.fetchall()

            # 한국어 번역 맵
            stage_translation = {
                'process_start': '프로세스 시작',
                'playwright_init': 'Playwright 초기화',
                'browser_started': '브라우저 시작',
                'context_created': '브라우저 컨텍스트 생성',
                'page_creation_start': '페이지 생성 시작',
                'page_creation_attempt_1': '페이지 생성 시도 1',
                'page_creation_attempt_2': '페이지 생성 시도 2',
                'page_creation_attempt_3': '페이지 생성 시도 3',
                'page_created': '페이지 생성 완료',
                'login_start': '로그인 시작',
                'page_navigation': '페이지 이동',
                'page_loaded': '페이지 로드 완료',
                'login_form_loaded': '로그인 폼 로드',
                'userid_filled': '사용자 ID 입력',
                'password_filled': '비밀번호 입력',
                'login_button_click': '로그인 버튼 클릭',
                'main_page_wait': '메인 페이지 대기',
                'main_page_loaded': '메인 페이지 로드',
                'page_load_wait': '페이지 로드 대기',
                'page_load_complete': '페이지 로드 완료',
                'login_success': '로그인 성공',
                'page_stabilize_wait': '페이지 안정화 대기',
                'popup_close_start': '팝업 정리 시작',
                'popup_close_complete': '팝업 정리 완료',
                'button_click_start': '버튼 클릭 시작',
                'button_clicked_success': '버튼 클릭 성공',
                'process_complete': '프로세스 완료'
            }

            action_translation = {
                'punch_in': '출근',
                'punch_out': '퇴근'
            }

            status_translation = {
                'success': '성공',
                'failed': '실패',
                'already_done': '이미 완료됨'
            }

            heartbeat_data = []
            for hb in heartbeats:
                heartbeat_data.append({
                    'stage': stage_translation.get(hb[0], hb[0]),
                    'stage_raw': hb[0],
                    'action_type': action_translation.get(hb[1], hb[1]),
                    'action_type_raw': hb[1],
                    'timestamp': hb[2].isoformat() if hb[2] else None
                })

            return jsonify({
                'attendance': {
                    'id': attendance_id,
                    'action_type': action_translation.get(attendance[1], attendance[1]),
                    'action_type_raw': attendance[1],
                    'attempt_time': attendance[2].isoformat(),
                    'status': status_translation.get(attendance[3], attendance[3]),
                    'status_raw': attendance[3]
                },
                'heartbeats': heartbeat_data,
                'total': len(heartbeat_data)
            }), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/web/user/summary', methods=['GET'])
@jwt_required()
def get_user_summary():
    """사용자별 요약 정보 조회"""
    try:
        current_user = get_jwt_identity()

        session = db_manager.get_session()
        try:
            # 오늘 출퇴근 상태
            today = datetime.now().strftime('%Y-%m-%d')
            result = session.execute(
                text("""
                    SELECT action_type, status, attempt_time
                    FROM attendance_logs
                    WHERE user_id = :user_id
                    AND DATE(attempt_time) = :today
                    AND status IN ('success', 'already_done')
                    ORDER BY attempt_time DESC
                """),
                {"user_id": current_user, "today": today}
            )
            today_records = result.fetchall()

            # 이번 주 통계
            result = session.execute(
                text("""
                    SELECT
                        COUNT(CASE WHEN action_type = 'punch_in' AND status IN ('success', 'already_done') THEN 1 END) as punch_in_count,
                        COUNT(CASE WHEN action_type = 'punch_out' AND status IN ('success', 'already_done') THEN 1 END) as punch_out_count
                    FROM attendance_logs
                    WHERE user_id = :user_id
                    AND DATE(attempt_time) >= CURRENT_DATE - INTERVAL '7 days'
                """),
                {"user_id": current_user}
            )
            week_stats = result.fetchone()

            summary = {
                'today': {
                    'punch_in': any(r[0] == 'punch_in' for r in today_records),
                    'punch_out': any(r[0] == 'punch_out' for r in today_records)
                },
                'this_week': {
                    'punch_in_count': week_stats[0] if week_stats else 0,
                    'punch_out_count': week_stats[1] if week_stats else 0
                }
            }

            return jsonify(summary), 200

        finally:
            session.close()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 개발 모드로 실행 (9000번 포트 - 대시보드와 매칭)
    app.run(host='0.0.0.0', port=9000, debug=True)