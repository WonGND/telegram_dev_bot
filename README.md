# telegram_dev_bot

텔레그램으로 Claude와 대화하며 코드를 생성/실행/수정할 수 있는 개발 봇입니다.

## 주요 기능
- 텔레그램 메시지로 Claude(claude-sonnet-4-6)와 멀티턴 대화
- Claude 응답에 포함된 ```python 코드 블록을 자동 추출
- 인라인 키보드([▶️ 실행] [⏭️ 건너뜀])로 코드 실행 여부 선택
- 실행 결과(stdout/stderr/returncode)를 자동으로 대화 히스토리에 추가하여 Claude가 분석 및 개선안 제시
- `/clear`로 히스토리 초기화, `/status`로 workspace 파일 목록 확인
- ALLOWED_USER_ID로 단일 사용자만 접근 허용
- 4000자를 초과하는 메시지는 자동 분할 전송

## 설치 방법

1. 저장소를 클론하고 디렉터리로 이동합니다.

```bash
git clone <repo-url>
cd telegram_dev_bot
```

2. 가상환경을 생성하고 활성화합니다. (선택사항이지만 권장)

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

3. 의존성을 설치합니다.

```bash
pip install -r requirements.txt
```

4. `.env.example`을 복사해 `.env` 파일을 만들고 값을 채웁니다.

```bash
cp .env.example .env
```

`.env` 내용:

```
TELEGRAM_TOKEN=텔레그램_봇_토큰
ANTHROPIC_API_KEY=Anthropic_API_키
ALLOWED_USER_ID=텔레그램_사용자_ID
```

- `TELEGRAM_TOKEN`: [@BotFather](https://t.me/BotFather)에서 봇을 생성하면 발급받을 수 있습니다.
- `ANTHROPIC_API_KEY`: Anthropic 콘솔에서 발급받은 API 키입니다.
- `ALLOWED_USER_ID`: [@userinfobot](https://t.me/userinfobot) 등을 통해 확인할 수 있는 본인의 텔레그램 사용자 ID입니다. (숫자)

## 실행 방법

```bash
python3 bot.py
```

정상적으로 실행되면 텔레그램에서 봇과 대화를 시작할 수 있습니다.

## 사용 방법

1. 텔레그램에서 봇에게 `/start`를 보냅니다.
2. 일반 메시지를 보내면 Claude와 대화하며 코드를 요청할 수 있습니다.
3. Claude가 ```python 코드 블록을 포함한 응답을 보내면, [▶️ 실행] 버튼을 눌러 즉시 실행하거나 [⏭️ 건너뜀] 버튼으로 건너뛸 수 있습니다.
4. 코드를 실행하면 결과(stdout/stderr/returncode)가 전송되고, Claude가 결과를 분석해 개선안을 제시합니다.
5. `/clear`로 대화 히스토리를 초기화하고, `/status`로 `workspace/` 폴더의 파일 목록을 확인할 수 있습니다.

## 디렉터리 구조

```
telegram_dev_bot/
├── bot.py              # 텔레그램 봇 진입점
├── claude_client.py    # Claude API 클라이언트
├── context_manager.py  # 대화 히스토리 관리
├── executor.py         # 코드 저장 및 실행
├── requirements.txt
├── .env.example
├── workspace/          # 생성/실행되는 코드 파일 저장 위치 (자동 생성)
└── history.json        # 대화 히스토리 저장 파일 (자동 생성)
```

## 주의 사항
- 이 봇은 텔레그램 메시지로 받은 코드를 서버에서 직접 실행합니다. 반드시 본인만 접근 가능한 환경(`ALLOWED_USER_ID`)에서 사용하세요.
- 신뢰할 수 없는 코드 실행은 보안 위험이 있으므로, 격리된 환경(컨테이너, VM 등)에서 운영하는 것을 권장합니다.
