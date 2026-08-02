import re
from datetime import datetime, timedelta
import locale
from typing import Optional, Tuple, Dict, List
import json

# Set locale
try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Indonesian')
    except:
        pass

# ==================== FORMAT RUPIAH ====================
def format_rupiah(amount: int) -> str:
    """Format angka ke Rupiah"""
    try:
        return f"Rp{amount:,.0f}".replace(',', '.')
    except:
        return f"Rp{amount}"

# ==================== PARSE NOMINAL ====================
def parse_nominal(text: str) -> Optional[int]:
    """
    Ekstrak nominal dari text
    Support: 25k, 25rb, 1.5jt, 1,5jt, 50000, 50rb, 50k, 1jt, 1 juta
    """
    text = text.lower().strip()
    
    # Pola: angka + satuan
    patterns = [
        # 1.5jt, 1,5jt, 1.5 juta
        (r'(\d+[.,]?\d*)\s*(jt|juta|juta-an)', 1000000),
        # 1.5m, 1,5m, 1.5 mil
        (r'(\d+[.,]?\d*)\s*(m|mil|juta|juta-an)', 1000000),
        # 25rb, 25k, 25 ribu
        (r'(\d+[.,]?\d*)\s*(rb|ribu|k|k-an)', 1000),
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            num_str = match.group(1).replace(',', '.')
            try:
                num = float(num_str)
                return int(num * multiplier)
            except:
                continue
    
    # Pola: angka biasa (tanpa satuan)
    # Cari semua angka di text
    numbers = re.findall(r'(\d+[.,]?\d*)', text)
    if numbers:
        for num_str in numbers:
            try:
                num = float(num_str.replace(',', '.'))
                # Kalau angkanya > 100, anggap nominal langsung
                if num >= 100:
                    return int(num)
                # Kalau angkanya 1-99, tapi ada kata "rb" atau "k" di dekatnya
                if 1 <= num <= 99:
                    # Cek apakah ada "rb" atau "k" di sekitar
                    if re.search(r'\b(rb|ribu|k)\b', text):
                        return int(num * 1000)
            except:
                continue
    
    return None

# ==================== DETECT CATEGORY ====================
def detect_category(text: str, category_keywords: Dict, default: str = 'lainnya') -> str:
    """
    Deteksi kategori dari text
    Prioritas: keyword terpanjang > keyword pendek
    """
    text = text.lower().strip()
    best_match = None
    best_category = default
    best_length = 0
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Cek apakah keyword ada di text (whole word)
            # Gunakan word boundary biar lebih akurat
            pattern = r'\b' + re.escape(keyword_lower) + r'\b'
            if re.search(pattern, text):
                if len(keyword_lower) > best_length:
                    best_length = len(keyword_lower)
                    best_category = category
                    best_match = keyword_lower
    
    # Kalau tidak ketemu dengan word boundary, coba partial match
    if best_category == default:
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in text:
                    if len(keyword_lower) > best_length:
                        best_length = len(keyword_lower)
                        best_category = category
    
    return best_category

# ==================== EXTRACT ITEM ====================
def extract_item(text: str, stop_words: list, default: str = "transaksi") -> str:
    """
    Ekstrak item dari text
    1. Hapus nominal
    2. Hapus kata kerja (stop words) - tapi hati-hati
    3. Bersihkan spasi
    """
    text = text.strip()
    
    # Hapus nominal (angka + satuan)
    text = re.sub(r'\d+[.,]?\d*\s*(jt|juta|m|mil|rb|ribu|k|k-an)', '', text, flags=re.IGNORECASE)
    # Hapus angka doang
    text = re.sub(r'\d+[.,]?\d*', '', text)
    
    # Hapus stop words (kata kerja) - tapi hati-hati
    # Hapus yang di awal kata
    for word in stop_words:
        pattern = r'^' + re.escape(word.lower()) + r'\s+'
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Hapus yang di tengah (dengan spasi)
    for word in stop_words:
        pattern = r'\s+' + re.escape(word.lower()) + r'\s+'
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
        # Hapus di akhir
        pattern = r'\s+' + re.escape(word.lower()) + r'$'
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Hapus kata "investasi" dari awal item
    text = re.sub(r'^investasi\s+', '', text, flags=re.IGNORECASE)
    
    # Bersihkan spasi berlebih
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Kalau kosong, pakai default
    if not text:
        return default
    
    return text

# ==================== SPLIT MULTI TRANSACTIONS ====================
def split_multi_transactions(text: str, separators: list) -> List[str]:
    """Split teks menjadi beberapa transaksi berdasarkan separator"""
    text = text.strip()
    parts = [text]
    
    for sep in separators:
        new_parts = []
        for part in parts:
            if sep in part:
                split_parts = part.split(sep)
                new_parts.extend([p.strip() for p in split_parts if p.strip()])
            else:
                new_parts.append(part)
        parts = new_parts
    
    # Filter out empty parts
    return [p for p in parts if p]

# ==================== GET CATEGORY TYPE ====================
def get_category_type(category: str) -> str:
    """
    Tentukan type (income/expense/investment) dari kategori
    """
    income_categories = ['income']
    
    if category in income_categories:
        return 'income'
    else:
        return 'expense'

# ==================== DETECT TYPE ====================
def detect_type(text: str, categories: dict) -> str:
    """Deteksi tipe transaksi dari text (income/expense/investment)"""
    text = text.lower()
    
    # Cek income
    for keyword in categories.get("income", []):
        if keyword in text:
            return "income"
    
    # Default: expense
    return "expense"

# ==================== DETECT INCOME CATEGORY ====================
def detect_income_category(text: str) -> str:
    """Deteksi kategori income"""
    text = text.lower()
    income_keywords = {
        "gaji": ["gaji", "salary"],
        "bonus": ["bonus", "thr"],
        "freelance": ["freelance", "proyek", "project"],
        "dividen": ["dividen", "dividend"],
        "bunga": ["bunga", "interest"],
        "sewa": ["sewa", "rent"],
        "hadiah": ["hadiah", "gift", "reward"],
        "komisi": ["komisi", "commission"],
        "lainnya": []
    }
    
    for category, keywords in income_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category
    
    return "lainnya"

# ==================== PARSE DATE ====================
def parse_date(text: str) -> Optional[datetime]:
    """Parse berbagai format tanggal"""
    text = text.strip().lower()
    
    # Ganti nama bulan ke angka
    bulan_map = {
        'januari': '01', 'februari': '02', 'maret': '03', 'april': '04',
        'mei': '05', 'juni': '06', 'juli': '07', 'agustus': '08',
        'september': '09', 'oktober': '10', 'november': '11', 'desember': '12',
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    for nama, angka in bulan_map.items():
        if nama in text:
            text = text.replace(nama, angka)
    
    # Coba berbagai format
    date_formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d %m %Y",
        "%d/%m/%y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(text, fmt)
        except:
            continue
    
    return None

# ==================== FORMAT DATE ====================
def format_date(date) -> str:
    """Format date ke string yang rapi"""
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()
        except:
            return date
    if hasattr(date, 'strftime'):
        return date.strftime("%d %B %Y")
    return str(date)

# ==================== GET DATE RANGE ====================
def get_date_range(period: str):
    """Dapatkan range tanggal untuk berbagai periode"""
    today = datetime.now().date()
    
    if period == 'today':
        return today, today
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'month':
        start = today.replace(day=1)
        return start, today
    else:
        return today, today

# ==================== TRUNCATE TEXT ====================
def truncate_text(text: str, max_length: int = 50) -> str:
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

# ==================== CALCULATE PERCENTAGE ====================
def calculate_percentage(current: int, previous: int) -> float:
    if previous == 0:
        return 0
    return ((current - previous) / previous) * 100

# ==================== FORMAT PERCENTAGE ====================
def format_percentage(value: float) -> str:
    if value > 0:
        return f"▲ +{value:.1f}%"
    elif value < 0:
        return f"▼ {value:.1f}%"
    else:
        return "━ 0%"