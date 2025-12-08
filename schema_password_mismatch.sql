-- 비밀번호 불일치 상태 추가
-- users 테이블에 password_mismatch 플래그 추가

-- password_mismatch 컬럼 추가 (기본값: false)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_mismatch BOOLEAN DEFAULT false;

-- password_mismatch_at 컬럼 추가 (불일치 발생 시각 기록)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_mismatch_at TIMESTAMP;

-- 인덱스 추가 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_users_password_mismatch ON users(password_mismatch) WHERE password_mismatch = true;

-- 컬럼 설명 주석
COMMENT ON COLUMN users.password_mismatch IS '비밀번호 불일치 상태 (true: 불일치로 크롤링 차단, false: 정상)';
COMMENT ON COLUMN users.password_mismatch_at IS '비밀번호 불일치 발생 시각';
