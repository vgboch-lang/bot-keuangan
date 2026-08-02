import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env
env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ .env loaded from: {env_path.absolute()}")
else:
    print(f"❌ .env not found at: {env_path.absolute()}")

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN tidak ditemukan di .env")

# DeepSeek API (opsional, bisa dikosongkan)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Database
# ===== DATABASE =====
import os
if os.getenv("RAILWAY_ENVIRONMENT"):
    DATABASE_FILE = os.path.join("/app/data", "finance.db")
else:
    DATABASE_FILE = os.getenv("DATABASE_FILE", "finance.db")
print(f"📁 Database file: {DATABASE_FILE}")

# Report settings
REPORT_TIME = os.getenv("REPORT_TIME", "21:00")
TIMEZONE = "Asia/Jakarta"

# ===================================================================
# ============ DATABASE KEYWORD SUPER LENGKAP ======================
# ===================================================================

CATEGORY_KEYWORDS = {

    # ========== 1. 🍔 MAKANAN (Makanan Berat / Utama) ==========
    'makanan': [
        # Nasi & Olahan
        'nasi', 'nasi goreng', 'nasi padang', 'naspad', 'nasi uduk', 'nasi kuning',
        'nasi campur', 'nasi rames', 'nasi kotak', 'nasi bungkus', 'nasi liwet',
        'nasi bakar', 'nasi tutug', 'nasi tim', 'nasi ayam', 'nasi bebek',
        'nasi soto', 'nasi rawon', 'nasi gudeg', 'nasi pecel', 'nasi uduk',
        
        # Ayam
        'ayam', 'ayam goreng', 'ayam bakar', 'ayam geprek', 'ayam penyet',
        'ayam kremes', 'ayam suwir', 'ayam rica', 'ayam betutu', 'ayam panggang',
        'ayam woku', 'ayam kecap', 'ayam kari', 'ayam opor', 'ayam bumbu',
        'ayam rempah', 'ayam sambal', 'ayam cabe', 'ayam goreng mentega',
        
        # Bebek
        'bebek', 'bebek goreng', 'bebek bakar', 'bebek sinjay', 'bebek bumbu',
        
        # Ikan & Seafood
        'ikan', 'ikan bakar', 'ikan goreng', 'ikan tongkol', 'ikan tuna',
        'ikan asin', 'ikan teri', 'ikan bandeng', 'ikan gurame', 'ikan lele',
        'ikan mujair', 'ikan nila', 'ikan patin', 'ikan salmon',
        'seafood', 'udang', 'cumi', 'kerang', 'kepiting', 'lobster',
        
        # Daging Sapi / Kambing
        'daging', 'sapi', 'kambing', 'rendang', 'gulai', 'tongseng', 'rawon',
        'soto sapi', 'soto daging', 'sop buntut', 'sop iga', 'steak',
        'semur', 'dendeng', 'abon', 'empal', 'gepuk',
        
        # Mie & Pasta
        'mie', 'mie ayam', 'mie goreng', 'mie rebus', 'mie kocok',
        'mie bakso', 'mie celor', 'mie ramen', 'mie instan', 'indomie',
        'spaghetti', 'pasta', 'lasagna', 'fettuccine',
        
        # Bakso & Soto
        'bakso', 'bakso bakar', 'bakso goreng', 'soto', 'soto ayam', 'soto daging',
        'soto madura', 'soto betawi', 'soto lamongan', 'soto banjar',
        
        # Sate & Gado-gado
        'sate', 'sate ayam', 'sate kambing', 'gado-gado', 'pecel', 'ketoprak',
        'kupat tahu', 'lontong sayur', 'lontong balap', 'batagor', 'siomay',
        
        # Warung & Restoran
        'warteg', 'resto', 'restoran', 'cafe', 'warung', 'kaki lima',
        'food court', 'rumah makan', 'kedai', 'angkringan',
        
        # Makanan Khas
        'gudeg', 'sambal', 'lalapan', 'tahu', 'tempe', 'pepes',
        'perkedel', 'kroket', 'risoles', 'pastel', 'lumpia',
        'martabak', 'martabak manis', 'martabak telor',
        'terang bulan', 'apem', 'putu', 'kue bugis', 'kue lapis',
        
        # Fast Food & Cepat Saji
        'fast food', 'mcd', 'kfc', 'burger', 'kentang', 'french fries',
        'pizza hut', 'domino', 'pizza', 'hoka-hoka', 'kebab', 'shawarma',
        
        # Sushi & Jepang
        'sushi', 'ramen', 'takoyaki', 'okonomiyaki', 'tempura', 'teriyaki',
        
        # China & Asia
        'dimsum', 'hakau', 'pao', 'bakpao', 'lumpia', 'kwetiau', 'bihun',
        
        # Nama Slang / Singkatan
        'nasgor', 'naskun', 'sego', 'sego goreng', 'sego pecel',
        
        # Nasi Khas Daerah
        'nasi kebuli', 'nasi minyak', 'nasi megono', 'nasi jamblang', 'nasi lengko',
        'nasi timbel', 'nasi tutug oncom', 'nasi jinggo', 'nasi campur bali',
        
        # Ayam & Unggas
        'ayam bacem', 'ayam pop', 'ayam tangkap', 'ayam rica-rica', 'ayam kungpao',
        'bebek madura', 'bebek kalasan', 'bebek peking',
        
        # Seafood
        'rajungan', 'cumi goreng', 'udang goreng', 'kepiting soka', 'otak-otak',
        'pindang', 'bandeng presto', 'ikan pepes', 'ikan kuah', 'ikan kembung',
        
        # Mie
        'mie ayam bakso', 'mie jawa', 'mie tektek', 'mie gacoan', 'mie glagah',
        'mie babat', 'mie kocok bandung', 'mie kuah', 'mie yamin', 'mie aceh',
        
        # Soto & Sup
        'soto mie', 'soto padang', 'soto babat', 'sop iga sapi', 'sup ayam',
        'sup jagung', 'sayur sop', 'sayur asem', 'sayur lodeh',
        
        # Sate & Lauk
        'sate padang', 'sate madura', 'sate taichan', 'sate klatak', 'sate telur puyuh',
        'tempe penyet', 'tahu penyet', 'tahu telur', 'pecel lele', 'sambal goreng',
        
        # Makanan Berat Lain
        'ketupat', 'lemang', 'lontong opor', 'krengsengan', 'oseng-oseng', 'tumis',
        'capcay', 'fu yung hai', 'rawon setan',
        
        # Fast Food
        'wendys', 'a&w', 'burger king', 'subway', 'ramly burger', 'kentang goreng',
        
        # Lainnya
        'makan', 'sarapan', 'makan siang', 'makan malam', 'makanan'
    ],

    # ========== 2. 🍿 JAJANAN (Makanan Ringan / Camilan) ==========
    'jajanan': [
        # Gorengan
        'gorengan', 'pisang goreng', 'ubi goreng', 'tahu isi', 'tempe mendoan',
        'bakwan', 'ote-ote', 'risol', 'pastel', 'lumpia',
        'cemilan', 'camilan', 'kudapan', 'snack',
        
        # Cilok & Sejenis
        'cilok', 'cilor', 'cimol', 'batagor', 'siomay',
        'pentol', 'basreng', 'gehu', 'tahu bulat', 'tahu gejrot',
        
        # Kerupuk & Keripik
        'kerupuk', 'keripik', 'kacang', 'ciki', 'chiki',
        'emping', 'rempeyek', 'kripik', 'kripik singkong',
        
        # Kue & Roti
        'kue', 'roti', 'roti tawar', 'roti manis', 'roti gandum',
        'nastar', 'kastengel', 'putri salju', 'lemper', 'arem-arem',
        'donat', 'donat madu', 'jco', 'dunkin', 'muffin', 'cupcake',
        'croissant', 'bolu', 'kue lumpur', 'kue cubit', 'kue pancong',
        
        # Es Krim & Manisan
        'es krim', 'eskrim', 'ice cream', 'cream', 'puding', 'agar-agar',
        'coklat', 'permen', 'jelly', 'marshmallow', 'candy', 'lollipop',
        
        # Popcorn & Snack
        'popcorn', 'pop corn', 'snack', 'ciki', 'chiki',
        
        # Cireng, Seblak & Kekinian
        'cireng', 'seblak', 'baso aci', 'mie lidi', 'tahu coklat', 'tahu mercon',
        'pisang keju', 'pisang coklat', 'ubi cilembu', 'singkong goreng',
        'jamur goreng', 'onion ring', 'chicken nugget', 'nugget', 'sosis',
        'sosis bakar', 'corn dog', 'sempol', 'cilok kuah', 'basreng',
        
        # Roti & Kue Kekinian
        'roti bakar', 'roti goreng', 'croffle', 'waffle', 'pancake', 'crepe',
        'kue pukis', 'klepon', 'onde-onde', 'kue moci', 'lupis', 'brownies',
        'cheesecake', 'cake', 'cookies',
        
        # Lainnya
        'jajan', 'jajanan'
    ],

    # ========== 3. 🥤 MINUMAN ==========
    'minuman': [
        # Teh
        'es teh', 'teh manis', 'teh tawar', 'teh susu', 'teh tarik',
        'teh poci', 'teh botol', 'teh kotak', 'teh gelas',
        
        # Kopi
        'kopi', 'kopi hitam', 'kopi susu', 'kopi jahe', 'es kopi',
        'cold brew', 'kopi luwak', 'kopi tubruk', 'kopi kapal api',
        'kopi kenangan', 'kopi nescafe', 'kopi kian',
        
        # Jus
        'jus', 'jus jeruk', 'jus alpukat', 'jus mangga', 'jus melon',
        'jus tomat', 'jus apel', 'jus nanas', 'jus strawberry', 'jus pisang',
        
        # Bubble & Milk Tea
        'boba', 'bubble', 'thai tea', 'milk tea', 'matcha',
        'greentea', 'redvelvet', 'bubble tea', 'boba tea',
        
        # Soda & Minuman Ringan
        'soda', 'coca-cola', 'coke', 'fanta', 'sprite', 'pepsi',
        
        # Air Mineral
        'air mineral', 'aqua', 'vit', 'le minerale', 'air putih',
        
        # Susu & Olahan
        'susu', 'susu segar', 'susu kental manis', 'susu kedelai',
        'yogurt', 'yakult', 'susu coklat', 'susu strawberry',
        
        # Es & Campuran
        'es', 'es buah', 'es campur', 'es teler', 'es doger', 'es kelapa',
        
        # Minuman Kekinian
        'milkshake', 'smoothie', 'frappucino', 'mocha', 'latte',
        
        # Alkohol
        'bir', 'anker', 'heineken', 'tuak', 'arak', 'alkohol',
        
        # Teh & Es Tradisional
        'es teh tarik', 'teh hangat', 'teh tubruk', 'es jeruk', 'es sirup',
        'es degan', 'es kelapa muda', 'es cendol', 'es dawet', 'es cincau',
        'es blewah', 'soda gembira',
        
        # Kopi Kekinian
        'es kopi susu', 'kopi susu gula aren', 'kopi aren', 'espresso',
        'americano', 'cappuccino', 'kopi senja', 'kopi nako',
        
        # Jus & Smoothie
        'jus avokad', 'jus jambu', 'jus sirsak', 'jus semangka', 'jus pepaya',
        'smoothies',
        
        # Susu & Minuman Kemasan
        'susu murni', 'susu uht', 'milku', 'good day', 'cimory', 'ultra milk',
        'indomilk', 'greenfields', 'nestle', 'cleo', 'amidis', 'crystaline',
        
        # Soda & Energy
        'cola', 'sarsi', 'extra joss', 'kuku bima', 'hemaviton', 'red bull',
        'monster', 'isoplus', 'pocari',
        
        # Bubble Tea & Kekinian
        'brown sugar', 'pearl milk tea', 'thai milk tea', 'matcha latte', 'taro',
        'eskul', 'redvelvet latte',
        
        # Lainnya
        'minum', 'minuman'
    ],

    # ========== 4. 🚬 ROKOK ==========
    'rokok': [
        # Rokok Kretek
        'rokok', 'kretek', 'filter', 'mild', 'menthol',
        'sampoerna', 'djarum', 'gudang garam', 'marlboro', 'dunhill',
        'lucky strike', 'camel', 'philips', 'rokok clove',
        
        # Rokok Elektronik / Vape
        'vape', 'pod', 'liquid', 'relx', 'rokok elektronik',
        'tembakau', 'linting', 'cerutu', 'cigar',
        
        # Merek Lain
        'surya', 'surya 16', 'surya pro', 'dji sam soe', 'dji sam soe magnum',
        'malboro', 'l.a. bold', 'u bold', 'rokok filter', 'rokok kretek',
        'rokok menthol',
        
        # Aksesoris
        'korek', 'korek api', 'gas', 'korek gas', 'rokok'
    ],

    # ========== 5. 🚗 TRANSPORT ==========
    'transport': [
        # Ojek Online
        'gojek', 'grab', 'ojek', 'ojol', 'taxi', 'taksi', 'maxim',
        
        # BBM
        'bensin', 'pertalite', 'pertamax', 'solar', 'bbm',
        'minyak', 'oli', 'servis', 'ganti oli', 'servis motor',
        
        # Parkir & Tol
        'parkir', 'tol', 'jalan tol', 'e-toll', 'parkir motor',
        
        # Kereta
        'kereta', 'ktb', 'commuter', 'krl', 'mrt', 'lrt', 'transjakarta',
        
        # Bus & Angkot
        'bus', 'angkot', 'bemo', 'transjakarta', 'busway',
        
        # Kapal & Pesawat
        'kapal', 'feri', 'speedboat', 'pesawat', 'tiket pesawat',
        
        # Ongkir & Paket
        'ongkir', 'kirim barang', 'paket', 'jne', 'jnt', 'pos', 'sicepat',
        'tiki', 'wahana', 'ninja express',
        
        # Ride Hailing
        'gocar', 'grabcar', 'grabbike', 'maxim', 'in driver', 'ojek online',
        'ojek pangkalan', 'taksi online',
        
        # Angkutan Umum
        'kereta commuter', 'kci', 'lrt', 'mrt jakarta', 'mikrolet', 'metromini',
        'kopaja',
        
        # BBM & Kendaraan
        'pertamax turbo', 'shell', 'vivo', 'cuci motor', 'cuci mobil',
        'ganti ban', 'servis kendaraan',
        
        # Jasa Kirim & Travel
        'jasa kirim', 'jasa antar', 'shuttle', 'tiket kereta', 'tiket bus',
        'tiket kapal',
        
        # Lainnya
        'transport', 'jalan', 'perjalanan', 'travel'
    ],

    # ========== 6. 🛒 BELANJA ==========
    'belanja': [
        # Pakaian
        'baju', 'celana', 'sepatu', 'sandal', 'tas', 'dompet', 'jaket',
        'kaos', 'kemeja', 'rok', 'dress', 'pakaian', 'fashion',
        'aksesoris', 'jam tangan', 'perhiasan', 'cincin', 'kalung',
        
        # Elektronik
        'elektronik', 'hp', 'laptop', 'tablet', 'charger', 'kabel',
        'powerbank', 'kipas', 'tv', 'ac', 'kulkas', 'dispenser',
        'mesin cuci', 'kompor', 'rice cooker', 'blender', 'mixer',
        
        # Peralatan Rumah
        'peralatan rumah', 'meja', 'kursi', 'lemari', 'lampu', 'karpet',
        'gorden', 'vas bunga', 'furniture', 'dekorasi', 'hiasan',
        
        # Kebutuhan Dapur
        'peralatan dapur', 'panci', 'wajan', 'piring', 'gelas',
        'sendok', 'garpu', 'pisau', 'baskom', 'saringan',
        
        # Kebersihan
        'sabun', 'shampoo', 'pasta gigi', 'sikat gigi', 'detergen',
        'pelembut', 'pembersih lantai', 'kantong plastik', 'sampah',
        'tissue', 'tisu', 'pembersih',
        
        # Mainan & Hadiah
        'mainan', 'hadiah', 'kado', 'parcel', 'boneka',
        
        # Top Up & E-Wallet
        'topup', 'saldo', 'ewallet', 'gopay', 'ovo', 'shopeepay', 'spay',
        
        # E-commerce & Online
        'shopee', 'tokopedia', 'lazada', 'blibli', 'bukalapak', 'tiktok shop',
        'e-commerce', 'belanja online', 'checkout', 'marketplace',
        
        # Fashion & Pakaian
        'hoodie', 'sweater', 'kaos kaki', 'celana jeans', 'sneakers', 'gamis',
        'hijab', 'cardigan',
        
        # Skincare & Kosmetik
        'makeup', 'skincare', 'sunscreen', 'kosmetik', 'serum', 'masker wajah',
        'moisturizer', 'toner', 'foundation', 'lipstik',
        
        # Rumah & Perabot
        'perkakas', 'alat rumah', 'perabot', 'hiasan dinding', 'tanaman hias',
        'pot', 'rak', 'lemari',
        
        # Lainnya
        'belanja', 'beli', 'barang', 'keperluan'
    ],

    # ========== 7. 📄 TAGIHAN ==========
    'tagihan': [
        # Listrik & Air
        'listrik', 'pdam', 'air', 'tagihan air', 'token listrik',
        
        # Internet & WiFi
        'internet', 'wifi', 'indihome', 'firstmedia', 'myrepublic',
        'netflix', 'spotify', 'langganan', 'subscription', 'premium',
        
        # Pulsa & Kuota
        'pulsa', 'kuota', 'paket data', 'telepon', 'telp',
        
        # Kartu Kredit & Cicilan
        'kartu kredit', 'cc', 'tagihan kartu kredit', 'cicilan',
        'kpr', 'kendaraan', 'motor', 'mobil',
        
        # BPJS & Asuransi
        'bpjs', 'asuransi', 'insurance', 'jamsostek',
        
        # Sekolah & Kuliah
        'sekolah', 'spp', 'uang kuliah', 'ukt', 'pendaftaran',
        
        # Listrik & Utilitas
        'pln', 'token pln', 'samsat', 'pajak', 'pbb',
        
        # Paylater & Pinjaman
        'shopee paylater', 'spaylater', 'gopaylater', 'akulaku', 'kredivo',
        'pinjol', 'pinjaman online',
        
        # Streaming & Langganan
        'youtube premium', 'yt premium', 'disney+', 'vidio', 'iflix',
        'berlangganan',
        
        # Lainnya
        'tagihan', 'bayar', 'administrasi', 'biaya admin', 'materai'
    ],

    # ========== 8. 🎮 HIBURAN ==========
    'hiburan': [
        # Nonton
        'nonton', 'film', 'bioskop', 'theater', 'sinema', 'netflix',
        'disney', 'prime video', 'hbo',
        
        # Game
        'game', 'steam', 'playstation', 'xbox', 'nintendo', 'ps',
        'mobile legend', 'free fire', 'pubg', 'valorant',
        
        # Musik
        'spotify', 'youtube premium', 'konser', 'festival', 'music',
        'langganan musik',
        
        # Wisata & Liburan
        'wisata', 'liburan', 'traveling', 'tour', 'jalan-jalan',
        'tiket wisata', 'tiket masuk', 'taman', 'pantai', 'gunung',
        
        # Olahraga
        'olahraga', 'fitness', 'gym', 'futsal', 'bulu tangkis',
        'renang', 'sepak bola', 'badminton',
        
        # Salon & Spa
        'pijat', 'spa', 'salon', 'potong rambut', 'haircut',
        'manicure', 'pedicure', 'facial',
        
        # Game & In-game
        'diamond', 'v-bucks', 'roblox', 'genshin', 'mobile legends',
        'mlbb', 'free fire', 'pubg mobile', 'ps5', 'nintendo switch',
        'game online',
        
        # Nonton & Event
        'xxi', 'cgv', 'konser', 'festival musik', 'screening', 'nonton bareng',
        
        # Wisata & Rekreasi
        'dufan', 'trans studio', 'kebun binatang', 'zoo', 'theme park',
        'waterpark', 'camping', 'glamping',
        
        # Lainnya
        'nongkrong', 'cafe', 'kopi darat', 'kencan', 'date',
        'hiburan', 'fun', 'refreshing'
    ],

    # ========== 9. 💊 KESEHATAN ==========
    'kesehatan': [
        # Obat-obatan
        'obat', 'apotek', 'farmasi', 'kimia farma', 'guardian',
        'obat batuk', 'obat flu', 'paracetamol', 'bodrex', 'promag',
        'antangin', 'tolak angin', 'vitamin c', 'vitamin d', 'zinc',
        
        # Dokter & Klinik
        'dokter', 'klinik', 'rumah sakit', 'rs', 'puskesmas',
        'periksa', 'konsultasi', 'cek darah', 'laboratorium', 'usg',
        'rawat inap', 'rawat jalan', 'operasi',
        
        # Vitamin & Suplemen
        'vitamin', 'supplement', 'suplemen', 'fit', 'echinacea',
        
        # Kacamata
        'kaca mata', 'lensa kontak', 'kacamata',
        
        # Psikolog
        'psikolog', 'terapi', 'konseling',
        
        # COVID
        'masker', 'handsanitizer', 'rapid test', 'antigen', 'swab',
        'pcr', 'vaksin', 'booster', 'imunisasi',
        
        # Obat & Vitamin
        'obat demam', 'obat maag', 'obat pusing', 'obat masuk angin',
        'vitamin c', 'vitamin d', 'zinc',
        
        # Layanan Kesehatan
        'cek kesehatan', 'medical check up', 'mcu', 'fisioterapi', 'terapi',
        'konsultasi dokter', 'telemedicine', 'halodoc', 'alodokter',
        
        # Lainnya
        'kesehatan', 'sehat', 'obat-obatan'
    ],

    # ========== 10. 📚 PENDIDIKAN ==========
    'pendidikan': [
        # Buku
        'buku', 'novel', 'komik', 'majalah', 'ensiklopedia',
        
        # Kursus & Les
        'kursus', 'les', 'pelatihan', 'workshop', 'kelas online',
        'seminar', 'webinar', 'bootcamp', 'training',
        
        # Skripsi & Tugas
        'skripsi', 'tugas', 'makalah', 'jurnal', 'penelitian',
        'fotokopi', 'print', 'scanning', 'jilid', 'laminating',
        
        # Alat Tulis
        'alat tulis', 'pensil', 'pulpen', 'kertas', 'binder', 'map',
        'buku tulis', 'spidol', 'penghapus',
        
        # Biaya Sekolah
        'uang kuliah', 'ukt', 'spp', 'pendaftaran', 'ospek',
        
        # Bimbel & Kursus
        'bimbel', 'tutor', 'les privat', 'kursus online', 'kelas online',
        'kelas bahasa', 'kursus bahasa', 'bootcamp',
        
        # Sekolah & Perlengkapan
        'seragam', 'sepatu sekolah', 'uang saku', 'iuran sekolah', 'uang kas',
        'ekstrakurikuler', 'pramuka', 'try out', 'ujian', 'utbk',
        
        # Buku & Alat Tulis
        'materi', 'modul', 'binder', 'map', 'pulpen', 'pensil', 'spidol',
        'penghapus',
        
        # Lainnya
        'pendidikan', 'belajar', 'les', 'sekolah'
    ],

    # ========== 11. 💰 PEMASUKAN (INCOME) ==========
    'income': [
        # Gaji
        'gaji', 'salary', 'gajian', 'pensiun', 'tunjangan',
        
        # Bonus & THR
        'bonus', 'thr', 'bonus tahunan', 'insentif',
        
        # Freelance & Proyek
        'freelance', 'proyek', 'project', 'kerja sampingan',
        
        # Investasi
        'dividen', 'dividend', 'deviden', 'bunga', 'interest',
        
        # Sewa
        'sewa', 'rent', 'kontrakan', 'rumah kontrakan',
        
        # Hadiah
        'hadiah', 'gift', 'reward', 'doorprize',
        
        # Komisi
        'komisi', 'commission', 'fee', 'jasa',
        
        # Endorsement
        'royalti', 'affiliate', 'sponsor', 'endorsement',
        
        # Usaha & Dagang
        'jualan', 'dagang', 'omzet', 'penjualan', 'hasil jualan', 'cuan',
        
        # Online & Lainnya
        'cashback', 'refund', 'pengembalian', 'reimburse', 'angpao',
        'transfer masuk', 'menang undian',
        
        # Lainnya
        'pendapatan', 'penghasilan', 'income', 'pemasukan',
        'upah', 'honor', 'uang masuk'
    ],

    # ========== 12.  LAINNYA ==========
    'lainnya': [
        'lainnya', 'lain', 'dll', 'dsb', 'lain-lain',
        'tak terduga', 'mendadak', 'dadakan',
        'donasi', 'amal', 'zakat', 'infak', 'sedekah', 'wakaf',
        'qurban', 'kurban', 'denda', 'tilang', 'sumbangan', 'iuran',
        'keperluan lain', 'biaya lain', 'pengeluaran lain'
    ]
}

# ===== ALIAS UNTUK KOMPATIBILITAS =====
CATEGORIES = CATEGORY_KEYWORDS

# ===== STOP WORDS (Kata Kerja yang Dihapus dari Item) =====
STOP_WORDS = [
    'makan', 'beli', 'jajan', 'minum', 'sarapan', 'makan siang', 'makan malam',
    'ngopi', 'ngemil', 'order', 'pesan', 'bayar', 'isi', 'isi ulang',
    'ambil', 'cari', 'dapat', 'kirim', 'transfer', 'bayarin', 'masuk', 'keluar',
    'tambah', 'kurang', 'pakai', 'buat', 'pergi', 'datang', 'pulang'
]

# ===== SEPARATOR UNTUK MULTI-TRANSAKSI =====
SEPARATORS = ['dan', 'lalu', 'kemudian', 'terus', '+', '&', ',', ';']

# ===== CATEGORY DISPLAY NAMES =====
CATEGORY_DISPLAY = {
    'makanan': '🍔 Makanan',
    'jajanan': '🍿 Jajanan',
    'minuman': '🥤 Minuman',
    'rokok': '🚬 Rokok',
    'transport': '🚗 Transport',
    'belanja': '🛒 Belanja',
    'tagihan': '📄 Tagihan',
    'hiburan': '🎮 Hiburan',
    'kesehatan': '💊 Kesehatan',
    'pendidikan': '📚 Pendidikan',
    'income': '💰 Pemasukan',
    'lainnya': '📦 Lainnya'
}

# ===== DEFAULT BUDGET =====
DEFAULT_BUDGET = {
    "makanan": 1500000,
    "jajanan": 500000,
    "minuman": 300000,
    "rokok": 300000,
    "transport": 500000,
    "belanja": 1000000,
    "tagihan": 1500000,
    "hiburan": 500000,
    "kesehatan": 300000,
    "pendidikan": 500000,
    "lainnya": 500000
}

DEFAULT_INCOME_TARGET = 5000000
