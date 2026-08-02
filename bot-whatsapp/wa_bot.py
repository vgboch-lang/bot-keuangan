"""
Bot Catat Keuangan untuk WhatsApp (unofficial, via WhatsApp Web + Playwright).

- Memakai ulang kode inti dari bot Telegram: core/{config,database,parser,utils,report}.py
- Data tersimpan di finance.db yang SAMA dengan bot Telegram (jika volume sama).
- Login: jalankan sekali, scan QR. Session disimpan di folder wa_session/ (persisten).

CATATAN:
- Pendekatan unofficial (WhatsApp Web). Risiko akun bisa diblokir.
- Jika nomor di-blokir: data tetap aman di finance.db; cukup link nomor baru (hapus wa_session).
- Selector WhatsApp Web bisa berubah; jika ada fitur yang tidak jalan, cek log & sesuaikan.

Cara pakai:
  pip install -r requirements.txt
  playwright install chromium
  python wa_bot.py
"""
import os
import time
import json
import threading
import functools
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Di Railway: simpan session login & QR di volume /app/data agar PERSISTEN
# (tidak hilang saat restart) dan satu volume yang sama dengan bot Telegram
# → data otomatis tergabung.
DATA_DIR = '/app/data' if os.getenv('RAILWAY_ENVIRONMENT') else BASE_DIR
SESSION_DIR = os.path.join(DATA_DIR, 'wa_session')
QR_PATH = os.path.join(DATA_DIR, 'qr_login.png')

# Mode tes: WA_TEST_MODE=1 → pakai database terpisah finance_test.db (lokal),
# supaya tes tidak menyentuh data asli finance.db. WAJIB di-set SEBELUM import
# core.config agar DATABASE_FILE terbaca sebagai DB test.
TEST_MODE = os.getenv('WA_TEST_MODE', '').strip().lower() in ('1', 'true', 'yes')
if TEST_MODE:
    os.environ['DATABASE_FILE'] = os.path.join(BASE_DIR, 'finance_test.db')

from playwright.sync_api import sync_playwright

from core.config import DATABASE_FILE, CATEGORY_DISPLAY
from core.database import (
    init_db, save_transaction, get_transactions, get_summary, get_transaction_months,
    get_transaction_by_id, update_transaction, delete_transaction
)
from core.parser import parse_transaction
from core.utils import format_rupiah, format_date
from core.report import generate_pdf_report

# ===== KONFIGURASI (via env) =====
WA_OWNER = os.getenv('WA_OWNER', '').strip()  # nomor WA pemilik, format 62xxxxxxxxxx
ALLOWED = [x.strip() for x in os.getenv('WA_ALLOWED', '').split(',') if x.strip()]
# user_id yang dipakai untuk menyimpan data WhatsApp.
# SET INI = ID Telegram kamu (cek lewat /myid di bot Telegram) supaya
# data WhatsApp & Telegram tergabung di user yang sama.
WA_USER_ID = os.getenv('WA_USER_ID', '').strip()

# WhatsApp Web versi ini TIDAK mengekspos nomor HP pengirim di DOM/URL/Store.
# Jadi identifikasi pengirim memakai NAMA pengirim (dari data-pre-plain-text pesan).
# WA_OWNER_NAME = nama kontak pemilik seperti tersimpan di HP nomor bot.
# WA_ALLOWED_NAMES = nama kontak lain yang boleh pakai bot (pisah koma).
# Identifikasi admin = chat PALING ATAS di daftar chat (idealnya disematkan/pin).
# Admin TIDAK ditentukan dari nama → tidak ada data nama di script ini.
# TEST_MODE sudah didefinisikan di atas (sebelum import core.config) → pakai finance_test.db


def get_wa_user_id() -> int:
    """user_id stabil untuk data WhatsApp: WA_USER_ID > WA_OWNER > fallback."""
    for v in (WA_USER_ID, WA_OWNER):
        if v.isdigit():
            return int(v)
    return 1000000001


# ===== EDIT INTERAKTIF =====
# State per user untuk flow: edit → pilih nomor → kirim nilai baru
EDIT_STATE = {}
CATEGORY_KEYS = list(CATEGORY_DISPLAY.keys())

HELP_TEXT = (
    "❓ *Panduan Lengkap Bot Catat Keuangan (WhatsApp)*\n\n"
    "📝 *1. Mencatat Transaksi*\n"
    "Kirim chat bebas, contoh:\n"
    "• 'makan siang 25rb' → pengeluaran\n"
    "• 'gaji 4jt' → pemasukan\n"
    "• 'gojek 15rb dan kopi 5rb' → 2 transaksi sekaligus\n\n"
    "📊 *2. Rekap Hari Ini (teks di chat)*\n"
    "• 'rekap' / 'rekap hari ini' / 'rekap hariini' → rekap harian\n\n"
    "✏️ *3. Edit & Hapus Transaksi*\n"
    "• 'edit' → pilih transaksi dari daftar\n"
    "• 'edit 12 makan 30k' → ubah langsung\n"
    "• 'kategori transport' → ganti kategori saja\n"
    "• 'hapus 12' → hapus transaksi\n\n"
    "❓ *4. Bantuan*\n"
    "• 'bantuan' / 'help' → panduan ini\n\n"
    "💡 *Tips:* Semua data tersimpan otomatis di database, "
    "tergabung dengan data Telegram.\n"
    "🗓️ Rekap mingguan/bulanan & PDF hanya tersedia di Telegram."
)


def allowed(sender: str) -> bool:
    """Cek apakah pengirim diizinkan"""
    if not ALLOWED:
        return sender == WA_OWNER
    return sender in ALLOWED


def format_today(user_id):
    """Daftar transaksi hari ini (untuk /pengeluaran)"""
    today = datetime.now().date().isoformat()
    rows = get_transactions(user_id, today, today)
    if not rows:
        return "📭 Belum ada transaksi hari ini."
    lines = [f"📋 Pengeluaran Hari Ini — {datetime.now().strftime('%d %B %Y')}\n"]
    t_exp = t_inc = 0
    for t in rows:
        if t['type'] == 'income':
            t_inc += t['amount']
            lines.append(f"💰 [#{t['id']}] {t['item']} — {format_rupiah(t['amount'])}")
        else:
            t_exp += t['amount']
            lines.append(f"💸 [#{t['id']}] {t['item']} — {format_rupiah(t['amount'])}")
    lines.append("")
    lines.append(f"Total Pengeluaran: {format_rupiah(t_exp)}")
    lines.append(f"Total Pemasukan: {format_rupiah(t_inc)}")
    return "\n".join(lines)


def format_recap(user_id, start, end, label):
    """Rekap CHAT: SEMUA transaksi keluar, dikelompokkan per kategori."""
    from collections import defaultdict
    rows = get_transactions(user_id, start.isoformat(), end.isoformat())
    if not rows:
        return f"📭 Belum ada transaksi di periode {label.lower()}."
    exp = defaultdict(list)
    inc = defaultdict(list)
    total_exp = total_inc = 0
    for t in rows:
        if t['type'] == 'income':
            inc[t['category']].append(t)
            total_inc += t['amount']
        else:
            exp[t['category']].append(t)
            total_exp += t['amount']
    lines = [f"📊 Rekap {label}",
             f"🗓️ {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')}"]
    if exp:
        lines.append("")
        lines.append("💸 Pengeluaran:")
        for cat in sorted(exp, key=lambda c: -sum(x['amount'] for x in exp[c])):
            lines.append(f"\n  {cat.capitalize()}:")
            for t in exp[cat]:
                lines.append(f"    • [#{t['id']}] {t['item']} — {format_rupiah(t['amount'])}")
            lines.append(f"    Subtotal: {format_rupiah(sum(x['amount'] for x in exp[cat]))}")
        lines.append(f"\n  Total Pengeluaran: {format_rupiah(total_exp)}")
    if inc:
        lines.append("")
        lines.append("💰 Pemasukan:")
        for cat in sorted(inc, key=lambda c: -sum(x['amount'] for x in inc[c])):
            lines.append(f"\n  {cat.capitalize()}:")
            for t in inc[cat]:
                lines.append(f"    • [#{t['id']}] {t['item']} — {format_rupiah(t['amount'])}")
            lines.append(f"    Subtotal: {format_rupiah(sum(x['amount'] for x in inc[cat]))}")
        lines.append(f"\n  Total Pemasukan: {format_rupiah(total_inc)}")
    return "\n".join(lines)


class _QRFileHandler(SimpleHTTPRequestHandler):
    """Hanya melayani file QR — tidak mengekspos isi direktori (aman)."""
    def do_GET(self):
        if self.path.split('?')[0] not in ('/', '/qr_login.png', '/favicon.ico'):
            self.send_error(404)
            return
        self.path = '/qr_login.png'
        super().do_GET()

    def log_message(self, *args):
        pass


def start_qr_server(qr_path):
    """Sajikan file QR lewat HTTP (lokal / publik di Railway). Bind 0.0.0.0 agar
    bisa dijangkau proxy Railway dari luar container."""
    d = os.path.dirname(qr_path)
    handler = functools.partial(_QRFileHandler, directory=d)
    server = HTTPServer(('0.0.0.0', 8787), handler)
    print(f"🌐 Buka / unduh QR: http://0.0.0.0:8787/qr_login.png")
    server.serve_forever()


def handle_text(text: str, user_id: int):
    """Proses pesan teks → balasan (str) atau ('pdf', path)."""
    text = text.strip()
    low = text.lower().lstrip('/')  # terima perintah tanpa tanda '/'
    first = low.split()[0] if low.split() else ''

    # ===== LANJUTAN FLOW EDIT INTERAKTIF =====
    st = EDIT_STATE.get(user_id)
    if st and st.get('step') == 'choose' and text.strip().isdigit():
        num = int(text.strip())
        choices = st['choices']
        if num not in choices:
            return "❌ Nomor tidak ada di daftar. Ketik nomor yang benar."
        trans_id = choices[num]
        txn = get_transaction_by_id(user_id, trans_id)
        if not txn:
            EDIT_STATE.pop(user_id, None)
            return "❌ Transaksi tidak ditemukan."
        EDIT_STATE[user_id] = {'step': 'new_value', 'trans_id': trans_id}
        cat_disp = CATEGORY_DISPLAY.get(txn['category'], txn['category'])
        return (f"✏️ Transaksi #{trans_id}: {txn['item']} — {format_rupiah(txn['amount'])} ({cat_disp})\n"
                f"Kirim deskripsi baru (mis. 'makan 30k')\n"
                f"atau 'kategori <nama>' untuk ganti kategori.")
    if st and st.get('step') == 'new_value':
        EDIT_STATE.pop(user_id, None)
        trans_id = st['trans_id']
        txn = get_transaction_by_id(user_id, trans_id)
        if not txn:
            return "❌ Transaksi tidak ditemukan."
        if low.startswith('kategori '):
            cat = low.split('kategori ', 1)[1].strip()
            if cat not in CATEGORY_KEYS:
                return "❌ Kategori tidak dikenal. Pilihan: " + ', '.join(CATEGORY_KEYS)
            update_transaction(user_id, trans_id, 'category', cat, txn['category'])
            return f"✅ Kategori transaksi #{trans_id} → {CATEGORY_DISPLAY.get(cat, cat)}."
        results = parse_transaction(text)
        if not results:
            return ("❌ Tidak ada nominal.\nKirim deskripsi baru mis. 'makan 30k',\n"
                    "atau 'kategori <nama>' untuk ganti kategori.")
        r = results[0]
        done = []
        if r.get('amount'):
            update_transaction(user_id, trans_id, 'amount', r['amount'], txn['amount'])
            done.append('nominal')
        if r.get('item'):
            update_transaction(user_id, trans_id, 'item', r['item'], txn['item'])
            done.append('item')
        if r.get('category') and r['category'] != txn['category']:
            update_transaction(user_id, trans_id, 'category', r['category'], txn['category'])
            done.append('kategori')
        if not done:
            return "❌ Tidak ada yang diubah."
        new_item = r.get('item', txn['item'])
        new_amt = r.get('amount', txn['amount'])
        return (f"✅ Transaksi #{trans_id} diubah ({', '.join(done)}).\n"
                f"Sekarang: {new_item} — {format_rupiah(new_amt)}")

    if low in ('bantuan', 'help'):
        return HELP_TEXT

    if low in ('pengeluaran', 'pengeluaran hari ini'):
        return format_today(user_id)

    if first in ('rekap', 'riwayat'):
        # WhatsApp: rekap HARIAN bentuk teks chat (tanpa PDF).
        # Trigger: 'rekap' | 'rekap hari ini' | 'rekap hariini'
        # Mingguan/bulanan → hanya PDF, dan PDF cukup di Telegram saja.
        today = datetime.now().date()
        if 'mingguan' in low or 'bulanan' in low:
            return "🗓️ Rekap mingguan/bulanan hanya tersedia di Telegram (PDF).\nDi WhatsApp cukup: 'rekap' / 'rekap hari ini' → rekap teks."
        return format_recap(user_id, today, today, 'Harian')

    # ===== EDIT / HAPUS TRANSAKSI =====
    if first in ('edit', 'ubah'):
        parts = text.split(None, 2)
        if len(parts) >= 2 and parts[1].isdigit():
            trans_id = int(parts[1])
            txn = get_transaction_by_id(user_id, trans_id)
            if not txn:
                return "❌ Transaksi #" + parts[1] + " tidak ditemukan."
            if len(parts) >= 3:
                # edit langsung: 'edit 12 makan 25rb'
                results = parse_transaction(parts[2])
                if not results:
                    return "❌ Format edit tidak valid.\nContoh: edit 12 makan 25rb"
                r = results[0]
                done = []
                if r.get('amount'):
                    update_transaction(user_id, trans_id, 'amount', r['amount'], txn['amount'])
                    done.append('nominal')
                if r.get('item'):
                    update_transaction(user_id, trans_id, 'item', r['item'], txn['item'])
                    done.append('item')
                if r.get('category') and r['category'] != txn['category']:
                    update_transaction(user_id, trans_id, 'category', r['category'], txn['category'])
                    done.append('kategori')
                if not done:
                    return "❌ Tidak ada yang diubah."
                new_amt = r.get('amount', txn['amount'])
                new_item = r.get('item', txn['item'])
                return (f"✅ Transaksi #{trans_id} diubah ({', '.join(done)}).\n"
                        f"Sekarang: {new_item} — {format_rupiah(new_amt)}")
            # 'edit <id>' saja → minta nilai baru
            cat_disp = CATEGORY_DISPLAY.get(txn['category'], txn['category'])
            EDIT_STATE[user_id] = {'step': 'new_value', 'trans_id': trans_id}
            return (f"✏️ Transaksi #{trans_id}: {txn['item']} — {format_rupiah(txn['amount'])} ({cat_disp})\n"
                    f"Kirim deskripsi baru (mis. 'makan 30k')\n"
                    f"atau 'kategori <nama>' untuk ganti kategori.")
        # 'edit' saja → daftar interaktif
        today = datetime.now().date().isoformat()
        rows = get_transactions(user_id, '2000-01-01', today)
        rows = rows[:10]  # 10 terbaru
        if not rows:
            return "📭 Belum ada transaksi untuk diedit."
        choices = {}
        lines = ["✏️ Pilih transaksi yang mau diedit:\n"]
        for i, t in enumerate(rows, 1):
            choices[i] = t['id']
            cat_disp = CATEGORY_DISPLAY.get(t['category'], t['category'])
            lines.append(f"{i}) [#{t['id']}] {t['item']} — {format_rupiah(t['amount'])} ({cat_disp})")
        lines.append("\nketik nomor yang mau di-edit")
        EDIT_STATE[user_id] = {'step': 'choose', 'choices': choices}
        return "\n".join(lines)

    if first in ('hapus', 'delete'):
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            trans_id = int(parts[1])
            if delete_transaction(user_id, trans_id):
                return f"🗑️ Transaksi #{trans_id} dihapus."
            return "❌ Transaksi #" + parts[1] + " tidak ditemukan."
        return "❌ Format: hapus <nomor>\nContoh: hapus 12"

    # default: catat transaksi
    results = parse_transaction(text)
    if not results:
        return "❌ Tidak ditemukan nominal.\nContoh: 'makan siang 25rb' / 'gaji 4jt'"

    saved = []
    for r in results:
        tid = save_transaction(
            user_id=user_id,
            type_=r.get('type', 'expense'),
            amount=r['amount'],
            category=r.get('category', 'lainnya'),
            item=r.get('item', 'transaksi'),
            note=r.get('note', text)
        )
        saved.append({**r, 'id': tid})

    if len(saved) == 1:
        r = saved[0]
        msg = f"✅ Dicatat: {r['category'].capitalize()} {format_rupiah(r['amount'])} - {r['item']}"
    else:
        msg = f"✅ Dicatat {len(saved)} transaksi!\n"
        for i, r in enumerate(saved, 1):
            msg += f"{i}. {r['category'].capitalize()} {format_rupiah(r['amount'])} - {r['item']}\n"
    if TEST_MODE:
        msg += "\n🧪 [TEST] — disimpan di database test (finance_test.db)."
    return msg.strip()


def main():
    init_db()
    print("✅ Database siap:", DATABASE_FILE)

    # Headless dipakai di server (Railway dsb). Lokal pakai jendela Chrome asli
    # biar QR tampil dan bisa di-scan langsung (WA blokir QR di headless).
    headless = os.getenv('WA_HEADLESS', '0').strip().lower() in ('1', 'true', 'yes')

    # Lokal non-headless → pakai Google Chrome yang terpasang.
    # Railway → tidak ada Chrome; pakai Chromium bawaan Playwright.
    # WhatsApp Web TIDAK menampilkan QR di mode headless, jadi di Railway
    # kita jalankan "berjendela" di atas layar virtual (xvfb) → pakai WA_HEADLESS=0.
    launch_kwargs = {
        'headless': headless,
        'args': ['--no-sandbox', '--disable-dev-shm-usage'],
        'viewport': {'width': 1280, 'height': 720},
        # User-Agent Chrome terbaru agar WhatsApp Web tidak menganggap browser lama
        'user_agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
    }
    if not headless and not os.getenv('RAILWAY_ENVIRONMENT'):
        launch_kwargs['channel'] = 'chrome'

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(SESSION_DIR, **launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://web.whatsapp.com')

        # ===== LOGIN (QR) =====
        print("⏳ Menunggu login WhatsApp Web...")
        qr_path = QR_PATH

        def _logged_in():
            """Deteksi sudah login via beberapa selector umum UI WhatsApp Web."""
            for sel in (
                'div[contenteditable="true"][data-tab="3"]',  # kotak pencarian chat
                'div#pane-side',                              # sidebar daftar chat
                'div[data-testid="chatlist"]',
                'button[data-testid="menu-bar"]',             # tombol menu
            ):
                if page.query_selector(sel):
                    return True
            return False

        def _capture_qr():
            """Simpan QR. Coba crop elemen QR; kalau tidak ketemu, tangkap seluruh halaman."""
            el = (
                page.query_selector('div[data-ref]')
                or page.query_selector('div[data-ref] canvas')
                or page.query_selector('canvas')
                or page.query_selector('img[src^="data:image"]')
            )
            if el:
                el.screenshot(path=qr_path)
                return True
            # Fallback: seluruh halaman (QR pasti tampil di jendela Chrome asli)
            page.screenshot(path=qr_path)
            return True

        # Beri waktu halaman memuat session (kalau sudah pernah login)
        try:
            page.wait_for_selector(
                'div#pane-side, div[data-testid="chatlist"],'
                ' div[contenteditable="true"][data-tab="3"]',
                timeout=20000)
        except Exception:
            pass

        if _logged_in():
            print("✅ Sudah login (session tersimpan).")
        else:
            print(f"📱 Belum login. Scan QR di file: {qr_path}")
            print("   WhatsApp > Setelan > Perangkat Tertaut > Tautkan Perangkat > scan QR")
            threading.Thread(target=start_qr_server, args=(qr_path,), daemon=True).start()

            try:
                # Tunggu sampai canvas QR benar-benar muncul, baru simpan
                ok = False
                for _ in range(10):
                    page.wait_for_timeout(1500)
                    if _capture_qr():
                        ok = True
                        break
                if ok:
                    print("✅ QR tersimpan. File QR di-refresh otomatis tiap beberapa detik.")
                else:
                    print("⚠️ Elemen QR belum muncul. Coba jalankan ulang.")
            except Exception as e:
                print("⚠️ Gagal simpan QR:", e)

            # Refresh QR berkala sampai login berhasil (QR WA berganti ~20 detik,
            # jadi file harus selalu update agar bisa di-scan).
            deadline = time.time() + 180
            while time.time() < deadline:
                if _logged_in():
                    print("✅ Login berhasil.")
                    break
                try:
                    _capture_qr()
                except Exception:
                    pass
                page.wait_for_timeout(3000)
            else:
                print("❌ Timeout menunggu login. Coba lagi.")
                return

        # ===== LOOP PESAN =====
        print("✅ Bot aktif. Menunggu pesan...")
        processed = set()      # data-id pesan yang sudah diproses
        last_scan = 0

        def _latest_incoming():
            """Ambil (data_id, teks) pesan MASUK terakhir di chat terbuka (#main)."""
            msgs = page.query_selector_all('#main div[data-id][data-testid^="conv-msg-"]')
            for m in reversed(msgs):
                # Pesan masuk ditandai tail-in; pesan keluar pakai tail-out
                if m.query_selector('span[data-testid="tail-in"]'):
                    sel = m.query_selector('span[data-testid="selectable-text"]')
                    if sel:
                        return (m.get_attribute('data-id'), sel.inner_text().strip())
            return (None, None)

        while True:
            try:
                now = time.time()
                if now - last_scan > 3:
                    last_scan = now

                    # 1) Kumpulkan baris chat (skip Diarsipkan)
                    rows = []
                    for row in page.query_selector_all(
                            '#pane-side div[data-testid="cell-frame-container"]'):
                        t = (row.inner_text() or '')
                        if 'Diarsipkan' in t:
                            continue
                        rows.append(row)

                    # 1b) Buka chat yang punya pesan belum dibaca (kalau belum terbuka)
                    for row in rows:
                        if row.query_selector('span[data-testid="icon-unread-count"]'):
                            row.click()
                            page.wait_for_timeout(2000)
                            break

                    # 1c) Admin = chat PALING ATAS yang sedang terbuka.
                    #     Struktur WA: elemen aria-selected berada DI ATAS cell-frame-container,
                    #     jadi cari cell-frame-container DI DALAM elemen ter-selected.
                    open_idx = page.evaluate("""() => {
                        const sel = document.querySelector('#pane-side [aria-selected="true"]');
                        let openFrame = null;
                        if (sel) {
                            let node = sel;
                            for (let i = 0; i < 4 && node; i++) {
                                const f = node.querySelector
                                    ? node.querySelector('div[data-testid="cell-frame-container"]')
                                    : null;
                                if (f) { openFrame = f; break; }
                                node = node.parentElement;
                            }
                        }
                        if (!openFrame) return -1;
                        const frames = [...document.querySelectorAll(
                            '#pane-side div[data-testid="cell-frame-container"]')];
                        let idx = 0;
                        for (const f of frames) {
                            if ((f.innerText || '').includes('Diarsipkan')) continue;
                            if (f === openFrame) return idx;
                            idx++;
                        }
                        return -1;
                    }""")
                    is_owner = (open_idx == 0)

                    # 2) Baca pesan masuk terbaru dari chat yang terbuka
                    mid, latest = _latest_incoming()
                    if mid and latest and mid not in processed:
                        processed.add(mid)
                        if not is_owner:
                            print(f"🚫 Diabaikan (bukan chat paling atas/admin): '{latest}'")
                            continue
                        user_id = get_wa_user_id()
                        print(f"📩 Pesan → user {user_id}:", latest)
                        res = handle_text(latest, user_id)
                        if isinstance(res, tuple) and res[0] == 'pdf':
                            # kirim file PDF
                            try:
                                # 1) klik tombol Lampirkan
                                attach = page.query_selector(
                                    'button[aria-label="Lampirkan"], div[aria-label="Lampirkan"]')
                                if not attach:
                                    attach = page.query_selector(
                                        'div[title="Lampirkan"], [data-testid="attach-menu-plus"]')
                                if not attach:
                                    raise RuntimeError('tombol Lampirkan tidak ditemukan')
                                attach.click()
                                page.wait_for_timeout(1000)
                                # 2) klik menu Dokumen
                                doc = page.query_selector(
                                    'button[aria-label="Dokumen"], button[aria-label="Document"]')
                                if not doc:
                                    raise RuntimeError('menu Dokumen tidak ditemukan')
                                doc.click()
                                page.wait_for_timeout(1000)
                                # 3) pilih file di input dokumen (accept="*")
                                file_input = page.query_selector(
                                    'input[type="file"][accept="*"]') \
                                    or page.query_selector('input[type="file"]')
                                if not file_input:
                                    raise RuntimeError('input file tidak ditemukan')
                                file_input.set_input_files(res[1])
                                page.wait_for_timeout(2000)
                                page.keyboard.press('Enter')
                                print("📎 PDF terkirim")
                            except Exception as e:
                                print("⚠️ Gagal kirim PDF:", e)
                        elif res:
                            box = page.query_selector(
                                'div[contenteditable="true"][data-tab="10"]')
                            if box:
                                box.click()
                                box.fill(res)
                                page.keyboard.press('Enter')
                                print("✅ Balasan terkirim")
                page.wait_for_timeout(2000)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("⚠️ Loop error:", e)
                page.wait_for_timeout(5000)


if __name__ == '__main__':
    main()
