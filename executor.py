# executor.py
# config.py에 등록된 프로젝트를 원격에서 실행/중지/모니터링하는 모듈
# 프로젝트별 프로세스를 딕셔너리로 관리하여 여러 프로젝트를 동시에 실행할 수 있다.
# 각 프로젝트의 실행 로그는 logs/ 폴더에 날짜별 파일로 누적 저장된다.

import subprocess
import time
from pathlib import Path

LOGS_DIR = Path("logs")


class ProjectExecutor:
    def __init__(self, logs_dir=LOGS_DIR):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        # 프로젝트명 -> {"process", "log_file", "log_path", "started_at", "timeout"}
        self.processes = {}

    def _log_path(self, project_name):
        """프로젝트명과 오늘 날짜를 기준으로 로그 파일 경로를 생성한다."""
        date_str = time.strftime("%Y%m%d")
        return self.logs_dir / f"{project_name}_{date_str}.log"

    def is_running(self, project_name):
        """해당 프로젝트가 현재 실행 중인지 확인한다."""
        info = self.processes.get(project_name)
        if not info:
            return False
        return info["process"].poll() is None

    def run(self, project_name, entry_path, timeout=None):
        """프로젝트를 백그라운드로 실행하고 출력을 로그 파일에 기록한다. 로그 파일 경로를 반환한다."""
        if self.is_running(project_name):
            raise RuntimeError(f"'{project_name}'은(는) 이미 실행 중입니다.")

        entry_path = Path(entry_path).resolve()
        if not entry_path.exists():
            raise FileNotFoundError(f"진입점 파일을 찾을 수 없습니다: {entry_path}")

        log_path = self._log_path(project_name)
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            log_file.write(f"\n===== 실행 시작: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            log_file.flush()

            process = subprocess.Popen(
                ["python", str(entry_path)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(entry_path.parent),
                text=True,
            )
        except Exception as e:
            raise RuntimeError(f"'{project_name}' 실행 중 오류 발생: {e}")

        self.processes[project_name] = {
            "process": process,
            "log_file": log_file,
            "log_path": log_path,
            "started_at": time.time(),
            "timeout": timeout,
        }
        return log_path

    def kill(self, project_name):
        """실행 중인 프로젝트의 프로세스를 강제 종료한다."""
        info = self.processes.get(project_name)
        if not info or info["process"].poll() is not None:
            self._cleanup(project_name)
            raise RuntimeError(f"'{project_name}'은(는) 실행 중이 아닙니다.")
        try:
            info["process"].kill()
            info["process"].wait()
            info["log_file"].write(f"===== 강제 종료: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        except Exception as e:
            raise RuntimeError(f"'{project_name}' 종료 중 오류 발생: {e}")
        finally:
            self._cleanup(project_name)

    def _cleanup(self, project_name):
        """종료된 프로세스 정보를 정리하고 로그 파일 핸들을 닫는다."""
        info = self.processes.pop(project_name, None)
        if info:
            try:
                info["log_file"].close()
            except Exception:
                pass

    def check_timeouts(self):
        """timeout이 설정된 프로젝트 중 실행 시간이 초과된 프로세스를 자동 종료한다."""
        for name in list(self.processes.keys()):
            info = self.processes.get(name)
            if not info:
                continue
            if info["process"].poll() is not None:
                self._cleanup(name)
                continue
            if info["timeout"] is None:
                continue
            elapsed = time.time() - info["started_at"]
            if elapsed > info["timeout"]:
                try:
                    self.kill(name)
                except Exception as e:
                    print(f"[ProjectExecutor] '{name}' 타임아웃 종료 중 오류 발생: {e}")

    def tail_log(self, project_name, lines=50):
        """프로젝트의 가장 최근 로그 파일에서 마지막 N줄을 반환한다. 로그가 없으면 None을 반환한다."""
        log_path = self._log_path(project_name)
        if not log_path.exists():
            candidates = sorted(self.logs_dir.glob(f"{project_name}_*.log"))
            if not candidates:
                return None
            log_path = candidates[-1]
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.readlines()
            return "".join(content[-lines:]) or "(로그 내용 없음)"
        except Exception as e:
            raise RuntimeError(f"로그 조회 중 오류 발생: {e}")
