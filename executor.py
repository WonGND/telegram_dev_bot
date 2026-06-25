# executor.py
# config.py에 등록된 프로젝트를 원격에서 실행/중지/모니터링하는 모듈
# 프로젝트별 프로세스를 딕셔너리로 관리하여 여러 프로젝트를 동시에 실행할 수 있다.
# 각 프로젝트의 실행 로그는 logs/ 폴더에 날짜별 파일로 누적 저장된다.

import os
import signal
import subprocess
import time
from collections import deque
from pathlib import Path

LOGS_DIR = Path("logs")

# 이 봇 자신의 .env에서 로드된 환경변수. 자식 프로세스에 그대로 상속되면
# 각 프로젝트가 자기 .env로 같은 이름의 변수(예: TELEGRAM_TOKEN)를 로드하려 해도
# python-dotenv가 기존 값을 덮어쓰지 않아 dev bot의 값이 그대로 사용되는 문제가 생긴다.
_OWN_ENV_KEYS = ("TELEGRAM_TOKEN", "ALLOWED_USER_ID")


def _child_env():
    """자식 프로세스용 환경을 만든다. dev bot 전용 변수는 제거해 각 프로젝트의 .env가 우선되도록 한다."""
    env = os.environ.copy()
    for key in _OWN_ENV_KEYS:
        env.pop(key, None)
    # Windows cp949 환경에서 한글/특수문자 UnicodeEncodeError 방지
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


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

    @staticmethod
    def _find_pids_by_path(entry_path):
        """엔트리 경로를 커맨드라인에 포함하는 실행 중 python PID 목록을 반환한다.
        봇 재시작 등으로 self.processes 추적을 잃은 고아 프로세스를 탐지하기 위함.
        '상위폴더명*파일명' 패턴으로 매칭해 동명 파일(main.py) 충돌을 방지한다."""
        try:
            p = Path(entry_path)
            pattern = f"*{p.parent.name}*{p.name}*"
            ps = (
                "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                f"Where-Object {{ $_.CommandLine -like '{pattern}' }} | "
                "Select-Object -ExpandProperty ProcessId"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                text=True, timeout=20, stderr=subprocess.DEVNULL)
            return [int(x) for x in out.split() if x.strip().isdigit()]
        except Exception:
            return []

    def is_running(self, project_name, entry_path=None):
        """해당 프로젝트가 현재 실행 중인지 확인한다.
        self.processes에 없고 entry_path가 주어지면 경로 기반으로 고아 프로세스도 탐지한다."""
        info = self.processes.get(project_name)
        if info and info["process"].poll() is None:
            return True
        if entry_path:
            return len(self._find_pids_by_path(entry_path)) > 0
        return False

    def run(self, project_name, entry_path, timeout=None, python_path=None, args=None):
        """프로젝트를 백그라운드로 실행하고 출력을 로그 파일에 기록한다. 로그 파일 경로를 반환한다.

        python_path가 주어지면 해당 인터프리터(예: 프로젝트 전용 venv의 python.exe)로 실행하고,
        주어지지 않으면 시스템 PATH의 기본 python을 사용한다.
        """
        entry_path = Path(entry_path).resolve()
        if not entry_path.exists():
            raise FileNotFoundError(f"진입점 파일을 찾을 수 없습니다: {entry_path}")

        # entry_path를 함께 넘겨, 봇 재시작 등으로 추적을 잃은 고아 프로세스가 떠 있는데도
        # 중복 실행되는 것을 막는다.
        if self.is_running(project_name, entry_path=str(entry_path)):
            raise RuntimeError(f"'{project_name}'은(는) 이미 실행 중입니다.")

        interpreter = python_path or "python"
        log_path = self._log_path(project_name)
        log_file = None
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            log_file.write(f"\n===== 실행 시작: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            log_file.flush()

            popen_kwargs = dict(
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(entry_path.parent),
                env=_child_env(),
                text=True,
            )
            # Windows: 별도 프로세스 그룹으로 실행해 graceful 종료 신호를 안전하게 전달
            if os.name == "nt":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                [interpreter, str(entry_path), *(args or [])],
                **popen_kwargs,
            )
        except Exception as e:
            # 실패 시 열어둔 로그 파일 핸들을 닫아 누수를 방지한다.
            if log_file is not None:
                try:
                    log_file.close()
                except Exception:
                    pass
            raise RuntimeError(f"'{project_name}' 실행 중 오류 발생: {e}")

        self.processes[project_name] = {
            "process": process,
            "log_file": log_file,
            "log_path": log_path,
            "started_at": time.time(),
            "timeout": timeout,
        }
        return log_path

    def wait_for(self, project_name, timeout=None):
        """실행 중인 프로젝트가 끝날 때까지 대기한 뒤 정리한다.

        일회성 작업(일일 시뮬 등)의 출력이 로그에 모두 기록된 뒤 읽기 위해 사용한다.
        run()은 백그라운드 실행이라 직후에 로그를 읽으면 비어 있을 수 있으므로,
        run() 다음에 이 메서드로 종료를 기다린 후 tail_log()로 결과를 읽으면 된다.
        timeout(초) 안에 끝나지 않으면 강제 종료한다. 종료코드를 반환한다(추적 없으면 None)."""
        info = self.processes.get(project_name)
        if not info:
            return None
        proc = info["process"]
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        rc = proc.returncode
        self._cleanup(project_name)
        return rc

    def _kill_orphans(self, entry_path):
        """추적하지 못한(봇 재시작 등) 고아 프로세스를 경로로 찾아 강제 종료한다."""
        pids = self._find_pids_by_path(entry_path)
        if not pids:
            return 0
        killed = 0
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                killed += 1
            except Exception:
                pass
        return killed

    def kill(self, project_name, graceful_timeout=15, entry_path=None):
        """실행 중인 프로젝트를 종료한다.

        먼저 graceful 종료 신호를 보내 프로세스가 정리 작업(텔레그램 알림 등)을 마칠 시간을 준다.
        graceful_timeout 초 안에 종료되지 않으면 강제로 죽인다.
        self.processes에 없으면(봇 재시작으로 추적 상실) entry_path로 고아 프로세스를 찾아 종료한다.
        """
        info = self.processes.get(project_name)
        if not info or info["process"].poll() is not None:
            self._cleanup(project_name)
            # 추적 못한 고아 프로세스를 경로 기반으로 종료 시도
            if entry_path:
                n = self._kill_orphans(entry_path)
                if n > 0:
                    return
            raise RuntimeError(f"'{project_name}'은(는) 실행 중이 아닙니다.")
        try:
            proc = info["process"]
            # Windows: CTRL_BREAK_EVENT → 자식 프로세스 그룹에만 전달, 부모는 영향 없음
            # Unix:    SIGTERM → 프로세스가 잡아서 정리 가능
            if os.name == "nt":
                os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=graceful_timeout)
                info["log_file"].write(f"===== 종료: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                info["log_file"].write(f"===== 강제 종료(타임아웃): {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
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
            # 로그 파일이 수 MB~수십 MB까지 커질 수 있으므로 전체를 메모리에 올리지 않고
            # deque(maxlen)로 마지막 N줄만 유지한다. errors="replace"로 인코딩 깨짐에도 견딘다.
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                last_lines = deque(f, maxlen=lines)
            return "".join(last_lines) or "(로그 내용 없음)"
        except Exception as e:
            raise RuntimeError(f"로그 조회 중 오류 발생: {e}")
