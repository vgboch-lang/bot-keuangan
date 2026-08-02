import os
import re
import calendar
import logging
from typing import Optional
from datetime import datetime, timedelta, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import (
    save_transaction, get_transactions, get_transaction_by_id,
    update_transaction, delete_transaction, get_summary,
    get_user_settings, update_user_setting,
    get_transaction_history, get_all_users, get_transaction_months,
    is_owner, add_authorized_user, remove_authorized_user,
    get_authorized_users, is_owner_or_approved,
    has_trial, start_trial, is_trial_active
)
from keyboards import (
    get_main_keyboard, get_start_menu, get_feedback_menu,
    get_after_report_menu, get_settings_menu, get_budget_menu,
    get_edit_menu, get_edit_action_menu, get_confirm_delete_menu,
    get_hidden_menu, get_hidden_edit_menu
)
from parser import parse_transaction
from report import generate_pdf_report
from utils import format_rupiah, get_date_range, format_date
from config import CATEGORY_DISPLAY, TRIAL_DAYS

logger = logging.getLogger(__name__)

# ==================== PANDUAN LENGKAP ====================

HELP_TEXT = (
    "❓ <b>Panduan Lengkap Bot Catat Keuangan</b>\n\n"
    "📝 <b>1. Mencatat Transaksi</b>\n"
    "Kirim chat bebas, contoh:\n"
    "• 'makan siang 25rb' → pengeluaran\n"
    "• 'gaji 4jt' → pemasukan\n"
    "• 'gojek 15rb dan kopi 5rb' → 2 transaksi sekaligus\n\n"
    "🧭 <b>2. Tombol di bawah (Reply Keyboard)</b>\n"
    "• 📝 Catat Cepat → panduan mencatat\n"
    "• 💰 Pemasukan → catat pemasukan\n"
    "• � Pengeluaran Hari Ini → daftar transaksi hari ini\n"
    "• 📊 PDF Rekap Harian → laporan PDF hari ini\n"
    "• 📈 PDF Rekap Mingguan → laporan PDF minggu ini\n"
    "• 📉 PDF Rekap Bulanan → laporan PDF bulan ini\n"
    "• 📅 Bulan Berjalan → laporan tgl 1 sampai hari ini\n"
    "• ✏️ Edit Transaksi → edit/hapus transaksi hari ini\n"
    "• 📁 Riwayat → unduh PDF bulan-bulan sebelumnya\n"
    "• ⚙️ Settings → budget, target, waktu laporan otomatis\n"
    "• ❓ Bantuan → panduan ini\n\n"
    "💬 <b>3. Perintah Slash</b>\n"
    "• /rekap 01/07/2026 12/07/2026 → rekap tanggal tertentu\n"
    "• /edit → edit transaksi\n"
    "• /review → rekap hari ini\n"
    "• /myid → lihat User ID kamu\n\n"
    "🧠 <b>4. Bot Bisa Belajar</b>\n"
    "Kalau kategori salah, edit manual lewat ✏️ Edit Transaksi.\n"
    "Bot akan mengingat & memakai kategori itu untuk kata serupa.\n\n"
    "⚙️ <b>5. Settings</b>\n"
    "• ⏰ Atur Waktu Laporan → laporan otomatis harian\n"
    "• 💰 Atur Budget Bulanan → batas pengeluaran per kategori\n"
    "• 💵 Atur Target Pemasukan → target bulanan\n\n"
    "📁 <b>6. Riwayat</b>\n"
    "Buka 📁 Riwayat → pilih bulan → bot kirim laporan PDF bulan itu.\n\n"
    "💡 <b>Tips:</b> Semua data tersimpan otomatis di database.\n"
)

# ==================== AKSES KONTROL ====================

_NOTIFIED_OWNER = set()  # dedup notifikasi ke pemilik (per proses)

async def notify_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim notifikasi ke pemilik + tombol izinkan/tolak saat ada user baru"""
    from config import OWNER_ID
    if not OWNER_ID:
        return

    user = update.effective_user
    if not user:
        return
    uid = user.id
    if uid in _NOTIFIED_OWNER:
        return
    _NOTIFIED_OWNER.add(uid)

    name = (user.first_name or '').strip() or 'Tanpa nama'
    username = user.username or ''
    uname = f'@{username}' if username else '-'

    text = (
        f"🆕 <b>Ada yang mau pakai bot</b>\n\n"
        f"👤 Nama: {name}\n"
        f"🆔 User ID: <code>{uid}</code>\n"
        f"🔖 Username: {uname}\n\n"
        f"Pilih aksi:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Izinkan", callback_data=f"approve_{uid}"),
            InlineKeyboardButton("❌ Tolak", callback_data=f"deny_{uid}"),
        ]
    ])
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID, text=text,
            parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Gagal notifikasi owner: {e}")

async def send_trial_welcome(update: Update):
    """Sambutan + panduan untuk user baru (masa percobaan)"""
    chat = update.effective_chat
    if not chat:
        return
    text = (
        f"🎉 Selamat datang! Kamu mendapat <b>masa percobaan {TRIAL_DAYS} hari</b>.\n"
        f"Setelah itu kamu perlu izin dari pemilik bot untuk terus memakai.\n\n"
        f"{HELP_TEXT}"
    )
    await chat.send_message(text, parse_mode=ParseMode.HTML)

def authorized_only(func):
    """Batasi handler: owner/approved/trial aktif boleh pakai; user baru dapat trial"""
    from functools import wraps

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return

        # Owner / sudah di-approve (atau fitur off) → langsung boleh
        if is_owner_or_approved(update.effective_user.id):
            return await func(update, context)

        # User baru (belum pernah) → mulai trial + tampilkan panduan
        if not has_trial(update.effective_user.id):
            start_trial(update.effective_user.id, TRIAL_DAYS)
            await send_trial_welcome(update)
            return await func(update, context)

        # Trial masih aktif → boleh pakai
        if is_trial_active(update.effective_user.id):
            return await func(update, context)

        # Trial habis → tolak + beri tahu pemilik
        if update.callback_query:
            try:
                await update.callback_query.answer()
            except:
                pass
        chat = update.effective_chat
        if chat:
            await chat.send_message(
                f"⛔ Masa percobaanmu sudah habis.\n"
                f"👤 User ID kamu: <code>{update.effective_user.id}</code>\n"
                f"Permintaan akses sudah dikirim ke pemilik bot.",
                parse_mode=ParseMode.HTML
            )
        await notify_owner(update, context)
        return

    return wrapper

# ==================== START & HELP ====================

@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Halo {user.first_name}! Selamat datang di Bot Catat Keuangan!\n\n"
        "📝 Kirim chat bebas seperti:\n"
        "• 'makan siang 25rb'\n"
        "• 'gaji 4jt'\n\n"
        "Atau pilih menu di bawah!",
        parse_mode=ParseMode.HTML,
        reply_markup=get_start_menu(visible=True)
    )

@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())

# ==================== ADMIN: AKSES USER ====================

async def allow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Perintah ini khusus pemilik bot.")
        return
    if not context.args:
        await update.message.reply_text("📝 Format: /allow <user_id>\nContoh: /allow 123456789")
        return
    try:
        target = int(context.args[0].strip())
    except:
        await update.message.reply_text("❌ User ID tidak valid.")
        return
    add_authorized_user(target)
    await update.message.reply_text(
        f"✅ User <code>{target}</code> ditambahkan ke daftar izin.",
        parse_mode=ParseMode.HTML
    )

async def deny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Perintah ini khusus pemilik bot.")
        return
    if not context.args:
        await update.message.reply_text("📝 Format: /deny <user_id>\nContoh: /deny 123456789")
        return
    try:
        target = int(context.args[0].strip())
    except:
        await update.message.reply_text("❌ User ID tidak valid.")
        return
    remove_authorized_user(target)
    await update.message.reply_text(
        f"🗑️ User <code>{target}</code> dihapus dari daftar izin.",
        parse_mode=ParseMode.HTML
    )

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⛔ Perintah ini khusus pemilik bot.")
        return
    users = get_authorized_users()
    if not users:
        await update.message.reply_text("📋 Belum ada user yang diizinkan selain pemilik.")
        return
    text = "📋 <b>Daftar User yang Diizinkan:</b>\n\n"
    for u in users:
        text += f"• <code>{u}</code>\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

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
    elif period in ('month', 'month_to_date'):
        start_date = today.replace(day=1)
        end_date = today
    # period 'past_month' & 'custom' → start_date & end_date sudah ditentukan pemanggil
    
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
        'month_to_date': 'Bulanan',
        'past_month': 'Bulanan'
    }
    label = period_labels.get(period, 'Laporan')
    
    if period in ['month', 'month_to_date', 'past_month']:
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
    
    # Kirim daftar transaksi di chat (khusus laporan harian)
    if period == 'today':
        text_list = format_today_transactions(user_id)
        if text_list:
            await update.effective_chat.send_message(text_list, parse_mode=ParseMode.HTML)
    
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

# ==================== TRANSAKSI HARI INI (DI CHAT) ====================

def format_today_transactions(user_id: int) -> Optional[str]:
    """Format daftar transaksi hari ini (pengeluaran + pemasukan) untuk chat"""
    today = datetime.now().date().isoformat()
    transactions = get_transactions(user_id, today, today)

    if not transactions:
        return None

    date_label = datetime.now().strftime('%d %B %Y')
    lines = [f"📋 <b>Pengeluaran Hari Ini</b> — {date_label}\n"]

    total_expense = 0
    total_income = 0
    shown = 0
    max_items = 20

    for t in transactions:
        if t['type'] == 'investment':
            continue  # fitur investasi sudah dihapus
        if shown >= max_items:
            break
        cat = CATEGORY_DISPLAY.get(t['category'], t['category'].capitalize())
        if t['type'] == 'income':
            total_income += t['amount']
            lines.append(f"💰 {t['item']} <i>({cat})</i> — {format_rupiah(t['amount'])}")
        else:
            total_expense += t['amount']
            lines.append(f"💸 {t['item']} <i>({cat})</i> — {format_rupiah(t['amount'])}")
        shown += 1

    active_count = len([t for t in transactions if t['type'] != 'investment'])
    remaining = active_count - shown
    if remaining > 0:
        lines.append(f"\n…dan {remaining} transaksi lainnya")

    lines.append("")
    lines.append(f"Total Pengeluaran: {format_rupiah(total_expense)}")
    lines.append(f"Total Pemasukan: {format_rupiah(total_income)}")
    return "\n".join(lines)

async def show_today_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim daftar transaksi hari ini ke chat (dari tombol)"""
    user_id = update.effective_user.id
    text = format_today_transactions(user_id)
    if not text:
        await update.message.reply_text(
            "📭 Belum ada transaksi hari ini.",
            reply_markup=get_main_keyboard()
        )
        return
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ==================== BELAJAR (AUTO-LEARNING KATEGORI) ====================

def learn_from_item(item: str, category: str):
    """Pelajari item & kata-katanya → kategori, agar deteksi otomatis ke depannya benar"""
    from database import save_keyword_learn

    type_ = 'income' if category == 'income' else 'expense'
    item = (item or '').lower().strip()
    if not item:
        return

    save_keyword_learn(item, type_, category)
    for word in item.split():
        if len(word) > 2:
            save_keyword_learn(word, type_, category)

# ==================== HANDLE MESSAGE ====================

@authorized_only
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
    
    elif text == "📋 Pengeluaran Hari Ini":
        await show_today_transactions(update, context)
        return
    
    elif text == "📊 PDF Rekap Harian":
        await generate_report(update, context, "today")
        return
    
    elif text == "📈 PDF Rekap Mingguan":
        await generate_report(update, context, "week")
        return
    
    elif text == "📉 PDF Rekap Bulanan":
        await generate_report(update, context, "month")
        return
    
    elif text == "📅 Bulan Berjalan":
        await generate_report(update, context, "month_to_date")
        return
    
    elif text == "📁 Riwayat":
        await show_history_menu(update, context)
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
                "• 'gaji 4jt'",
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
        last_id = saved[-1]['id'] if saved else None
        sent_msg = await update.message.reply_text(
            msg,
            reply_markup=get_feedback_menu(last_id) if last_id else None
        )
        
        # Simpan data transaksi untuk tombol "Kembali"
        context.user_data['last_transaction_data'] = {
            'chat_id': sent_msg.chat_id,
            'message_id': sent_msg.message_id,
            'text': msg,
            'trans_id': last_id,
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

# ==================== RIWAYAT (HISTORY) ====================

MONTH_NAMES = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
    5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
}

async def show_history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan daftar bulan yang punya transaksi untuk unduh laporan PDF"""
    user_id = update.effective_user.id
    is_callback = update.callback_query is not None

    months = get_transaction_months(user_id)

    if not months:
        text = "📭 Belum ada riwayat transaksi."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
        ])
    else:
        text = "📁 <b>Pilih bulan untuk mengunduh laporan PDF:</b>\n\n"
        keyboard_rows = []
        for m in months:
            try:
                year, month = map(int, m.split('-'))
                label = f"{MONTH_NAMES.get(month, month)} {year}"
            except Exception:
                label = m
            keyboard_rows.append([
                InlineKeyboardButton(f"📅 {label}", callback_data=f"history_month_{m}")
            ])
        keyboard_rows.append([InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")])
        keyboard = InlineKeyboardMarkup(keyboard_rows)

    if is_callback:
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )

# ==================== SETTINGS ====================

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

@authorized_only
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
                menu = get_feedback_menu(last_data['trans_id']) if last_data.get('trans_id') else None
                await query.edit_message_text(
                    last_data['text'],
                    reply_markup=menu
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
    
    # ===== APPROVE / DENY (dari notifikasi pemilik) =====
    elif data.startswith("approve_"):
        target = int(data.replace("approve_", ""))
        add_authorized_user(target)
        await query.edit_message_text(
            f"✅ User <code>{target}</code> diizinkan memakai bot.",
            parse_mode=ParseMode.HTML
        )
        return
    
    elif data.startswith("deny_"):
        target = int(data.replace("deny_", ""))
        remove_authorized_user(target)
        await query.edit_message_text(
            f"❌ Akses user <code>{target}</code> ditolak.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # ===== TOGGLE FEEDBACK (pesan setelah catat) =====
    elif data.startswith("hide_feedback_"):
        trans_id = int(data.replace("hide_feedback_", ""))
        await query.edit_message_reply_markup(
            reply_markup=get_feedback_menu(trans_id, visible=False)
        )
        return
    
    elif data.startswith("show_feedback_"):
        trans_id = int(data.replace("show_feedback_", ""))
        await query.edit_message_reply_markup(
            reply_markup=get_feedback_menu(trans_id, visible=True)
        )
        return
    
    # ===== QUICK ADD =====
    elif data == "quick_add":
        await query.edit_message_text(
            "📝 Kirim chat bebas seperti:\n\n"
            "• 'makan siang 25rb'\n"
            "• 'gaji 4jt'",
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
    
    # ===== RIWAYAT / HISTORY =====
    elif data == "history":
        await show_history_menu(update, context)
        return
    
    elif data.startswith("history_month_"):
        month_str = data.replace("history_month_", "")
        try:
            year, month = map(int, month_str.split('-'))
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
        except Exception as e:
            logger.error(f"Error parse history month: {e}")
            await query.edit_message_text("❌ Bulan tidak valid.")
            return
        await generate_report(update, context, "past_month", start_date, end_date)
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
            [InlineKeyboardButton("💰 Pemasukan", callback_data=f"cat_{trans_id}_income")],
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
            # Belajar: simpan mapping keyword → kategori agar otomatis ke depannya
            learn_from_item(old_data['item'], category)
            # Kembali ke detail transaksi
            await query.edit_message_text(
                f"✅ Kategori diubah menjadi {CATEGORY_DISPLAY.get(category, category)}\n🧠 Bot sudah belajar, lain kali otomatis.",
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
            HELP_TEXT,
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

💰 Di sini kamu bisa mengatur budget bulanan 
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

💰 Di sini kamu bisa mengatur budget bulanan 
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

    inc_target = settings.get('income_target', 0)
    text += f"\n💰 <b>Target Pemasukan Bulanan:</b> {format_rupiah(inc_target) if inc_target > 0 else 'Belum diatur'}"

    text += """
    
💡 <b>Tips:</b>
• Budget = batas maksimal pengeluaran per kategori per bulan
• Target Pemasukan = target pemasukan per bulan
• Laporan otomatis dikirim setiap hari jam yang kamu atur
"""

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_settings_menu()
    )
