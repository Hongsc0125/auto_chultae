-- 사용자 수정 로그 테이블
-- 모든 사용자 정보 변경 내역을 기록하는 테이블

CREATE TABLE IF NOT EXISTS user_change_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    changed_by VARCHAR(100) NOT NULL,  -- 변경을 수행한 사용자 (본인 또는 관리자)
    change_type VARCHAR(50) NOT NULL,  -- password_change, activate, deactivate, email_change 등
    field_name VARCHAR(50),            -- 변경된 필드 이름 (password, email, is_active 등)
    old_value TEXT,                    -- 이전 값 (비밀번호는 평문 저장)
    new_value TEXT,                    -- 새 값 (비밀번호는 평문 저장)
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),            -- IPv4 또는 IPv6
    user_agent TEXT,                   -- 브라우저 정보
    notes TEXT,                        -- 추가 메모
    CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 인덱스 생성 (조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_user_change_logs_user_id ON user_change_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_change_logs_changed_at ON user_change_logs(changed_at);
CREATE INDEX IF NOT EXISTS idx_user_change_logs_change_type ON user_change_logs(change_type);

-- 테이블 설명 주석
COMMENT ON TABLE user_change_logs IS '사용자 정보 변경 이력 로그';
COMMENT ON COLUMN user_change_logs.user_id IS '변경된 사용자 ID';
COMMENT ON COLUMN user_change_logs.changed_by IS '변경을 수행한 사용자 ID';
COMMENT ON COLUMN user_change_logs.change_type IS '변경 타입 (password_change, activate, deactivate, email_change 등)';
COMMENT ON COLUMN user_change_logs.field_name IS '변경된 필드 이름';
COMMENT ON COLUMN user_change_logs.old_value IS '이전 값 (보안상 민감한 정보 포함, 평문)';
COMMENT ON COLUMN user_change_logs.new_value IS '새 값 (보안상 민감한 정보 포함, 평문)';
COMMENT ON COLUMN user_change_logs.changed_at IS '변경 시간';
COMMENT ON COLUMN user_change_logs.ip_address IS '변경 요청 IP 주소';
COMMENT ON COLUMN user_change_logs.user_agent IS '변경 요청 브라우저 정보';
