# bot.py
# 텔레그램으로 PC에 등록된 프로젝트를 원격에서 실행/중지/모니터링하는 제어 봇의 진입점
# python-telegram-bot 20.x 사용, ALLOWED_USER_ID 환경변수로 단일 사용자만 접근 허용
# config.py의 PROJECTS에 등록된 프로그램을 /run, /stop, /log, /projects 명령으로 원격 제어한다.

import logging
import os

from dotenv import load_dotenv
from telegram import Update
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


async def send_long_message(target, text):
    """4000자를 초과하는 메시지를 분할하여 전송한다."""
    if not text:
        return
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await target.reply_text(text[i:i + MAX_MESSAGE_LENGTH])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start 명령어 처리"""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    await update.message.reply_text(
        "안녕하세요! 프로젝트 원격 제어 봇입니다.\n"
        "/projects - 등록된 프로젝트 목록과 실행 상태 확인\n"
        "/run <프로젝트명> - 프로젝트 실행\n"
        "/stop <프로젝트명> - 실행 중인 프로젝트 중지\n"
        "/log <프로젝트명> - 최근 로그 50줄 조회"
    )


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/projects 명령어 처리: 등록된 프로젝트 목록과 실행 상태 출력"""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    try:
        if not PROJECTS:
            await update.message.reply_text(
                "등록된 프로젝트가 없습니다. config.py의 PROJECTS에 프로젝트를 추가해주세요."
            )
            return
        lines = ["등록된 프로젝트 목록:"]
        for project in PROJECTS:
            status = "🟢 실행 중" if executor.is_running(project["name"]) else "⚪ 중지됨"
            lines.append(f"- {project['name']} [{status}]\n  {project['description']}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"프로젝트 목록 조회 중 오류 발생: {e}")


async def run_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/run <프로젝트명> 명령어 처리: 등록된 프로젝트를 실행한다."""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await update.message.reply_text("사용법: /run <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await update.message.reply_text(f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    try:
        log_path = executor.run(project["name"], project["path"], project.get("timeout"))
        await update.message.reply_text(
            f"'{project['name']}' 실행을 시작했습니다.\n로그 파일: {log_path}"
        )
    except Exception as e:
        await update.message.reply_text(f"'{name}' 실행 중 오류 발생: {e}")


async def stop_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop <프로젝트명> 명령어 처리: 실행 중인 프로젝트를 중지한다."""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await update.message.reply_text("사용법: /stop <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await update.message.reply_text(f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    try:
        executor.kill(project["name"])
        await update.message.reply_text(f"'{project['name']}'을(를) 중지했습니다.")
    except Exception as e:
        await update.message.reply_text(f"'{name}' 중지 중 오류 발생: {e}")


async def log_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/log <프로젝트명> 명령어 처리: 최근 로그 50줄을 출력한다."""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    if not context.args:
        await update.message.reply_text("사용법: /log <프로젝트명>")
        return

    name = context.args[0]
    project = get_project(name)
    if project is None:
        await update.message.reply_text(f"'{name}' 프로젝트를 찾을 수 없습니다. /projects 로 등록된 목록을 확인하세요.")
        return

    try:
        log_text = executor.tail_log(project["name"], lines=50)
        if log_text is None:
            await update.message.reply_text(f"'{project['name']}'의 로그 파일이 아직 없습니다.")
            return
        await send_long_message(update.message, f"[{project['name']}] 최근 로그 50줄\n{log_text}")
    except Exception as e:
        await update.message.reply_text(f"'{name}' 로그 조회 중 오류 발생: {e}")


async def check_timeouts_job(context: ContextTypes.DEFAULT_TYPE):
    """주기적으로 timeout이 설정된 프로젝트의 실행 시간을 점검하고, 초과 시 자동 종료한다."""
    try:
        executor.check_timeouts()
    except Exception as e:
        logger.error(f"타임아웃 점검 중 오류 발생: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """전역 에러 핸들러: 에러 발생 시 텔레그램으로 에러 내용을 즉시 전송한다."""
    logger.error("업데이트 처리 중 오류 발생", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                f"봇 처리 중 오류가 발생했습니다: {context.error}"
            )
    except Exception:
        logger.exception("에러 메시지 전송 중 추가 오류 발생")


def main():
    """봇 실행 엔트리 포인트"""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN 환경변수가 설정되어 있지 않습니다.")
    if not ALLOWED_USER_ID:
        raise ValueError("ALLOWED_USER_ID 환경변수가 설정되어 있지 않습니다.")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("projects", projects))
    application.add_handler(CommandHandler("run", run_project))
    application.add_handler(CommandHandler("stop", stop_project))
    application.add_handler(CommandHandler("log", log_project))
    application.add_error_handler(error_handler)

    # timeout이 설정된 프로젝트의 실행 시간을 60초마다 점검하여 초과 시 자동 종료
    application.job_queue.run_repeating(check_timeouts_job, interval=60, first=60)

    logger.info("프로젝트 원격 제어 봇을 시작합니다.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
