# Auto Chultae API 명세서

## 📋 목차
- [기본 정보](#기본-정보)
- [인증](#인증)
- [에러 코드](#에러-코드)
- [API 엔드포인트](#api-엔드포인트)
  - [인증 관련](#1-인증-관련)
  - [사용자 정보](#2-사용자-정보)
  - [출퇴근 기록](#3-출퇴근-기록)
  - [스케줄 관리](#4-스케줄-관리)
  - [서버 상태](#5-서버-상태)

---

## 기본 정보

### Base URL
```
http://localhost:8080/api
```

프로덕션 환경에서는 실제 서버 주소로 변경하세요.

### Content-Type
모든 요청과 응답은 JSON 형식입니다.
```
Content-Type: application/json
```

### CORS
다음 오리진에서 접근 가능:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://localhost:5174`

---

## 인증

### JWT 토큰 방식
로그인 후 받은 `access_token`을 Authorization 헤더에 포함하여 요청합니다.

```http
Authorization: Bearer {access_token}
```

### 토큰 유효기간
- **8시간** (480분)

### 인증이 필요한 엔드포인트
로그인, 회원가입을 제외한 모든 `/api/web/*` 엔드포인트는 JWT 토큰이 필요합니다.

---

## 에러 코드

### HTTP 상태 코드

| 코드 | 의미 | 설명 |
|------|------|------|
| 200 | OK | 성공 |
| 201 | Created | 리소스 생성 성공 |
| 400 | Bad Request | 잘못된 요청 (필수 필드 누락, 유효성 검증 실패) |
| 401 | Unauthorized | 인증 실패 (토큰 없음, 만료, 비밀번호 불일치) |
| 404 | Not Found | 리소스를 찾을 수 없음 |
| 500 | Internal Server Error | 서버 오류 |

### 에러 응답 형식
```json
{
  "error": "에러 메시지"
}
```

---

## API 엔드포인트

## 1. 인증 관련

### 1.1 회원가입

새로운 사용자 계정을 생성합니다.

**Endpoint**
```
POST /web/auth/register
```

**인증 필요**: ❌ No

**요청 본문**
```json
{
  "user_id": "string",      // 필수: 사용자 ID (영문, 숫자)
  "password": "string",     // 필수: 비밀번호
  "email": "string"         // 필수: 이메일 주소
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "회원가입이 완료되었습니다"
}
```

**에러 응답**
```json
// 400 - 필드 누락
{
  "error": "모든 필드를 입력해주세요"
}

// 400 - 사용자 ID 중복
{
  "error": "이미 존재하는 사용자 ID입니다"
}

// 500 - 서버 오류
{
  "error": "회원가입 중 오류가 발생했습니다"
}
```

**사용 예시**
```javascript
const register = async (userId, password, email) => {
  const response = await fetch('http://localhost:8080/api/web/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: userId,
      password: password,
      email: email
    })
  });

  const data = await response.json();
  return data;
};
```

---

### 1.2 로그인

사용자 인증 후 JWT 토큰을 발급합니다.

**Endpoint**
```
POST /web/auth/login
```

**인증 필요**: ❌ No

**요청 본문**
```json
{
  "user_id": "string",      // 필수: 사용자 ID
  "password": "string"      // 필수: 비밀번호
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user123",
    "username": "user123",
    "email": "user@example.com"
  }
}
```

**에러 응답**
```json
// 400 - 필드 누락
{
  "error": "사용자 ID와 비밀번호를 입력해주세요"
}

// 401 - 인증 실패
{
  "error": "사용자 ID 또는 비밀번호가 잘못되었습니다"
}
```

**사용 예시**
```javascript
const login = async (userId, password) => {
  const response = await fetch('http://localhost:8080/api/web/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_id: userId,
      password: password
    })
  });

  const data = await response.json();

  if (data.success) {
    // 토큰을 로컬 스토리지에 저장
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
  }

  return data;
};
```

---

## 2. 사용자 정보

### 2.1 비밀번호 변경 ⭐ 신규

현재 사용자의 비밀번호를 변경합니다.

**Endpoint**
```
PUT /web/user/password
```

**인증 필요**: ✅ Yes (JWT)

**요청 본문**
```json
{
  "current_password": "string",  // 필수: 현재 비밀번호
  "new_password": "string"       // 필수: 새 비밀번호
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "비밀번호가 변경되었습니다"
}
```

**에러 응답**
```json
// 400 - 필드 누락
{
  "error": "현재 비밀번호와 새 비밀번호를 모두 입력해주세요"
}

// 401 - 현재 비밀번호 불일치
{
  "error": "현재 비밀번호가 일치하지 않습니다"
}

// 404 - 사용자 없음
{
  "error": "사용자를 찾을 수 없습니다"
}

// 500 - 서버 오류
{
  "error": "비밀번호 변경에 실패했습니다"
}
```

**사용 예시**
```javascript
const changePassword = async (currentPassword, newPassword) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/user/password', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword
    })
  });

  const data = await response.json();
  return data;
};
```

---

### 2.2 사용자 활성화 상태 조회

현재 사용자의 활성화 상태를 조회합니다.

**Endpoint**
```
GET /web/user/status
```

**인증 필요**: ✅ Yes (JWT)

**요청 파라미터**: 없음

**응답 (200 OK)**
```json
{
  "success": true,
  "is_active": true  // true: 활성, false: 비활성
}
```

**에러 응답**
```json
// 404 - 사용자 없음
{
  "error": "사용자를 찾을 수 없습니다"
}
```

**사용 예시**
```javascript
const getUserStatus = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/user/status', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const data = await response.json();
  return data;
};
```

---

### 2.3 사용자 활성화 상태 변경

현재 사용자의 활성화/비활성화 상태를 변경합니다.

**Endpoint**
```
PUT /web/user/status
```

**인증 필요**: ✅ Yes (JWT)

**요청 본문**
```json
{
  "is_active": true  // true: 활성화, false: 비활성화
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "상태가 변경되었습니다"
}
```

**에러 응답**
```json
// 400 - 필드 누락
{
  "error": "is_active 값이 필요합니다"
}

// 404 - 사용자 없음
{
  "error": "사용자를 찾을 수 없습니다"
}
```

**사용 예시**
```javascript
const updateUserStatus = async (isActive) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/user/status', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      is_active: isActive
    })
  });

  const data = await response.json();
  return data;
};
```

---

### 2.4 사용자 변경 로그 조회 ⭐ 신규

현재 사용자의 정보 변경 이력을 조회합니다.

**Endpoint**
```
GET /web/user/change-logs
```

**인증 필요**: ✅ Yes (JWT)

**쿼리 파라미터**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| limit | integer | ❌ | 50 | 조회할 로그 개수 (최대값 없음) |

**응답 (200 OK)**
```json
{
  "success": true,
  "logs": [
    {
      "id": 1,
      "user_id": "user123",
      "changed_by": "user123",
      "change_type": "password_change",  // register, password_change, activate, deactivate, delete_account
      "field_name": "password",
      "old_value": "***",  // 비밀번호는 마스킹됨
      "new_value": "***",  // 비밀번호는 마스킹됨
      "changed_at": "2025-12-08T10:30:00",
      "ip_address": "127.0.0.1",
      "notes": null
    },
    {
      "id": 2,
      "user_id": "user123",
      "changed_by": "user123",
      "change_type": "activate",
      "field_name": "is_active",
      "old_value": "false",
      "new_value": "true",
      "changed_at": "2025-12-08T09:15:00",
      "ip_address": "127.0.0.1",
      "notes": null
    }
  ]
}
```

**change_type 종류**
| 타입 | 설명 |
|------|------|
| register | 회원가입 |
| password_change | 비밀번호 변경 |
| activate | 사용자 활성화 |
| deactivate | 사용자 비활성화 |
| delete_account | 계정 삭제 |

**에러 응답**
```json
// 500 - 서버 오류
{
  "error": "변경 로그 조회 중 오류가 발생했습니다"
}
```

**사용 예시**
```javascript
const getChangeLogs = async (limit = 50) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8080/api/web/user/change-logs?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );

  const data = await response.json();
  return data;
};
```

---

### 2.5 계정 삭제

현재 사용자의 계정을 완전히 삭제합니다. 삭제된 데이터는 복구할 수 없습니다.

**Endpoint**
```
DELETE /web/user/delete
```

**인증 필요**: ✅ Yes (JWT)

**요청 본문**: 없음

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "계정이 완전히 삭제되었습니다"
}
```

**삭제되는 데이터**
- 사용자 계정 정보
- 출석 로그 (attendance_logs)
- 하트비트 로그 (heartbeat_status)
- 사용자 변경 로그 (user_change_logs) - CASCADE 삭제

**에러 응답**
```json
// 404 - 사용자 없음
{
  "error": "사용자를 찾을 수 없습니다"
}

// 500 - 서버 오류
{
  "error": "계정 삭제 중 오류가 발생했습니다"
}
```

**사용 예시**
```javascript
const deleteAccount = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/user/delete', {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const data = await response.json();

  if (data.success) {
    // 로컬 스토리지 정리
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  }

  return data;
};
```

---

## 3. 출퇴근 기록

### 3.1 오늘의 출근 상태 조회

현재 사용자의 오늘 출근/퇴근 시간을 조회합니다.

**Endpoint**
```
GET /web/user/summary
```

**인증 필요**: ✅ Yes (JWT)

**요청 파라미터**: 없음

**응답 (200 OK)**
```json
{
  "success": true,
  "status": {
    "punchIn": "08:35",   // 출근 시간 (HH:MM), 없으면 빈 문자열
    "punchOut": "18:10"   // 퇴근 시간 (HH:MM), 없으면 빈 문자열
  }
}
```

**사용 예시**
```javascript
const getTodayStatus = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/user/summary', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const data = await response.json();
  return data;
};
```

---

### 3.2 출퇴근 기록 조회

현재 사용자의 출퇴근 시도 기록을 조회합니다.

**Endpoint**
```
GET /web/user/attendance
```

**인증 필요**: ✅ Yes (JWT)

**쿼리 파라미터**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| limit | integer | ❌ | 50 | 조회할 로그 개수 |

**응답 (200 OK)**
```json
{
  "success": true,
  "logs": [
    {
      "id": 123,
      "user_id": "user123",
      "action_type": "punch_in",  // punch_in 또는 punch_out
      "status": "success",        // success, failed, already_done
      "message": "",
      "timestamp": "2025-12-08T08:35:12"
    },
    {
      "id": 124,
      "user_id": "user123",
      "action_type": "punch_out",
      "status": "success",
      "message": "",
      "timestamp": "2025-12-08T18:10:05"
    }
  ]
}
```

**status 종류**
| 상태 | 설명 |
|------|------|
| success | 성공 |
| failed | 실패 |
| already_done | 이미 처리됨 |

**사용 예시**
```javascript
const getAttendanceLogs = async (limit = 50) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8080/api/web/user/attendance?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );

  const data = await response.json();
  return data;
};
```

---

### 3.3 출퇴근 하트비트 조회

특정 출퇴근 기록의 상세 진행 과정을 조회합니다.

**Endpoint**
```
GET /web/user/attendance/{attendance_id}/heartbeat
```

**인증 필요**: ✅ Yes (JWT)

**경로 파라미터**
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| attendance_id | integer | ✅ | 출퇴근 기록 ID |

**응답 (200 OK)**
```json
{
  "success": true,
  "heartbeats": [
    {
      "id": 1,
      "stage": "login_start",
      "user_id": "user123",
      "action_type": "punch_in",
      "pid": 12345,
      "timestamp": "2025-12-08T08:35:10",
      "attendance_log_id": 123
    },
    {
      "id": 2,
      "stage": "button_click",
      "user_id": "user123",
      "action_type": "punch_in",
      "pid": 12345,
      "timestamp": "2025-12-08T08:35:12",
      "attendance_log_id": 123
    }
  ]
}
```

**사용 예시**
```javascript
const getHeartbeats = async (attendanceId) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8080/api/web/user/attendance/${attendanceId}/heartbeat`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );

  const data = await response.json();
  return data;
};
```

---

## 4. 스케줄 관리

### 4.1 월별 스케줄 조회

특정 월의 출근 스케줄을 조회합니다.

**Endpoint**
```
GET /web/schedules
```

**인증 필요**: ✅ Yes (JWT)

**쿼리 파라미터**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| year | integer | ❌ | 현재 연도 | 조회할 연도 (예: 2025) |
| month | integer | ❌ | 현재 월 | 조회할 월 (1-12) |

**응답 (200 OK)**
```json
{
  "success": true,
  "schedules": [
    {
      "date": "2025-12-01",
      "is_workday": true,           // 출근일 여부
      "schedule_type": "regular",   // regular 또는 custom
      "punch_in_time": "08:00",     // 출근 시간
      "punch_out_time": "18:00",    // 퇴근 시간
      "notes": null                 // 메모
    },
    {
      "date": "2025-12-06",
      "is_workday": false,
      "schedule_type": "regular",
      "punch_in_time": null,
      "punch_out_time": null,
      "notes": null
    }
  ]
}
```

**사용 예시**
```javascript
const getSchedules = async (year, month) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8080/api/web/schedules?year=${year}&month=${month}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );

  const data = await response.json();
  return data;
};
```

---

### 4.2 연간 스케줄 조회

1년치 스케줄을 한 번에 조회합니다. (성능 최적화용)

**Endpoint**
```
GET /web/schedules/yearly
```

**인증 필요**: ✅ Yes (JWT)

**쿼리 파라미터**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| year | integer | ❌ | 현재 연도 | 조회할 연도 |

**응답 (200 OK)**
```json
{
  "success": true,
  "schedules": [
    {
      "date": "2025-01-01",
      "is_workday": false,
      "schedule_type": "regular"
    },
    {
      "date": "2025-01-02",
      "is_workday": true,
      "schedule_type": "regular"
    }
    // ... 365개 항목
  ],
  "year": 2025,
  "count": 365
}
```

**사용 예시**
```javascript
const getYearlySchedules = async (year) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8080/api/web/schedules/yearly?year=${year}`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );

  const data = await response.json();
  return data;
};
```

---

### 4.3 스케줄 토글

특정 날짜의 출근/휴무 상태를 전환합니다.

**Endpoint**
```
POST /web/schedules/toggle
```

**인증 필요**: ✅ Yes (JWT)

**요청 본문**
```json
{
  "date": "2025-12-08"  // 필수: YYYY-MM-DD 형식
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "date": "2025-12-08",
  "is_workday": true,        // 토글 후 상태
  "schedule_type": "custom"
}
```

**에러 응답**
```json
// 400 - 날짜 누락
{
  "error": "날짜가 필요합니다"
}
```

**사용 예시**
```javascript
const toggleSchedule = async (date) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/schedules/toggle', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      date: date  // "2025-12-08"
    })
  });

  const data = await response.json();
  return data;
};
```

---

### 4.4 월별 기본 스케줄 생성

특정 월의 기본 평일 스케줄을 자동 생성합니다. (월-금: 출근, 토-일: 휴무)

**Endpoint**
```
POST /web/schedules/bulk
```

**인증 필요**: ✅ Yes (JWT)

**요청 본문**
```json
{
  "year": 2025,   // 선택: 기본값은 현재 연도
  "month": 12     // 선택: 기본값은 현재 월
}
```

**응답 (200 OK)**
```json
{
  "success": true,
  "message": "2025년 12월 기본 스케줄이 생성되었습니다"
}
```

**참고**
- 이미 스케줄이 있는 날짜는 건너뜁니다
- 평일(월-금)은 출근일, 주말(토-일)은 휴무로 자동 설정됩니다
- 기본 출근 시간: 08:00, 퇴근 시간: 18:00

**사용 예시**
```javascript
const createBulkSchedules = async (year, month) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/schedules/bulk', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      year: year,
      month: month
    })
  });

  const data = await response.json();
  return data;
};
```

---

## 5. 서버 상태

### 5.1 서버 상태 조회

메인 서버와 워치독 서버의 상태를 조회합니다.

**Endpoint**
```
GET /web/server/status
```

**인증 필요**: ✅ Yes (JWT)

**요청 파라미터**: 없음

**응답 (200 OK)**
```json
{
  "success": true,
  "status": {
    "main": true,       // 메인 서버 온라인 여부
    "watchdog": true    // 워치독 서버 온라인 여부
  }
}
```

**사용 예시**
```javascript
const getServerStatus = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8080/api/web/server/status', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const data = await response.json();
  return data;
};
```

---

### 5.2 헬스체크

서버의 기본 상태를 확인합니다.

**Endpoint**
```
GET /health
```

**인증 필요**: ❌ No

**요청 파라미터**: 없음

**응답 (200 OK)**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-08T10:30:00",
  "database": "connected",
  "pid": 12345
}
```

**사용 예시**
```javascript
const healthCheck = async () => {
  const response = await fetch('http://localhost:8080/api/health', {
    method: 'GET'
  });

  const data = await response.json();
  return data;
};
```

---

## 📚 부록

### A. 공통 에러 처리

프론트엔드에서 공통적으로 사용할 수 있는 에러 처리 함수 예시:

```javascript
const handleApiError = (response, data) => {
  switch (response.status) {
    case 400:
      alert(`잘못된 요청: ${data.error}`);
      break;
    case 401:
      alert('로그인이 필요합니다.');
      // 로그인 페이지로 리다이렉트
      localStorage.removeItem('access_token');
      window.location.href = '/login';
      break;
    case 404:
      alert(`리소스를 찾을 수 없습니다: ${data.error}`);
      break;
    case 500:
      alert(`서버 오류가 발생했습니다: ${data.error}`);
      break;
    default:
      alert(`오류가 발생했습니다: ${data.error || '알 수 없는 오류'}`);
  }
};

// 사용 예시
const apiCall = async () => {
  const response = await fetch('...');
  const data = await response.json();

  if (!response.ok) {
    handleApiError(response, data);
    return null;
  }

  return data;
};
```

---

### B. Axios 사용 예시

Axios를 사용하는 경우:

```javascript
import axios from 'axios';

// Axios 인스턴스 생성
const api = axios.create({
  baseURL: 'http://localhost:8080/api',
  headers: {
    'Content-Type': 'application/json'
  }
});

// 요청 인터셉터: JWT 토큰 자동 추가
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 응답 인터셉터: 에러 처리
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 로그아웃 처리
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 사용 예시
const login = async (userId, password) => {
  try {
    const response = await api.post('/web/auth/login', {
      user_id: userId,
      password: password
    });

    if (response.data.success) {
      localStorage.setItem('access_token', response.data.access_token);
    }

    return response.data;
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
};
```

---

### C. TypeScript 타입 정의

TypeScript를 사용하는 경우 타입 정의 예시:

```typescript
// types/api.ts

// 공통 응답 타입
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  error?: string;
  [key: string]: any;
}

// 로그인 응답
export interface LoginResponse extends ApiResponse {
  access_token: string;
  user: {
    id: string;
    username: string;
    email: string;
  };
}

// 출퇴근 로그
export interface AttendanceLog {
  id: number;
  user_id: string;
  action_type: 'punch_in' | 'punch_out';
  status: 'success' | 'failed' | 'already_done';
  message: string;
  timestamp: string;
}

// 변경 로그
export interface ChangeLog {
  id: number;
  user_id: string;
  changed_by: string;
  change_type: 'register' | 'password_change' | 'activate' | 'deactivate' | 'delete_account';
  field_name: string;
  old_value: string;
  new_value: string;
  changed_at: string;
  ip_address: string;
  notes: string | null;
}

// 스케줄
export interface Schedule {
  date: string;
  is_workday: boolean;
  schedule_type: 'regular' | 'custom';
  punch_in_time: string | null;
  punch_out_time: string | null;
  notes: string | null;
}
```

---

### D. React Hook 예시

React에서 사용할 수 있는 커스텀 훅 예시:

```javascript
// hooks/useAuth.js
import { useState, useEffect } from 'react';

export const useAuth = () => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const storedToken = localStorage.getItem('access_token');
    const storedUser = localStorage.getItem('user');

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));
      setIsAuthenticated(true);
    }
  }, []);

  const login = async (userId, password) => {
    const response = await fetch('http://localhost:8080/api/web/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ user_id: userId, password: password })
    });

    const data = await response.json();

    if (data.success) {
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
      setIsAuthenticated(true);
    }

    return data;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setIsAuthenticated(false);
  };

  return { user, token, isAuthenticated, login, logout };
};
```

---

## 📞 문의

API 관련 문의사항이나 버그 리포트는 이슈로 등록해주세요.

**버전**: 1.0.0
**최종 업데이트**: 2025-12-08
