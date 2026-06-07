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
# }

PROJECTS = [
    # 예시 (실제 사용 시 본인의 프로젝트 정보로 교체하거나, 이 형식대로 추가하세요)
    # {
    #     "name": "bybit",
    #     "path": "C:/Users/원용/Desktop/Wonyong company/bybit_trader/main.py",
    #     "description": "Bybit 자동매매 트레이딩 봇",
    #     "timeout": None,
    # },
]


def get_project(name):
    """이름으로 등록된 프로젝트 설정을 조회한다. 없으면 None을 반환한다."""
    for project in PROJECTS:
        if project["name"] == name:
            return project
    return None
