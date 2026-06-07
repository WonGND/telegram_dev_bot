# bot.py
# 텔레그램으로 Claude와 대화하며 코드를 생성/실행/수정하는 개발 봇의 진입점
# python-telegram-bot 20.x 사용, ALLOWED_USER_ID 환경변수로 단일 사용자만 접근 허용

import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from claude_client import ClaudeClient
from context_manager import ContextManager
from executor import Executor

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

MAX_MESSAGE_LENGTH = 4000

# 모듈 전역 인스턴스 (단일 사용자 봇이므로 전역으로 관리)
context_manager = ContextManager()
executor = Executor()
claude_client = ClaudeClient()

# 콜백 데이터로 코드를 직접 전달하면 길이 제한에 걸릴 수 있으므로
# 추출된 코드 블록을 임시로 보관해두는 캐시
pending_code_blocks = {}
_pending_id_counter = 0


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
        "안녕하세요! Claude 개발 봇입니다.\n"
        "메시지를 보내면 Claude와 대화하며 코드를 생성/실행할 수 있습니다.\n"
        "/clear - 대화 히스토리 초기화\n"
        "/status - workspace 파일 목록 확인"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/clear 명령어 처리: 대화 히스토리 초기화"""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    try:
        context_manager.clear()
        context_manager.save_to_file()
        await update.message.reply_text("대화 히스토리를 초기화했습니다.")
    except Exception as e:
        await update.message.reply_text(f"히스토리 초기화 중 오류 발생: {e}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status 명령어 처리: workspace 폴더 파일 목록 출력"""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return
    try:
        files = executor.list_files()
        if files:
            text = "현재 workspace 파일 목록:\n" + "\n".join(f"- {f}" for f in files)
        else:
            text = "workspace 폴더가 비어 있습니다."
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"상태 조회 중 오류 발생: {e}")


def _store_pending_code(code: str) -> str:
    """코드 블록을 캐시에 저장하고 콜백용 식별자를 반환한다."""
    global _pending_id_counter
    _pending_id_counter += 1
    pending_id = str(_pending_id_counter)
    pending_code_blocks[pending_id] = code
    return pending_id


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """일반 메시지 처리: Claude와 멀티턴 대화"""
    if not is_allowed(update):
        await update.message.reply_text("접근이 허용되지 않은 사용자입니다.")
        return

    user_text = update.message.text
    try:
        context_manager.add("user", user_text)
        reply_text = claude_client.ask(context_manager.get())
        context_manager.add("assistant", reply_text)
        context_manager.save_to_file()

        await send_long_message(update.message, reply_text)

        # 코드 블록 감지 시 인라인 키보드로 실행 여부를 묻는다
        code_blocks = ClaudeClient.extract_code_blocks(reply_text)
        for code in code_blocks:
            pending_id = _store_pending_code(code)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ 실행", callback_data=f"run:{pending_id}"),
                    InlineKeyboardButton("⏭️ 건너뜀", callback_data=f"skip:{pending_id}"),
                ]
            ])
            await update.message.reply_text(
                "코드 블록이 감지되었습니다. 실행하시겠습니까?",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.exception("메시지 처리 중 오류 발생")
        await update.message.reply_text(f"오류가 발생했습니다: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """인라인 키보드 콜백 처리: 코드 실행 또는 건너뜀"""
    query = update.callback_query
    if not is_allowed(update):
        await query.answer("접근이 허용되지 않은 사용자입니다.", show_alert=True)
        return

    await query.answer()

    try:
        action, pending_id = query.data.split(":", 1)
    except ValueError:
        return

    code = pending_code_blocks.pop(pending_id, None)

    if action == "skip":
        await query.edit_message_text("코드 실행을 건너뛰었습니다.")
        return

    if action != "run":
        return

    if code is None:
        await query.edit_message_text("코드 정보를 찾을 수 없습니다. (이미 처리되었거나 만료됨)")
        return

    await query.edit_message_text("코드를 실행 중입니다...")

    try:
        filepath = executor.save_code(code)
        stdout, stderr, returncode = executor.run(filepath)

        result_text = (
            f"실행 결과 (returncode={returncode})\n"
            f"--- stdout ---\n{stdout or '(없음)'}\n"
            f"--- stderr ---\n{stderr or '(없음)'}"
        )
        await send_long_message(query.message, result_text)

        # 실행 결과를 히스토리에 추가하여 Claude가 분석할 수 있도록 한다
        context_manager.add(
            "user",
            f"다음 코드를 실행한 결과입니다.\n[stdout]\n{stdout}\n[stderr]\n{stderr}\n"
            f"[returncode] {returncode}\n원인을 분석하고 개선안을 제시해주세요.",
        )
        analysis = claude_client.ask(context_manager.get())
        context_manager.add("assistant", analysis)
        context_manager.save_to_file()

        await send_long_message(query.message, analysis)

        # 분석 결과에 새로운 코드 블록이 있으면 다시 실행 버튼 제공
        code_blocks = ClaudeClient.extract_code_blocks(analysis)
        for new_code in code_blocks:
            new_pending_id = _store_pending_code(new_code)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("▶️ 실행", callback_data=f"run:{new_pending_id}"),
                    InlineKeyboardButton("⏭️ 건너뜀", callback_data=f"skip:{new_pending_id}"),
                ]
            ])
            await query.message.reply_text(
                "개선된 코드 블록이 감지되었습니다. 실행하시겠습니까?",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.exception("코드 실행 처리 중 오류 발생")
        await send_long_message(query.message, f"코드 실행 중 오류가 발생했습니다: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """전역 에러 핸들러: 에러 발생 시 텔레그램으로 에러 내용 전송"""
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

    # 이전 세션의 대화 히스토리 불러오기
    context_manager.load_from_file()

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("텔레그램 개발 봇을 시작합니다.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
