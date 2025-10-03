#!/usr/bin/env python3
"""
데이터베이스 관리 모듈
"""

import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스 설정
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다. .env 파일에 DATABASE_URL을 설정해주세요.")

# SQLAlchemy 설정
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def get_session(self):
        """데이터베이스 세션 반환"""
        return self.SessionLocal()

    def test_connection(self):
        """데이터베이스 연결 테스트"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return True
        except SQLAlchemyError as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            return False

    def insert_user(self, user_id, password):
        """사용자 추가"""
        session = self.get_session()
        try:
            # 사용자가 이미 존재하는지 확인
            result = session.execute(
                text("SELECT id FROM users WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            if result.fetchone():
                logger.info(f"사용자 {user_id}는 이미 존재합니다")
                return True

            # 새 사용자 추가
            session.execute(
                text("""
                    INSERT INTO users (user_id, password)
                    VALUES (:user_id, :password)
                """),
                {"user_id": user_id, "password": password}
            )
            session.commit()
            logger.info(f"사용자 {user_id} 추가 완료")
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"사용자 추가 실패: {e}")
            return False
        finally:
            session.close()

    def log_attendance(self, user_id, action_type, status, error_message=None, screenshot_path=None, html_path=None):
        """출퇴근 기록 저장 - 생성된 log ID 반환"""
        session = self.get_session()
        try:
            result = session.execute(
                text("""
                    INSERT INTO attendance_logs
                    (user_id, action_type, status, attempt_time, error_message, screenshot_path, html_path)
                    VALUES (:user_id, :action_type, :status, :attempt_time, :error_message, :screenshot_path, :html_path)
                    RETURNING id
                """),
                {
                    "user_id": user_id,
                    "action_type": action_type,
                    "status": status,
                    "attempt_time": datetime.now(),
                    "error_message": error_message,
                    "screenshot_path": screenshot_path,
                    "html_path": html_path
                }
            )

            log_id = result.fetchone()[0]
            session.commit()
            logger.debug(f"출퇴근 기록 저장: {user_id} - {action_type} - {status} (ID: {log_id})")
            return log_id

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"출퇴근 기록 저장 실패: {e}")
            return None
        finally:
            session.close()

    def log_system(self, log_level, component, message, stage=None, user_id=None, action_type=None):
        """시스템 로그 저장"""
        session = self.get_session()
        try:
            session.execute(
                text("""
                    INSERT INTO system_logs
                    (log_level, component, stage, message, user_id, action_type)
                    VALUES (:log_level, :component, :stage, :message, :user_id, :action_type)
                """),
                {
                    "log_level": log_level,
                    "component": component,
                    "stage": stage,
                    "message": message,
                    "user_id": user_id,
                    "action_type": action_type
                }
            )
            session.commit()
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"시스템 로그 저장 실패: {e}")
            return False
        finally:
            session.close()


    def get_daily_summary(self, date=None):
        """일일 출퇴근 현황 조회"""
        session = self.get_session()
        try:
            if date is None:
                date = datetime.now().date()

            result = session.execute(
                text("""
                    SELECT * FROM daily_attendance_summary
                    WHERE attendance_date = :date
                    ORDER BY user_id
                """),
                {"date": date}
            )
            return result.fetchall()

        except SQLAlchemyError as e:
            logger.error(f"일일 현황 조회 실패: {e}")
            return []
        finally:
            session.close()

    def get_latest_attendance(self, user_id=None):
        """최신 출퇴근 상태 조회"""
        session = self.get_session()
        try:
            if user_id:
                result = session.execute(
                    text("SELECT * FROM latest_attendance WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
            else:
                result = session.execute(text("SELECT * FROM latest_attendance ORDER BY user_id, action_type"))

            return result.fetchall()

        except SQLAlchemyError as e:
            logger.error(f"최신 출퇴근 상태 조회 실패: {e}")
            return []
        finally:
            session.close()

    def has_today_success(self, user_id, action_type):
        """오늘자 성공 출퇴근 이력이 있는지 확인"""
        session = self.get_session()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            result = session.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM attendance_logs
                    WHERE user_id = :user_id
                    AND action_type = :action_type
                    AND status IN ('success', 'already_done')
                    AND DATE(attempt_time) = :today
                """),
                {"user_id": user_id, "action_type": action_type, "today": today}
            )

            count = result.fetchone()
            return count[0] > 0 if count else False

        except SQLAlchemyError as e:
            logger.error(f"오늘자 성공 이력 확인 실패: {e}")
            return False
        finally:
            session.close()

    def get_active_users(self):
        """활성 사용자 목록 조회"""
        session = self.get_session()
        try:
            result = session.execute(
                text("SELECT user_id, password FROM users WHERE is_active = true ORDER BY user_id")
            )
            users = result.fetchall()
            return [{"user_id": user[0], "password": user[1]} for user in users]

        except SQLAlchemyError as e:
            logger.error(f"활성 사용자 조회 실패: {e}")
            return []
        finally:
            session.close()

    def add_user(self, user_id, password):
        """새 사용자 추가 (중복 체크 포함)"""
        return self.insert_user(user_id, password)

    def deactivate_user(self, user_id):
        """사용자 비활성화"""
        session = self.get_session()
        try:
            result = session.execute(
                text("UPDATE users SET is_active = false, updated_at = :updated_at WHERE user_id = :user_id"),
                {"user_id": user_id, "updated_at": datetime.now()}
            )
            session.commit()

            if result.rowcount > 0:
                logger.info(f"사용자 {user_id} 비활성화 완료")
                return True
            else:
                logger.warning(f"사용자 {user_id}를 찾을 수 없습니다")
                return False

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"사용자 비활성화 실패: {e}")
            return False
        finally:
            session.close()

    def activate_user(self, user_id):
        """사용자 활성화"""
        session = self.get_session()
        try:
            result = session.execute(
                text("UPDATE users SET is_active = true, updated_at = :updated_at WHERE user_id = :user_id"),
                {"user_id": user_id, "updated_at": datetime.now()}
            )
            session.commit()

            if result.rowcount > 0:
                logger.info(f"사용자 {user_id} 활성화 완료")
                return True
            else:
                logger.warning(f"사용자 {user_id}를 찾을 수 없습니다")
                return False

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"사용자 활성화 실패: {e}")
            return False
        finally:
            session.close()

    def update_user_password(self, user_id, new_password):
        """사용자 비밀번호 업데이트"""
        session = self.get_session()
        try:
            result = session.execute(
                text("UPDATE users SET password = :password, updated_at = :updated_at WHERE user_id = :user_id"),
                {"user_id": user_id, "password": new_password, "updated_at": datetime.now()}
            )
            session.commit()

            if result.rowcount > 0:
                logger.info(f"사용자 {user_id} 비밀번호 업데이트 완료")
                return True
            else:
                logger.warning(f"사용자 {user_id}를 찾을 수 없습니다")
                return False

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"비밀번호 업데이트 실패: {e}")
            return False
        finally:
            session.close()

    def is_workday_scheduled(self, user_id, date=None):
        """특정 날짜에 사용자가 출근일로 스케줄되어 있는지 확인"""
        if date is None:
            date = datetime.now().date()

        session = self.get_session()
        try:
            result = session.execute(
                text("""
                    SELECT is_workday FROM attendance_schedules
                    WHERE user_id = :user_id AND schedule_date = :date
                """),
                {"user_id": user_id, "date": date}
            )

            row = result.fetchone()
            if row is None:
                # 스케줄이 없으면 기본적으로 평일은 출근일로 간주
                weekday = date.weekday()  # 0=월요일, 6=일요일
                return weekday < 5  # 월-금요일만 출근일

            return row.is_workday

        except SQLAlchemyError as e:
            logger.error(f"스케줄 확인 실패: {e}")
            # 에러 시 기본적으로 평일은 출근일로 간주
            weekday = date.weekday() if date else datetime.now().weekday()
            return weekday < 5
        finally:
            session.close()

    def update_heartbeat(self, component, status, message=None):
        """서버 하트비트 업데이트 (server_heartbeat 테이블 사용)"""
        session = self.get_session()
        try:
            import os
            session.execute(
                text("""
                    INSERT INTO server_heartbeat
                    (component, status, pid, stage, timestamp)
                    VALUES (:component, :status, :pid, :stage, :timestamp)
                """),
                {
                    "component": component,
                    "status": status,
                    "pid": os.getpid(),
                    "stage": message or f"{component}_{status}",
                    "timestamp": datetime.now()
                }
            )
            session.commit()
            logger.debug(f"서버 하트비트 업데이트: {component} - {status}")
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"서버 하트비트 업데이트 실패: {e}")
            return False
        finally:
            session.close()

    def log_server_heartbeat(self, component, status, stage=None, user_id=None, action=None):
        """서버 하트비트 로깅 (워치독용) - UPSERT 방식"""
        session = self.get_session()
        try:
            import os
            # PostgreSQL UPSERT (ON CONFLICT DO UPDATE)
            session.execute(
                text("""
                    INSERT INTO server_heartbeat
                    (component, status, pid, stage, user_id, action, timestamp, updated_at)
                    VALUES (:component, :status, :pid, :stage, :user_id, :action, :timestamp, :updated_at)
                    ON CONFLICT (component) DO UPDATE SET
                        status = EXCLUDED.status,
                        pid = EXCLUDED.pid,
                        stage = EXCLUDED.stage,
                        user_id = EXCLUDED.user_id,
                        action = EXCLUDED.action,
                        timestamp = EXCLUDED.timestamp,
                        updated_at = EXCLUDED.updated_at
                """),
                {
                    "component": component,
                    "status": status,
                    "pid": os.getpid(),
                    "stage": stage,
                    "user_id": user_id,
                    "action": action,
                    "timestamp": datetime.now(),
                    "updated_at": datetime.now()
                }
            )
            session.commit()
            return True

        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"서버 하트비트 로깅 실패: {e}")
            return False
        finally:
            session.close()

# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()

if __name__ == "__main__":
    # 연결 테스트
    if db_manager.test_connection():
        print("데이터베이스 연결 성공!")
        print("사용자 관리는 'python manage_users.py migrate' 명령어를 사용하세요.")
    else:
        print("데이터베이스 연결 실패!")