import os
import shutil
import sqlite3
import tempfile
import zipfile
import calendar
from datetime import datetime, date

from database import get_all_users
from report import generate_pdf_report
from config import BOT_TOKEN, OWNER_ID
from telegram import Bot

DATABASE_FILE = os.path.join("/app/data", "finance.db") if os.getenv("RAILWAY_ENVIRONMENT") else os.getenv("DATABASE_FILE", "finance.db")
DATA_DIR = os.path.dirname(DATABASE_FILE) or "."
REPORTS_DIR = os.path.join(os.getcwd(), "reports")
MAX_TELEGRAM_BYTES = 50 * 1024 * 1024


def previous_month(today=None):
    today = today or datetime.now().date()
    if today.month == 1:
        return date(today.year - 1, 12, 1), date(today.year - 1, 12, 31)
    year, month = today.year, today.month - 1
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _snapshot_database(target_path):
    """Buat snapshot SQLite yang konsisten tanpa sekadar menyalin file yang sedang ditulis."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    source = sqlite3.connect(DATABASE_FILE)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def create_full_backup(user_id=None, report_start=None, report_end=None):
    """
    Buat satu ZIP kumulatif:
    - snapshot database finance.db (seluruh riwayat)
    - seluruh isi /app/data kecuali folder sementara backup
    - PDF rekap bulanan yang diminta
    - manifest informasi backup
    """
    if not os.path.exists(DATABASE_FILE):
        raise FileNotFoundError(f"Database tidak ditemukan: {DATABASE_FILE}")

    today = datetime.now().date()
    if report_start is None or report_end is None:
        report_start, report_end = previous_month(today)

    stamp = today.strftime("%Y-%m-%d")
    month_label = report_start.strftime("%B_%Y")
    zip_name = f"Backup_Keuangan_{stamp}.zip"

    with tempfile.TemporaryDirectory(prefix="finance_backup_") as tmp:
        snapshot = os.path.join(tmp, "finance_snapshot.db")
        _snapshot_database(snapshot)

        # Buat PDF bulan yang baru selesai dari database yang sama.
        pdf_path = None
        if user_id:
            pdf_path = generate_pdf_report(
                user_id,
                report_start,
                report_end,
                "past_month",
                "Bulanan",
                report_start.strftime("%d-%m-%y"),
            )

        zip_path = os.path.join(tmp, zip_name)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(snapshot, arcname="database/finance_snapshot.db")

            # Masukkan semua data mentah yang ada di volume, kecuali file backup
            # sementara agar tidak terjadi backup di dalam backup.
            for root, dirs, files in os.walk(DATA_DIR):
                dirs[:] = [d for d in dirs if d not in {"backups", "__pycache__"}]
                for filename in files:
                    full = os.path.join(root, filename)
                    if os.path.abspath(full) == os.path.abspath(snapshot):
                        continue
                    arc = os.path.relpath(full, DATA_DIR)
                    z.write(full, arcname=os.path.join("data", arc))

            if pdf_path and os.path.exists(pdf_path):
                z.write(pdf_path, arcname=os.path.join("laporan", f"Rekap_{month_label}.pdf"))

            manifest = (
                "BACKUP BOT KEUANGAN\n"
                f"Dibuat: {datetime.now().isoformat()}\n"
                f"Cakupan database: seluruh riwayat sampai backup dibuat\n"
                f"PDF rekap: {report_start.isoformat()} s.d. {report_end.isoformat()}\n"
                "Isi volume /app/data: seluruh file yang tersedia, kecuali folder sementara backups.\n"
                "Tidak ada AI yang digunakan dalam proses backup.\n"
            )
            z.writestr("MANIFEST.txt", manifest)

        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

        # Salin ZIP keluar dari TemporaryDirectory sebelum dikirim.
        final_path = os.path.join(tempfile.gettempdir(), zip_name)
        shutil.copy2(zip_path, final_path)

    return final_path


async def send_full_backup(chat_id, user_id=None, report_start=None, report_end=None):
    """Buat dan kirim backup lengkap ke Telegram."""
    path = create_full_backup(
        user_id=user_id,
        report_start=report_start,
        report_end=report_end,
    )
    try:
        size = os.path.getsize(path)
        if size > MAX_TELEGRAM_BYTES:
            raise ValueError(
                f"Backup berukuran {size / 1024 / 1024:.1f} MB, "
                "melewati batas upload Telegram 50 MB."
            )

        bot = Bot(token=BOT_TOKEN)
        with open(path, "rb") as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=os.path.basename(path),
                caption=(
                    "🗃️ <b>Backup Keuangan Lengkap</b>\n"
                    "Berisi database seluruh riwayat + seluruh data volume + PDF rekap bulanan."
                ),
                parse_mode="HTML",
            )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


async def manual_backup(update, context):
    """Perintah /backup — hanya owner."""
    if not OWNER_ID or update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Perintah backup hanya untuk pemilik bot.")
        return

    msg = await update.message.reply_text("⏳ Menyiapkan backup lengkap...")
    try:
        await send_full_backup(
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id,
        )
        await msg.edit_text("✅ Backup lengkap sudah dikirim.")
    except Exception as e:
        await msg.edit_text(f"❌ Backup gagal: {str(e)[:500]}")


async def monthly_backup():
    """Backup otomatis tanggal 1: seluruh data sampai saat itu + PDF bulan sebelumnya."""
    if not OWNER_ID:
        return

    start, end = previous_month()
    try:
        await send_full_backup(
            chat_id=OWNER_ID,
            user_id=OWNER_ID,
            report_start=start,
            report_end=end,
        )
    except Exception as e:
        # Tidak membocorkan token/secret ke log.
        print(f"Monthly backup error: {e}")
