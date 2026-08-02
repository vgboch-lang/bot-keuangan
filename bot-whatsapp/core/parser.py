import re
import json
import requests
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from .config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL,
    CATEGORIES, STOP_WORDS, SEPARATORS
)
from .utils import (
    parse_nominal, detect_type, detect_category,
    detect_income_category,
    extract_item, parse_date
)
from .database import get_keyword_category, save_keyword

# ==================== PARSE WITH REGEX (GRATIS) ====================

def parse_with_regex(text: str) -> Optional[Dict]:
    """Parse dengan regex & dictionary (GRATIS!)"""
    text = text.strip()
    
    amount = parse_nominal(text)
    if not amount:
        return None
    
    type_ = detect_type(text, CATEGORIES)
    
    if type_ == "income":
        category = detect_income_category(text)
    else:
        category = detect_category(text, CATEGORIES)
    
    # Ambil item
    raw_item = re.sub(r'\d+[.,]?\d*\s*(jt|juta|m|mil|rb|ribu|k|k-an)', '', text, flags=re.IGNORECASE)
    raw_item = re.sub(r'\d+[.,]?\d*', '', raw_item).strip()
    item_text = raw_item
    
    for word in STOP_WORDS:
        if item_text.lower().startswith(word + ' '):
            item_text = item_text[len(word):].strip()
        elif f' {word} ' in item_text.lower():
            item_text = item_text.replace(f' {word} ', ' ')
    
    if item_text.lower().startswith('investasi '):
        item_text = item_text[len('investasi '):].strip()
    
    if not item_text:
        item_text = re.sub(r'\d+[.,]?\d*\s*(jt|juta|m|mil|rb|ribu|k|k-an).*$', '', text, flags=re.IGNORECASE)
        item_text = re.sub(r'\d+[.,]?\d*$', '', item_text).strip()
    
    # Aturan chat singkat: kalau input pendek (<= 2 kata) simpan SEMUA,
    # jangan dipangkas jadi 1 kata (mis. "makan pagi" jangan jadi "pagi")
    if len(raw_item.split()) >= 2 and len(item_text.split()) <= 1:
        item_text = raw_item
    
    return {
        'type': type_,
        'amount': amount,
        'category': category,
        'item': item_text if item_text else "transaksi",
        'note': text
    }

# ==================== PARSE WITH AI (FALLBACK) ====================

def parse_with_ai(text: str) -> Optional[Dict]:
    """Parse dengan DeepSeek API (FALLBACK - BERBAYAR)"""
    prompt = f"""
    Ekstrak informasi transaksi dari chat berikut:
    "{text}"
    
    Output dalam format JSON:
    {{
        "type": "income" atau "expense" atau "investment",
        "amount": integer (nominal dalam Rupiah),
        "category": "kategori (contoh: makanan, transport, gaji, saham, dll)",
        "item": "string (deskripsi singkat transaksi)",
        "note": "string (catatan tambahan)"
    }}
    
    Hanya output JSON, tanpa teks lain.
    """
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Kamu adalah asisten yang mengekstrak data transaksi keuangan."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 200
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        print(f"DeepSeek error: {e}")
        return None

# ==================== CHECK KEYWORD IN DATABASE ====================

def check_keyword_in_db(item: str) -> Optional[Tuple[str, str]]:
    """Cek keyword di database"""
    result = get_keyword_category(item.lower())
    if result:
        return result
    
    words = item.lower().split()
    for word in words:
        if len(word) > 2:
            result = get_keyword_category(word)
            if result:
                return result
    
    return None

# ==================== PARSE MULTI TRANSACTIONS ====================

def parse_multi_transactions(text: str) -> List[Dict]:
    """Parse multiple transaksi dalam satu chat"""
    text = text.strip()
    
    parts = [text]
    for sep in SEPARATORS:
        new_parts = []
        for part in parts:
            if sep.isalpha():
                # Separator berupa kata: harus kata utuh (hindari 'dan' di dalam 'padang')
                pattern = r'\b' + re.escape(sep) + r'\b'
                if not re.search(pattern, part):
                    new_parts.append(part)
                    continue
                split_parts = re.split(pattern, part)
            elif sep in part:
                split_parts = part.split(sep)
            else:
                new_parts.append(part)
                continue
            new_parts.extend([p.strip() for p in split_parts if p.strip()])
        parts = new_parts
    
    results = []
    for part in parts:
        if part:
            parsed = parse_with_regex(part)
            if parsed and parsed.get('amount'):
                results.append(parsed)
    
    # Kalau hasil 0 atau 1, coba split berdasarkan nominal
    if len(results) <= 1:
        nominal_positions = []
        for match in re.finditer(r'\d+[.,]?\d*\s*(jt|juta|m|mil|rb|ribu|k|k-an)', text):
            nominal_positions.append((match.start(), match.end()))
        
        if len(nominal_positions) > 1:
            parts = []
            prev_end = 0
            for start, end in nominal_positions:
                if start > prev_end:
                    part_text = text[prev_end:start].strip()
                    if part_text:
                        parts.append(part_text + ' ' + text[start:end].strip())
                prev_end = end
            if prev_end < len(text):
                remaining = text[prev_end:].strip()
                if remaining:
                    parts.append(remaining)
            
            results = []
            for part in parts:
                if part:
                    parsed = parse_with_regex(part)
                    if parsed and parsed.get('amount'):
                        results.append(parsed)
    
    return results

# ==================== MAIN PARSER (SELALU RETURN LIST) ====================

def parse_transaction(text: str, use_db: bool = True) -> List[Dict]:
    """
    Hybrid parser: SELALU return list of dict
    1. Check database keyword
    2. Regex parsing (gratis)
    3. AI fallback (berbayar)
    """
    text = text.strip()
    
    # Step 1: Coba parse multi transaksi dengan regex
    results = parse_multi_transactions(text)
    
    # Step 2: Kalau hasilnya kosong, coba single transaksi (regex)
    if not results:
        single_result = parse_with_regex(text)
        
        # Step 3: Kalau regex gagal, coba AI
        if not single_result or single_result['amount'] is None:
            print(f"⚠️ Regex gagal, panggil AI: {text}")
            single_result = parse_with_ai(text)
            if single_result and single_result.get('item'):
                save_keyword(single_result['item'], single_result.get('type', 'expense'), single_result.get('category', 'lainnya'))
        
        # Step 4: Kalau ada hasil, masukkan ke list
        if single_result and single_result.get('amount'):
            results = [single_result]
    
    # Step 5: Kalau results masih kosong, return []
    if not results:
        return []
    
    # Step 6: Cek keyword di database (auto-learning)
    for result in results:
        if use_db and result.get('item'):
            db_result = check_keyword_in_db(result['item'])
            if db_result:
                db_type, db_category = db_result
                result['type'] = db_type
                result['category'] = db_category
                
                # Simpan keyword baru jika berbeda
                if db_result[1] != result['item']:
                    save_keyword(result['item'], db_type, db_category)
        
        # Auto-learning: simpan keyword baru ke database
        if result.get('item'):
            existing = get_keyword_category(result['item'].lower())
            if not existing:
                save_keyword(result['item'], result['type'], result['category'])
                # Tambahkan juga kata-kata individual
                words = result['item'].lower().split()
                for word in words:
                    if len(word) > 2:
                        existing_word = get_keyword_category(word)
                        if not existing_word:
                            save_keyword(word, result['type'], result['category'])
    
    # Fitur investasi sudah dihapus: pastikan tidak ada transaksi bertipe investment
    for result in results:
        if result.get('type') == 'investment':
            result['type'] = 'expense'
            result['category'] = 'lainnya'
    
    # SAFETY: PASTIKAN RETURN LIST!
    if not isinstance(results, list):
        if isinstance(results, dict):
            return [results]
        return []
    
    return results

# ==================== PARSE CUSTOM DATE ====================

def parse_custom_date(text: str) -> Optional[Dict]:
    """
    Parse rekap custom date dari chat
    Contoh: "rekap 01/07/2026 sampai 12/07/2026"
    """
    text = text.lower().strip()
    
    patterns = [
        r'(?:rekap|laporan|pdf|lihat|tampilkan)\s+(.+?)\s+(?:sampai|ke|sd|s/d|-)\s+(.+)',
        r'(?:rekap|laporan|pdf|lihat|tampilkan)\s+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*(?:-|sampai|sd|s/d)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*(?:-|sampai|sd|s/d)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            start_text = match.group(1).strip()
            end_text = match.group(2).strip()
            
            start_date = parse_date(start_text)
            end_date = parse_date(end_text)
            
            if start_date and end_date:
                return {
                    'start': start_date.date(),
                    'end': end_date.date()
                }
    
    return None