import logging
import os
from datetime import datetime
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, REPORT_TIME
from database import init_db
from keyboards import get_main_keyboard
from handlers import (
    start_command, help_command, handle_message, handle_callback,
    auto_report, generate_report
)
from utils import format_date

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MAIN ====================

def main():
    """Main function"""
    # Init database
    init_db()
    logger.info("✅ Database initialized")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Command: rekap custom
    async def rekap_command(update, context):
        args = context.args
        if len(args) >= 2:
            from utils import parse_date
            start = parse_date(args[0])
            end = parse_date(args[1])
            if start and end:
                await generate_report(update, context, "custom", start.date(), end.date())
                return
        await update.message.reply_text(
            "❌ Format: /rekap DD/MM/YYYY DD/MM/YYYY\n\nContoh: /rekap 01/07/2026 12/07/2026",
            reply_markup=get_main_keyboard()
        )
    
    application.add_handler(CommandHandler("rekap", rekap_command))
    
    # Command: edit
    async def edit_command(update, context):
        from handlers import show_edit_menu
        await show_edit_menu(update, context)
    
    application.add_handler(CommandHandler("edit", edit_command))
    
    # Command: review
    async def review_command(update, context):
        today = datetime.now().date()
        await generate_report(update, context, "today")
    
    application.add_handler(CommandHandler("review", review_command))
    
    # Callback & message handlers
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Scheduler untuk auto report
    scheduler = AsyncIOScheduler()
    hour, minute = map(int, REPORT_TIME.split(':'))
    scheduler.add_job(auto_report, CronTrigger(hour=hour, minute=minute))
    scheduler.start()
    
    logger.info(f"🤖 Bot started! Auto report at {REPORT_TIME}")
    logger.info(f"📅 Today: {datetime.now().strftime('%d %B %Y %H:%M')}")
    
    # Start polling
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()