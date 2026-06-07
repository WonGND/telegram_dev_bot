# executor.py
# Claude가 생성한 코드를 workspace/ 폴더에 저장하고 실행하는 모듈
# 타임스탬프 기반 파일명을 자동 생성하며, 실행 중인 프로세스를 강제 종료하는 기능도 제공한다.

import os
import subprocess
import time

WORKSPACE_DIR = "workspace"


class Executor:
    def __init__(self, workspace_dir=WORKSPACE_DIR):
        self.workspace_dir = workspace_dir
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.current_process = None

    def save_code(self, code, prefix="code"):
        """코드를 타임스탬프가 포함된 파일명으로 workspace/ 에 저장하고 경로를 반환한다."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.py"
        filepath = os.path.join(self.workspace_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            raise RuntimeError(f"코드 저장 중 오류 발생: {e}")
        return filepath

    def run(self, filepath, timeout=60):
        """지정된 파일을 python으로 실행하고 (stdout, stderr, returncode)를 반환한다."""
        try:
            self.current_process = subprocess.Popen(
                ["python3", filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout, stderr = self.current_process.communicate(timeout=timeout)
                returncode = self.current_process.returncode
            except subprocess.TimeoutExpired:
                self.kill()
                stdout, stderr = "", f"실행 시간이 {timeout}초를 초과하여 강제 종료되었습니다."
                returncode = -1
            return stdout, stderr, returncode
        except Exception as e:
            return "", f"코드 실행 중 오류 발생: {e}", -1
        finally:
            self.current_process = None

    def kill(self):
        """현재 실행 중인 프로세스를 강제 종료한다."""
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.kill()
                self.current_process.wait()
            except Exception as e:
                print(f"[Executor] 프로세스 종료 중 오류 발생: {e}")

    def list_files(self):
        """workspace/ 폴더 내 파일 목록을 반환한다."""
        try:
            return sorted(os.listdir(self.workspace_dir))
        except Exception as e:
            print(f"[Executor] 파일 목록 조회 중 오류 발생: {e}")
            return []
