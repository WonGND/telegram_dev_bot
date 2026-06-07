# claude_client.py
# anthropic 라이브러리를 사용하여 Claude와 대화하는 클라이언트 모듈
# 응답에서 ```python 코드 블록을 자동으로 추출하는 기능을 제공한다.

import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 4000

SYSTEM_PROMPT = (
    "개발 터미널 AI. 코드는 반드시 ```python 블록으로 감쌀 것. "
    "실행 결과 수신 시 원인 분석 및 개선안 제시."
)

# ```python ... ``` 형태의 코드 블록을 추출하는 정규식
CODE_BLOCK_PATTERN = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


class ClaudeClient:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")
        self.client = Anthropic(api_key=api_key)

    def ask(self, history):
        """대화 히스토리를 받아 Claude의 응답 텍스트를 반환한다."""
        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=history,
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            )
        except Exception as e:
            return f"[ClaudeClient] Claude 응답 요청 중 오류 발생: {e}"

    @staticmethod
    def extract_code_blocks(text):
        """응답 텍스트에서 ```python 코드 블록 목록을 추출한다."""
        return [block.strip() for block in CODE_BLOCK_PATTERN.findall(text)]
