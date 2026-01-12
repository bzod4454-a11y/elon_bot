import os
import json
import logging
import asyncio
import sqlite3
import aiofiles
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Environment variables
load_dotenv()

# Konfiguratsiya
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://sizning-domeningiz.com")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "123456789").split(",")))  # Sizning ID ingiz birinchi
DB_PATH = os.getenv("DB_PATH", "data/elon_bot.db")
CHECKS_DIR = os.getenv("CHECKS_DIR", "data/checks")

# Papkalarni yaratish
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(CHECKS_DIR, exist_ok=True)

# Loggerni sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM holatlari
class AdStates(StatesGroup):
    waiting_for_ad_data = State()
    waiting_for_check = State()

class SuperAdminStates(StatesGroup):
    waiting_for_channel_info = State()
    waiting_for_admin_info = State()
    waiting_for_commission = State()
    waiting_for_channel_prices = State()

class ChannelAdminStates(StatesGroup):
    waiting_for_card_info = State()
    waiting_for_price_update = State()
    waiting_for_message_to_user = State()

# Database connection funksiyasi
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# Database initialization
def init_database():
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # ==================== ESKI JADVALLAR ====================
        # Foydalanuvchilar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Kanallar jadvali
        cursor.execute('''
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
        ''')
        
        # E'lonlar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_id INTEGER,
                category TEXT NOT NULL,
                
                -- Umumiy maydonlar
                title TEXT,
                description TEXT,
                price REAL NOT NULL,
                location TEXT,
                latitude REAL,
                longitude REAL,
                tel1 TEXT,
                tel2 TEXT,
                telegram_username TEXT,
                
                -- Telefon uchun
                phone_model TEXT,
                phone_condition TEXT,
                phone_color TEXT,
                phone_box TEXT,
                phone_exchange INTEGER DEFAULT 0,
                exchange_phone_model TEXT,
                
                -- Mashina uchun
                car_model TEXT,
                car_year INTEGER,
                car_mileage TEXT,
                car_fuel_types TEXT,
                car_amenities TEXT,
                
                -- Ko'chmas mulk uchun
                property_type TEXT,
                property_custom_type TEXT,
                property_area TEXT,
                property_yard_area TEXT,
                property_transaction TEXT,
                property_amenities TEXT,
                
                -- Aralash uchun
                mixed_features TEXT,
                
                -- Media
                media_count INTEGER DEFAULT 0,
                media_files TEXT,
                
                -- Status va to'lov
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending',
                payment_amount REAL,
                check_image TEXT,
                channel_admin_id INTEGER,
                commission_percent REAL DEFAULT 95.0,
                owner_percent REAL DEFAULT 5.0,
                admin_verified INTEGER DEFAULT 0,
                admin_message TEXT,
                
                -- Vaqtlar
                expires_at TEXT,
                published_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (channel_admin_id) REFERENCES channel_admins (id)
            )
        ''')
        
        # To'lovlar jadvali
        cursor.execute('''
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
        ''')
        
        # ==================== YANGI JADVALLAR ====================
        # Kanal adminlari jadvali
        cursor.execute('''
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
        ''')
        
        # Kanal statistikasi jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                ads_count INTEGER DEFAULT 0,
                total_income REAL DEFAULT 0,
                active_ads INTEGER DEFAULT 0,
                pending_ads INTEGER DEFAULT 0,
                deleted_ads INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels (id),
                UNIQUE(channel_id, date)
            )
        ''')
        
        # Admin tekshiruvlari jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL, -- 'approve', 'reject'
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ad_id) REFERENCES ads (id),
                FOREIGN KEY (admin_id) REFERENCES channel_admins (id)
            )
        ''')
        
        # ==================== INDEXLAR ====================
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ads_user_id ON ads(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ads_channel_id ON ads(channel_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_ad_id ON payments(ad_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_admins_telegram_id ON channel_admins(admin_telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_admins_channel_id ON channel_admins(channel_id)')
        
        conn.commit()
        logger.info("✅ Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False
    finally:
        conn.close()

# ==================== YORDAMCHI FUNKSIYALAR ====================

# Foydalanuvchi mavjudligini tekshirish
async def get_or_create_user(telegram_id, username, first_name, last_name=None):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        
        if user:
            user_id = user[0]
        else:
            cursor.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name)
            )
            conn.commit()
            user_id = cursor.lastrowid
        
        return user_id
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        return None
    finally:
        conn.close()

# Foydalanuvchining oxirgi e'lon ma'lumotlari
async def get_last_ad_data(user_id, category):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM ads 
            WHERE user_id = ? AND category = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (user_id, category))
        
        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return {columns[i]: row[i] for i in range(len(columns))}
        return None
    except Exception as e:
        logger.error(f"Error in get_last_ad_data: {e}")
        return None
    finally:
        conn.close()

# Kanal ma'lumotlarini olish
async def get_channels():
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE is_active = 1")
        rows = cursor.fetchall()
        
        channels = []
        for row in rows:
            channels.append(dict(row))
        
        return channels
    except Exception as e:
        logger.error(f"Error in get_channels: {e}")
        return []
    finally:
        conn.close()

# Kanal adminini olish
async def get_channel_admin(telegram_id):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ca.*, c.channel_name, c.channel_username 
            FROM channel_admins ca
            LEFT JOIN channels c ON ca.channel_id = c.id
            WHERE ca.admin_telegram_id = ? AND ca.is_active = 1
        ''', (telegram_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error in get_channel_admin: {e}")
        return None
    finally:
        conn.close()

# Kanal narxlarini olish
async def get_channel_prices(channel_id):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT phone_price, car_price, property_price, mixed_price 
            FROM channel_admins 
            WHERE channel_id = ? AND is_active = 1
        ''', (channel_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Error in get_channel_prices: {e}")
        return None
    finally:
        conn.close()

# Bot a'zo bo'lgan guruhlar/kanallar
async def get_bot_chats():
    # Bu funksiya Telegram API orqali bot a'zo bo'lgan guruhlarni olishi kerak
    # Hozircha test ma'lumotlar qaytaramiz
    return [
        {"id": -1001234567890, "title": "Test Kanal", "username": "@testkanal", "type": "channel"},
        {"id": -1009876543210, "title": "Test Grupp", "username": None, "type": "group"},
    ]

# ==================== ASOSIY HANDLERLAR ====================

# /start komandasi
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if not user_id:
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return
    
    # Katta admin tekshirish
    if message.from_user.id == ADMIN_IDS[0]:
        kb = [
            [InlineKeyboardButton(text="👑 Katta Admin Panel", callback_data="superadmin_panel")],
            [InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={message.from_user.id}"))],
            [InlineKeyboardButton(text="📋 Mening e'lonlarim", callback_data="my_ads")]
        ]
    else:
        # Kanal admini tekshirish
        channel_admin = await get_channel_admin(message.from_user.id)
        if channel_admin:
            kb = [
                [InlineKeyboardButton(text="⚙️ Kanal Boshqaruvi", callback_data="channel_manage")],
                [InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={message.from_user.id}"))],
                [InlineKeyboardButton(text="📋 Mening e'lonlarim", callback_data="my_ads")]
            ]
        else:
            # Oddiy foydalanuvchi
            kb = [[InlineKeyboardButton(
                text="📝 Yangi e'lon",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={message.from_user.id}")
            )]]
    
    await message.answer(
        f"👋 Assalomu alaykum, {message.from_user.first_name}!\n\n"
        f"🚀 *E'LON JOYLASH BOTIGA XUSH KELIBSIZ!*\n\n"
        f"✅ *Avzalliklarimiz:*\n"
        f"• Hech qanday ro'yxatdan o'tish yo'q\n"
        f"• Narx chegaralari yo'q\n"
        f"• 1 ta telefon YOKI Telegram username etarli\n"
        f"• Rasm/Video yuklash mumkin\n\n"
        f"📊 *Mavjud kanallar:* {len(await get_channels())} ta\n"
        f"💼 *E'lon berish uchun quyidagi tugmani bosing:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

# ==================== KATTA ADMIN PANELI ====================

@dp.callback_query(F.data == "superadmin_panel")
async def superadmin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_IDS[0]:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    kb = [
        [InlineKeyboardButton(text="📢 Yangi Kanal ulash", callback_data="super_add_channel")],
        [InlineKeyboardButton(text="👥 Kanal Admini tayinlash", callback_data="super_add_admin")],
        [InlineKeyboardButton(text="📊 Barcha kanallar statistikasi", callback_data="super_all_stats")],
        [InlineKeyboardButton(text="💰 Umumiy daromad", callback_data="super_total_income")],
        [InlineKeyboardButton(text="📋 Adminlar ro'yxati", callback_data="super_admin_list")]
    ]
    
    await callback.message.edit_text(
        "👑 *KATTA ADMIN PANELI*\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# Yangi kanal ulash
@dp.callback_query(F.data == "super_add_channel")
async def super_add_channel_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_IDS[0]:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    # Bot a'zo bo'lgan guruhlarni olish
    chats = await get_bot_chats()
    
    if not chats:
        await callback.message.edit_text(
            "❌ Bot hech qanday guruh yoki kanalga a'zo emas!\n"
            "Avval botni kanalga admin qiling.",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Guruhlar ro'yxatini ko'rsatish
    kb = []
    for chat in chats:
        chat_type = "📢 Kanal" if chat['type'] == 'channel' else "👥 Grupp"
        chat_name = chat['username'] if chat['username'] else chat['title']
        kb.append([InlineKeyboardButton(
            text=f"{chat_type}: {chat_name}",
            callback_data=f"select_chat:{chat['id']}:{chat['type']}"
        )])
    
    kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_super")])
    
    await callback.message.edit_text(
        "📢 *YANGI KANAL ULASH*\n\n"
        "Bot a'zo bo'lgan guruh yoki kanallar:\n"
        "Ulardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# Guruh tanlash
@dp.callback_query(F.data.startswith("select_chat:"))
async def select_chat_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_IDS[0]:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    parts = callback.data.split(":")
    chat_id = parts[1]
    chat_type = parts[2]
    
    await state.update_data(chat_id=chat_id, chat_type=chat_type)
    
    await callback.message.edit_text(
        f"✅ Guruh tanlandi!\n\n"
        f"Endi kanal adminining Telegram ID sini yuboring:\n"
        f"*(Admin @username yoki raqamini yuboring)*",
        parse_mode="Markdown"
    )
    await state.set_state(SuperAdminStates.waiting_for_admin_info)
    await callback.answer()

# Admin ID sini qabul qilish
@dp.message(SuperAdminStates.waiting_for_admin_info)
async def process_admin_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_IDS[0]:
        return
    
    admin_id = None
    admin_username = None
    
    # ID ni aniqlash
    if message.text.isdigit():
        admin_id = int(message.text)
    elif message.text.startswith('@'):
        admin_username = message.text[1:]
        # Username dan ID ni olish uchun test qilamiz
        admin_id = 987654321  # Test uchun
    
    if not admin_id:
        await message.answer("❌ Noto'g'ri format! Telegram ID yoki @username yuboring.")
        return
    
    await state.update_data(admin_id=admin_id, admin_username=admin_username)
    
    await message.answer(
        f"✅ Admin ID qabul qilindi: {admin_id}\n\n"
        f"Endi foizlarni belgilang:\n"
        f"Kanal adminiga foiz (95%):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="95")], [KeyboardButton(text="90")], [KeyboardButton(text="85")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(SuperAdminStates.waiting_for_commission)

# Foizlarni qabul qilish
@dp.message(SuperAdminStates.waiting_for_commission)
async def process_commission(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_IDS[0]:
        return
    
    try:
        admin_percent = float(message.text)
        owner_percent = 100 - admin_percent
        
        if admin_percent < 80 or admin_percent > 95:
            await message.answer("❌ Foiz 80% dan 95% gacha bo'lishi kerak!")
            return
        
        state_data = await state.get_data()
        chat_id = state_data.get('chat_id')
        chat_type = state_data.get('chat_type')
        admin_id = state_data.get('admin_id')
        admin_username = state_data.get('admin_username')
        
        # Kanalni database ga qo'shish
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Kanalni qo'shish
        cursor.execute('''
            INSERT INTO channels (channel_id, channel_name, is_group, is_active)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, f"Kanal {chat_id}", 1 if chat_type == 'group' else 0, 1))
        
        channel_id = cursor.lastrowid
        
        # Adminni tayinlash
        cursor.execute('''
            INSERT INTO channel_admins (channel_id, admin_telegram_id, admin_username, 
                                     commission_percent, owner_percent, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (channel_id, admin_id, admin_username, admin_percent, owner_percent, 1))
        
        conn.commit()
        
        await message.answer(
            f"✅ *Kanal muvaffaqiyatli ulandi!*\n\n"
            f"📢 Kanal ID: {chat_id}\n"
            f"👤 Admin ID: {admin_id}\n"
            f"💰 Foizlar: Admin={admin_percent}%, Siz={owner_percent}%\n\n"
            f"Admin endi /start bosganda 'Kanal Boshqaruvi' tugmasini ko'radi.",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)
        )
        
        # Yangi adminga xabar yuborish
        try:
            await bot.send_message(
                admin_id,
                f"🎉 Tabriklaymiz! Siz kanal admini bo'ldingiz!\n\n"
                f"Botdan /start bosing va 'Kanal Boshqaruvi' tugmasini bosing.\n"
                f"Bu yerda kartangizni va narxlarni sozlashingiz mumkin."
            )
        except:
            pass
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in process_commission: {e}")
        await message.answer("❌ Xatolik yuz berdi!")
        await state.clear()

# ==================== KANAL ADMIN PANELI ====================

@dp.callback_query(F.data == "channel_manage")
async def channel_manage_callback(callback: types.CallbackQuery):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    kb = [
        [InlineKeyboardButton(text="💳 Karta ma'lumotlari", callback_data="admin_card")],
        [InlineKeyboardButton(text="💰 Narxlarni sozlash", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⏳ Kutilayotgan e'lonlar", callback_data="admin_pending")],
        [InlineKeyboardButton(text="✅ Tasdiqlangan e'lonlar", callback_data="admin_approved")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")]
    ]
    
    await callback.message.edit_text(
        f"⚙️ *KANAL BOSHQARUVI*\n\n"
        f"📢 Kanal: {channel_admin['channel_name']}\n"
        f"💰 Foiz: {channel_admin['commission_percent']}%\n"
        f"📊 Aktiv e'lonlar: 0 ta\n\n"
        f"Quyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# Karta ma'lumotlari
@dp.callback_query(F.data == "admin_card")
async def admin_card_callback(callback: types.CallbackQuery, state: FSMContext):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    card_info = ""
    if channel_admin['card_number']:
        card_info = f"💳 *Karta ma'lumotlari:*\n"
        card_info += f"Karta: `{channel_admin['card_number']}`\n"
        card_info += f"Egasi: {channel_admin['card_holder']}\n\n"
        card_info += f"Yangilash uchun karta raqamini yuboring:"
    else:
        card_info = "💳 *Karta ma'lumotlari kiritilmagan!*\n\nKarta raqamingizni yuboring:"
    
    await callback.message.edit_text(
        card_info,
        parse_mode="Markdown"
    )
    await state.set_state(ChannelAdminStates.waiting_for_card_info)
    await callback.answer()

# Karta ma'lumotlarini qabul qilish
@dp.message(ChannelAdminStates.waiting_for_card_info)
async def process_card_info(message: types.Message, state: FSMContext):
    channel_admin = await get_channel_admin(message.from_user.id)
    
    if not channel_admin:
        return
    
    # Oddiy karta validatsiyasi
    card_text = message.text.strip()
    
    # Karta raqami va egasini ajratish
    if '|' in card_text:
        parts = card_text.split('|')
        card_number = parts[0].strip()
        card_holder = parts[1].strip() if len(parts) > 1 else ""
    else:
        # Faqat raqam kiritilgan
        card_number = card_text
        card_holder = ""
    
    # Database yangilash
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE channel_admins 
        SET card_number = ?, card_holder = ?
        WHERE admin_telegram_id = ?
    ''', (card_number, card_holder, message.from_user.id))
    conn.commit()
    
    await message.answer(
        f"✅ *Karta ma'lumotlari saqlandi!*\n\n"
        f"Karta: `{card_number}`\n"
        f"Egasi: {card_holder or 'Kiritilmagan'}\n\n"
        f"Endi to'lovlar shu kartaga o'tkaziladi.",
        parse_mode="Markdown"
    )
    
    await state.clear()

# Narxlarni sozlash
@dp.callback_query(F.data == "admin_prices")
async def admin_prices_callback(callback: types.CallbackQuery):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    kb = [
        [InlineKeyboardButton(text="📱 Telefon narxi", callback_data="price_phone")],
        [InlineKeyboardButton(text="🚗 Mashina narxi", callback_data="price_car")],
        [InlineKeyboardButton(text="🏠 Ko'chmas mulk narxi", callback_data="price_property")],
        [InlineKeyboardButton(text="📦 Aralash narxi", callback_data="price_mixed")],
        [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
    ]
    
    await callback.message.edit_text(
        f"💰 *NARXLARNI SOZLASH*\n\n"
        f"Hozirgi narxlar:\n"
        f"📱 Telefon: {channel_admin['phone_price']:,} so'm\n"
        f"🚗 Mashina: {channel_admin['car_price']:,} so'm\n"
        f"🏠 Mulk: {channel_admin['property_price']:,} so'm\n"
        f"📦 Aralash: {channel_admin['mixed_price']:,} so'm\n\n"
        f"O'zgartirmoqchi bo'lgan narzingizni tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# Narx turini tanlash
@dp.callback_query(F.data.startswith("price_"))
async def select_price_type(callback: types.CallbackQuery, state: FSMContext):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    price_type = callback.data.split("_")[1]  # phone, car, property, mixed
    
    price_names = {
        'phone': '📱 Telefon',
        'car': '🚗 Mashina', 
        'property': '🏠 Ko\'chmas mulk',
        'mixed': '📦 Aralash'
    }
    
    current_price = channel_admin[f'{price_type}_price']
    
    await state.update_data(price_type=price_type)
    
    await callback.message.edit_text(
        f"💰 *{price_names[price_type]} NARXINI O'ZGARTIRISH*\n\n"
        f"Hozirgi narx: {current_price:,} so'm\n\n"
        f"Yangi narxni kiriting (faqat raqam):",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelAdminStates.waiting_for_price_update)
    await callback.answer()

# Yangi narxni qabul qilish
@dp.message(ChannelAdminStates.waiting_for_price_update)
async def process_new_price(message: types.Message, state: FSMContext):
    channel_admin = await get_channel_admin(message.from_user.id)
    
    if not channel_admin:
        return
    
    try:
        new_price = float(message.text)
        
        if new_price < 1000 or new_price > 1000000:
            await message.answer("❌ Narx 1,000 dan 1,000,000 so'm gacha bo'lishi kerak!")
            return
        
        state_data = await state.get_data()
        price_type = state_data.get('price_type')
        
        # Database yangilash
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE channel_admins 
            SET {price_type}_price = ?
            WHERE admin_telegram_id = ?
        ''', (new_price, message.from_user.id))
        conn.commit()
        
        price_names = {
            'phone': 'Telefon',
            'car': 'Mashina', 
            'property': 'Ko\'chmas mulk',
            'mixed': 'Aralash'
        }
        
        await message.answer(
            f"✅ *{price_names[price_type]} narxi yangilandi!*\n\n"
            f"Yangi narx: {new_price:,} so'm\n\n"
            f"Endi yangi e'lonlar shu narxda joylanadi.",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
    except Exception as e:
        logger.error(f"Error in process_new_price: {e}")
        await message.answer("❌ Xatolik yuz berdi!")

# Statistika
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Oxirgi 30 kunlik statistika
    cursor.execute('''
        SELECT 
            COUNT(*) as total_ads,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_ads,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_ads,
            SUM(CASE WHEN status = 'deleted' THEN 1 ELSE 0 END) as deleted_ads,
            SUM(payment_amount) as total_income
        FROM ads 
        WHERE channel_admin_id = ? 
        AND created_at >= date('now', '-30 days')
    ''', (channel_admin['id'],))
    
    stats = cursor.fetchone()
    
    stats_text = f"📊 *{channel_admin['channel_name']} STATISTIKASI*\n\n"
    stats_text += f"📅 Oxirgi 30 kun:\n"
    stats_text += f"📈 Jami e'lonlar: {stats[0] or 0} ta\n"
    stats_text += f"✅ Aktiv e'lonlar: {stats[1] or 0} ta\n"
    stats_text += f"⏳ Kutilayotgan: {stats[2] or 0} ta\n"
    stats_text += f"🗑 O'chirilgan: {stats[3] or 0} ta\n"
    stats_text += f"💰 Daromad: {stats[4] or 0:,.0f} so'm\n\n"
    stats_text += f"💳 Sizga: {(stats[4] or 0) * channel_admin['commission_percent'] / 100:,.0f} so'm"
    
    kb = [[InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]]
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# Kutilayotgan e'lonlar
@dp.callback_query(F.data == "admin_pending")
async def admin_pending_callback(callback: types.CallbackQuery):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.id, a.category, a.title, a.price, a.created_at, 
               u.username, u.first_name, p.check_image
        FROM ads a
        LEFT JOIN users u ON a.user_id = u.id
        LEFT JOIN payments p ON a.id = p.ad_id
        WHERE a.channel_admin_id = ? 
        AND a.status = 'pending'
        AND a.payment_status = 'pending'
        ORDER BY a.created_at DESC
        LIMIT 10
    ''', (channel_admin['id'],))
    
    ads = cursor.fetchall()
    
    if not ads:
        await callback.message.edit_text(
            "⏳ *Kutilayotgan e'lonlar yo'q!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
            ])
        )
        await callback.answer()
        return
    
    response = "⏳ *KUTILAYOTGAN E'LONLAR*\n\n"
    
    for ad in ads:
        category_emoji = {
            'phone': '📱',
            'car': '🚗',
            'property': '🏠',
            'mixed': '📦'
        }.get(ad[1], '📦')
        
        response += f"{category_emoji} *{ad[2]}*\n"
        response += f"💰 {ad[3]:,} $\n"
        response += f"👤 {ad[6]} (@{ad[5] or 'username yoq'})\n"
        response += f"📅 {ad[4].split()[0]}\n"
        
        kb_actions = []
        if ad[7]:  # Check bor
            kb_actions.append(
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_ad:{ad[0]}")
            )
            kb_actions.append(
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_ad:{ad[0]}")
            )
        else:
            kb_actions.append(
                InlineKeyboardButton(text="🔄 Chek kutilmoqda", callback_data=f"#")
            )
        
        response += "━" * 20 + "\n"
    
    kb = [
        [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_pending")]
    ]
    
    await callback.message.edit_text(
        response,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await callback.answer()

# E'lonni tasdiqlash
@dp.callback_query(F.data.startswith("approve_ad:"))
async def approve_ad_callback(callback: types.CallbackQuery, state: FSMContext):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    ad_id = int(callback.data.split(":")[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # E'lonni tasdiqlash
    cursor.execute('''
        UPDATE ads 
        SET status = 'active', 
            payment_status = 'verified',
            admin_verified = 1,
            published_at = ?
        WHERE id = ? AND channel_admin_id = ?
    ''', (datetime.now().isoformat(), ad_id, channel_admin['id']))
    
    # To'lovni tasdiqlash
    cursor.execute('''
        UPDATE payments 
        SET status = 'verified',
            verified_by = ?,
            verified_at = ?
        WHERE ad_id = ?
    ''', (callback.from_user.id, datetime.now().isoformat(), ad_id))
    
    # Admin tekshiruvi yozuvi
    cursor.execute('''
        INSERT INTO admin_verifications (ad_id, admin_id, action)
        VALUES (?, ?, ?)
    ''', (ad_id, channel_admin['id'], 'approve'))
    
    conn.commit()
    
    # E'lon egasiga xabar yuborish
    cursor.execute('SELECT user_id FROM ads WHERE id = ?', (ad_id,))
    user_row = cursor.fetchone()
    
    if user_row:
        try:
            await bot.send_message(
                user_row[0],
                f"🎉 *Tabriklaymiz! E'loningiz tasdiqlandi!*\n\n"
                f"🆔 E'lon ID: #{ad_id}\n"
                f"✅ Status: Faol\n"
                f"⏰ Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"E'loningiz kanalda joylandi!"
            )
        except Exception as e:
            logger.error(f"Error sending approval message: {e}")
    
    await callback.answer("✅ E'lon tasdiqlandi!")
    await callback.message.delete()
    
    # Yangi xabar yuborish
    await callback.message.answer(
        f"✅ *E'lon tasdiqlandi!*\n\n"
        f"E'lon egasiga xabar yuborildi.",
        parse_mode="Markdown"
    )

# E'lonni rad etish
@dp.callback_query(F.data.startswith("reject_ad:"))
async def reject_ad_callback(callback: types.CallbackQuery, state: FSMContext):
    channel_admin = await get_channel_admin(callback.from_user.id)
    
    if not channel_admin:
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    ad_id = int(callback.data.split(":")[1])
    
    await state.update_data(ad_id=ad_id)
    
    await callback.message.edit_text(
        f"❌ *E'LONNI RAD ETISH*\n\n"
        f"E'lon ID: #{ad_id}\n\n"
        f"Iltimos, rad etish sababini yozing yoki 'Sababsiz' deb yozing:",
        parse_mode="Markdown"
    )
    await state.set_state(ChannelAdminStates.waiting_for_message_to_user)
    await callback.answer()

# Rad etish xabarini qabul qilish
@dp.message(ChannelAdminStates.waiting_for_message_to_user)
async def process_reject_message(message: types.Message, state: FSMContext):
    channel_admin = await get_channel_admin(message.from_user.id)
    
    if not channel_admin:
        return
    
    state_data = await state.get_data()
    ad_id = state_data.get('ad_id')
    
    if not ad_id:
        await message.answer("❌ Xatolik yuz berdi!")
        await state.clear()
        return
    
    reject_message = message.text
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # E'lonni rad etish
    cursor.execute('''
        UPDATE ads 
        SET status = 'rejected', 
            payment_status = 'rejected',
            admin_message = ?
        WHERE id = ? AND channel_admin_id = ?
    ''', (reject_message, ad_id, channel_admin['id']))
    
    # To'lovni rad etish
    cursor.execute('''
        UPDATE payments 
        SET status = 'rejected',
            admin_message = ?
        WHERE ad_id = ?
    ''', (reject_message, ad_id))
    
    # Admin tekshiruvi yozuvi
    cursor.execute('''
        INSERT INTO admin_verifications (ad_id, admin_id, action, message)
        VALUES (?, ?, ?, ?)
    ''', (ad_id, channel_admin['id'], 'reject', reject_message))
    
    conn.commit()
    
    # E'lon egasiga xabar yuborish
    cursor.execute('SELECT user_id FROM ads WHERE id = ?', (ad_id,))
    user_row = cursor.fetchone()
    
    if user_row:
        try:
            await bot.send_message(
                user_row[0],
                f"❌ *E'loningiz rad etildi!*\n\n"
                f"🆔 E'lon ID: #{ad_id}\n"
                f"📝 Sabab: {reject_message}\n\n"
                f"Iltimos, to'lov chekingizni tekshiring va qayta urinib ko'ring."
            )
        except Exception as e:
            logger.error(f"Error sending rejection message: {e}")
    
    await message.answer(
        f"❌ *E'lon rad etildi!*\n\n"
        f"E'lon egasiga xabar yuborildi.",
        parse_mode="Markdown"
    )
    
    await state.clear()

# ==================== WEBAPP DATA HANDLER ====================

@dp.message(lambda m: m.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    try:
        data = json.loads(message.web_app_data.data)
        logger.info(f"WebApp data received: {data}")
        
        action = data.get('action')
        
        if action == 'submit_ad':
            await handle_ad_submission(message, data, state)
        elif action == 'upload_check':
            await handle_check_upload(message, data)
        elif action == 'delete_ad':
            await handle_ad_deletion(message, data)
        else:
            await message.answer("❌ Noma'lum amal!")
            
    except json.JSONDecodeError as e:
        await message.answer("❌ Ma'lumot formatida xatolik!")
        logger.error(f"JSON decode error: {e}")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")
        logger.error(f"Error in handle_web_app_data: {e}")

# E'lon yuborishni qayta ishlash
async def handle_ad_submission(message: types.Message, data: dict, state: FSMContext):
    user_id = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if not user_id:
        await message.answer("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return
    
    # Telefon yoki Telegram username borligini tekshirish
    if not data.get('tel1') and not data.get('telegram_username'):
        await message.answer(
            "❌ *Kamida 1 ta telefon raqam YOKI Telegram username kiriting!*\n\n"
            "Iltimos, quyidagilardan kamida bittasini to'ldiring:\n"
            "• Telefon raqami\n"
            "• Telegram username",
            parse_mode="Markdown"
        )
        return
    
    # Kanallarni olish
    channels = await get_channels()
    
    if not channels:
        await message.answer(
            "❌ Hech qanday kanal mavjud emas!\n"
            "Iltimos, keyinroq urinib ko'ring yoki admin bilan bog'laning.",
            parse_mode="Markdown"
        )
        return
    
    # State ga ma'lumotlarni saqlash
    await state.update_data(ad_data=data, user_id=user_id)
    
    # Kanal tanlash uchun tugmalar
    kb = []
    for channel in channels:
        # Har bir kanal uchun narxni olish
        prices = await get_channel_prices(channel['id'])
        if prices:
            price = prices.get(f"{data.get('category')}_price", 10000)
        else:
            price = 10000
        
        kb.append([InlineKeyboardButton(
            text=f"{channel['channel_name']} - {price:,} so'm",
            callback_data=f"select_channel:{channel['id']}:{price}"
        )])
    
    kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ad")])
    
    await message.answer(
        f"✅ *E'lon ma'lumotlari qabul qilindi!*\n\n"
        f"📂 *Kategoriya:* {data.get('category')}\n"
        f"💰 *Narx:* {data.get('price')} $\n\n"
        f"📢 *Kanal tanlang:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    
    await state.set_state(AdStates.waiting_for_ad_data)

# Kanal tanlash
@dp.callback_query(AdStates.waiting_for_ad_data, F.data.startswith("select_channel:"))
async def handle_channel_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split(":")
        channel_id = int(parts[1])
        price = int(parts[2])
        
        state_data = await state.get_data()
        ad_data = state_data.get('ad_data')
        user_id = state_data.get('user_id')
        
        # Kanal adminini olish
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ca.*, c.channel_name 
            FROM channel_admins ca
            LEFT JOIN channels c ON ca.channel_id = c.id
            WHERE ca.channel_id = ? AND ca.is_active = 1
        ''', (channel_id,))
        
        admin_row = cursor.fetchone()
        
        if not admin_row:
            await callback.answer("❌ Kanal admini topilmadi!")
            return
        
        admin = dict(admin_row)
        
        # E'lon yaratish
        cursor.execute('''
            INSERT INTO ads (
                user_id, channel_id, category, title, description, price, location,
                latitude, longitude, tel1, tel2, telegram_username,
                phone_model, phone_condition, phone_color, phone_box, phone_exchange, exchange_phone_model,
                car_model, car_year, car_mileage, car_fuel_types, car_amenities,
                property_type, property_custom_type, property_area, property_yard_area, property_transaction, property_amenities,
                mixed_features, media_count, media_files,
                status, payment_status, payment_amount, channel_admin_id, commission_percent, owner_percent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, channel_id, ad_data.get('category'),
            ad_data.get('title') or ad_data.get('phone_model') or ad_data.get('car_model'),
            ad_data.get('description') or ad_data.get('extra') or '',
            float(ad_data.get('price', 0)),
            ad_data.get('location'), ad_data.get('latitude'), ad_data.get('longitude'),
            ad_data.get('tel1'), ad_data.get('tel2'), ad_data.get('telegram_username'),
            # Telefon
            ad_data.get('phone_model'), ad_data.get('condition'),
            ad_data.get('color'), ad_data.get('box'),
            1 if ad_data.get('exchange') == 'ha' else 0,
            ad_data.get('exchange_phone_model'),
            # Mashina
            ad_data.get('car_model'), ad_data.get('year'),
            ad_data.get('mileage'), ','.join(ad_data.get('fuel_types', [])) if ad_data.get('fuel_types') else None,
            json.dumps(ad_data.get('amenities', [])) if ad_data.get('amenities') else None,
            # Ko'chmas mulk
            ad_data.get('type'), ad_data.get('custom_type'),
            ad_data.get('area'), ad_data.get('yard_area'),
            ad_data.get('transaction'),
            json.dumps(ad_data.get('amenities', [])) if ad_data.get('category') == 'property' else None,
            # Aralash
            json.dumps(ad_data.get('features', [])) if ad_data.get('category') == 'mixed' else None,
            # Media
            ad_data.get('media_count', 0),
            json.dumps(ad_data.get('media_files', [])),
            # Status va to'lov
            'waiting_payment', 'pending', price,
            admin['id'], admin['commission_percent'], admin['owner_percent']
        ))
        
        ad_id = cursor.lastrowid
        conn.commit()
        
        # To'lov ma'lumotlari
        payment_info = f"💳 *TO'LOV MA'LUMOTLARI*\n\n"
        
        if admin['card_number']:
            payment_info += f"Karta raqami: `{admin['card_number']}`\n"
            payment_info += f"Karta egasi: {admin['card_holder'] or 'Kiritilmagan'}\n"
        else:
            payment_info += "⚠️ *Diqqat!* Karta ma'lumotlari kiritilmagan.\n"
            payment_info += "Iltimos, admin bilan bog'laning.\n"
        
        payment_info += f"\n💰 *To'lov summasi:* {price:,} so'm\n"
        payment_info += f"📢 *Kanal:* {admin['channel_name']}\n"
        payment_info += f"💼 *Admin:* @{admin['admin_username'] or 'username yoq'}\n"
        payment_info += f"📅 *Muddati:* 30 kun\n\n"
        payment_info += f"💡 *Eslatma:* To'lov qilgandan so'ng chek rasmni yuklang."
        
        # Tugmalar
        kb = [
            [InlineKeyboardButton(text="💳 To'lov qildim", callback_data=f"payment_done:{ad_id}:{channel_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
        ]
        
        await callback.message.edit_text(
            payment_info,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in handle_channel_selection: {e}")
        await callback.answer("❌ Xatolik yuz berdi!")

# To'lov qilganligini tasdiqlash
@dp.callback_query(F.data.startswith("payment_done:"))
async def handle_payment_confirmation(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split(":")
        ad_id = int(parts[1])
        channel_id = int(parts[2])
        
        # Kanal adminini olish
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ca.* 
            FROM channel_admins ca
            WHERE ca.channel_id = ? AND ca.is_active = 1
        ''', (channel_id,))
        
        admin_row = cursor.fetchone()
        admin = dict(admin_row) if admin_row else {}
        
        # E'lonni yangilash
        cursor.execute('SELECT payment_amount FROM ads WHERE id = ?', (ad_id,))
        payment_amount = cursor.fetchone()[0]
        
        cursor.execute('''
            UPDATE ads 
            SET payment_status = 'pending',
                status = 'pending'
            WHERE id = ?
        ''', (ad_id,))
        
        # To'lov yozuvini yaratish
        cursor.execute('''
            INSERT INTO payments (ad_id, channel_admin_id, amount, card_number, card_holder, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (ad_id, admin.get('id'), payment_amount, admin.get('card_number'), admin.get('card_holder')))
        
        conn.commit()
        
        # Adminlarga xabar yuborish
        cursor.execute('SELECT user_id, title, category FROM ads WHERE id = ?', (ad_id,))
        ad_row = cursor.fetchone()
        
        if ad_row and admin.get('admin_telegram_id'):
            try:
                await bot.send_message(
                    admin['admin_telegram_id'],
                    f"💰 *YANGI TO'LOV!*\n\n"
                    f"📝 E'lon ID: #{ad_id}\n"
                    f"📦 Nomi: {ad_row[1]}\n"
                    f"📂 Kategoriya: {ad_row[2]}\n"
                    f"💰 Summa: {payment_amount:,} so'm\n"
                    f"👤 Foydalanuvchi: @{callback.from_user.username or 'username yoq'}\n\n"
                    f"⏳ Chekni kuting..."
                )
            except Exception as e:
                logger.error(f"Error sending to admin: {e}")
        
        await callback.message.edit_text(
            f"✅ *To'lov qilganingiz tasdiqlandi!*\n\n"
            f"📝 *E'lon ID:* #{ad_id}\n"
            f"💰 *Summa:* {payment_amount:,} so'm\n\n"
            f"📸 *Endi to'lov chekini rasmga olib yuklang.*\n"
            f"Chekda quyidagilar ko'rinishi kerak:\n"
            f"• To'lov summasi\n"
            f"• Sana va vaqt\n"
            f"• Karta raqamining oxirgi 4 raqami\n\n"
            f"📤 *Chekni yuborish uchun:*\n"
            f"1. Rasmga oling\n"
            f"2. Bu xabarga reply qilib yuboring\n"
            f"3. Yoki to'g'ridan-to'g'ri yuboring",
            parse_mode="Markdown"
        )
        
        await state.update_data(ad_id=ad_id)
        await state.set_state(AdStates.waiting_for_check)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in handle_payment_confirmation: {e}")
        await callback.answer("❌ Xatolik yuz berdi!")

# Chek rasmni qabul qilish
@dp.message(AdStates.waiting_for_check, F.photo)
async def handle_check_photo(message: types.Message, state: FSMContext):
    try:
        state_data = await state.get_data()
        ad_id = state_data.get('ad_id')
        
        if not ad_id:
            await message.answer("❌ E'lon ID topilmadi!")
            return
        
        # Rasmni saqlash
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_path = file_info.file_path
        
        # Faylni yuklab olish
        file = await bot.download_file(file_path)
        check_filename = f"check_{ad_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        check_path = f"{CHECKS_DIR}/{check_filename}"
        
        # Faylni saqlash
        async with aiofiles.open(check_path, 'wb') as f:
            await f.write(file.read())
        
        # Database yangilash
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE ads 
            SET check_image = ?,
                payment_status = 'pending'
            WHERE id = ?
        ''', (check_filename, ad_id))
        
        cursor.execute('''
            UPDATE payments 
            SET check_image = ?,
                status = 'pending'
            WHERE ad_id = ?
        ''', (check_filename, ad_id))
        
        # E'lon ma'lumotlarini olish
        cursor.execute('''
            SELECT a.title, a.category, a.payment_amount, ca.admin_telegram_id, u.username
            FROM ads a
            LEFT JOIN channel_admins ca ON a.channel_admin_id = ca.id
            LEFT JOIN users u ON a.user_id = u.id
            WHERE a.id = ?
        ''', (ad_id,))
        
        ad_info = cursor.fetchone()
        
        conn.commit()
        
        await message.answer(
            f"✅ *Chek qabul qilindi!*\n\n"
            f"📝 *E'lon ID:* #{ad_id}\n"
            f"📸 *Chek fayli:* {check_filename}\n"
            f"⏳ *Admin tekshiruvi kutilmoqda...*\n\n"
            f"📞 *Aloqa:* @{message.from_user.username or 'username yoq'}\n"
            f"⏰ *Tasdiqlash vaqti:* 1-24 soat",
            parse_mode="Markdown"
        )
        
        # Kanal adminiga xabar yuborish
        if ad_info and ad_info[3]:
            try:
                category_emoji = {
                    'phone': '📱',
                    'car': '🚗', 
                    'property': '🏠',
                    'mixed': '📦'
                }.get(ad_info[1], '📦')
                
                await bot.send_message(
                    ad_info[3],
                    f"📸 *YANGI TO'LOV CHEKI!*\n\n"
                    f"{category_emoji} {ad_info[0]}\n"
                    f"💰 {ad_info[2]:,} so'm\n"
                    f"👤 @{ad_info[4] or 'username yoq'}\n"
                    f"🆔 #{ad_id}\n\n"
                    f"Botda 'Kutilayotgan e'lonlar' bo'limiga o'ting."
                )
                
                # Rasmni ham yuborish
                await bot.send_photo(
                    ad_info[3],
                    photo=photo.file_id,
                    caption=f"🆔 #{ad_id} | {ad_info[2]:,} so'm"
                )
            except Exception as e:
                logger.error(f"Error sending check to admin: {e}")
        
        # State ni tozalash
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error in handle_check_photo: {e}")
        await message.answer("❌ Chek yuklashda xatolik!")

# ==================== BOSHQA HANDLERLAR ====================

# /myads - Mening e'lonlarim
@dp.message(Command("myads"))
async def my_ads_command(message: types.Message):
    user_id = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    if not user_id:
        await message.answer("❌ Xatolik yuz berdi!")
        return
    
    conn = get_db_connection()
    if not conn:
        await message.answer("❌ Database xatolik!")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.id, a.category, a.title, a.price, a.status, a.created_at, c.channel_name
            FROM ads a
            LEFT JOIN channels c ON a.channel_id = c.id
            WHERE a.user_id = ? AND a.status != 'deleted'
            ORDER BY a.created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            await message.answer("📭 *Sizda hali e'lonlar mavjud emas.*", parse_mode="Markdown")
            return
        
        response = "📋 *MENING E\'LONLARIM*\n\n"
        
        for row in rows:
            emoji = {
                'phone': '📱',
                'car': '🚗',
                'property': '🏠',
                'mixed': '📦'
            }.get(row[1], '📦')
            
            status_text = {
                'pending': '⏳ Kutilmoqda',
                'waiting_payment': '💳 Tolov kutilmoqda',
                'active': '✅ Faol',
                'expired': '⌛️ Muddati tugagan',
                'rejected': '❌ Rad etilgan'
            }.get(row[4], '❓ Noma\'lum')
            
            response += f"{emoji} *{row[2] or 'Elon'}*\n"
            response += f"💰 {row[3]:,} $\n"
            response += f"📅 {row[5].split()[0]}\n"
            response += f"📊 {status_text}\n"
            
            if row[6]:
                response += f"📢 {row[6]}\n"
            
            response += f"🆔 #{row[0]}\n"
            response += "━" * 20 + "\n"
        
        response += "\n📱 *Batafsil korish uchun:* /ad [ID]\n"
        response += "🗑 *O'chirish uchun:* /delete [ID]"
        
        await message.answer(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in my_ads_command: {e}")
        await message.answer("❌ Xatolik yuz berdi!")
    finally:
        conn.close()

# ==================== ASOSIY FUNKSIYA ====================

async def main():
    print("=" * 50)
    print("🚀 E'LON BOT ISHGA TUSHMOQDA...")
    print(f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Bot: @{(await bot.get_me()).username}")
    print(f"🌐 WebApp URL: {WEBAPP_URL}")
    print(f"💾 Database: {DB_PATH}")
    print("=" * 50)
    
    # Database initialization
    if init_database():
        print("✅ Database muvaffaqiyatli ishga tushdi!")
    else:
        print("❌ Database ishga tushirishda xatolik!")
    
    # Polling ni boshlash
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "web_app_data"])

if __name__ == "__main__":
    asyncio.run(main())
