#!/usr/bin/env python3
"""
사용자 관리 CLI 스크립트
"""

import sys
import os
import argparse
from db_manager import db_manager

def list_users():
    """사용자 목록 조회"""
    try:
        from sqlalchemy import text
        session = db_manager.get_session()
        result = session.execute(text("SELECT user_id, email, is_active, created_at FROM users ORDER BY user_id"))
        users = result.fetchall()
        session.close()

        if not users:
            print("등록된 사용자가 없습니다.")
            return

        print("\n📋 사용자 목록:")
        print("-" * 70)
        print(f"{'사용자 ID':<15} {'이메일':<30} {'상태':<8} {'등록일'}")
        print("-" * 70)

        for user in users:
            status = "활성" if user[2] else "비활성"
            created_at = user[3].strftime("%Y-%m-%d") if user[3] else "N/A"
            print(f"{user[0]:<15} {user[1] or 'N/A':<30} {status:<8} {created_at}")

    except Exception as e:
        print(f"❌ 사용자 목록 조회 실패: {e}")

def add_user(user_id, password):
    """사용자 추가"""
    if db_manager.add_user(user_id, password):
        print(f"✅ 사용자 '{user_id}' 추가 완료")
    else:
        print(f"❌ 사용자 '{user_id}' 추가 실패")

def activate_user(user_id):
    """사용자 활성화"""
    if db_manager.activate_user(user_id):
        print(f"✅ 사용자 '{user_id}' 활성화 완료")
    else:
        print(f"❌ 사용자 '{user_id}' 활성화 실패")

def deactivate_user(user_id):
    """사용자 비활성화"""
    if db_manager.deactivate_user(user_id):
        print(f"✅ 사용자 '{user_id}' 비활성화 완료")
    else:
        print(f"❌ 사용자 '{user_id}' 비활성화 실패")

def update_password(user_id, password):
    """비밀번호 업데이트"""
    if db_manager.update_user_password(user_id, password):
        print(f"✅ 사용자 '{user_id}' 비밀번호 업데이트 완료")
    else:
        print(f"❌ 사용자 '{user_id}' 비밀번호 업데이트 실패")

def show_active_users():
    """활성 사용자만 조회"""
    users = db_manager.get_active_users()
    if not users:
        print("활성 사용자가 없습니다.")
        return

    print("\n🟢 활성 사용자 목록:")
    print("-" * 30)
    for user in users:
        print(f"  - {user['user_id']}")


def main():
    parser = argparse.ArgumentParser(description="Auto Chultae 사용자 관리")
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')

    # 목록 조회
    subparsers.add_parser('list', help='모든 사용자 목록 조회')
    subparsers.add_parser('active', help='활성 사용자만 조회')

    # 사용자 추가
    add_parser = subparsers.add_parser('add', help='새 사용자 추가')
    add_parser.add_argument('user_id', help='사용자 ID')
    add_parser.add_argument('password', help='비밀번호')

    # 사용자 활성화/비활성화
    activate_parser = subparsers.add_parser('activate', help='사용자 활성화')
    activate_parser.add_argument('user_id', help='사용자 ID')

    deactivate_parser = subparsers.add_parser('deactivate', help='사용자 비활성화')
    deactivate_parser.add_argument('user_id', help='사용자 ID')

    # 비밀번호 변경
    password_parser = subparsers.add_parser('password', help='비밀번호 변경')
    password_parser.add_argument('user_id', help='사용자 ID')
    password_parser.add_argument('new_password', help='새 비밀번호')


    args = parser.parse_args()

    # 데이터베이스 연결 확인
    if not db_manager.test_connection():
        print("❌ 데이터베이스 연결 실패!")
        sys.exit(1)

    if args.command == 'list':
        list_users()
    elif args.command == 'active':
        show_active_users()
    elif args.command == 'add':
        add_user(args.user_id, args.password)
    elif args.command == 'activate':
        activate_user(args.user_id)
    elif args.command == 'deactivate':
        deactivate_user(args.user_id)
    elif args.command == 'password':
        update_password(args.user_id, args.new_password)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()