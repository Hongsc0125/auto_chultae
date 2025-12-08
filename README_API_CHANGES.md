# API 변경사항 및 사용자 변경 로그 기능

## 개요

사용자 정보 변경 내역을 추적하고 관리하기 위한 기능이 추가되었습니다.
- 비밀번호 변경 API
- 사용자 변경 로그 조회 API
- 모든 사용자 수정 작업에 대한 로그 자동 기록

## 데이터베이스 설정

### 1. 테이블 생성

PostgreSQL 데이터베이스에 새로운 `user_change_logs` 테이블을 생성해야 합니다.

```bash
# PostgreSQL에 연결
psql -U your_username -d your_database

# 또는 DATABASE_URL 환경변수 사용
psql $DATABASE_URL

# SQL 스키마 실행
\i schema_user_change_logs.sql
```

또는 직접 SQL 실행:

```bash
psql $DATABASE_URL < schema_user_change_logs.sql
```

### 2. 테이블 구조

`user_change_logs` 테이블은 다음 필드를 포함합니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | 로그 ID (PRIMARY KEY) |
| user_id | VARCHAR(100) | 변경된 사용자 ID |
| changed_by | VARCHAR(100) | 변경을 수행한 사용자 ID |
| change_type | VARCHAR(50) | 변경 타입 (password_change, activate, deactivate 등) |
| field_name | VARCHAR(50) | 변경된 필드 이름 |
| old_value | TEXT | 이전 값 (비밀번호 평문 포함) |
| new_value | TEXT | 새 값 (비밀번호 평문 포함) |
| changed_at | TIMESTAMP | 변경 시간 |
| ip_address | VARCHAR(45) | 변경 요청 IP 주소 |
| user_agent | TEXT | 변경 요청 브라우저 정보 |
| notes | TEXT | 추가 메모 |

**⚠️ 보안 주의사항**:
- 이 시스템은 크롤링을 위해 비밀번호를 평문으로 저장합니다
- `old_value`와 `new_value` 필드에 비밀번호 평문이 저장될 수 있습니다
- 프로덕션 환경에서는 데이터베이스 접근 권한을 엄격히 관리해야 합니다

## 새로운 API 엔드포인트

### 1. 비밀번호 변경 API

**Endpoint**: `PUT /api/web/user/password`

**인증**: JWT 토큰 필요

**요청 본문**:
```json
{
  "current_password": "현재_비밀번호",
  "new_password": "새_비밀번호"
}
```

**응답**:
```json
{
  "success": true,
  "message": "비밀번호가 변경되었습니다"
}
```

**에러 응답**:
- 400: 필수 필드 누락
- 401: 현재 비밀번호 불일치
- 404: 사용자를 찾을 수 없음
- 500: 서버 오류

**사용 예시**:
```bash
curl -X PUT http://localhost:8080/api/web/user/password \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "old_pass",
    "new_password": "new_pass"
  }'
```

### 2. 사용자 변경 로그 조회 API

**Endpoint**: `GET /api/web/user/change-logs`

**인증**: JWT 토큰 필요

**쿼리 파라미터**:
- `limit` (선택): 조회할 로그 수 (기본값: 50)

**응답**:
```json
{
  "success": true,
  "logs": [
    {
      "id": 1,
      "user_id": "user123",
      "changed_by": "user123",
      "change_type": "password_change",
      "field_name": "password",
      "old_value": "***",
      "new_value": "***",
      "changed_at": "2025-12-08T10:30:00",
      "ip_address": "127.0.0.1",
      "notes": null
    }
  ]
}
```

**참고**: API 응답에서 비밀번호 값(`field_name`이 `password`인 경우)은 보안을 위해 `***`로 마스킹됩니다.

**사용 예시**:
```bash
curl -X GET "http://localhost:8080/api/web/user/change-logs?limit=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 자동 로그 기록

다음 작업들은 자동으로 `user_change_logs` 테이블에 기록됩니다:

### 1. 회원가입
- `change_type`: `register`
- `field_name`: `user_account`
- IP 주소와 User-Agent 기록

### 2. 비밀번호 변경
- `change_type`: `password_change`
- `field_name`: `password`
- 이전 비밀번호와 새 비밀번호 평문 기록
- IP 주소와 User-Agent 기록

### 3. 사용자 활성화
- `change_type`: `activate`
- `field_name`: `is_active`
- `old_value`: `false`, `new_value`: `true`
- IP 주소와 User-Agent 기록

### 4. 사용자 비활성화
- `change_type`: `deactivate`
- `field_name`: `is_active`
- `old_value`: `true`, `new_value`: `false`
- IP 주소와 User-Agent 기록

### 5. 계정 삭제
- `change_type`: `delete_account`
- `field_name`: `user_account`
- 삭제 전에 로그 기록 (삭제 후에는 FK CASCADE로 로그도 함께 삭제됨)
- IP 주소와 User-Agent 기록

## 기존 API 변경사항

### 사용자 상태 변경 API (`PUT /api/web/user/status`)

이제 사용자 활성화/비활성화 시 자동으로 변경 로그가 기록됩니다.

**변경 전**:
```python
# 단순히 is_active 값만 업데이트
```

**변경 후**:
```python
# is_active 업데이트 + 변경 로그 자동 기록
# IP 주소와 User-Agent 포함
```

## CLI 도구 (manage_users.py)

CLI에서 비밀번호 변경 시에도 로그가 기록됩니다 (단, IP와 User-Agent는 기록되지 않음).

```bash
# 비밀번호 변경
python manage_users.py password user_id new_password
```

## db_manager.py 함수 변경사항

### 추가된 함수

1. **`log_user_change()`**: 사용자 변경 로그 기록
   ```python
   db_manager.log_user_change(
       user_id="user123",
       changed_by="user123",
       change_type="password_change",
       field_name="password",
       old_value="old_pass",
       new_value="new_pass",
       ip_address="127.0.0.1",
       user_agent="Mozilla/5.0...",
       notes="사용자 요청으로 비밀번호 변경"
   )
   ```

2. **`get_user_change_logs()`**: 특정 사용자의 변경 로그 조회
   ```python
   logs = db_manager.get_user_change_logs(user_id="user123", limit=50)
   ```

### 수정된 함수 (파라미터 추가)

1. **`update_user_password()`**
   - 추가 파라미터: `changed_by`, `ip_address`, `user_agent`
   - 변경 시 자동으로 로그 기록

2. **`activate_user()`**
   - 추가 파라미터: `changed_by`, `ip_address`, `user_agent`
   - 활성화 시 자동으로 로그 기록

3. **`deactivate_user()`**
   - 추가 파라미터: `changed_by`, `ip_address`, `user_agent`
   - 비활성화 시 자동으로 로그 기록

## 보안 고려사항

1. **평문 비밀번호 저장**
   - 크롤링 시스템 특성상 평문 저장 필요
   - 데이터베이스 접근 권한 관리 필수
   - 로그 테이블 접근 권한 더욱 엄격히 제한

2. **API 응답에서 비밀번호 마스킹**
   - 변경 로그 조회 API는 비밀번호를 `***`로 마스킹하여 반환
   - 실제 비밀번호는 데이터베이스에만 저장

3. **IP 및 User-Agent 기록**
   - 변경 이력 추적을 위해 IP와 브라우저 정보 기록
   - 개인정보 보호 정책 준수 필요

## 마이그레이션 가이드

### 1. 데이터베이스 백업
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### 2. 테이블 생성
```bash
psql $DATABASE_URL < schema_user_change_logs.sql
```

### 3. 코드 배포
```bash
# 서버 중지
./stop.sh

# 코드 업데이트
git pull  # 또는 파일 복사

# 서버 시작
./start.sh
```

### 4. 테스트
```bash
# 헬스체크
curl http://localhost:8080/api/health

# 비밀번호 변경 테스트 (JWT 토큰 필요)
# 먼저 로그인하여 토큰 획득 후 테스트
```

## 트러블슈팅

### 테이블 생성 오류
```
ERROR: relation "users" does not exist
```
→ FK 제약 조건 때문에 `users` 테이블이 먼저 존재해야 합니다.

### 로그 기록 실패
```
ERROR: insert or update on table "user_change_logs" violates foreign key constraint
```
→ `user_id`가 `users` 테이블에 존재하는지 확인하세요.

## 문의사항

기능 관련 문의사항이나 버그 리포트는 이슈로 등록해주세요.
