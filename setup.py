"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                       E'LON BOT - DASTLABKI SOZLASH SKRIPTI                   ║
║                                                                               ║
║   Bu skript bir marta ishga tushiriladi va quyidagilarni bajaradi:            ║
║   1. Barcha kerakli papkalarni yaratish                                       ║
║   2. .env faylini yaratish va barcha kalitlarni generatsiya qilish           ║
║   3. SQLite database va barcha jadvallarni yaratish                           ║
║   4. Kerakli Python paketlarini tekshirish                                    ║
║   5. Har bir amal haqida batafsil ma'lumot chiqarish                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import sqlite3
import secrets
import subprocess
import importlib
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Any

# ==================== KONSOLE UCHUN RANGLAR ====================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# ==================== XATOLIKLARNI USHLASH KLASSI ====================
class SetupError(Exception):
    """Sozlash vaqtidagi xatoliklar uchun"""
    pass

# ==================== PRINT FUNKSIYALARI ====================
def print_header():
    print(f"\n{Colors.CYAN}{'╔' + '═'*78 + '╗'}{Colors.ENDC}")
    print(f"{Colors.CYAN}║{Colors.ENDC}{Colors.BOLD}{' ' * 20}🚀 E'LON BOT - DASTLABKI SOZLASH SKRIPTI{' ' * 28}{Colors.ENDC}{Colors.CYAN}║{Colors.ENDC}")
    print(f"{Colors.CYAN}╚{'═'*78}╝{Colors.ENDC}")

def print_step(step_num: int, total: int, title: str, status: str = "start"):
    """Qadamni chiroyli ko'rsatish"""
    print(f"\n{Colors.BLUE}{'═'*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}📌 QADAM {step_num}/{total}: {title}{Colors.ENDC}")
    print(f"{Colors.BLUE}{'═'*80}{Colors.ENDC}")
    if status == "start":
        print(f"{Colors.CYAN}⏳ Jarayon boshlandi...{Colors.ENDC}")
    elif status == "success":
        print(f"{Colors.GREEN}✅ Jarayon muvaffaqiyatli yakunlandi!{Colors.ENDC}")
    elif status == "error":
        print(f"{Colors.FAIL}❌ Jarayonda xatolik yuz berdi!{Colors.ENDC}")

def print_info(msg: str):
    print(f"   {Colors.CYAN}ℹ️{Colors.ENDC} {msg}")

def print_success(msg: str):
    print(f"   {Colors.GREEN}✅{Colors.ENDC} {msg}")

def print_error(msg: str):
    print(f"   {Colors.FAIL}❌{Colors.ENDC} {msg}")

def print_warning(msg: str):
    print(f"   {Colors.WARNING}⚠️{Colors.ENDC} {msg}")

def print_debug(msg: str):
    print(f"   {Colors.CYAN}🔍{Colors.ENDC} {msg}")

def print_result(msg: str, success: bool = True):
    if success:
        print(f"   {Colors.GREEN}✓{Colors.ENDC} {msg}")
    else:
        print(f"   {Colors.FAIL}✗{Colors.ENDC} {msg}")

# ==================== 1. BOSHLANG'ICH TEKSHIRUV ====================
print_header()
print(f"\n{Colors.BOLD}📅 Vaqt:{Colors.ENDC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{Colors.BOLD}📂 Ishchi papka:{Colors.ENDC} {os.getcwd()}")
print(f"{Colors.BOLD}🐍 Python versiyasi:{Colors.ENDC} {sys.version}")
print(f"{Colors.BOLD}💻 Operatsion tizim:{Colors.ENDC} {sys.platform}")

# ==================== 2. PAPKALARNI YARATISH ====================
print_step(1, 6, "PAPKALARNI YARATISH", "start")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
    print_info(f"Ishchi papkaga o'tildi: {BASE_DIR}")
except Exception as e:
    print_error(f"Papkaga o'tish xatosi: {e}")
    sys.exit(1)

# Papkalar ro'yxati: (papka_nomi, to'liq_yol, tavsif)
directories: List[Tuple[str, str, str]] = [
    ("data", os.path.join(BASE_DIR, "data"), "Asosiy ma'lumotlar papkasi"),
    ("data/checks", os.path.join(BASE_DIR, "data", "checks"), "To'lov cheklari saqlanadigan papka"),
    ("data/media", os.path.join(BASE_DIR, "data", "media"), "Rasm va videolar saqlanadigan papka"),
    ("logs", os.path.join(BASE_DIR, "logs"), "Log fayllari saqlanadigan papka"),
]

created_count = 0
existing_count = 0
failed_count = 0

for dir_name, full_path, description in directories:
    try:
        print_info(f"Yaratilmoqda: {dir_name} ({description})")
        print_debug(f"   Manzil: {full_path}")
        
        if os.path.exists(full_path):
            print_debug(f"   Papka allaqachon mavjud")
            existing_count += 1
        else:
            Path(full_path).mkdir(parents=True, exist_ok=True)
            print_success(f"   Papka yaratildi")
            created_count += 1
        
        # Ruxsatlarni tekshirish
        if os.access(full_path, os.W_OK):
            print_debug(f"   Yozish ruxsati: ✅ mavjud")
        else:
            print_warning(f"   Yozish ruxsati: ❌ yo'q!")
            failed_count += 1
            
    except PermissionError as e:
        print_error(f"   Ruxsat xatosi: {e}")
        failed_count += 1
    except Exception as e:
        print_error(f"   Kutilmagan xato: {e}")
        failed_count += 1

print_success(f"Papkalar: {created_count} ta yangi yaratildi, {existing_count} ta mavjud edi")
if failed_count > 0:
    print_warning(f"{failed_count} ta papkada muammo bor")

# ==================== 3. .ENV FAYLINI YARATISH ====================
print_step(2, 6, ".ENV FAYLINI YARATISH", "start")

env_path = Path(".env")
env_vars_created = []
env_vars_existing = []

try:
    if env_path.exists():
        print_info(".env fayli mavjud")
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = len(content.split('\n'))
        print_debug(f"   Fayl hajmi: {len(content)} bayt, {lines} qator")
    else:
        print_info(".env fayli mavjud emas, yangisi yaratiladi")
        env_path.touch()
        print_success("   Bo'sh .env fayli yaratildi")
    
    # Kerakli kalitlarni o'qish va generatsiya qilish
    from dotenv import load_dotenv, set_key
    load_dotenv()
    
    # API_KEY
    api_key = os.getenv("API_KEY")
    if not api_key or api_key == "":
        api_key = secrets.token_urlsafe(32)
        set_key(".env", "API_KEY", api_key)
        env_vars_created.append("API_KEY")
        print_success(f"   API_KEY yaratildi: {api_key[:20]}...")
    else:
        env_vars_existing.append("API_KEY")
        print_info(f"   API_KEY mavjud: {api_key[:20]}...")
    
    # ENCRYPTION_KEY
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key or encryption_key == "":
        try:
            from cryptography.fernet import Fernet
            encryption_key = Fernet.generate_key().decode()
            set_key(".env", "ENCRYPTION_KEY", encryption_key)
            env_vars_created.append("ENCRYPTION_KEY")
            print_success("   ENCRYPTION_KEY yaratildi")
        except ImportError:
            print_warning("   cryptography o'rnatilmagan, ENCRYPTION_KEY keyinroq yaratiladi")
    else:
        env_vars_existing.append("ENCRYPTION_KEY")
        print_info("   ENCRYPTION_KEY mavjud")
    
    # JWT_SECRET_KEY
    jwt_key = os.getenv("JWT_SECRET_KEY")
    if not jwt_key or jwt_key == "":
        jwt_key = secrets.token_urlsafe(32)
        set_key(".env", "JWT_SECRET_KEY", jwt_key)
        env_vars_created.append("JWT_SECRET_KEY")
        print_success("   JWT_SECRET_KEY yaratildi")
    else:
        env_vars_existing.append("JWT_SECRET_KEY")
        print_info("   JWT_SECRET_KEY mavjud")
    
    # BOT_TOKEN
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or bot_token == "":
        print_warning("   BOT_TOKEN mavjud emas!")
        print_warning("   Iltimos, .env fayliga qo'shing: BOT_TOKEN=8242261337:AAFVRroU8AM1uxGAvN7CIf0sipUYxDLtcA8")
    else:
        print_success(f"   BOT_TOKEN mavjud: {bot_token[:15]}...")
        env_vars_existing.append("BOT_TOKEN")
    
    # ADMIN_IDS
    admin_ids = os.getenv("ADMIN_IDS")
    if not admin_ids or admin_ids == "":
        print_warning("   ADMIN_IDS mavjud emas!")
        print_warning("   Iltimos, .env fayliga qo'shing: ADMIN_IDS=8225569789")
    else:
        print_success(f"   ADMIN_IDS mavjud: {admin_ids}")
        env_vars_existing.append("ADMIN_IDS")
    
    # WEBAPP_URL
    webapp_url = os.getenv("WEBAPP_URL")
    if not webapp_url or webapp_url == "":
        print_warning("   WEBAPP_URL mavjud emas!")
        print_warning("   Iltimos, ngrok ishga tushgandan keyin qo'shing")
    else:
        print_success(f"   WEBAPP_URL mavjud: {webapp_url[:50]}...")
        env_vars_existing.append("WEBAPP_URL")
    
    # API_URL
    api_url = os.getenv("API_URL")
    if not api_url or api_url == "":
        print_warning("   API_URL mavjud emas!")
    else:
        print_success(f"   API_URL mavjud: {api_url[:50]}...")
        env_vars_existing.append("API_URL")
    
    # CORS_ALLOWED_ORIGINS
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if not cors_origins or cors_origins == "":
        print_warning("   CORS_ALLOWED_ORIGINS mavjud emas!")
    else:
        print_success(f"   CORS_ALLOWED_ORIGINS mavjud")
        env_vars_existing.append("CORS_ALLOWED_ORIGINS")
    
    # PORT
    port = os.getenv("PORT")
    if not port or port == "":
        set_key(".env", "PORT", "5000")
        env_vars_created.append("PORT")
        print_success("   PORT=5000 qo'shildi")
    else:
        env_vars_existing.append("PORT")
        print_info(f"   PORT={port}")
    
    # DB_PATH
    db_path = os.getenv("DB_PATH")
    if not db_path or db_path == "":
        set_key(".env", "DB_PATH", "data/elon_bot.db")
        env_vars_created.append("DB_PATH")
        print_success("   DB_PATH=data/elon_bot.db qo'shildi")
    else:
        env_vars_existing.append("DB_PATH")
        print_info(f"   DB_PATH={db_path}")
    
    # RATE_LIMIT
    rate_limit = os.getenv("RATE_LIMIT")
    if not rate_limit or rate_limit == "":
        set_key(".env", "RATE_LIMIT", "100")
        env_vars_created.append("RATE_LIMIT")
        print_success("   RATE_LIMIT=100 qo'shildi")
    else:
        env_vars_existing.append("RATE_LIMIT")
        print_info(f"   RATE_LIMIT={rate_limit}")
    
    # LOG_LEVEL
    log_level = os.getenv("LOG_LEVEL")
    if not log_level or log_level == "":
        set_key(".env", "LOG_LEVEL", "INFO")
        env_vars_created.append("LOG_LEVEL")
        print_success("   LOG_LEVEL=INFO qo'shildi")
    else:
        env_vars_existing.append("LOG_LEVEL")
        print_info(f"   LOG_LEVEL={log_level}")
    
    print_result(f"{len(env_vars_created)} ta yangi kalit yaratildi", True)
    print_result(f"{len(env_vars_existing)} ta mavjud kalit", True)
    
except Exception as e:
    print_error(f".env fayli bilan ishlashda xato: {e}")
    import traceback
    print_debug(traceback.format_exc())
    raise SetupError(".env fayli yaratilmadi")

# ==================== 4. DATABASE YARATISH ====================
print_step(3, 6, "DATABASE YARATISH", "start")

# Environmentni qayta yuklash
load_dotenv(override=True)
DB_PATH = os.getenv("DB_PATH", "data/elon_bot.db")
db_full_path = os.path.join(BASE_DIR, DB_PATH)

print_info(f"Database manzili: {db_full_path}")

# Papka mavjudligini tekshirish
db_dir = os.path.dirname(db_full_path)
if not os.path.exists(db_dir):
    print_error(f"Papka mavjud emas: {db_dir}")
    print_info("Papka yaratilmoqda...")
    try:
        Path(db_dir).mkdir(parents=True, exist_ok=True)
        print_success(f"Papka yaratildi: {db_dir}")
    except Exception as e:
        print_error(f"Papka yaratilmadi: {e}")
        sys.exit(1)

try:
    # Database ga ulanish
    print_info("SQLite database ga ulanish...")
    conn = sqlite3.connect(db_full_path)
    cursor = conn.cursor()
    print_success("Database ga ulandi")
    
    # Jadvallar ro'yxati va SQL so'rovlari
    tables = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "channels": """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE NOT NULL,
                channel_name TEXT NOT NULL,
                channel_username TEXT,
                description TEXT,
                is_group INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "channel_admins": """
            CREATE TABLE IF NOT EXISTS channel_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                admin_telegram_id INTEGER UNIQUE NOT NULL,
                admin_username TEXT,
                admin_name TEXT,
                card_number TEXT,
                card_holder TEXT,
                phone_price REAL DEFAULT 10000,
                car_price REAL DEFAULT 20000,
                property_price REAL DEFAULT 30000,
                mixed_price REAL DEFAULT 15000,
                commission_percent REAL DEFAULT 95.0,
                owner_percent REAL DEFAULT 5.0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        """,
        "ads": """
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER,
                category TEXT NOT NULL,
                title TEXT,
                description TEXT,
                price REAL NOT NULL,
                location TEXT,
                latitude REAL,
                longitude REAL,
                tel1 TEXT,
                tel2 TEXT,
                telegram_username TEXT,
                phone_model TEXT,
                phone_condition TEXT,
                phone_color TEXT,
                phone_box TEXT,
                phone_exchange INTEGER DEFAULT 0,
                exchange_phone_model TEXT,
                car_model TEXT,
                car_year INTEGER,
                car_mileage TEXT,
                car_fuel_types TEXT,
                car_amenities TEXT,
                property_type TEXT,
                property_custom_type TEXT,
                property_area TEXT,
                property_yard_area TEXT,
                property_transaction TEXT,
                property_amenities TEXT,
                mixed_features TEXT,
                media_count INTEGER DEFAULT 0,
                media_files TEXT,
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending',
                payment_amount REAL,
                check_image TEXT,
                channel_admin_id INTEGER,
                commission_percent REAL DEFAULT 95.0,
                owner_percent REAL DEFAULT 5.0,
                admin_verified INTEGER DEFAULT 0,
                admin_message TEXT,
                expires_at TEXT,
                published_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (channel_id) REFERENCES channels (id),
                FOREIGN KEY (channel_admin_id) REFERENCES channel_admins (id)
            )
        """,
        "payments": """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER NOT NULL,
                channel_admin_id INTEGER,
                amount REAL NOT NULL,
                card_number TEXT,
                card_holder TEXT,
                check_image TEXT,
                status TEXT DEFAULT 'pending',
                verified_by INTEGER,
                verified_at TEXT,
                admin_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ad_id) REFERENCES ads (id),
                FOREIGN KEY (channel_admin_id) REFERENCES channel_admins (id)
            )
        """,
        "admin_verifications": """
            CREATE TABLE IF NOT EXISTS admin_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ad_id) REFERENCES ads (id),
                FOREIGN KEY (admin_id) REFERENCES channel_admins (id)
            )
        """
    }
    
    # Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_ads_user_id ON ads(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_ads_channel_id ON ads(channel_id)",
        "CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status)",
        "CREATE INDEX IF NOT EXISTS idx_ads_payment_status ON ads(payment_status)",
        "CREATE INDEX IF NOT EXISTS idx_payments_ad_id ON payments(ad_id)",
        "CREATE INDEX IF NOT EXISTS idx_channel_admins_telegram_id ON channel_admins(admin_telegram_id)",
        "CREATE INDEX IF NOT EXISTS idx_channel_admins_channel_id ON channel_admins(channel_id)",
    ]
    
    created_tables = []
    
    # Jadvallarni yaratish
    for table_name, sql in tables.items():
        try:
            print_info(f"Yaratilmoqda: {table_name}")
            cursor.execute(sql)
            
            # Jadval mavjudligini tekshirish
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone():
                print_success(f"   {table_name} jadvali tayyor")
                created_tables.append(table_name)
            else:
                print_warning(f"   {table_name} jadvali yaratilmadi")
                
        except sqlite3.Error as e:
            print_error(f"   {table_name} jadvali xatosi: {e}")
    
    # Indexes yaratish
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            print_debug(f"Index yaratildi: {idx_sql.split('ON')[1].strip() if 'ON' in idx_sql else idx_sql[:30]}")
        except sqlite3.Error as e:
            print_warning(f"Index yaratilmadi: {e}")
    
    conn.commit()
    
    # Jadvallarni tekshirish
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [row[0] for row in cursor.fetchall()]
    print_info(f"Jami jadvallar: {len(all_tables)} ta")
    for tbl in all_tables:
        # Har bir jadvaldagi qatorlar sonini tekshirish
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
            count = cursor.fetchone()[0]
            print_debug(f"   - {tbl}: {count} ta qator")
        except:
            print_debug(f"   - {tbl}")
    
    conn.close()
    print_success(f"Database muvaffaqiyatli tayyor! {len(created_tables)} ta jadval")
    
except sqlite3.Error as e:
    print_error(f"SQLite xatosi: {e}")
    import traceback
    print_debug(traceback.format_exc())
    raise SetupError(f"Database yaratilmadi: {e}")
except Exception as e:
    print_error(f"Kutilmagan xato: {e}")
    import traceback
    print_debug(traceback.format_exc())
    raise SetupError(f"Database yaratilmadi: {e}")

# ==================== 5. KERAKLI PAKETLARNI TEKSHIRISH ====================
print_step(4, 6, "PAKETLARNI TEKSHIRISH", "start")

required_packages = {
    "flask": "Flask",
    "flask_cors": "Flask-CORS",
    "flask_limiter": "Flask-Limiter",
    "flask_sqlalchemy": "Flask-SQLAlchemy",
    "flask_jwt_extended": "Flask-JWT-Extended",
    "cryptography": "cryptography",
    "python_dotenv": "python-dotenv",
    "aiogram": "aiogram",
    "aiohttp": "aiohttp",
    "apscheduler": "APScheduler",
    "werkzeug": "Werkzeug"
}

missing_packages = []
installed_packages = []
version_info = []

for module_name, package_name in required_packages.items():
    try:
        module = importlib.import_module(module_name)
        # Versiyani olishga urinish
        try:
            version = module.__version__
            version_info.append(f"{package_name}=={version}")
        except:
            version_info.append(package_name)
        installed_packages.append(package_name)
        print_success(f"{package_name} o'rnatilgan")
    except ImportError:
        print_error(f"{package_name} o'rnatilmagan!")
        missing_packages.append(package_name)

print_info(f"O'rnatilgan paketlar: {len(installed_packages)}/{len(required_packages)}")

if missing_packages:
    print_warning(f"{len(missing_packages)} ta paket o'rnatilmagan:")
    for pkg in missing_packages:
        print_warning(f"   - {pkg}")
    print_info("Quyidagi buyruq bilan o'rnating:")
    print(f"   pip install {' '.join(missing_packages)}")
    
    # O'rnatishni taklif qilish
    response = input(f"\n{Colors.WARNING}⚡ O'rnatilmagan paketlarni hozir o'rnatmoqchimisiz? (y/n): {Colors.ENDC}")
    if response.lower() == 'y':
        print_info("Paketlar o'rnatilmoqda...")
        for pkg in missing_packages:
            print_debug(f"   O'rnatilmoqda: {pkg}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                print_success(f"   {pkg} o'rnatildi")
            except Exception as e:
                print_error(f"   {pkg} o'rnatilmadi: {e}")
    else:
        print_warning("Paketlar keyinroq o'rnatiladi")
else:
    print_success("Barcha kerakli paketlar o'rnatilgan")
    print_debug(f"Paket versiyalari: {', '.join(version_info[:5])}...")

# ==================== 6. NGROK TEKSHIRISH ====================
print_step(5, 6, "NGROK TEKSHIRISH", "start")

try:
    # Ngrok o'rnatilganligini tekshirish
    result = subprocess.run(["ngrok", "--version"], capture_output=True, text=True, shell=True)
    if result.returncode == 0:
        ngrok_version = result.stdout.strip()
        print_success(f"Ngrok o'rnatilgan: {ngrok_version}")
        
        # Ngrok ishlayotganligini tekshirish
        import urllib.request
        try:
            response = urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=3)
            import json
            tunnels = json.loads(response.read().decode())
            if tunnels.get('tunnels'):
                print_success("Ngrok ishlayapti!")
                for tunnel in tunnels['tunnels']:
                    if tunnel.get('public_url'):
                        public_url = tunnel['public_url']
                        print_info(f"   Public URL: {public_url}")
                        
                        # .env faylini yangilashni taklif qilish
                        current_webapp = os.getenv("WEBAPP_URL")
                        if not current_webapp or current_webapp != public_url:
                            print_warning(f"WEBAPP_URL yangilanishi kerak: {public_url}")
                            response = input(f"   WEBAPP_URL ni {public_url} ga yangilaysizmi? (y/n): ")
                            if response.lower() == 'y':
                                from dotenv import set_key
                                set_key(".env", "WEBAPP_URL", public_url)
                                set_key(".env", "API_URL", f"{public_url}/api")
                                set_key(".env", "BASE_URL", public_url)
                                
                                # CORS originlariga qo'shish
                                current_cors = os.getenv("CORS_ALLOWED_ORIGINS", "")
                                if public_url not in current_cors:
                                    new_cors = f"{current_cors},{public_url}" if current_cors else public_url
                                    set_key(".env", "CORS_ALLOWED_ORIGINS", new_cors)
                                
                                print_success("   .env fayli yangilandi!")
                                print_warning("   Iltimos, API server va botni qayta ishga tushiring!")
            else:
                print_warning("Ngrok ishlayapti lekin tunnel topilmadi")
        except Exception as e:
            print_warning(f"Ngrok API ga ulanish xatosi: {e}")
            print_info("Ngrok ishga tushirilmagan bo'lishi mumkin")
    else:
        print_error("Ngrok o'rnatilmagan!")
        print_info("Ngrok ni yuklab oling: https://ngrok.com/download")
        print_info("Yoki quyidagi buyruq bilan o'rnating: winget install ngrok")
except FileNotFoundError:
    print_error("Ngrok topilmadi!")
    print_info("Ngrok ni yuklab oling: https://ngrok.com/download")
except Exception as e:
    print_error(f"Ngrok tekshirish xatosi: {e}")

# ==================== 7. XULOSA ====================
print_step(6, 6, "XULOSA", "start")

print(f"\n{Colors.BOLD}{'═'*80}{Colors.ENDC}")
print(f"{Colors.BOLD}{' ' * 30}SOZLASH NATIJALARI{Colors.ENDC}")
print(f"{Colors.BOLD}{'═'*80}{Colors.ENDC}")

print(f"\n{Colors.GREEN}✅ MUVAFFAQIYATLI BAJARILGANLAR:{Colors.ENDC}")
print(f"   📁 Papkalar: {created_count} ta yangi, {existing_count} ta mavjud")
print(f"   🔑 .env kalitlari: {len(env_vars_created)} ta yangi, {len(env_vars_existing)} ta mavjud")
print(f"   🗄️ Database jadvallari: {len(created_tables)} ta")
print(f"   📦 Python paketlari: {len(installed_packages)}/{len(required_packages)} ta")

if missing_packages:
    print(f"\n{Colors.WARNING}⚠️ O'RNATILMAGAN PAKETLAR:{Colors.ENDC}")
    for pkg in missing_packages:
        print(f"   ❌ {pkg}")

if not os.getenv("WEBAPP_URL"):
    print(f"\n{Colors.WARNING}⚠️ WEBAPP_URL belgilanmagan!{Colors.ENDC}")
    print("   Ngrok ishga tushgandan keyin quyidagini .env fayliga qo'shing:")
    print("   WEBAPP_URL=https://your-ngrok-url.ngrok-free.dev")
    print("   API_URL=https://your-ngrok-url.ngrok-free.dev/api")

if not os.getenv("BOT_TOKEN"):
    print(f"\n{Colors.WARNING}⚠️ BOT_TOKEN belgilanmagan!{Colors.ENDC}")
    print("   .env fayliga qo'shing: BOT_TOKEN=8242261337:AAFVRroU8AM1uxGAvN7CIf0sipUYxDLtcA8")

if not os.getenv("ADMIN_IDS"):
    print(f"\n{Colors.WARNING}⚠️ ADMIN_IDS belgilanmagan!{Colors.ENDC}")
    print("   .env fayliga qo'shing: ADMIN_IDS=8225569789")

print(f"\n{Colors.BOLD}{'═'*80}{Colors.ENDC}")
print(f"{Colors.GREEN}🚀 SOZLASH TUGADI!{Colors.ENDC}")
print(f"{Colors.BOLD}{'═'*80}{Colors.ENDC}")

print(f"\n{Colors.CYAN}⏳ KEYINGI QADAMLAR:{Colors.ENDC}")
print("   1. Ngrok ni ishga tushiring:   ngrok http 5000")
print("   2. .env faylidagi WEBAPP_URL va API_URL ni yangilang")
print("   3. API serverni ishga tushiring:   python api.py")
print("   4. Botni ishga tushiring:          python bot.py")
print("   5. Telegramda @OsiyoMarketBot ni oching")

print(f"\n{Colors.BOLD}{'═'*80}{Colors.ENDC}")

if missing_packages:
    print(f"\n{Colors.WARNING}⚠️ DIQQAT! O'rnatilmagan paketlar bor!{Colors.ENDC}")
    print("   Iltimos, yuqoridagi buyruq bilan ularni o'rnating.")
    sys.exit(1)
else:
    print(f"\n{Colors.GREEN}✅ HAMMA TAYYOR! API va botni ishga tushirishingiz mumkin.{Colors.ENDC}")

input(f"\n{Colors.CYAN}📌 Davom etish uchun Enter ni bosing...{Colors.ENDC}")