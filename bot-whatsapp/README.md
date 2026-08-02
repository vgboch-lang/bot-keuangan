# 🤖 Bot Catat Keuangan — WhatsApp

Bot keuangan di WhatsApp (unofficial, via WhatsApp Web + Playwright).
**Memakai ulang kode inti dari bot Telegram** (`core/`): parser, database, laporan PDF.
Data disimpan di `finance.db` — **bisa digabung** dengan data bot Telegram (volume yang sama).

> ⚠️ **Risiko:** pendekatan unofficial melanggar ToS WhatsApp. Nomor bisa diblokir.
> Kalau di-blokir, **data tetap aman di `finance.db`** — tinggal link nomor WhatsApp baru.

---

## 📦 Setup lokal

```bash
cd bot-whatsapp
pip install -r requirements.txt
playwright install chromium
```

## 🚀 Menjalankan

```bash
python wa_bot.py
```

- Pertama kali: bot membuka WhatsApp Web, simpan QR ke `qr_login.png` → **scan dari HP** (WhatsApp → *Linked Devices*).
- Session tersimpan di `wa_session/` → setelah itu tidak perlu scan lagi.

## ⚙️ Variabel Environment

| Variabel | Fungsi | Contoh |
|----------|--------|--------|
| `WA_OWNER` | Nomor WA pemilik (format 62) | `628123456789` |
| `WA_ALLOWED` | Whitelist nomor (pisah koma) | `628123456789,628987654321` |
| `WA_USER_ID` | **user_id penyimpanan data** — set = ID Telegram kamu agar data WA & Telegram tergabung | `123456789` |
| `WA_TEST_MODE` | `1` → pakai database terpisah `finance_test.db` (buat tes) | `1` |

> 👤 **Admin = chat PALING ATAS di daftar chat** (bukan berdasarkan nama — tidak ada data nama di script).
> Agar andal, **sematkan (pin)** chat admin di WhatsApp; chat orang lain yang tidak disematkan otomatis diabaikan.
| `DATABASE_FILE` | Lokasi DB | `finance.db` |

Jika `WA_ALLOWED` kosong → hanya `WA_OWNER` yang boleh.

> 🔀 **Menggabung data WhatsApp + Telegram (khusus milikmu):**
> 1. Kedua bot harus memakai **file DB yang sama** (di Railway: pasang volume `/app/data` yang sama di kedua service).
> 2. Set `WA_USER_ID` = ID Telegram kamu (cek via `/myid` di bot Telegram). Dengan begitu semua transaksimu tersimpan di `user_id` yang sama → otomatis tergabung, sedangkan data pengguna lain tetap terpisah.
> 3. Untuk data lama yang sudah terlanjur tersimpan di `user_id` lain, pakai `../merge_data.py` (lihat bawah).
>
> `WA_USER_ID` tidak boleh di-hardcode di kode — selalu lewat environment variable.

## ☁️ Deploy di Railway (service terpisah dari bot Telegram)

1. Service baru → pilih **root directory**: `bot-whatsapp`.
2. **Variables**: `WA_OWNER`, `WA_ALLOWED`.
3. **Volume**: pasang di `/app/data` (SAMA dengan service Telegram agar data digabung).
4. **Start command**: `pip install -r requirements.txt && playwright install chromium && python wa_bot.py`
5. Lihat log → scan QR pertama kali (simpan `qr_login.png`/screenshot dari log atau volume).

> Catatan: karena bot berjalan di server, HP **tidak perlu nyala terus** — session tersimpan di volume.
> HP hanya perlu nyala saat **scan QR awal** atau **re-link** (kalau session hilang).

## 🔁 Migrasi ke nomor WhatsApp baru (kalau nomor lama di-blokir)

1. **Data tidak hilang** — sudah ada di `finance.db`.
2. Daftarkan nomor WA baru + verifikasi.
3. **Hapus folder `wa_session/`** (session nomor lama).
4. Jalankan ulang → **scan QR** nomor baru.
5. Selesai — semua data lama (transaksi, keyword belajar, budget) langsung muncul.

## 💬 Perintah

- Ketik bebas: `makan siang 25rb`, `gaji 4jt`, `gojek 15rb`
- `pengeluaran` → daftar transaksi hari ini
- `rekap harian` | `rekap mingguan` | `rekap bulanan` → **rekap dalam bentuk chat (teks)**
- `bantuan` → panduan

> Tanda `/` tetap bisa dipakai (mis. `/rekap bulanan`).

---

> ⚠️ Selector WhatsApp Web bisa berubah sewaktu-waktu. Kalau ada fitur tidak jalan,
> cek log `wa_bot.py` dan sesuaikan selector-nya.
