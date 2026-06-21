# config.py
# 원격 제어할 프로젝트 목록을 중앙에서 관리하는 설정 파일
#
# 새 프로젝트를 추가하는 방법:
# PROJECTS 리스트에 아래 형식의 딕셔너리를 추가하면 됩니다.
# {
#     "name": "프로젝트명 (텔레그램 명령어 식별자, 영문/숫자 권장. 예: bybit)",
#     "path": "진입점 파일의 절대경로 (예: C:/Users/원용/Desktop/.../main.py)",
#     "description": "프로젝트에 대한 간단한 설명",
#     "timeout": 실행 제한시간(초). 계속 실행되어야 하는 프로그램은 None으로 설정
#     "python": (선택) 실행에 사용할 인터프리터 경로. 프로젝트 전용 venv의 python.exe를 지정하면
#               해당 venv에 설치된 의존성으로 실행된다. 생략 시 시스템 PATH의 python 사용
#     "args": (선택) 진입점 파일에 전달할 커맨드라인 인자 리스트 (예: ["trade", "--mode", "paper"])
# }

PROJECTS = [
    {
        "name": "us_stock",
        "path": "C:/Users/원용/Desktop/Wonyong company/trading_bot/main.py",
        "description": "미국 주식 자동매매 봇 (Alpaca, SMA+RSI+볼린저밴드 전략, 자기학습 루프)",
        "timeout": None,
        "python": "C:/Users/원용/Desktop/Wonyong company/trading_bot/.venv/Scripts/python.exe",
    },
    {
        "name": "kr_stock",
        "path": "C:/Users/원용/Desktop/Wonyong company/auto_trader/scheduler.py",
        "description": "한국 주식 자동매매 스케줄러 (키움/대신 연동, 매매 로직은 아직 자리표시자 상태)",
        "timeout": None,
        "python": "C:/Users/원용/Desktop/Wonyong company/auto_trader/.venv/Scripts/python.exe",
    },
    {
        "name": "coin_futures",
        "path": "C:/Users/원용/Desktop/Wonyong company/autotrader_only_claude/run_live_trading.py",
        "description": "코인 선물 자동매매 봇 (Bybit Futures 실계좌, Donchian 10종목, 텔레그램 알림)",
        "timeout": None,
        # 기본 python엔 pybit 등 의존성이 없음 → 의존성 갖춘 Python 3.13 명시
        "python": "C:/Users/원용/AppData/Local/Programs/Python/Python313/python.exe",
    },
    {
        "name": "us_rotation",
        "path": "C:/Users/원용/Desktop/Wonyong company/trading_bot/run_rotation_live.py",
        "description": "미국 주식 코어 전략 — 모멘텀 로테이션 (월1회 리밸런스, top20 동일비중, CAGR16%/승률63%)",
        "timeout": None,
        "python": "C:/Users/원용/Desktop/Wonyong company/trading_bot/.venv/Scripts/python.exe",
        "args": ["--dry-run"],
    },
    {
        "name": "us_daytrade",
        "path": "C:/Users/원용/Desktop/Wonyong company/trading_bot/run_daytrade_live.py",
        "description": "단타 RSI2 평균회귀 시뮬레이션 (1주이내 보유, 매일 스캔, 별도 원장·비용0.2%반영) — 병행 테스트용",
        "timeout": None,
        "python": "C:/Users/원용/Desktop/Wonyong company/trading_bot/.venv/Scripts/python.exe",
    },
]


def get_project(name):
    """이름으로 등록된 프로젝트 설정을 조회한다. 없으면 None을 반환한다."""
    for project in PROJECTS:
        if project["name"] == name:
            return project
    return None
