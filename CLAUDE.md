# telegram_dev_bot

텔레그램으로 Claude(claude-sonnet-4-6)와 대화하며 코드를 생성/실행/수정하는 개발용 봇.

## 구조
- `bot.py` — 텔레그램 봇 진입점 (python-telegram-bot 20.x). 명령어 처리, 메시지 핸들링, 인라인 키보드를 통한 코드 실행 흐름 관리
- `claude_client.py` — anthropic SDK 래퍼. 시스템 프롬프트 정의, 멀티턴 대화 요청, 응답에서 ```python 코드 블록 추출
- `context_manager.py` — 멀티턴 대화 히스토리 관리 (리스트 기반, JSON 파일로 영속화)
- `executor.py` — workspace/ 폴더에 코드 저장 후 subprocess로 실행, 타임아웃/강제종료 지원
- `workspace/` — 생성된 코드 파일이 타임스탬프 이름으로 저장되는 위치 (실행 시 자동 생성)
- `history.json` — 대화 히스토리 영속화 파일 (실행 시 자동 생성)

## 동작 흐름
1. 사용자가 텔레그램 메시지 전송 → ALLOWED_USER_ID로 단일 사용자 인증
2. `context_manager`에 누적된 히스토리와 함께 `claude_client`로 Claude에 질의
3. 응답에 ```python 코드 블록이 있으면 인라인 키보드([▶️ 실행] [⏭️ 건너뜀])로 실행 여부 확인
4. 실행 시 `executor`가 코드를 저장/실행하고 결과(stdout/stderr/returncode)를 다시 히스토리에 추가
5. Claude가 실행 결과를 분석하고 개선안을 제시 (반복 가능)

## 환경변수 (.env)
- `TELEGRAM_TOKEN` — 텔레그램 봇 토큰
- `ANTHROPIC_API_KEY` — Anthropic API 키
- `ALLOWED_USER_ID` — 봇 사용을 허용할 텔레그램 사용자 ID (단일 사용자 제한)

## 코딩 규칙
- 모든 주석은 한국어로 작성
- 환경변수는 반드시 `python-dotenv`의 `load_dotenv()`로 로드
- 외부 호출/IO/서브프로세스 등은 try/except로 에러 처리
- 각 파일 상단에 역할 설명 주석 포함
