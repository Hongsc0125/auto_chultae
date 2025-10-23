# 출퇴근 자동화 시스템 - 크론탭 버전

## 사용 방법

### 크론탭 설정

```bash
crontab -e
```

아래 내용 추가:

```cron
# 출근: 평일 오전 8시 5분
5 8 * * 1-5 cd /home/hsc0125/auto_chultae && ./start.sh punch_in && ./stop.sh

# 퇴근: 평일 오후 6시 5분
5 18 * * 1-5 cd /home/hsc0125/auto_chultae && ./start.sh punch_out && ./stop.sh
```

## 동작 방식

1. **start.sh punch_in** 실행:
   - 메인 서버 시작
   - watchdog_simple.py 실행 (DB 체크 후 출근 명령 전송)
   - 종료

2. **stop.sh** 실행:
   - 메인 서버 종료
   - 모든 프로세스 정리

## 수동 실행

```bash
# 출근
./start.sh punch_in
./stop.sh

# 퇴근
./start.sh punch_out
./stop.sh
```

## 로그 확인

```bash
# 워치독 로그
tail -f logs/watchdog_$(date +%Y%m%d).log

# 메인 서버 로그
tail -f logs/main_server_$(date +%Y%m%d).log

# 크롤링 로그
tail -f logs/auto_chultae_$(date +%Y%m%d).log
```

## 백업 파일

- `watchdog.py.backup` - 기존 워치독 (스케줄러 포함)
- `main_server.py.backup` - 기존 메인 서버 (subprocess 포함)
- `start.sh.backup3`, `stop.sh.backup` - 기존 start/stop 스크립트

## 변경 사항

### watchdog_simple.py (신규)
- 크론탭에서 1회 실행
- DB 체크: 스케줄, 성공 이력 확인
- 성공 이력 없으면 메인 서버에 명령 전송

### main_server.py
- subprocess 제거
- punch_in(), punch_out() 직접 호출

### start.sh / stop.sh
- start.sh [punch_in|punch_out]: 서버 시작 + 출퇴근 실행
- stop.sh: 서버 종료
