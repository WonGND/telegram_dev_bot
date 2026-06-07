# telegram_dev_bot

텔레그램으로 PC에 등록된 프로젝트(프로그램)를 원격에서 실행/중지/모니터링할 수 있는 제어용 봇입니다.
휴대폰이나 다른 PC의 텔레그램 앱에서 명령을 보내면, 이 봇이 실행되고 있는 PC에서 등록된 프로그램을 실행하고 결과/로그를 텔레그램으로 전송해줍니다.

## 주요 기능
- `config.py`에 등록한 프로젝트들을 원격에서 실행/중지
- 여러 프로젝트를 동시에 백그라운드로 실행 (프로세스를 딕셔너리로 관리)
- 프로젝트별 실행 로그를 `logs/` 폴더에 날짜별 파일로 자동 기록
- `/log`로 최근 로그 50줄을 텔레그램에서 바로 확인
- `timeout`이 설정된 프로젝트는 실행 시간을 주기적으로 점검해 초과 시 자동 종료
- ALLOWED_USER_ID로 단일 사용자만 접근 허용
- 4000자를 초과하는 메시지는 자동 분할 전송, 에러 발생 시 텔레그램으로 즉시 알림

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
ALLOWED_USER_ID=텔레그램_사용자_ID
```

- `TELEGRAM_TOKEN`: [@BotFather](https://t.me/BotFather)에서 봇을 생성하면 발급받을 수 있습니다.
- `ALLOWED_USER_ID`: [@userinfobot](https://t.me/userinfobot) 등을 통해 확인할 수 있는 본인의 텔레그램 사용자 ID입니다. (숫자)

## 프로젝트 등록

원격으로 실행/제어하고 싶은 프로그램을 `config.py`의 `PROJECTS` 리스트에 등록합니다.

```python
PROJECTS = [
    {
        "name": "bybit",                      # 텔레그램 명령어에서 사용할 식별자 (영문 권장)
        "path": "C:/Users/.../main.py",       # 진입점 파일의 절대경로
        "description": "Bybit 자동매매 봇",     # 간단한 설명
        "timeout": None,                       # 실행 제한시간(초). 계속 실행될 프로그램은 None
    },
]
```

## 실행 방법

```bash
python3 bot.py
```

정상적으로 실행되면 텔레그램에서 봇과 대화를 시작할 수 있습니다. (이 봇이 켜져 있는 PC에서 등록된 프로그램들이 실행/제어됩니다.)

## 사용 방법

1. 텔레그램에서 봇에게 `/start`를 보내 사용 가능한 명령어를 확인합니다.
2. `/projects` — 등록된 프로젝트 목록과 현재 실행 상태(🟢 실행 중 / ⚪ 중지됨)를 확인합니다.
3. `/run <프로젝트명>` — 예: `/run bybit` — 등록된 프로젝트를 실행합니다.
4. `/stop <프로젝트명>` — 실행 중인 프로젝트를 중지합니다.
5. `/log <프로젝트명>` — 최근 로그 50줄을 텔레그램으로 받아봅니다.

다른 기기(휴대폰, 다른 PC 등)에서도 텔레그램 앱으로 봇과 대화하면 동일하게 PC의 프로그램을 원격 제어할 수 있습니다. (봇이 실행 중인 PC만 켜져 있으면 됩니다.)

## 디렉터리 구조

```
telegram_dev_bot/
├── bot.py              # 텔레그램 봇 진입점 및 명령어 처리
├── config.py           # 원격 제어 대상 프로젝트 목록 관리
├── executor.py         # 프로젝트 실행/중지/로그 관리
├── requirements.txt
├── .env.example
└── logs/               # 프로젝트별 날짜별 실행 로그 (자동 생성)
```

## 주의 사항
- 이 봇은 등록된 프로그램을 PC에서 직접 실행/중지합니다. 반드시 본인만 접근 가능한 환경(`ALLOWED_USER_ID`)에서 사용하세요.
- 봇을 항상 사용하려면 PC와 봇 프로세스(`python3 bot.py`)가 계속 켜져 있어야 합니다.
