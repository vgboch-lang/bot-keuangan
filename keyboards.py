from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

# ==================== REPLY KEYBOARD (MAIN MENU) ====================

def get_main_keyboard():
    """Keyboard utama yang selalu muncul di bawah (2 kolom)"""
    keyboard = [
        [KeyboardButton("📝 Catat Cepat"), KeyboardButton("💰 Pemasukan")],
        [KeyboardButton("📈 Investasi"), KeyboardButton("📊 Rekap Harian")],
        [KeyboardButton("📈 Rekap Mingguan"), KeyboardButton("📉 Rekap Bulanan")],
        [KeyboardButton("📅 Bulan Berjalan"), KeyboardButton("✏️ Edit Transaksi")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("❓ Bantuan")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== INLINE KEYBOARD ====================

def get_start_menu(visible: bool = True):
    """Menu inline di /start (2 kolom) dengan toggle"""
    if visible:
        keyboard = [
            [InlineKeyboardButton("📝 Catat Cepat", callback_data="quick_add"), 
             InlineKeyboardButton("💰 Pemasukan", callback_data="income_add")],
            [InlineKeyboardButton("📈 Investasi", callback_data="investment_add"), 
             InlineKeyboardButton("📊 Rekap Harian", callback_data="report_today")],
            [InlineKeyboardButton("📈 Rekap Mingguan", callback_data="report_week"), 
             InlineKeyboardButton("📉 Rekap Bulanan", callback_data="report_month")],
            [InlineKeyboardButton("📅 Bulan Berjalan", callback_data="report_month_to_date"), 
             InlineKeyboardButton("✏️ Edit Transaksi", callback_data="edit_menu")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), 
             InlineKeyboardButton("❓ Bantuan", callback_data="help")],
            [InlineKeyboardButton("▲", callback_data="hide_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("▼", callback_data="show_menu")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_after_add_menu(visible: bool = True):
    """Menu setelah catat transaksi (dengan toggle hide/unhide)"""
    if visible:
        keyboard = [
            [InlineKeyboardButton("📝 Catat Lagi", callback_data="quick_add"), 
             InlineKeyboardButton("📊 Rekap", callback_data="report_today")],
            [InlineKeyboardButton("✏️ Edit", callback_data="edit_last"), 
             InlineKeyboardButton("↩️ Menu", callback_data="main_menu")],
            [InlineKeyboardButton("▲", callback_data="hide_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("▼", callback_data="show_menu")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_after_report_menu(visible: bool = True):
    """Menu setelah laporan PDF (dengan toggle hide/unhide)"""
    if visible:
        keyboard = [
            [InlineKeyboardButton("📈 Rekap Mingguan", callback_data="report_week"), 
             InlineKeyboardButton("📉 Rekap Bulanan", callback_data="report_month")],
            [InlineKeyboardButton("📅 Bulan Berjalan", callback_data="report_month_to_date"), 
             InlineKeyboardButton("📝 Catat Lagi", callback_data="quick_add")],
            [InlineKeyboardButton("↩️ Menu Utama", callback_data="main_menu"), 
             InlineKeyboardButton("▲", callback_data="hide_menu")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("▼", callback_data="show_menu")]
        ]
    return InlineKeyboardMarkup(keyboard)

# ==================== SETTINGS ====================

def get_settings_menu():
    """Menu settings dengan tombol yang lebih jelas"""
    keyboard = [
        [InlineKeyboardButton("⏰ Atur Waktu Laporan", callback_data="set_time")],
        [InlineKeyboardButton("💰 Atur Budget Bulanan", callback_data="set_budget")],
        [InlineKeyboardButton("📈 Atur Target Investasi", callback_data="set_investment_target")],
        [InlineKeyboardButton("💵 Atur Target Pemasukan", callback_data="set_income_target")],
        [InlineKeyboardButton("📋 Review Hari Ini", callback_data="manual_review")],
        [InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_budget_menu():
    """Menu pilih kategori budget"""
    keyboard = [
        [InlineKeyboardButton("🍔 Makanan", callback_data="budget_makanan"), 
         InlineKeyboardButton("🍿 Jajanan", callback_data="budget_jajanan")],
        [InlineKeyboardButton("🥤 Minuman", callback_data="budget_minuman"), 
         InlineKeyboardButton("🚬 Rokok", callback_data="budget_rokok")],
        [InlineKeyboardButton("🚗 Transport", callback_data="budget_transport"), 
         InlineKeyboardButton("🛒 Belanja", callback_data="budget_belanja")],
        [InlineKeyboardButton("📄 Tagihan", callback_data="budget_tagihan"), 
         InlineKeyboardButton("🎮 Hiburan", callback_data="budget_hiburan")],
        [InlineKeyboardButton("💊 Kesehatan", callback_data="budget_kesehatan"), 
         InlineKeyboardButton("📚 Pendidikan", callback_data="budget_pendidikan")],
        [InlineKeyboardButton("↩️ Kembali", callback_data="settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== EDIT TRANSAKSI ====================

def get_edit_menu(transactions, page: int = 0, visible: bool = True):
    """Menu edit transaksi dengan toggle + pagination"""
    keyboard = []
    
    start_idx = page * 10
    end_idx = min(start_idx + 10, len(transactions))
    current_page = transactions[start_idx:end_idx]
    
    for t in current_page:
        item = t['item'][:20]
        amount = f"Rp{t['amount']:,.0f}".replace(',', '.')
        label = f"{t.get('category_emoji', '📦')} {item} - {amount}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"edit_{t['id']}")])
    
    # Navigasi halaman
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"edit_page_{page-1}"))
    if end_idx < len(transactions):
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"edit_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Tombol toggle + kembali
    action_buttons = []
    if visible:
        action_buttons.append(InlineKeyboardButton("▲", callback_data="hide_edit_menu"))
    else:
        action_buttons.append(InlineKeyboardButton("▼", callback_data="show_edit_menu"))
    action_buttons.append(InlineKeyboardButton("↩️ Kembali", callback_data="back_to_previous"))
    keyboard.append(action_buttons)
    
    return InlineKeyboardMarkup(keyboard)

def get_edit_action_menu(trans_id):
    """Menu aksi edit transaksi (2 kolom)"""
    keyboard = [
        [InlineKeyboardButton("📝 Item", callback_data=f"edit_item_{trans_id}"), 
         InlineKeyboardButton("📂 Kategori", callback_data=f"edit_category_{trans_id}")],
        [InlineKeyboardButton("💰 Nominal", callback_data=f"edit_amount_{trans_id}"), 
         InlineKeyboardButton("🗑️ Hapus", callback_data=f"delete_{trans_id}")],
        [InlineKeyboardButton("🔄 Kirim Ulang", callback_data=f"resend_{trans_id}"), 
         InlineKeyboardButton("↩️ Kembali", callback_data=f"back_to_edit_{trans_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_delete_menu(trans_id):
    """Menu konfirmasi hapus"""
    keyboard = [
        [InlineKeyboardButton("✅ Ya, Hapus", callback_data=f"confirm_delete_{trans_id}"), 
         InlineKeyboardButton("❌ Tidak", callback_data=f"back_to_edit_{trans_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== TOGGLE HELPERS ====================

def get_hidden_menu():
    """Menu saat ditutup (hanya tombol ▼)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▼", callback_data="show_menu")]
    ])

def get_hidden_edit_menu():
    """Menu edit saat ditutup (hanya tombol ▼)"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▼", callback_data="show_edit_menu")]
    ])