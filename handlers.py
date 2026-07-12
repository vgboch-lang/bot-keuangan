import os
import re
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import (
    save_transaction, get_transactions, get_transaction_by_id,
    update_transaction, delete_transaction, get_summary,
    get_user_settings, update_user_setting,
    get_transaction_history, get_all_users
)
from keyboards import (
    get_main_keyboard, get_start_menu, get_after_add_menu,
    get_after_report_menu, get_settings_menu, get_budget_menu,
    get_edit_menu, get_edit_action_menu, get_confirm_delete_menu,
    get_hidden_menu, get_hidden_edit_menu
)
from parser import parse_transaction
from report import generate_pdf_report
from utils import format_rupiah, get_date_range, format_date
from config import CATEGORY_DISPLAY

logger = logging.getLogger(__name__)

# ==================== START & HELP ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Halo {user.first_name}! Selamat datang di Bot Catat Keuangan!\n\n"
        "📝 Kirim chat bebas seperti:\n"
        "• 'makan siang 25rb'\n"
        "• 'gaji 4jt'\n"
        "• 'investasi saham 1jt'\n\n"
        "Atau pilih menu di bawah!",
        parse_mode=ParseMode.HTML,
        reply_markup=get_start_menu(visible=True)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
❓ <b>Panduan Penggunaan</b>

📝 <b>Catat Transaksi:</b>
Kirim pesan seperti:
• "makan siang 25rb" → pengeluaran
• "gaji 4jt" → pemasukan
• "investasi saham 1jt" → investasi

📊 <b>Lihat Laporan:</b>
• Rekap Harian / Mingguan / Bulanan
• Bulan Berjalan (dari tanggal 1 sampai hari ini)

✏️ <b>Edit Transaksi:</b>
• Pilih transaksi dari daftar hari ini
• Edit item, kategori, atau nominal

⚙️ <b>Settings:</b>
• Ubah waktu rekap otomatis
• Set budget per kategori
• Target investasi & pemasukan
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

# ==================== GENERATE REPORT (UNIVERSAL) ====================

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str, start_date=None, end_date=None):
    """Generate report - bisa dipanggil dari chat ATAU callback"""
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None
    
    today = datetime.now().date()
    
    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'month_to_date':
        start_date = today.replace(day=1)
        end_date = today
    
    if not start_date or not end_date:
        if is_callback:
            await update.callback_query.edit_message_text("❌ Tanggal tidak valid.")
        else:
            await update.message.reply_text("❌ Tanggal tidak valid.")
        return
    
    # Kirim loading
    if is_callback:
        query = update.callback_query
        await query.answer()
        msg = await query.edit_message_text("⏳ Membuat laporan...")
    else:
        msg = await update.message.reply_text("⏳ Membuat laporan...")
    
    period_labels = {
        'today': 'Harian',
        'week': 'Mingguan',
        'month': 'Bulanan',
        'month_to_date': 'Bulanan'
    }
    label = period_labels.get(period, 'Laporan')
    
    if period in ['month', 'month_to_date']:
        date_str = start_date.strftime('%d-%m-%y')
    else:
        date_str = today.strftime('%d-%m-%y')
    
    filename = generate_pdf_report(user_id, start_date, end_date, period, label, date_str)
    
    if not filename:
        await msg.delete()
        await update.effective_chat.send_message(
            "📭 Belum ada transaksi di periode ini.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Kirim PDF
    with open(filename, 'rb') as f:
        if is_callback:
            await update.effective_chat.send_document(
                document=f,
                filename=os.path.basename(filename),
                caption=f"📊 Laporan {label}\n{format_date(start_date)} - {format_date(end_date)}",
                reply_markup=get_after_report_menu(visible=False)
            )
        else:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(filename),
                caption=f"📊 Laporan {label}\n{format_date(start_date)} - {format_date(end_date)}",
                reply_markup=get_after_report_menu(visible=False)
            )
    
    # Reply keyboard
    if is_callback:
        await update.effective_chat.send_message(
            "Apa ada pengeluaran lain? 👀",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "Apa ada pengeluaran lain? 👀",
            reply_markup=get_main_keyboard()
        )
    
    await msg.delete()
    try:
        os.remove(filename)
    except:
        pass

# ==================== HANDLE MESSAGE ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"📩 Pesan dari {user_id}: {text}")
    
    # ===== HANDLE EDIT INPUT =====
    if context.user_data.get('editing'):
        editing_type = context.user_data['editing']
        
        if editing_type.startswith('item_'):
            trans_id = int(editing_type.replace('item_', ''))
            transaction = get_transaction_by_id(user_id, trans_id)
            if transaction:
                update_transaction(user_id, trans_id, 'item', text, transaction['item'])
                await update.message.reply_text(
                    f"✅ Item diubah menjadi: {text}",
                    reply_markup=get_main_keyboard()
                )
                context.user_data['editing'] = None
                return
        
        elif editing_type.startswith('amount_'):
            from utils import parse_nominal
            trans_id = int(editing_type.replace('amount_', ''))
            transaction = get_transaction_by_id(user_id, trans_id)
            if transaction:
                amount = parse_nominal(text)
                if not amount:
                    try:
                        amount = int(text.replace('.', '').replace(',', ''))
                    except:
                        await update.message.reply_text("❌ Nominal tidak valid. Contoh: 25000 atau 25k")
                        return
                update_transaction(user_id, trans_id, 'amount', amount, transaction['amount'])
                await update.message.reply_text(
                    f"✅ Nominal diubah menjadi: {format_rupiah(amount)}",
                    reply_markup=get_main_keyboard()
                )
                context.user_data['editing'] = None
                return
        
        context.user_data['editing'] = None
    
    # ===== HANDLE RESEND =====
    if context.user_data.get('resend'):
        trans_id = context.user_data['resend']
        transaction = get_transaction_by_id(user_id, trans_id)
        if transaction:
            results = parse_transaction(text)
            if results and isinstance(results, list) and len(results) > 0:
                result = results[0]
                if result.get('item'):
                    update_transaction(user_id, trans_id, 'item', result['item'], transaction['item'])
                if result.get('amount'):
                    update_transaction(user_id, trans_id, 'amount', result['amount'], transaction['amount'])
                await update.message.reply_text(
                    f"✅ Transaksi #{trans_id} berhasil diupdate!",
                    reply_markup=get_main_keyboard()
                )
                context.user_data['resend'] = None
                return
        context.user_data['resend'] = None
    
    # ===== TOMBOL REPLY KEYBOARD =====
    if text == "📝 Catat Cepat":
        await update.message.reply_text(
            "📝 Kirim pesan dengan format:\n\n"
            "• 'makan siang 25rb'\n"
            "• 'gojek 15rb'\n"
            "• 'beli sayur 50rb'\n\n"
            "Atau chat bebas seperti biasa!",
            reply_markup=get_main_keyboard()
        )
        return
    
    elif text == "💰 Pemasukan":
        await update.message.reply_text(
            "💰 Kirim pemasukan:\n\n"
            "• 'gaji 4jt'\n"
            "• 'bonus 500k'\n"
            "• 'freelance 1.5jt'\n\n"
            "Atau chat bebas dengan keyword 'gaji', 'bonus', dll",
            reply_markup=get_main_keyboard()
        )
        return
    
    elif text == "📈 Investasi":
        await update.message.reply_text(
            "📈 Kirim investasi:\n\n"
            "• 'investasi saham 1jt'\n"
            "• 'investasi tabungan 500k'\n"
            "• 'investasi kripto 1jt'\n\n"
            "Atau chat bebas dengan keyword 'investasi'",
            reply_markup=get_main_keyboard()
        )
        return
    
    elif text == "📊 Rekap Harian":
        await generate_report(update, context, "today")
        return
    
    elif text == "📈 Rekap Mingguan":
        await generate_report(update, context, "week")
        return
    
    elif text == "📉 Rekap Bulanan":
        await generate_report(update, context, "month")
        return
    
    elif text == "📅 Bulan Berjalan":
        await generate_report(update, context, "month_to_date")
        return
    
    elif text == "✏️ Edit Transaksi":
        await show_edit_menu(update, context)
        return
    
    elif text == "⚙️ Settings":
        await settings_menu(update, context)
        return
    
    elif text == "❓ Bantuan":
        await help_command(update, context)
        return
    
    # Cek setting input
    if context.user_data.get('waiting_for') == 'set_time':
        await handle_set_time(update, context, text)
        return
    
    if context.user_data.get('waiting_for') and context.user_data['waiting_for'].startswith('budget_'):
        await handle_set_budget(update, context, text)
        return
    
    if context.user_data.get('waiting_for') == 'set_investment_target':
        await handle_set_investment_target(update, context, text)
        return
    
    if context.user_data.get('waiting_for') == 'set_income_target':
        await handle_set_income_target(update, context, text)
        return
    
    # Proses transaksi
    logger.info(f"🔄 Memanggil process_transaction untuk: {text[:50]}...")
    await process_transaction(update, context, text)

# ==================== PROCESS TRANSACTION ====================

async def process_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Proses transaksi dari chat"""
    user_id = update.effective_user.id
    
    try:
        logger.info(f"🔄 START process_transaction: {text[:50]}...")
        
        results = parse_transaction(text)
        
        # SAFETY: pastikan results adalah list
        if isinstance(results, dict):
            results = [results]
        elif not isinstance(results, list):
            results = []
        
        logger.info(f"📊 Hasil parse: {results}")
        
        if not results:
            await update.message.reply_text(
                "❌ Tidak ditemukan nominal.\n\n"
                "Contoh:\n"
                "• 'makan siang 25rb'\n"
                "• 'gaji 4jt'\n"
                "• 'investasi saham 1jt'",
                reply_markup=get_main_keyboard()
            )
            return
        
        saved = []
        for result in results:
            trans_id = save_transaction(
                user_id=user_id,
                type_=result.get('type', 'expense'),
                amount=result['amount'],
                category=result.get('category', 'lainnya'),
                item=result.get('item', 'transaksi'),
                note=result.get('note', text)
            )
            saved.append({**result, 'id': trans_id})
        
        if len(saved) == 1:
            r = saved[0]
            cat_name = CATEGORY_DISPLAY.get(r['category'], r['category'].capitalize())
            msg = f"✅ Dicatat: {cat_name} {format_rupiah(r['amount'])} - {r['item']}"
        else:
            msg = f"✅ Dicatat {len(saved)} transaksi!\n\n"
            for i, r in enumerate(saved, 1):
                cat_name = CATEGORY_DISPLAY.get(r['category'], r['category'].capitalize())
                msg += f"{i}. {cat_name} {format_rupiah(r['amount'])} - {r['item']}\n"
        
        # Kirim pesan transaksi dan simpan referensi
        sent_msg = await update.message.reply_text(
            msg,
            reply_markup=get_after_add_menu(visible=False)
        )
        
        # Simpan data transaksi untuk tombol "Kembali"
        context.user_data['last_transaction_data'] = {
            'chat_id': sent_msg.chat_id,
            'message_id': sent_msg.message_id,
            'text': msg,
            'from_transaction': True
        }
        
        # Reply keyboard tetap muncul
        await update.message.reply_text(
            "Apa ada pengeluaran lain? 👀",
            reply_markup=get_main_keyboard()
        )
        
        logger.info("✅ Selesai process_transaction")
        
    except Exception as e:
        logger.error(f"❌ ERROR di process_transaction: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"⚠️ Error: {str(e)[:100]}",
            reply_markup=get_main_keyboard()
        )

# ==================== SHOW EDIT MENU ====================

async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user_id = update.effective_user.id
    
    today = datetime.now().date().isoformat()
    transactions = get_transactions(user_id, today, today)
    
    if not transactions:
        await update.message.reply_text(
            "📭 Belum ada transaksi hari ini yang bisa diedit.",
            reply_markup=get_main_keyboard()
        )
        return
    
    now = datetime.now()
    editable = []
    for t in transactions:
        created_at = datetime.fromisoformat(t['created_at'])
        age = (now - created_at).total_seconds() / 3600
        if age <= 24:
            t['category_emoji'] = CATEGORY_DISPLAY.get(t['category'], '📦')
            editable.append(t)
    
    if not editable:
        await update.message.reply_text(
            "⛔ Semua transaksi hari ini sudah lebih dari 24 jam dan tidak bisa diedit.",
            reply_markup=get_main_keyboard()
        )
        return
    
    context.user_data['editable_transactions'] = editable
    context.user_data['edit_page'] = page
    
    msg = "✏️ <b>Pilih transaksi yang mau diedit:</b>\n\n"
    
    start_idx = page * 10
    end_idx = min(start_idx + 10, len(editable))
    current_page = editable[start_idx:end_idx]
    
    for i, t in enumerate(current_page, start_idx + 1):
        msg += f"{i}. {CATEGORY_DISPLAY.get(t['category'], t['category'])} {format_rupiah(t['amount'])} - {t['item']}\n"
    
    if len(editable) > 10:
        msg += f"\nHalaman {page + 1} dari {(len(editable) + 9) // 10}"
    
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.HTML,
        reply_markup=get_edit_menu(editable, page, visible=True)
    )

# ==================== SETTINGS ====================

# ==================== SETTINGS MENU ====================
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    text = """
⚙️ <b>Settings</b>

💰 Di sini kamu bisa mengatur budget bulanan, target investasi, 
dan waktu laporan otomatis. Semua nominal adalah per bulan.

📅 <b>Waktu Laporan Otomatis:</b> {}
""".format(settings.get('report_time', '20:00'))

    text += "\n💰 <b>Budget per kategori (per bulan):</b>\n"
    budget_categories = [
        ('makanan', '🍔 Makanan'),
        ('jajanan', '🍿 Jajanan'),
        ('minuman', '🥤 Minuman'),
        ('rokok', '🚬 Rokok'),
        ('transport', '🚗 Transport'),
        ('belanja', '🛒 Belanja'),
        ('tagihan', '📄 Tagihan'),
        ('hiburan', '🎮 Hiburan'),
        ('kesehatan', '💊 Kesehatan'),
        ('pendidikan', '📚 Pendidikan')
    ]

    for key, label in budget_categories:
        value = settings.get(f'budget_{key}', 0)
        if value > 0:
            text += f"• {label}: {format_rupiah(value)}\n"
        else:
            text += f"• {label}: Belum diatur\n"

    inv_target = settings.get('investment_target', 0)
    inc_target = settings.get('income_target', 0)
    text += f"\n📈 <b>Target Investasi Bulanan:</b> {format_rupiah(inv_target) if inv_target > 0 else 'Belum diatur'}"
    text += f"\n💰 <b>Target Pemasukan Bulanan:</b> {format_rupiah(inc_target) if inc_target > 0 else 'Belum diatur'}"

    text += """
    
💡 <b>Tips:</b>
• Budget = batas maksimal pengeluaran per kategori per bulan
• Target Investasi = target nominal investasi per bulan
• Target Pemasukan = target pemasukan per bulan
• Laporan otomatis dikirim setiap hari jam yang kamu atur
"""

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_settings_menu()
    )

# ==================== HANDLE SETTINGS INPUT ====================

async def handle_set_time(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    
    if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', text):
        update_user_setting(user_id, 'report_time', text)
        await update.message.reply_text(
            f"✅ Waktu laporan diubah menjadi {text}",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Format jam salah. Gunakan format HH:MM (contoh: 20:00)",
            reply_markup=get_main_keyboard()
        )
    context.user_data['waiting_for'] = None

async def handle_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    category = context.user_data['waiting_for'].replace('budget_', '')
    
    from utils import parse_nominal
    amount = parse_nominal(text)
    if not amount:
        try:
            amount = int(text.replace('.', '').replace(',', ''))
        except:
            await update.message.reply_text("❌ Nominal tidak valid. Gunakan format: 1000000 atau 1jt")
            return
    
    update_user_setting(user_id, f'budget_{category}', amount)
    await update.message.reply_text(
        f"✅ Budget {category} diubah menjadi {format_rupiah(amount)}",
        reply_markup=get_main_keyboard()
    )
    context.user_data['waiting_for'] = None

async def handle_set_investment_target(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    
    from utils import parse_nominal
    amount = parse_nominal(text)
    if not amount:
        try:
            amount = int(text.replace('.', '').replace(',', ''))
        except:
            await update.message.reply_text("❌ Nominal tidak valid.")
            return
    
    update_user_setting(user_id, 'investment_target', amount)
    await update.message.reply_text(
        f"✅ Target investasi diubah menjadi {format_rupiah(amount)}",
        reply_markup=get_main_keyboard()
    )
    context.user_data['waiting_for'] = None

async def handle_set_income_target(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    
    from utils import parse_nominal
    amount = parse_nominal(text)
    if not amount:
        try:
            amount = int(text.replace('.', '').replace(',', ''))
        except:
            await update.message.reply_text("❌ Nominal tidak valid.")
            return
    
    update_user_setting(user_id, 'income_target', amount)
    await update.message.reply_text(
        f"✅ Target pemasukan diubah menjadi {format_rupiah(amount)}",
        reply_markup=get_main_keyboard()
    )
    context.user_data['waiting_for'] = None

# ==================== TOGGLE MENU ====================

async def toggle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "hide_menu":
        context.user_data['menu_visible'] = False
        await query.edit_message_reply_markup(
            reply_markup=get_hidden_menu()
        )
    
    elif data == "show_menu":
        context.user_data['menu_visible'] = True
        await query.edit_message_reply_markup(
            reply_markup=get_start_menu(visible=True)
        )
    
    elif data == "hide_edit_menu":
        context.user_data['edit_menu_visible'] = False
        await query.edit_message_reply_markup(
            reply_markup=get_hidden_edit_menu()
        )
    
    elif data == "show_edit_menu":
        context.user_data['edit_menu_visible'] = True
        editable = context.user_data.get('editable_transactions', [])
        page = context.user_data.get('edit_page', 0)
        await query.edit_message_reply_markup(
            reply_markup=get_edit_menu(editable, page, visible=True)
        )

# ==================== HANDLE CALLBACK ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    logger.info(f"📌 Callback: {data}")
    
    # ===== BACK TO PREVIOUS =====
    if data == "back_to_previous":
        # Cek apakah ada pesan transaksi yang disimpan
        last_data = context.user_data.get('last_transaction_data')
        if last_data and last_data.get('from_transaction'):
            # Restore pesan transaksi
            try:
                await query.edit_message_text(
                    last_data['text'],
                    reply_markup=get_after_add_menu(visible=False)
                )
                # Hapus data agar tidak dipakai lagi
                context.user_data['last_transaction_data'] = None
                return
            except Exception as e:
                logger.error(f"Error restoring transaction message: {e}")
        
        # Fallback ke menu utama
        await query.edit_message_text(
            "🏠 <b>Menu Utama</b>\n\nPilih menu di bawah:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_start_menu(visible=True)
        )
        return
    
    # ===== MAIN MENU =====
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 <b>Menu Utama</b>\n\nPilih menu di bawah:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_start_menu(visible=True)
        )
        return
    
    # ===== QUICK ADD =====
    elif data == "quick_add":
        await query.edit_message_text(
            "📝 Kirim chat bebas seperti:\n\n"
            "• 'makan siang 25rb'\n"
            "• 'gaji 4jt'\n"
            "• 'investasi saham 1jt'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        return
    
    elif data == "income_add":
        await query.edit_message_text(
            "💰 Kirim pemasukan:\n\n"
            "• 'gaji 4jt'\n"
            "• 'bonus 500k'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        return
    
    elif data == "investment_add":
        await query.edit_message_text(
            "📈 Kirim investasi:\n\n"
            "• 'investasi saham 1jt'",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        return
    
    # ===== REPORT =====
    elif data.startswith("report_"):
        period = data.replace("report_", "")
        if period == "today":
            await generate_report(update, context, "today")
        elif period == "week":
            await generate_report(update, context, "week")
        elif period == "month":
            await generate_report(update, context, "month")
        elif period == "month_to_date":
            await generate_report(update, context, "month_to_date")
        return
    
    # ===== EDIT =====
    elif data == "edit_menu":
        await show_edit_menu_callback(update, context)
        return
    
    elif data.startswith("edit_page_"):
        page = int(data.replace("edit_page_", ""))
        await show_edit_menu_callback(update, context, page)
        return
    
    elif data == "edit_last":
        today = datetime.now().date().isoformat()
        transactions = get_transactions(user_id, today, today)
        if transactions:
            for t in transactions:
                if not t.get('is_deleted'):
                    await query.edit_message_text(
                        f"✏️ Edit transaksi terakhir:\n\n"
                        f"📝 Item: {t['item']}\n"
                        f"📂 Kategori: {CATEGORY_DISPLAY.get(t['category'], t['category'])}\n"
                        f"💰 Nominal: {format_rupiah(t['amount'])}",
                        reply_markup=get_edit_action_menu(t['id'])
                    )
                    return
        await query.edit_message_text("❌ Tidak ada transaksi hari ini.")
        return
    
    # ===== EDIT ACTIONS (SPESIFIK DULU) =====
    elif data.startswith("edit_item_"):
        trans_id = int(data.replace("edit_item_", ""))
        await query.edit_message_text(
            f"✏️ Masukkan item baru untuk transaksi #{trans_id}:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Batal", callback_data=f"back_to_edit_{trans_id}")]
            ])
        )
        context.user_data['editing'] = f'item_{trans_id}'
        return
    
    elif data.startswith("edit_category_"):
        trans_id = int(data.replace("edit_category_", ""))
        keyboard = [
            [InlineKeyboardButton("🍔 Makanan", callback_data=f"cat_{trans_id}_makanan"),
             InlineKeyboardButton("🍿 Jajanan", callback_data=f"cat_{trans_id}_jajanan")],
            [InlineKeyboardButton("🥤 Minuman", callback_data=f"cat_{trans_id}_minuman"),
             InlineKeyboardButton("🚬 Rokok", callback_data=f"cat_{trans_id}_rokok")],
            [InlineKeyboardButton("🚗 Transport", callback_data=f"cat_{trans_id}_transport"),
             InlineKeyboardButton("🛒 Belanja", callback_data=f"cat_{trans_id}_belanja")],
            [InlineKeyboardButton("📄 Tagihan", callback_data=f"cat_{trans_id}_tagihan"),
             InlineKeyboardButton("🎮 Hiburan", callback_data=f"cat_{trans_id}_hiburan")],
            [InlineKeyboardButton("💊 Kesehatan", callback_data=f"cat_{trans_id}_kesehatan"),
             InlineKeyboardButton("📚 Pendidikan", callback_data=f"cat_{trans_id}_pendidikan")],
            [InlineKeyboardButton("💰 Pemasukan", callback_data=f"cat_{trans_id}_income"),
             InlineKeyboardButton("📈 Investasi", callback_data=f"cat_{trans_id}_investment")],
            [InlineKeyboardButton("📦 Lainnya", callback_data=f"cat_{trans_id}_lainnya")],
            [InlineKeyboardButton("↩️ Batal", callback_data=f"back_to_edit_{trans_id}")]
        ]
        await query.edit_message_text(
            f"📂 Pilih kategori baru untuk transaksi #{trans_id}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    elif data.startswith("cat_"):
        parts = data.split("_")
        trans_id = int(parts[1])
        category = parts[2]
        
        old_data = get_transaction_by_id(user_id, trans_id)
        if old_data:
            update_transaction(user_id, trans_id, 'category', category, old_data['category'])
            # Kembali ke detail transaksi
            await query.edit_message_text(
                f"✅ Kategori diubah menjadi {CATEGORY_DISPLAY.get(category, category)}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ Kembali", callback_data=f"back_to_edit_{trans_id}")]
                ])
            )
        return
    
    elif data.startswith("edit_amount_"):
        trans_id = int(data.replace("edit_amount_", ""))
        await query.edit_message_text(
            f"💰 Masukkan nominal baru untuk transaksi #{trans_id}:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Batal", callback_data=f"back_to_edit_{trans_id}")]
            ])
        )
        context.user_data['editing'] = f'amount_{trans_id}'
        return
    
    elif data.startswith("resend_"):
        trans_id = int(data.replace("resend_", ""))
        transaction = get_transaction_by_id(user_id, trans_id)
        if transaction:
            template = f"{transaction['item']} {transaction['amount']}"
            await query.edit_message_text(
                f"🔄 Kirim ulang chat untuk transaksi #{trans_id}:\n\n"
                f"Ketik: `{template}`\n\n"
                f"(Edit lalu kirim, bot akan update transaksi ini)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ Batal", callback_data=f"back_to_edit_{trans_id}")]
                ])
            )
            context.user_data['resend'] = trans_id
        return
    
    # ===== BACK TO EDIT (kembali ke detail transaksi) =====
    elif data.startswith("back_to_edit_"):
        trans_id = int(data.replace("back_to_edit_", ""))
        transaction = get_transaction_by_id(user_id, trans_id)
        if transaction:
            text = f"""
✏️ <b>Edit Transaksi #{trans_id}</b>

📝 Item: {transaction['item']}
📂 Kategori: {CATEGORY_DISPLAY.get(transaction['category'], transaction['category'])}
💰 Nominal: {format_rupiah(transaction['amount'])}
📅 Tanggal: {format_date(transaction['date'])}
"""
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_edit_action_menu(trans_id)
            )
        return
    
    # ===== CATCH ALL EDIT (DI PALING BAWAH) =====
    elif data.startswith("edit_"):
        trans_id = int(data.replace("edit_", ""))
        transaction = get_transaction_by_id(user_id, trans_id)
        if not transaction:
            await query.edit_message_text("❌ Transaksi tidak ditemukan.")
            return
        
        created_at = datetime.fromisoformat(transaction['created_at'])
        age = (datetime.now() - created_at).total_seconds() / 3600
        if age > 24:
            await query.edit_message_text(
                "⛔ Transaksi ini sudah lebih dari 24 jam dan tidak bisa diedit.",
                reply_markup=get_main_keyboard()
            )
            return
        
        text = f"""
✏️ <b>Edit Transaksi #{trans_id}</b>

📝 Item: {transaction['item']}
📂 Kategori: {CATEGORY_DISPLAY.get(transaction['category'], transaction['category'])}
💰 Nominal: {format_rupiah(transaction['amount'])}
📅 Tanggal: {format_date(transaction['date'])}
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_edit_action_menu(trans_id)
        )
        return
    
    # ===== DELETE =====
    elif data.startswith("delete_"):
        trans_id = int(data.replace("delete_", ""))
        await query.edit_message_text(
            f"⚠️ Yakin mau hapus transaksi #{trans_id}?\n\nData akan tetap tersimpan di history.",
            reply_markup=get_confirm_delete_menu(trans_id)
        )
        return
    
    elif data.startswith("confirm_delete_"):
        trans_id = int(data.replace("confirm_delete_", ""))
        if delete_transaction(user_id, trans_id):
            await query.edit_message_text(
                f"✅ Transaksi #{trans_id} berhasil dihapus.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
                ])
            )
        else:
            await query.edit_message_text(
                "❌ Gagal menghapus transaksi.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
                ])
            )
        return
    
    # ===== SETTINGS =====
    elif data == "settings":
        await settings_menu_callback(update, context)
        return
    
    elif data == "set_time":
        await query.edit_message_text(
            "⏰ Masukkan waktu laporan baru (format HH:MM):\n\nContoh: 20:00",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        context.user_data['waiting_for'] = 'set_time'
        return
    
    elif data == "set_budget":
        await query.edit_message_text(
            "💰 Pilih kategori untuk set budget:",
            reply_markup=get_budget_menu()
        )
        return
    
    elif data.startswith("budget_"):
        category = data.replace("budget_", "")
        cat_names = {
            'makanan': '🍔 Makanan', 'jajanan': '🍿 Jajanan', 'minuman': '🥤 Minuman',
            'rokok': '🚬 Rokok', 'transport': '🚗 Transport',
            'belanja': '🛒 Belanja', 'tagihan': '📄 Tagihan',
            'hiburan': '🎮 Hiburan', 'kesehatan': '💊 Kesehatan',
            'pendidikan': '📚 Pendidikan'
        }
        await query.edit_message_text(
            f"💰 Masukkan budget untuk {cat_names.get(category, category)}:\n\nContoh: 1000000 atau 1jt",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        context.user_data['waiting_for'] = f'budget_{category}'
        return
    
    elif data == "set_investment_target":
        await query.edit_message_text(
            "📈 Masukkan target investasi bulanan:\n\nContoh: 5000000 atau 5jt",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        context.user_data['waiting_for'] = 'set_investment_target'
        return
    
    elif data == "set_income_target":
        await query.edit_message_text(
            "💰 Masukkan target pemasukan bulanan:\n\nContoh: 5000000 atau 5jt",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        context.user_data['waiting_for'] = 'set_income_target'
        return
    
    elif data == "manual_review":
        await generate_report(update, context, "today")
        return
    
    # ===== TOGGLE MENU =====
    elif data in ["hide_menu", "show_menu", "hide_edit_menu", "show_edit_menu"]:
        await toggle_menu(update, context)
        return
    
    # ===== HELP =====
    elif data == "help":
        await query.edit_message_text(
            "❓ <b>Panduan Penggunaan</b>\n\n"
            "📝 <b>Catat Transaksi:</b>\n"
            "Kirim chat bebas dengan format:\n"
            "• 'makan siang 25rb' → pengeluaran\n"
            "• 'gaji 4jt' → pemasukan\n"
            "• 'investasi saham 1jt' → investasi\n\n"
            "📊 <b>Lihat Laporan:</b>\n"
            "Pilih menu Rekap Harian/Mingguan/Bulanan/Bulan Berjalan\n\n"
            "✏️ <b>Edit Transaksi:</b>\n"
            "Pilih transaksi dari daftar hari ini\n\n"
            "⚙️ <b>Settings:</b>\n"
            "Atur budget, target, dan waktu rekap",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
            ])
        )
        return

# ==================== CALLBACK HELPERS ====================

async def show_edit_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    user_id = update.effective_user.id
    query = update.callback_query
    
    today = datetime.now().date().isoformat()
    transactions = get_transactions(user_id, today, today)
    
    if not transactions:
        await query.edit_message_text(
            "📭 Belum ada transaksi hari ini.",
            reply_markup=get_main_keyboard()
        )
        return
    
    now = datetime.now()
    editable = []
    for t in transactions:
        created_at = datetime.fromisoformat(t['created_at'])
        age = (now - created_at).total_seconds() / 3600
        if age <= 24:
            t['category_emoji'] = CATEGORY_DISPLAY.get(t['category'], '📦')
            editable.append(t)
    
    if not editable:
        await query.edit_message_text(
            "⛔ Semua transaksi sudah lebih dari 24 jam.",
            reply_markup=get_main_keyboard()
        )
        return
    
    context.user_data['editable_transactions'] = editable
    context.user_data['edit_page'] = page
    
    msg = "✏️ <b>Pilih transaksi yang mau diedit:</b>\n\n"
    
    start_idx = page * 10
    end_idx = min(start_idx + 10, len(editable))
    current_page = editable[start_idx:end_idx]
    
    for i, t in enumerate(current_page, start_idx + 1):
        msg += f"{i}. {CATEGORY_DISPLAY.get(t['category'], t['category'])} {format_rupiah(t['amount'])} - {t['item']}\n"
    
    if len(editable) > 10:
        msg += f"\nHalaman {page + 1} dari {(len(editable) + 9) // 10}"
    
    await query.edit_message_text(
        msg,
        parse_mode=ParseMode.HTML,
        reply_markup=get_edit_menu(editable, page, visible=True)
    )



# ==================== AUTO REPORT ====================

async def auto_report():
    """Kirim laporan otomatis setiap hari ke semua user"""
    from telegram import Bot
    from config import BOT_TOKEN
    from database import get_all_users
    from report import generate_pdf_report
    from utils import format_date
    
    bot = Bot(token=BOT_TOKEN)
    users = get_all_users()
    
    for user_id in users:
        try:
            today = datetime.now().date()
            period = 'today'
            label = 'Harian'
            date_str = today.strftime('%d-%m-%y')
            filename = generate_pdf_report(user_id, today, today, period, label, date_str)
            if filename:
                with open(filename, 'rb') as f:
                    await bot.send_document(
                        chat_id=user_id,
                        document=f,
                        filename=os.path.basename(filename),
                        caption=f"📊 Laporan Harian\n{format_date(today)}"
                    )
                os.remove(filename)
        except Exception as e:
            print(f"Auto report error for {user_id}: {e}")




async def settings_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query
    settings = get_user_settings(user_id)
    
    text = """
⚙️ <b>Settings</b>

💰 Di sini kamu bisa mengatur budget bulanan, target investasi, 
dan waktu laporan otomatis. Semua nominal adalah per bulan.

📅 <b>Waktu Laporan Otomatis:</b> {}
""".format(settings.get('report_time', '20:00'))



    
    # Budget per kategori (tampilkan "Belum diatur" jika 0)
# ==================== SETTINGS MENU ====================
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    text = """
⚙️ <b>Settings</b>

💰 Di sini kamu bisa mengatur budget bulanan, target investasi, 
dan waktu laporan otomatis. Semua nominal adalah per bulan.

📅 <b>Waktu Laporan Otomatis:</b> {}
""".format(settings.get('report_time', '20:00'))

    text += "\n💰 <b>Budget per kategori (per bulan):</b>\n"
    budget_categories = [
        ('makanan', '🍔 Makanan'),
        ('jajanan', '🍿 Jajanan'),
        ('minuman', '🥤 Minuman'),
        ('rokok', '🚬 Rokok'),
        ('transport', '🚗 Transport'),
        ('belanja', '🛒 Belanja'),
        ('tagihan', '📄 Tagihan'),
        ('hiburan', '🎮 Hiburan'),
        ('kesehatan', '💊 Kesehatan'),
        ('pendidikan', '📚 Pendidikan')
    ]

    for key, label in budget_categories:
        value = settings.get(f'budget_{key}', 0)
        if value > 0:
            text += f"• {label}: {format_rupiah(value)}\n"
        else:
            text += f"• {label}: Belum diatur\n"

    inv_target = settings.get('investment_target', 0)
    inc_target = settings.get('income_target', 0)
    text += f"\n📈 <b>Target Investasi Bulanan:</b> {format_rupiah(inv_target) if inv_target > 0 else 'Belum diatur'}"
    text += f"\n💰 <b>Target Pemasukan Bulanan:</b> {format_rupiah(inc_target) if inc_target > 0 else 'Belum diatur'}"

    text += """
    
💡 <b>Tips:</b>
• Budget = batas maksimal pengeluaran per kategori per bulan
• Target Investasi = target nominal investasi per bulan
• Target Pemasukan = target pemasukan per bulan
• Laporan otomatis dikirim setiap hari jam yang kamu atur
"""

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_settings_menu()
    )
