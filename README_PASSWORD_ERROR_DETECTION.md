# 비밀번호 오류 팝업 감지 및 예외 처리 기능

## 개요

크롤링 중 비밀번호 오류 팝업을 자동으로 감지하고, 해당 사용자를 "비밀번호 불일치" 상태로 전환하여 추가 크롤링을 차단하는 기능입니다.

## 주요 기능

### 1. 비밀번호 오류 팝업 자동 감지
- 로그인 버튼 클릭 후 5초 대기하며 비밀번호 오류 팝업 검사
- 다양한 오류 메시지 키워드 감지:
  - "비밀번호 입력 오류"
  - "비밀번호 오류"
  - "입력오류"
  - "로그인이 자동 차단"
  - "비밀번호가 일치하지 않습니다"
  - "비밀번호를 확인해주세요"

### 2. 비밀번호 불일치 상태 관리
- 팝업 감지 시 사용자를 `password_mismatch = true` 상태로 전환
- 비밀번호 불일치 상태인 사용자는 모든 크롤링 작업에서 차단
- 비밀번호 변경 시 자동으로 불일치 상태 해제

### 3. 로깅 및 추적
- 비밀번호 오류 감지 시 스크린샷 및 HTML 자동 저장
- 사용자 변경 로그에 비밀번호 불일치 감지 이력 기록
- 비밀번호 변경으로 상태 해제 시에도 로그 기록

## 데이터베이스 설정

### 1. 테이블 생성

PostgreSQL 데이터베이스에 `password_mismatch` 컬럼을 추가합니다.

```bash
psql $DATABASE_URL < schema_password_mismatch.sql
```

또는 직접 SQL 실행:

```sql
-- password_mismatch 컬럼 추가 (기본값: false)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_mismatch BOOLEAN DEFAULT false;

-- password_mismatch_at 컬럼 추가 (불일치 발생 시각 기록)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_mismatch_at TIMESTAMP;

-- 인덱스 추가 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_users_password_mismatch ON users(password_mismatch) WHERE password_mismatch = true;
```

### 2. 컬럼 설명

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| password_mismatch | BOOLEAN | false | 비밀번호 불일치 상태 (true: 크롤링 차단) |
| password_mismatch_at | TIMESTAMP | NULL | 비밀번호 불일치 발생 시각 |

## 작동 원리

### 1. 크롤링 시작 전 체크

**우선순위**: 가장 먼저 체크 (활성화 상태, 스케줄, 성공 이력보다 우선)

```python
# process_users() 함수에서
if db_manager.is_password_mismatch(user_id):
    logger.warning(f"[{user_id}] 비밀번호 불일치 상태 - 크롤링 차단")
    continue  # 해당 사용자 스킵
```

**차단 범위**:
- 모든 출근/퇴근 크롤링 작업
- 워치독 스케줄러에서 실행되는 자동 크롤링
- 수동 실행 명령

### 2. 로그인 후 팝업 감지

**로직**:
1. 로그인 버튼 클릭
2. **5초 대기** (팝업이 나타날 시간 부여)
3. JavaScript로 페이지의 모든 알림 팝업 검사
4. 비밀번호 오류 관련 키워드 포함 여부 확인

**감지 시 동작**:
```python
if password_error:
    # 1. 스크린샷 저장
    page.screenshot(path=f"screenshots/password_error_{user_id}_{timestamp}.png")

    # 2. HTML 저장
    save_html(f"screenshots/password_error_{user_id}_{timestamp}.html")

    # 3. 데이터베이스 상태 업데이트
    db_manager.set_password_mismatch(user_id, changed_by="system")

    # 4. 크롤링 중단
    raise Exception(f"비밀번호 불일치: {error_message}")
```

### 3. 비밀번호 변경으로 상태 해제

**API를 통한 변경**:
```python
# main_server.py - PUT /api/web/user/password
if db_manager.update_user_password(user_id, new_password):
    if db_manager.is_password_mismatch(user_id):
        db_manager.clear_password_mismatch(user_id)
        # 다음 크롤링부터 정상 진행 가능
```

**CLI를 통한 변경**:
```bash
python manage_users.py password user123 new_password
# ✅ 사용자 'user123' 비밀번호 불일치 상태 해제
# ✅ 사용자 'user123' 비밀번호 업데이트 완료
```

## 사용 시나리오

### 시나리오 1: 비밀번호 오류 발생

```
1. 크롤링 시작
2. 로그인 시도
3. 비밀번호 오류 팝업 감지
   → "비밀번호 입력 오류 5회 초과 시 로그인이 자동 차단됩니다. 비밀번호 1회 입력오류"
4. 시스템 동작:
   - 스크린샷 저장: screenshots/password_error_user123_1733654321.png
   - HTML 저장: screenshots/password_error_user123_1733654321.html
   - 데이터베이스: password_mismatch = true 설정
   - 크롤링 즉시 중단
5. 이후 모든 크롤링 시도:
   - "⚠️ 비밀번호 불일치 상태 - 크롤링 차단" 메시지와 함께 스킵
```

### 시나리오 2: 비밀번호 변경 후 복구

```
1. 사용자가 웹 UI에서 비밀번호 변경
   - 현재 비밀번호: old_pass (틀림)
   - 새 비밀번호: new_pass (정확)
2. API 호출: PUT /api/web/user/password
3. 시스템 동작:
   - 비밀번호 업데이트 성공
   - password_mismatch = false 자동 설정
   - 변경 로그 기록
4. 다음 크롤링:
   - 정상적으로 실행됨
   - 새 비밀번호로 로그인 성공
```

### 시나리오 3: CLI로 복구

```bash
# 1. 현재 상태 확인
python manage_users.py list
# user123        email@example.com    활성    2025-12-08

# 2. 비밀번호 변경
python manage_users.py password user123 correct_password
# ✅ 사용자 'user123' 비밀번호 불일치 상태 해제
# ✅ 사용자 'user123' 비밀번호 업데이트 완료

# 3. 다음 크롤링부터 정상 진행
```

## API 변경사항

### 비밀번호 변경 API 강화

**Endpoint**: `PUT /api/web/user/password`

**추가 기능**:
- 비밀번호 변경 성공 시 `password_mismatch` 자동 해제
- 해제 이력 `user_change_logs`에 기록

**응답**:
```json
{
  "success": true,
  "message": "비밀번호가 변경되었습니다"
}
```

**로그 기록**:
```
INFO - 사용자 user123 비밀번호 불일치 상태 해제
INFO - 사용자 user123 비밀번호 변경 완료
```

## db_manager.py 새로운 함수

### 1. `set_password_mismatch(user_id, changed_by, ip_address, user_agent)`

비밀번호 불일치 상태로 설정합니다.

```python
db_manager.set_password_mismatch(
    user_id="user123",
    changed_by="system"
)
```

**동작**:
- `password_mismatch = true` 설정
- `password_mismatch_at`에 현재 시각 기록
- `user_change_logs`에 변경 이력 기록

### 2. `clear_password_mismatch(user_id, changed_by, ip_address, user_agent)`

비밀번호 불일치 상태를 해제합니다.

```python
db_manager.clear_password_mismatch(
    user_id="user123",
    changed_by="user123",
    ip_address="127.0.0.1",
    user_agent="Mozilla/5.0..."
)
```

**동작**:
- `password_mismatch = false` 설정
- `password_mismatch_at = NULL` 리셋
- `user_change_logs`에 해제 이력 기록

### 3. `is_password_mismatch(user_id)`

비밀번호 불일치 상태를 확인합니다.

```python
if db_manager.is_password_mismatch("user123"):
    print("비밀번호 불일치 상태 - 크롤링 차단")
else:
    print("정상 상태 - 크롤링 가능")
```

## auto_chultae.py 새로운 함수

### `check_password_error_popup(page, user_id)`

비밀번호 오류 팝업을 검사합니다.

```python
password_error, error_message = check_password_error_popup(page, user_id)

if password_error:
    # 비밀번호 오류 처리
    logger.error(f"비밀번호 오류: {error_message}")
```

**반환값**:
- `(True, "오류 메시지")`: 팝업 감지됨
- `(False, None)`: 팝업 없음 (정상)

**검사 대상 팝업 선택자**:
```javascript
'.system_alert_box.alert_guide'
'.alert_guide'
'[class*="alert"]'
```

## 변경 로그 타입

새로운 `change_type` 추가:

| change_type | 설명 |
|-------------|------|
| password_mismatch_detected | 비밀번호 오류 팝업 감지 (자동) |
| password_mismatch_cleared | 비밀번호 불일치 상태 해제 |

**로그 조회**:
```bash
curl -X GET "http://localhost:8080/api/web/user/change-logs" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**응답 예시**:
```json
{
  "success": true,
  "logs": [
    {
      "id": 10,
      "change_type": "password_mismatch_detected",
      "field_name": "password_mismatch",
      "old_value": "false",
      "new_value": "true",
      "changed_by": "system",
      "changed_at": "2025-12-08T14:30:00",
      "notes": "크롤링 중 비밀번호 오류 팝업 감지"
    },
    {
      "id": 11,
      "change_type": "password_mismatch_cleared",
      "field_name": "password_mismatch",
      "old_value": "true",
      "new_value": "false",
      "changed_by": "user123",
      "changed_at": "2025-12-08T15:00:00",
      "notes": "비밀번호 변경으로 불일치 상태 해제"
    }
  ]
}
```

## 로그 파일 확인

### 비밀번호 오류 감지 시 로그

```
INFO - [user123] [punch_in] 로그인 버튼 클릭 완료
INFO - [user123] [punch_in] 비밀번호 오류 팝업 검사 대기 중 (5초)...
INFO - [user123] 비밀번호 오류 팝업 검사 시작...
ERROR - [user123] ⚠️ 비밀번호 오류 팝업 감지: 비밀번호 입력 오류 5회 초과 시 로그인이 자동 차단됩니다. 비밀번호 1회 입력오류
ERROR - [user123] [punch_in] 비밀번호 오류 감지 - 사용자를 비밀번호 불일치 상태로 전환
ERROR - [user123] [punch_in] 비밀번호 오류 스크린샷 저장: screenshots/password_error_user123_1733654321.png
ERROR - [user123] [punch_in] 비밀번호 오류 HTML 저장: screenshots/password_error_user123_1733654321.html
WARNING - 사용자 user123 비밀번호 불일치 상태로 설정
ERROR - [user123] [punch_in] 오류 발생: 비밀번호 불일치: 비밀번호 입력 오류...
```

### 크롤링 차단 시 로그

```
INFO - === 사용자 처리 시작: user123, 작업: punch_in ===
WARNING - [user123] [punch_in] ⚠️ 비밀번호 불일치 상태 - 크롤링 차단 (비밀번호를 변경해주세요)
```

### 비밀번호 변경으로 복구 시 로그

```
INFO - 사용자 user123 비밀번호 불일치 상태 해제
INFO - 사용자 user123 비밀번호 변경 완료
```

## 보안 고려사항

1. **비밀번호 오류 횟수 제한**
   - 시스템이 5회 오류를 감지하기 전에 자동 차단
   - 사용자에게 즉시 알림 필요

2. **자동 복구 방지**
   - 비밀번호 불일치 상태는 자동으로 해제되지 않음
   - 반드시 비밀번호 변경을 통해서만 해제 가능

3. **로그 추적**
   - 모든 비밀번호 오류 감지 이력 기록
   - 스크린샷과 HTML을 증거로 보관

## 트러블슈팅

### 문제 1: 팝업 감지가 안 됨

**원인**: 팝업 선택자가 다를 수 있음

**해결**:
1. 스크린샷 확인: `screenshots/error_*.png`
2. HTML 저장본 확인: `screenshots/error_*.html`
3. 팝업의 실제 선택자 확인
4. `check_password_error_popup()` 함수의 선택자 수정

### 문제 2: 정상 상태인데 크롤링이 안 됨

**원인**: `password_mismatch`가 true로 남아있음

**해결**:
```bash
# CLI로 직접 비밀번호 변경
python manage_users.py password user123 new_password

# 또는 SQL로 직접 해제
psql $DATABASE_URL -c "UPDATE users SET password_mismatch = false WHERE user_id = 'user123';"
```

### 문제 3: 5초 대기가 너무 길거나 짧음

**현재 설정**: 5초 고정

**변경 방법**:
`auto_chultae.py` 753행 수정:
```python
# 기존
time.sleep(5)

# 변경
time.sleep(3)  # 3초로 단축
```

## 마이그레이션 가이드

### 1. 데이터베이스 백업
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

### 2. 스키마 적용
```bash
psql $DATABASE_URL < schema_password_mismatch.sql
```

### 3. 코드 배포
```bash
./stop.sh
git pull
./start.sh
```

### 4. 테스트
```bash
# 1. 크롤링 로그 확인
tail -f logs/auto_chultae_$(date +%Y%m%d).log

# 2. 비밀번호 변경 테스트
curl -X PUT http://localhost:8080/api/web/user/password \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "old", "new_password": "new"}'
```

## 요약

이 기능은 크롤링 시스템을 더욱 안정적이고 안전하게 만들어줍니다:

✅ **자동 감지**: 비밀번호 오류 팝업 즉시 감지
✅ **자동 차단**: 문제 계정의 추가 크롤링 방지
✅ **증거 보관**: 스크린샷과 HTML 자동 저장
✅ **간편 복구**: 비밀번호 변경만으로 자동 해제
✅ **완전 추적**: 모든 이력을 로그에 기록

**중요**: 비밀번호 오류가 감지되면 즉시 비밀번호를 변경하여 계정 차단을 방지하세요!
