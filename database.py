import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from config import DATABASE_FILE

# ==================== DATABASE INIT ====================

def get_db():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inisialisasi semua tabel + index + seeding keyword"""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Tabel transaksi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            item TEXT NOT NULL,
            note TEXT,
            date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            edited_at TEXT,
            edit_history_ids TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    ''')

    # ===== INDEX UNTUK PERFORMA QUERY (WAJIB) =====
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date
        ON transactions (user_id, date, is_deleted)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_transactions_user_id_deleted
        ON transactions (user_id, id, is_deleted)
    ''')

    # 2. Tabel history edit
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            field_changed TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            edited_at TEXT NOT NULL,
            edited_by INTEGER NOT NULL,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_transaction_history_trans_id
        ON transaction_history (transaction_id)
    ''')

    # 3. Tabel user settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            report_time TEXT DEFAULT '20:00',
            is_premium INTEGER DEFAULT 0,
            premium_expiry TEXT,
            budget_makanan INTEGER DEFAULT 1500000,
            budget_jajanan INTEGER DEFAULT 500000,
            budget_minuman INTEGER DEFAULT 300000,
            budget_rokok INTEGER DEFAULT 300000,
            budget_transport INTEGER DEFAULT 500000,
            budget_belanja INTEGER DEFAULT 1000000,
            budget_tagihan INTEGER DEFAULT 1500000,
            budget_hiburan INTEGER DEFAULT 500000,
            budget_kesehatan INTEGER DEFAULT 300000,
            budget_pendidikan INTEGER DEFAULT 500000,
            budget_lainnya INTEGER DEFAULT 500000,
            investment_target INTEGER DEFAULT 5000000,
            income_target INTEGER DEFAULT 5000000
        )
    ''')

    # 4. Tabel category keywords
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            keyword TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Tabel temp untuk edit token
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_transactions_temp (
            user_id INTEGER,
            transaction_id INTEGER,
            edit_token TEXT,
            expires_at TEXT,
            UNIQUE(user_id, transaction_id)
        )
    ''')

    conn.commit()

    # ===== SEED KEYWORD =====
    seed_keywords(cursor)

    conn.commit()
    conn.close()
    print("✅ Database initialized with all tables, indexes, and keywords")

def seed_keywords(cursor):
    """Seed semua keyword ke category_keywords"""
    from config import CATEGORY_KEYWORDS

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'income':
            type_ = 'income'
        elif category == 'investment':
            type_ = 'investment'
        else:
            type_ = 'expense'

        for keyword in keywords:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO category_keywords (type, category, keyword)
                    VALUES (?, ?, ?)
                ''', (type_, category, keyword.lower()))
            except:
                pass

    print(f"✅ Seeded {sum(len(kw) for kw in CATEGORY_KEYWORDS.values())} keywords")

# ==================== TRANSACTIONS ====================

def save_transaction(user_id: int, type_: str, amount: int, category: str, item: str, note: str = "") -> int:
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    date_today = datetime.now().date().isoformat()

    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, category, item, note, date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, type_, amount, category, item, note, date_today, now))

    conn.commit()
    trans_id = cursor.lastrowid
    conn.close()
    return trans_id

def get_transactions(user_id: int, start_date: str, end_date: str, type_filter: str = None) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT * FROM transactions
        WHERE user_id = ? AND date >= ? AND date <= ? AND is_deleted = 0
    '''
    params = [user_id, start_date, end_date]

    if type_filter:
        query += ' AND type = ?'
        params.append(type_filter)

    query += ' ORDER BY date DESC, created_at DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---- versi internal yang menerima koneksi ----
def _get_transactions_by_date_range_conn(conn, user_id: int, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM transactions
        WHERE user_id = ? AND date >= ? AND date <= ? AND is_deleted = 0
        ORDER BY date DESC, created_at DESC
    ''', (user_id, start_date, end_date))

    rows = cursor.fetchall()
    result = {'income': [], 'expense': [], 'investment': []}
    for row in rows:
        data = dict(row)
        if data['type'] in result:
            result[data['type']].append(data)
    return result

def get_transactions_by_date_range(user_id: int, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
    conn = get_db()
    try:
        return _get_transactions_by_date_range_conn(conn, user_id, start_date, end_date)
    finally:
        conn.close()

def get_transaction_by_id(user_id: int, trans_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM transactions
        WHERE user_id = ? AND id = ? AND is_deleted = 0
    ''', (user_id, trans_id))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_transaction(user_id: int, trans_id: int, field: str, new_value: Any, old_value: Any = None) -> bool:
    conn = get_db()
    cursor = conn.cursor()

    old_data = get_transaction_by_id(user_id, trans_id)
    if not old_data:
        conn.close()
        return False

    now = datetime.now().isoformat()
    cursor.execute(f'UPDATE transactions SET {field} = ?, edited_at = ? WHERE id = ? AND user_id = ?',
                   (new_value, now, trans_id, user_id))

    cursor.execute('''
        INSERT INTO transaction_history (transaction_id, field_changed, old_value, new_value, edited_at, edited_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (trans_id, field, str(old_value), str(new_value), now, user_id))

    cursor.execute('SELECT edit_history_ids FROM transactions WHERE id = ?', (trans_id,))
    row = cursor.fetchone()

    history_ids = row['edit_history_ids']
    if history_ids:
        ids = json.loads(history_ids)
        ids.append(cursor.lastrowid)
    else:
        ids = [cursor.lastrowid]

    cursor.execute('UPDATE transactions SET edit_history_ids = ? WHERE id = ?', (json.dumps(ids), trans_id))

    conn.commit()
    conn.close()
    return True

def delete_transaction(user_id: int, trans_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()

    old_data = get_transaction_by_id(user_id, trans_id)
    if not old_data:
        conn.close()
        return False

    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE transactions SET is_deleted = 1, edited_at = ?
        WHERE id = ? AND user_id = ?
    ''', (now, trans_id, user_id))

    cursor.execute('''
        INSERT INTO transaction_history (transaction_id, field_changed, old_value, new_value, edited_at, edited_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (trans_id, 'deleted', 'active', 'deleted', now, user_id))

    cursor.execute('SELECT edit_history_ids FROM transactions WHERE id = ?', (trans_id,))
    row = cursor.fetchone()

    history_ids = row['edit_history_ids']
    if history_ids:
        ids = json.loads(history_ids)
        ids.append(cursor.lastrowid)
    else:
        ids = [cursor.lastrowid]

    cursor.execute('UPDATE transactions SET edit_history_ids = ? WHERE id = ?', (json.dumps(ids), trans_id))

    conn.commit()
    conn.close()
    return True

def get_transaction_history(user_id: int, trans_id: int) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM transaction_history
        WHERE transaction_id = ?
        ORDER BY edited_at DESC
    ''', (trans_id,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---- versi internal yang menerima koneksi ----
def _get_summary_conn(conn, user_id: int, start_date: str, end_date: str) -> Dict:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT type, category, SUM(amount) as total
        FROM transactions
        WHERE user_id = ? AND date >= ? AND date <= ? AND is_deleted = 0
        GROUP BY type, category
    ''', (user_id, start_date, end_date))

    rows = cursor.fetchall()

    result = {
        'total_income': 0, 'total_expense': 0, 'total_investment': 0,
        'balance': 0, 'expense_breakdown': {}, 'income_breakdown': {},
        'investment_breakdown': {}, 'count_income': 0, 'count_expense': 0,
        'count_investment': 0
    }

    for row in rows:
        if row['type'] == 'income':
            result['total_income'] += row['total']
            result['income_breakdown'][row['category']] = row['total']
            result['count_income'] += 1
        elif row['type'] == 'investment':
            result['total_investment'] += row['total']
            result['investment_breakdown'][row['category']] = row['total']
            result['count_investment'] += 1
        else:
            result['total_expense'] += row['total']
            result['expense_breakdown'][row['category']] = result['expense_breakdown'].get(row['category'], 0) + row['total']
            result['count_expense'] += 1

    result['balance'] = result['total_income'] + result['total_investment'] - result['total_expense']
    return result

def get_summary(user_id: int, start_date: str, end_date: str) -> Dict:
    conn = get_db()
    try:
        return _get_summary_conn(conn, user_id, start_date, end_date)
    finally:
        conn.close()

def _get_previous_month_summary_conn(conn, user_id: int, reference_date=None) -> Dict:
    """Ringkasan bulan sebelum reference_date (default: bulan berjalan)"""
    if reference_date is None:
        reference_date = datetime.now().date()
    if hasattr(reference_date, 'date'):
        reference_date = reference_date.date()

    first_day = reference_date.replace(day=1)
    last_day_prev = first_day - timedelta(days=1)
    first_day_prev = last_day_prev.replace(day=1)

    return _get_summary_conn(
        conn, user_id,
        first_day_prev.isoformat(),
        last_day_prev.isoformat()
    )

def get_previous_month_summary(user_id: int, reference_date=None) -> Dict:
    """Dapatkan ringkasan bulan sebelum reference_date (default: bulan ini)"""
    conn = get_db()
    try:
        return _get_previous_month_summary_conn(conn, user_id, reference_date)
    finally:
        conn.close()




def get_previous_week_summary(user_id: int, start_date) -> Dict:
    """Dapatkan ringkasan minggu sebelumnya (Senin–Minggu)"""
    from datetime import timedelta
    if hasattr(start_date, 'date'):
        start_date = start_date.date()
    prev_monday = start_date - timedelta(days=7)
    prev_sunday = prev_monday + timedelta(days=6)
    return get_summary(
        user_id,
        prev_monday.isoformat(),
        prev_sunday.isoformat()
    )







def _get_user_settings_conn(conn, user_id: int) -> Dict:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()

    if row:
        return dict(row)
    else:
        # Default: semua budget 0 (belum diatur)
        return {
            'user_id': user_id,
            'report_time': '20:00',
            'is_premium': 0,
            'premium_expiry': None,
            'budget_makanan': 0,
            'budget_jajanan': 0,
            'budget_minuman': 0,
            'budget_rokok': 0,
            'budget_transport': 0,
            'budget_belanja': 0,
            'budget_tagihan': 0,
            'budget_hiburan': 0,
            'budget_kesehatan': 0,
            'budget_pendidikan': 0,
            'budget_lainnya': 0,
            'investment_target': 0,
            'income_target': 0
        }





def get_user_settings(user_id: int) -> Dict:
    conn = get_db()
    try:
        return _get_user_settings_conn(conn, user_id)
    finally:
        conn.close()







def update_user_setting(user_id: int, key: str, value):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM user_settings WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()

    if not exists:
        # Insert default semua budget 0
        cursor.execute('''
            INSERT INTO user_settings (
                user_id, report_time, is_premium, premium_expiry,
                budget_makanan, budget_jajanan, budget_minuman,
                budget_rokok, budget_transport, budget_belanja,
                budget_tagihan, budget_hiburan, budget_kesehatan,
                budget_pendidikan, budget_lainnya,
                investment_target, income_target
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, '20:00', 0, None,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0
        ))

    cursor.execute(f'UPDATE user_settings SET {key} = ? WHERE user_id = ?', (value, user_id))
    conn.commit()
    conn.close()







def get_all_users() -> List[int]:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT user_id FROM transactions WHERE is_deleted = 0')
    rows = cursor.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]


def get_transaction_months(user_id: int) -> List[str]:
    """Daftar bulan (format 'YYYY-MM') yang punya transaksi, terbaru dulu"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT substr(date, 1, 7) AS month
        FROM transactions
        WHERE user_id = ? AND is_deleted = 0
        ORDER BY month DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['month'] for row in rows]

# ==================== KEYWORD FUNCTIONS ====================

def get_keyword_category(keyword: str) -> Optional[Tuple[str, str]]:
    """Cari kategori dari keyword (type, category)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT type, category FROM category_keywords WHERE keyword = ?', (keyword.lower(),))
    row = cursor.fetchone()
    conn.close()

    if row:
        return (row['type'], row['category'])
    return None

def save_keyword(keyword: str, type_: str, category: str):
    """Simpan keyword ke database"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR IGNORE INTO category_keywords (type, category, keyword)
            VALUES (?, ?, ?)
        ''', (type_, category, keyword.lower()))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

# ==================== OPTIMIZED REPORT DATA (1 KONEKSI) ====================

def get_report_data_optimized(user_id: int, start_date: str, end_date: str) -> Dict:
    """
    Ambil semua data untuk laporan dengan 1 koneksi database.
    Jauh lebih cepat daripada 4 koneksi terpisah.
    """
    from utils import format_rupiah, format_date
    import calendar

    conn = get_db()
    try:
        # 1. Summary
        summary = _get_summary_conn(conn, user_id, start_date, end_date)

        # 2. Detail transaksi
        data = _get_transactions_by_date_range_conn(conn, user_id, start_date, end_date)

        # 3. User settings
        settings = _get_user_settings_conn(conn, user_id)

        # 4. Previous month summary (relatif terhadap periode laporan)
        prev_summary = _get_previous_month_summary_conn(
            conn, user_id, datetime.fromisoformat(start_date).date()
        )

        # ===== RINGKASAN =====
        ringkasan = {
            'pemasukan': summary['total_income'],
            'pengeluaran': summary['total_expense'],
            'saldo': summary['balance']
        }

        # ===== INSIGHT =====
        insights = []
        if summary['expense_breakdown']:
            top_cat = max(summary['expense_breakdown'].items(), key=lambda x: x[1])
            insights.append(f"Kategori terbesar: {top_cat[0].capitalize()} ({format_rupiah(top_cat[1])})")

        for cat, budget in settings.items():
            if cat.startswith('budget_') and budget > 0:
                cat_name = cat.replace('budget_', '')
                spent = summary['expense_breakdown'].get(cat_name, 0)
                pct = (spent / budget) * 100 if budget > 0 else 0
                if pct >= 90:
                    insights.append(f"Budget {cat_name.capitalize()} hampir habis ({pct:.0f}%)")

        if summary['balance'] > 0:
            insights.append(f"Saldo positif: {format_rupiah(summary['balance'])}")
        else:
            insights.append(f"Saldo negatif: {format_rupiah(summary['balance'])}")

        # ===== PERBANDINGAN =====
        perbandingan = {
            'bulan_ini': {
                'pemasukan': summary['total_income'],
                'pengeluaran': summary['total_expense'],
                'saldo': summary['balance']
            },
            'bulan_lalu': {
                'pemasukan': prev_summary.get('total_income', 0),
                'pengeluaran': prev_summary.get('total_expense', 0),
                'saldo': prev_summary.get('balance', 0)
            }
        }

        # ===== PIE CHART =====
        pie_chart = []
        for cat, amount in summary['expense_breakdown'].items():
            if amount > 0:
                pie_chart.append({'kategori': cat.capitalize(), 'nominal': amount})

        # ===== PENGELUARAN HARIAN =====
        daily_raw = {}
        for t in data['expense']:
            date_str = datetime.fromisoformat(t['date']).strftime('%d/%m/%y')
            daily_raw[date_str] = daily_raw.get(date_str, 0) + t['amount']

        start_date_obj = datetime.fromisoformat(start_date).date()
        year = start_date_obj.year
        month = start_date_obj.month
        days_in_month = calendar.monthrange(year, month)[1]

        daily_data = []
        for day in range(1, days_in_month + 1):
            tanggal = f"{day:02d}/{month:02d}/{str(year)[-2:]}"
            nominal = daily_raw.get(tanggal, 0)
            daily_data.append({
                'tanggal': tanggal,
                'nominal': nominal
            })

        # ===== DETAIL =====
        pemasukan = []
        for t in data['income']:
            pemasukan.append({
                'tanggal': format_date(t['date']),
                'kategori': t['category'].capitalize(),
                'item': t['item'],
                'nominal': t['amount']
            })

        pengeluaran = []
        for t in data['expense']:
            pengeluaran.append({
                'tanggal': format_date(t['date']),
                'kategori': t['category'].capitalize(),
                'item': t['item'],
                'nominal': t['amount']
            })

        # ===== BUDGET =====
        budget_data = []
        budget_categories = {
            'makanan': 'Makanan', 'jajanan': 'Jajanan', 'minuman': 'Minuman',
            'rokok': 'Rokok', 'transport': 'Transport', 'belanja': 'Belanja',
            'tagihan': 'Tagihan', 'hiburan': 'Hiburan',
            'kesehatan': 'Kesehatan', 'pendidikan': 'Pendidikan'
        }
        for key, label in budget_categories.items():
            budget_key = f'budget_{key}'
            if budget_key in settings and settings[budget_key] > 0:
                budget = settings[budget_key]
                spent = summary['expense_breakdown'].get(key, 0)
                remaining = budget - spent
                status = 'Aman' if remaining >= 0 else 'Over'
                budget_data.append({
                    'kategori': label,
                    'budget': budget,
                    'realisasi': spent,
                    'sisa': remaining,
                    'status': status
                })

        # ===== TARGET =====
        target_data = [
            {
                'target': f"Pemasukan: {format_rupiah(settings.get('income_target', 0))}",
                'realisasi': format_rupiah(summary['total_income']),
                'sisa': format_rupiah(settings.get('income_target', 0) - summary['total_income'])
            }
        ]

        return {
            'periode': f"{format_date(start_date_obj)} - {format_date(datetime.fromisoformat(end_date).date())}",
            'ringkasan': ringkasan,
            'insight': insights[:4],
            'perbandingan': perbandingan,
            'pie_chart': pie_chart,
            'daily_data': daily_data,
            'pemasukan': pemasukan,
            'pengeluaran': pengeluaran,
            'budget': budget_data,
            'target': target_data
        }
    finally:
        conn.close()
