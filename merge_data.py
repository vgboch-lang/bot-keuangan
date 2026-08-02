"""
Gabungkan data finance dari database Telegram + WhatsApp menjadi satu.

Schema kedua bot identik (memakai ulang kode inti yang sama), jadi cukup:
  1. Import semua baris dari database sumber ke database target.
  2. (Opsional) remap user_id lama -> user_id baru (mis. pindahkan data WhatsApp
     yang tersimpan di 1000000001 ke ID Telegram kamu agar data tergabung).

Cara pakai:
  python merge_data.py SUMBER TARGET [--remap OLD:NEW ...] [--dry-run]

Contoh:
  python merge_data.py finance_telegram.db finance.db --remap 1000000001:123456789
  python merge_data.py bot-whatsapp/finance.db finance.db --dry-run
"""
import argparse
import sqlite3
import sys
from collections import OrderedDict

# Tabel yang di-import (data penting). history/edit/temp tidak disalin utuh
# karena id-nya beda antar DB; transaksi tetap di-import dengan id baru.
TABLE_ORDER = [
    'transactions',
    'user_settings',
    'authorized_users',
    'trial_users',
    'category_keywords',
]

# Kunci dedup untuk transactions (abaikan id & created_at agar tidak dobel)
TRANSACTION_DEDUP = ['user_id', 'type', 'amount', 'category', 'item',
                     'note', 'date', 'is_deleted']


def table_columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]


def parse_remaps(raw):
    """['A:B','C:D'] -> {int(A):int(B)}"""
    out = {}
    for item in raw or []:
        if ':' not in item:
            raise SystemExit(f'--remap harus format OLD:NEW, dapat: {item!r}')
        o, n = item.split(':', 1)
        out[int(o)] = int(n)
    return out


def dedup_key(row, cols):
    """Kunci dedup sesuai kolom yang dipilih (transactions)."""
    vals = []
    for c in TRANSACTION_DEDUP:
        if c in cols:
            vals.append(str(row[c]))
    return tuple(vals)


def main():
    ap = argparse.ArgumentParser(description='Gabungkan database finance')
    ap.add_argument('source', help='DB sumber (mis. export Telegram dari Railway)')
    ap.add_argument('target', help='DB target (yang akan dipakai kedua bot)')
    ap.add_argument('--remap', action='append',
                    help='Ubah user_id lama ke baru, format OLD:NEW (bisa diulang)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Hanya laporan, tanpa mengubah file')
    args = ap.parse_args()

    remap = parse_remaps(args.remap)

    src = sqlite3.connect(args.source)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(args.target)
    dst.row_factory = sqlite3.Row

    # pastikan target punya schema
    src_has = [r[0] for r in src.execute(
        "select name from sqlite_master where type='table'").fetchall()]
    dst_has = [r[0] for r in dst.execute(
        "select name from sqlite_master where type='table'").fetchall()]
    if 'transactions' not in dst_has:
        raise SystemExit(f'Target {args.target!r} belum punya schema. '
                         'Jalankan bot dulu sekali agar init_db() membuat tabelnya.')

    print(f'🔀 Sumber : {args.source}  ({len(src_has)} tabel)')
    print(f'🎯 Target : {args.target}  ({len(dst_has)} tabel)')
    print(f'🔁 Remap  : {remap or "-"}')
    print(f'👀 Dry-run: {args.dry_run}')
    print()

    total_added = 0
    seen = set()

    # read target transactions dedup keys first (transactions)
    dst_txn_keys = set()
    if 'transactions' in dst_has:
        cols = table_columns(dst, 'transactions')
        for r in dst.execute('select * from transactions').fetchall():
            dst_txn_keys.add(dedup_key(r, cols))

    for table in TABLE_ORDER:
        if table not in src_has:
            continue
        cols = table_columns(src, table)
        src_rows = src.execute(f'select * from {table}').fetchall()
        if not src_rows:
            continue

        if table == 'transactions':
            # import dengan id baru + remap + dedup
            insert_cols = [c for c in cols if c != 'id']
            ph = ','.join('?' * len(insert_cols))
            sql = f'INSERT INTO transactions ({",".join(insert_cols)}) VALUES ({ph})'
            added = 0
            for row in src_rows:
                r = dict(zip(cols, row))
                old_uid = r['user_id']
                r['user_id'] = remap.get(old_uid, old_uid)
                k = dedup_key(r, cols)
                if k in dst_txn_keys or k in seen:
                    continue
                seen.add(k)
                dst_txn_keys.add(k)
                vals = [r[c] for c in insert_cols]
                if not args.dry_run:
                    dst.execute(sql, vals)
                added += 1
            total_added += added
            print(f'📄 transactions : +{added} baris (dedup)')
        else:
            # merge sederhana; user_settings/authorized/trial by user_id, keywords by keyword
            key_col = 'user_id' if table != 'category_keywords' else 'keyword'
            insert_cols = cols
            ph = ','.join('?' * len(insert_cols))
            sql = (f'INSERT OR IGNORE INTO {table} ({",".join(insert_cols)}) '
                   f'VALUES ({ph})')
            added = 0
            cur = dst.cursor()
            for row in src_rows:
                r = dict(zip(cols, row))
                if key_col == 'user_id':
                    r['user_id'] = remap.get(r['user_id'], r['user_id'])
                vals = [r[c] for c in insert_cols]
                if not args.dry_run:
                    cur.execute(sql, vals)
                    added += max(cur.rowcount, 0)
            total_added += added
            print(f'📄 {table:<16}: +{added} baris (OR IGNORE)')

    if not args.dry_run:
        dst.commit()
    print()
    print(f'{"[DRY-RUN] " if args.dry_run else ""}Selesai. Total baris baru: {total_added}')
    src.close()
    dst.close()


if __name__ == '__main__':
    main()
