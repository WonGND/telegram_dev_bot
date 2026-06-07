# context_manager.py
# 멀티턴 대화 히스토리를 관리하는 모듈
# 히스토리는 리스트(role, content) 형태로 저장하며 JSON 파일로 저장/불러오기를 지원한다.
# 세션이 재시작되어도 history.json 파일을 통해 대화 맥락을 이어갈 수 있다.

import json
import os


class ContextManager:
    def __init__(self, history_file="history.json"):
        self.history_file = history_file
        self.history = []

    def add(self, role, content):
        """대화 히스토리에 메시지를 추가한다. role: 'user' 또는 'assistant'"""
        self.history.append({"role": role, "content": content})

    def get(self):
        """현재까지 누적된 대화 히스토리를 반환한다."""
        return self.history

    def clear(self):
        """대화 히스토리를 초기화한다."""
        self.history = []

    def save_to_file(self, filepath=None):
        """현재 히스토리를 JSON 파일로 저장한다."""
        path = filepath or self.history_file
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ContextManager] 히스토리 저장 중 오류 발생: {e}")

    def load_from_file(self, filepath=None):
        """JSON 파일에서 히스토리를 불러온다. 파일이 없으면 빈 히스토리로 시작한다."""
        path = filepath or self.history_file
        if not os.path.exists(path):
            self.history = []
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.history = json.load(f)
        except Exception as e:
            print(f"[ContextManager] 히스토리 불러오기 중 오류 발생: {e}")
            self.history = []
