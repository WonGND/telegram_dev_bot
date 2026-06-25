# bot.py
# 텔레그램으로 PC에 등록된 프로젝트를 원격에서 실행/중지/모니터링하는 제어 봇의 진입점
# python-telegram-bot 20.x 사용, ALLOWED_USER_ID 환경변수로 단일 사용자만 접근 허용
# config.py의 PROJECTS에 등록된 프로그램을 /run, /stop, /log, /projects 명령으로 원격 제어한다.

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes

from config import PROJECTS, get_project
from executor import ProjectExecutor

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

MAX_MESSAGE_LENGTH = 4000

executor = ProjectExecutor()


def is_allowed(update: Update) -> bool:
    """허용된 사용자인지 확인한다."""
    if ALLOWED_USER_ID is None:
        return False
    user_id = update.effective_user.id if update.effective_user else None
    return str(user_id) == str(ALLOWED_USER_ID)


async def reply(update: Update, text):
    """update에 안전하게 답장한다. (편집된 메시지 등 update.message가 None인 경우 대비)"""
    message = update.effective_message
    if message is None:
        return
    if not text:
        return
    # 4000자를 초과하는 메시지는 분할하여 전송한다.
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await message.reply_text(text[i:i + MAX_MESSAGE_LENGTH])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 처리"""
    if not is_allowed(update):
        await reply(update, "접근이 허용되지 않은 사용자입니다.")
        return
    await reply(
        update,
        "안녕하세요! 프로젝트 원격 제어 봇입니다.\n"
        "/projects - 등록된 프로젝트 목록과 실행 상태 확인\n"
        "/run <프로젝트명> - 프로젝트 실행 (미리보기)\n"
        "/run us_rotation live - 미국주식 모멘텀 로테이션 실거래 리밸런스\n"
        "/stop <프로젝트명> - 실행 중인 프로젝트 중지\n"
        "/log <프로젝트명> - 최근 로그 50줄 조회\n"
        "\n※ 미국주식 로테이션은 매월 1일 00:10 자동 리밸런스됩니다(무인)."
    )


def _build_projects_text():
    """등록된 프로젝트 목록과 실행 상태 문자열을 만든다. (블로킹 IO → 스레드에서 호출)"""
    lines = ["등록된 프로젝트 목록:"]
    for project in PROJECTS:
        running = executor.is_running(project["name"], entry_path=project["path"])
        status = "🟢 실행 중" if running else "⚪ 중지됨"
        lines.append(f"- {project['name']} [{status}]\n  {project['description']}")
    return "\n".join(lines)


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/projects 명령어 처리: 등록된 프로젝트 목록과 실행 상태 출력"""
    if not is_allowed(update):
        await reply(update, "접근이 허용되지 않은 사용자입니다.")
        return
    try:
        if not PROJECTS:
            await reply(
                update,
                "등록된 프로젝트가 없습니다. config.py의 PROJECTS에 프로젝트를 추가해주세요.",
            )
            return
        # is_running은 PowerShell 프로세스 조회(블로킹)를 포함하므로 별도 스레드에서 실행해
        # asyncio 이벤트 루프가 막혀 폴링이 끊기는(NetworkError) 문제를 방지한다.
        text = await asyncio.to_thread(_build_projects_text)
        await reply(update, text)
    except Exception as e:
        await reply(update, f"프로젝트 목록 조회 중 오류 발생: {e}")


async def run_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/run <프로젝트명> 명령어 처리: 등록된 프로젝트를 실행한다."""
    if not is_allowed(update):
        await reply(update, "접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await reply(update, "사용법: /run <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await reply(update, f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    # "/run <name> live" → config의 --dry-run 제거하고 실거래 실행
    run_args = list(project.get("args") or [])
    if len(context.args) > 1 and context.args[1].lower() == "live":
        run_args = [a for a in run_args if a != "--dry-run"]

    try:
        # 실행 가드(is_running)에 PowerShell 조회가 포함되므로 스레드에서 실행한다.
        log_path = await asyncio.to_thread(
            executor.run,
            project["name"],
            project["path"],
            project.get("timeout"),
            project.get("python"),
            run_args,
        )
        await reply(update, f"'{project['name']}' 실행을 시작했습니다.\n로그 파일: {log_path}")
    except Exception as e:
        await reply(update, f"'{name}' 실행 중 오류 발생: {e}")


async def stop_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop <프로젝트명> 명령어 처리: 실행 중인 프로젝트를 중지한다."""
    if not is_allowed(update):
        await reply(update, "접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await reply(update, "사용법: /stop <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await reply(update, f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    try:
        # kill은 graceful 종료 대기(최대 15초)와 PowerShell 조회를 포함하므로 스레드에서 실행한다.
        await asyncio.to_thread(executor.kill, project["name"], 15, project["path"])
        await reply(update, f"'{project['name']}'을(를) 중지했습니다.")
    except Exception as e:
        await reply(update, f"'{name}' 중지 중 오류 발생: {e}")


async def log_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/log <프로젝트명> 명령어 처리: 최근 로그 50줄을 출력한다."""
    if not is_allowed(update):
        await reply(update, "접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await reply(update, "사용법: /log <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await reply(update, f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    try:
        # 로그 파일 읽기(대용량 가능)는 블로킹이므로 스레드에서 실행한다.
        log_text = await asyncio.to_thread(executor.tail_log, project["name"], 50)
        if log_text is None:
            await reply(update, f"'{project['name']}'의 로그 파일이 아직 없습니다.")
            return
        await reply(update, f"[{project['name']}] 최근 로그 50줄\n{log_text}")
    except Exception as e:
        await reply(update, f"'{name}' 로그 조회 중 오류 발생: {e}")


async def check_timeouts_job(context: ContextTypes.DEFAULT_TYPE):
    """주기적으로 timeout이 설정된 프로젝트의 실행 시간을 점검하고, 초과 시 자동 종료한다."""
    try:
        # 종료 대기(blocking)가 포함될 수 있으므로 스레드에서 실행해 이벤트 루프를 막지 않는다.
        await asyncio.to_thread(executor.check_timeouts)
    except Exception as e:
        logger.error(f"타임아웃 점검 중 오류 발생: {e}")


async def daily_daytrade_job(context: ContextTypes.DEFAULT_TYPE):
    """평일 1회 단타(RSI2) 시뮬레이션 실행 — 보유 청산체크 + 신규 진입 스캔."""
    project = get_project("us_daytrade")
    if project is None:
        return
    try:
        await asyncio.to_thread(
            executor.run, "us_daytrade", project["path"], project.get("timeout"),
            project.get("python"), project.get("args"))
        # run()은 백그라운드 실행이라 직후 로그가 비어 있다.
        # 실행이 끝날 때까지 기다린 뒤 로그를 읽어 알림 본문에 직접 포함한다.
        await asyncio.to_thread(executor.wait_for, "us_daytrade", 300)
        log_text = await asyncio.to_thread(executor.tail_log, "us_daytrade", 40)
        body = (log_text or "").strip()
        # 이번 실행분만 보이도록 마지막 '실행 시작' 마커 이후로 자른다(있으면).
        if "===== 실행 시작" in body:
            body = body[body.rindex("===== 실행 시작"):]
        body = body or "(로그 내용 없음)"
        msg = f"📈 단타 시뮬 일일 실행 완료\n\n{body}"
        # 텔레그램 메시지 길이 제한(4096자) 대비 안전 컷
        if len(msg) > 3500:
            msg = msg[:3500] + "\n…(이하 생략 — 전체는 /log us_daytrade)"
    except Exception as e:
        msg = f"⚠️ 단타 시뮬 실행 오류: {e}"
    try:
        if ALLOWED_USER_ID:
            await context.bot.send_message(chat_id=int(ALLOWED_USER_ID), text=msg)
    except Exception as e:
        logger.error(f"단타 알림 전송 오류: {e}")


async def monthly_rebalance_job(context: ContextTypes.DEFAULT_TYPE):
    """매월 1회 미국 주식 모멘텀 로테이션 실거래 리밸런스를 자동 실행한다(무인 운용)."""
    project = get_project("us_rotation")
    if project is None:
        return
    try:
        # --dry-run 제거 → 실거래 리밸런스
        run_args = [a for a in (project.get("args") or []) if a != "--dry-run"]
        log_path = await asyncio.to_thread(
            executor.run, "us_rotation", project["path"], project.get("timeout"),
            project.get("python"), run_args)
        msg = (f"📅 월간 자동 리밸런스 실행\n"
               f"미국 주식 모멘텀 로테이션(top20) 리밸런스를 시작했습니다.\n"
               f"결과 확인: /log us_rotation\n로그: {log_path}")
    except Exception as e:
        msg = f"⚠️ 월간 리밸런스 실행 오류: {e}"
    try:
        if ALLOWED_USER_ID:
            await context.bot.send_message(chat_id=int(ALLOWED_USER_ID), text=msg)
    except Exception as e:
        logger.error(f"월간 리밸런스 알림 전송 오류: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """전역 에러 핸들러.

    네트워크 일시 오류(ReadError/Bad Gateway/Timed out 등)는 python-telegram-bot이
    폴링 루프에서 자동 재시도하고, update도 없어 사용자에게 알릴 대상이 없다.
    이런 오류까지 ERROR+트레이스백으로 남기면 로그가 도배되므로 WARNING으로만 기록하고 넘어간다.
    그 외 실제 처리 오류만 ERROR로 남기고, 가능하면 사용자에게 알린다.
    """
    err = context.error
    if isinstance(err, (NetworkError, TimedOut, RetryAfter)):
        logger.warning("네트워크 일시 오류(자동 재시도): %s", err)
        return

    logger.error("업데이트 처리 중 오류 발생", exc_info=err)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                f"봇 처리 중 오류가 발생했습니다: {err}"
            )
    except Exception:
        logger.exception("에러 메시지 전송 중 추가 오류 발생")


def main():
    """봇 실행 엔트리 포인트"""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN 환경변수가 설정되어 있지 않습니다.")
    if not ALLOWED_USER_ID:
        raise ValueError("ALLOWED_USER_ID 환경변수가 설정되어 있지 않습니다.")

    # HTTP 타임아웃을 넉넉히 잡아 일시적 네트워크 지연으로 인한 ReadError/Timed out 발생을 줄인다.
    # get_updates는 long polling(기본 10초)이므로 read timeout을 그보다 충분히 크게 둔다.
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .get_updates_read_timeout(40.0)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("projects", projects))
    application.add_handler(CommandHandler("run", run_project))
    application.add_handler(CommandHandler("stop", stop_project))
    application.add_handler(CommandHandler("log", log_project))
    application.add_error_handler(error_handler)

    # timeout이 설정된 프로젝트의 실행 시간을 60초마다 점검하여 초과 시 자동 종료
    application.job_queue.run_repeating(check_timeouts_job, interval=60, first=60)

    # 매월 1일 미국 주식 모멘텀 로테이션 자동 리밸런스 (무인 운용)
    import datetime as _dt
    try:
        application.job_queue.run_monthly(
            monthly_rebalance_job, when=_dt.time(hour=0, minute=10), day=1)
        logger.info("월간 자동 리밸런스 스케줄 등록 (매월 1일 00:10)")
    except Exception as e:
        logger.error(f"월간 스케줄 등록 실패: {e}")

    # 평일 단타(RSI2) 시뮬레이션 일일 실행 (월~금 07:30 = 美 종가 후)
    try:
        application.job_queue.run_daily(
            daily_daytrade_job, time=_dt.time(hour=7, minute=30), days=(0, 1, 2, 3, 4))
        logger.info("단타 시뮬 일일 스케줄 등록 (평일 07:30)")
    except Exception as e:
        logger.error(f"단타 스케줄 등록 실패: {e}")

    logger.info("프로젝트 원격 제어 봇을 시작합니다.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
