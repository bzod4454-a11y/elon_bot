"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         E'LON BOT - TELEGRAM BOT v2.0                         ║
║                                                                               ║
║   Yangi funksiyalar:                                                          ║
║   1. Kanalga e'lon yuborish (publish)                                         ║
║   2. Qidiruv (/search)                                                        ║
║   3. Push-xabarlar (/notifications)                                           ║
║   4. Kanalga yuborilgan xabar ID sini saqlash                                 ║
║   5. E'lon muddati tugashiga 3 kun qolgan eslatma                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import secrets
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, Message,
    BotCommand, BotCommandScopeDefault, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from dotenv import load_dotenv

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

def print_step(msg: str, status: str = "info"):
    if status == "info":
        print(f"   {Colors.CYAN}ℹ️{Colors.ENDC} {msg}")
    elif status == "success":
        print(f"   {Colors.GREEN}✅{Colors.ENDC} {msg}")
    elif status == "error":
        print(f"   {Colors.FAIL}❌{Colors.ENDC} {msg}")
    elif status == "warning":
        print(f"   {Colors.WARNING}⚠️{Colors.ENDC} {msg}")

def print_header():
    print(f"\n{Colors.CYAN}{'╔' + '═'*78 + '╗'}{Colors.ENDC}")
    print(f"{Colors.CYAN}║{Colors.ENDC}{Colors.BOLD}{' ' * 25}🤖 E'LON BOT - TELEGRAM BOT v2.0{' ' * 28}{Colors.ENDC}{Colors.CYAN}║{Colors.ENDC}")
    print(f"{Colors.CYAN}╚{'═'*78}╝{Colors.ENDC}")

# ==================== ENVIRONMENT YUKLASH ====================
print_header()
print(f"\n{Colors.BOLD}📅 Ishga tushirish vaqti:{Colors.ENDC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{Colors.BOLD}📂 Ishchi papka:{Colors.ENDC} {os.getcwd()}")
print(f"{Colors.BOLD}🐍 Python versiyasi:{Colors.ENDC} {sys.version}")

print("\n📁 Environment yuklanmoqda...")

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")

ADMIN_IDS = []
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip().isdigit()]
        print_step(f"ADMIN_IDS yuklandi: {ADMIN_IDS}", "success")
    except ValueError as e:
        print_step(f"ADMIN_IDS xatosi: {e}", "error")

print_step(f"BOT_TOKEN: {BOT_TOKEN[:15] + '...' if BOT_TOKEN else '❌ MAVJUD EMAS'}", "info")
print_step(f"WEBAPP_URL: {WEBAPP_URL}", "info")
print_step(f"API_URL: {API_URL}", "info")
print_step(f"API_KEY: {API_KEY[:20] + '...' if API_KEY else '❌ MAVJUD EMAS'}", "info")

if not BOT_TOKEN:
    print_step("BOT_TOKEN mavjud emas! Bot ishlamaydi.", "error")
    sys.exit(1)
if not WEBAPP_URL:
    print_step("WEBAPP_URL mavjud emas! WebApp ishlamaydi.", "warning")
if not API_URL:
    print_step("API_URL mavjud emas! Bot API ga ulana olmaydi.", "error")
    sys.exit(1)
if not API_KEY:
    print_step("API_KEY mavjud emas! Bot API ga ulana olmaydi.", "error")
    sys.exit(1)

# ==================== LOGGING ====================
print("\n📝 Logging sozlanmoqda...")

try:
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    print_step("Logging tayyor", "success")
except Exception as e:
    print_step(f"Logging xatosi: {e}", "error")
    sys.exit(1)

# ==================== BOT SOZLAMALARI ====================
print("\n🤖 Bot sozlanmoqda...")

try:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    print_step("Bot yaratildi", "success")
except Exception as e:
    print_step(f"Bot yaratish xatosi: {e}", "error")
    sys.exit(1)

# ==================== FSM HOLATLARI ====================
class AdStates(StatesGroup):
    waiting_for_check = State()

class SuperAdminStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_name = State()
    waiting_for_admin_telegram_id = State()
    waiting_for_admin_percent = State()

class ChannelAdminStates(StatesGroup):
    waiting_for_card_info = State()
    waiting_for_price_update = State()
    waiting_for_reject_reason = State()

# ==================== API CALL FUNKSIYASI ====================
print("\n🔌 API call funksiyasi sozlanmoqda...")

async def api_call(endpoint: str, method: str = 'GET', data: Dict = None, files: Dict = None, admin_id: int = None) -> Dict:
    """API ga so'rov yuborish"""
    url = f"{API_URL}{endpoint}"
    headers = {
        'X-API-Key': API_KEY,
        'ngrok-skip-browser-warning': '1',
        'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/2.0)'
    }
    
    if admin_id:
        headers['X-Admin-ID'] = str(admin_id)
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if files:
                form_data = aiohttp.FormData()
                for key, value in files.items():
                    if isinstance(value, tuple):
                        form_data.add_field(key, value[0], filename=value[1])
                    else:
                        form_data.add_field(key, value)
                if data:
                    for key, value in data.items():
                        form_data.add_field(key, str(value))
                
                async with session.post(url, data=form_data, headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except:
                            text = await resp.text()
                            return {'success': False, 'error': f'Invalid JSON response: {text[:200]}'}
                    return {'success': False, 'error': f'HTTP {resp.status}'}
                    
            elif method == 'GET':
                params = data or {}
                if admin_id and 'admin_id' not in params:
                    params['admin_id'] = admin_id
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except:
                            text = await resp.text()
                            return {'success': False, 'error': f'Invalid JSON response: {text[:200]}'}
                    return {'success': False, 'error': f'HTTP {resp.status}'}
                    
            elif method == 'POST':
                async with session.post(url, json=data, headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except:
                            text = await resp.text()
                            return {'success': False, 'error': f'Invalid JSON response: {text[:200]}'}
                    return {'success': False, 'error': f'HTTP {resp.status}'}
                    
            elif method == 'PUT':
                async with session.put(url, json=data, headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except:
                            text = await resp.text()
                            return {'success': False, 'error': f'Invalid JSON response: {text[:200]}'}
                    return {'success': False, 'error': f'HTTP {resp.status}'}
                    
            else:
                return {'success': False, 'error': 'Invalid method'}
                
    except aiohttp.ClientConnectorError as e:
        print_step(f"API ga ulana olmadi! Server ishlayaptimi? {e}", "error")
        return {'success': False, 'error': f'Cannot connect to API server: {e}'}
    except aiohttp.ServerTimeoutError as e:
        print_step(f"API timeout! {e}", "error")
        return {'success': False, 'error': f'API timeout: {e}'}
    except Exception as e:
        print_step(f"API xatosi: {e}", "error")
        return {'success': False, 'error': str(e)}

# ==================== BOT KOMANDALARI ====================
async def set_bot_commands():
    """Bot komandalarini o'rnatish"""
    commands = [
        BotCommand(command="start", description="🚀 Botni ishga tushirish"),
        BotCommand(command="help", description="❓ Yordam"),
        BotCommand(command="my_ads", description="📋 Mening e'lonlarim"),
        BotCommand(command="new_ad", description="📝 Yangi e'lon"),
        BotCommand(command="search", description="🔍 E'lonlarni qidirish"),
        BotCommand(command="notifications", description="📬 Xabarlar"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    print_step("Bot komandalari o'rnatildi", "success")

# ==================== FORMATLASH FUNKSIYALARI ====================
def format_ad_message(ad: Dict[str, Any]) -> tuple:
    """E'lonni formatlash - matn va inline tugmalar"""
    
    category_emoji = {
        'phone': '📱', 'car': '🚗', 'property': '🏠', 'mixed': '📦'
    }.get(ad.get('category'), '📦')
    
    if ad.get('category') == 'phone':
        title = ad.get('phone_model', 'Telefon')
    elif ad.get('category') == 'car':
        title = ad.get('car_model', 'Avtomobil')
    elif ad.get('category') == 'property':
        title = ad.get('property_type', "Ko'chmas mulk")
    else:
        title = ad.get('title', 'E\'lon')
    
    text = f"{category_emoji} <b>{title}</b>\n\n"
    text += f"💰 <b>Narx:</b> {ad.get('price', 0)} $\n"
    
    if ad.get('location'):
        text += f"📍 <b>Joylashuv:</b> {ad.get('location')}\n"
    
    if ad.get('description'):
        text += f"\n📄 <b>Tavsif:</b>\n{ad.get('description')[:300]}\n"
    
    if ad.get('category') == 'phone':
        if ad.get('phone_condition'):
            text += f"\n🛠 <b>Holati:</b> {ad.get('phone_condition')}\n"
        if ad.get('phone_color'):
            text += f"🎨 <b>Rangi:</b> {ad.get('phone_color')}\n"
    elif ad.get('category') == 'car':
        if ad.get('car_year'):
            text += f"\n📆 <b>Yil:</b> {ad.get('car_year')}\n"
        if ad.get('car_mileage'):
            text += f"📏 <b>Probeg:</b> {ad.get('car_mileage')} km\n"
    elif ad.get('category') == 'property':
        if ad.get('property_area'):
            text += f"\n📏 <b>Maydon:</b> {ad.get('property_area')} m²\n"
    
    text += f"\n━━━━━━━━━━━━━━━\n"
    text += f"<b>📞 Aloqa:</b>\n"
    
    if ad.get('tel1'):
        text += f"📱 Telefon: <code>{ad.get('tel1')}</code>\n"
    if ad.get('telegram_username'):
        text += f"💬 Telegram: @{ad.get('telegram_username')}\n"
    
    text += f"\n🆔 <b>E'lon ID:</b> #{ad.get('id')}\n"
    text += f"📅 <b>Sana:</b> {ad.get('created_at', '')[:10] if ad.get('created_at') else 'Nomalum'}\n"
    
    inline_kb = [
        [
            InlineKeyboardButton(text="📞 Aloqa", callback_data=f"contact_ad:{ad.get('id')}"),
            InlineKeyboardButton(text="📤 Ulashish", switch_inline_query=f"elon_{ad.get('id')}")
        ],
        [
            InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"view_ad:{ad.get('id')}"),
            InlineKeyboardButton(text="📋 Boshqa e'lonlar", callback_data="other_ads")
        ]
    ]
    
    if ad.get('tel1'):
        inline_kb[0].insert(0, InlineKeyboardButton(
            text="📞 Qo'ng'iroq", 
            url=f"tel:{ad.get('tel1')}"
        ))
    
    return text, InlineKeyboardMarkup(inline_keyboard=inline_kb)

# ==================== KANALGA E'LON YUBORISH ====================
async def publish_ad_to_channel(ad_id: int, admin_telegram_id: int) -> bool:
    """E'lonni kanalga yuborish"""
    try:
        print_step(f"Publish ad {ad_id} by admin {admin_telegram_id}", "info")
        
        ad_result = await api_call(f'/ad/{ad_id}', 'GET')
        if not ad_result.get('success'):
            print_step(f"Ad {ad_id} not found", "error")
            return False
        
        ad = ad_result.get('ad')
        
        channels_result = await api_call('/channels', 'GET')
        channels = channels_result.get('channels', [])
        
        target_channel = None
        for ch in channels:
            if ch.get('id') == ad.get('channel_id'):
                target_channel = ch
                break
        
        if not target_channel:
            print_step(f"Channel not found for ad {ad_id}", "error")
            return False
        
        channel_tg_id = target_channel.get('channel_id')
        text, reply_markup = format_ad_message(ad)
        
        media_files = ad.get('media_files', [])
        message_id = None
        
        if media_files and len(media_files) > 0:
            media_group = []
            for i, media in enumerate(media_files[:10]):
                url = media if isinstance(media, str) else media.get('url', '')
                if url:
                    try:
                        full_url = f"{API_URL}{url}" if url.startswith('/') else url
                        async with aiohttp.ClientSession() as session:
                            async with session.get(full_url) as resp:
                                if resp.status == 200:
                                    img_data = await resp.read()
                                    media_group.append(
                                        InputMediaPhoto(
                                            media=BytesIO(img_data),
                                            caption=text if i == 0 else "",
                                            parse_mode="HTML"
                                        )
                                    )
                    except Exception as e:
                        logger.error(f"Error downloading media: {e}")
            
            if media_group:
                try:
                    messages = await bot.send_media_group(
                        chat_id=channel_tg_id,
                        media=media_group
                    )
                    if messages:
                        message_id = messages[0].message_id
                    
                    await bot.send_message(
                        chat_id=channel_tg_id,
                        text="📌 <b>E'lon ma'lumotlari:</b>",
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending media group: {e}")
                    msg = await bot.send_message(
                        chat_id=channel_tg_id,
                        text=text,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                    message_id = msg.message_id
            else:
                msg = await bot.send_message(
                    chat_id=channel_tg_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                message_id = msg.message_id
        else:
            msg = await bot.send_message(
                chat_id=channel_tg_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            message_id = msg.message_id
        
        if message_id:
            await api_call(f'/ad/{ad_id}', 'PUT', {
                'published_message_id': message_id
            })
        
        await api_call(f'/publish-ad/{ad_id}', 'POST', {
            'admin_telegram_id': admin_telegram_id
        })
        
        user_id = ad.get('user_id')
        if user_id:
            try:
                await bot.send_message(
                    user_id,
                    f"✅ <b>E'loningiz #{ad_id} kanalda nashr qilindi!</b>\n\n"
                    f"📢 Kanal: {target_channel.get('channel_name')}\n"
                    f"🔗 E'lonni ko'rish uchun kanalga o'ting.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to notify user: {e}")
        
        print_step(f"Ad {ad_id} published to channel {channel_tg_id}", "success")
        return True
        
    except Exception as e:
        logger.error(f"Publish ad error: {e}")
        print_step(traceback.format_exc(), "debug")
        return False

# ==================== START KOMANDASI ====================
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    print_step(f"START komandasi: user_id={user_id}, username={username}", "info")
    
    result = await api_call('/create-user', 'POST', {
        'telegram_id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name
    })
    
    if result.get('success'):
        print_step(f"   Foydalanuvchi tayyor: id={result.get('user_id')}", "success")
    else:
        print_step(f"   Foydalanuvchi xatosi: {result.get('error')}", "error")
    
    webapp_url = f"{WEBAPP_URL}?user_id={user_id}&api_url={API_URL}"
    
    kb = []
    
    if user_id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="👑 Katta Admin Panel", callback_data="superadmin_panel")])
        print_step("   Admin panel tugmasi qo'shildi", "debug")
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if admin_result.get('success') and admin_result.get('admin'):
        kb.append([InlineKeyboardButton(text="⚙️ Kanal Boshqaruvi", callback_data="channel_manage")])
        print_step("   Kanal admin panel tugmasi qo'shildi", "debug")
    
    kb.extend([
        [InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="📋 Mening e'lonlarim", callback_data="my_ads")],
        [InlineKeyboardButton(text="🔍 Qidirish", callback_data="search_menu")],
        [InlineKeyboardButton(text="📬 Xabarlar", callback_data="notifications_menu")],
        [InlineKeyboardButton(text="🤝 Biz bilan hamkorlik", callback_data="cooperation")]
    ])
    
    channels_result = await api_call('/channels', 'GET')
    channels = channels_result.get('channels', []) if channels_result.get('success') else []
    print_step(f"   {len(channels)} ta kanal yuklandi", "success")
    
    notifications_result = await api_call(f'/notifications/{user_id}', 'GET')
    unread_count = len(notifications_result.get('notifications', []))
    
    welcome_text = (
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        f"🚀 <b>E'LON JOYLASH BOTIGA XUSH KELIBSIZ!</b>\n\n"
        f"✅ <b>Avzalliklarimiz:</b>\n"
        f"• Hech qanday ro'yxatdan o'tish yo'q\n"
        f"• Narx chegaralari yo'q\n"
        f"• 1 ta telefon YOKI Telegram username etarli\n"
        f"• Rasm/Video yuklash mumkin\n\n"
        f"📊 <b>Mavjud kanallar:</b> {len(channels)} ta\n"
    )
    
    if unread_count > 0:
        welcome_text += f"📬 <b>Yangi xabarlar:</b> {unread_count} ta\n\n"
    
    welcome_text += f"💼 <b>E'lon berish uchun quyidagi tugmani bosing:</b>"
    
    await message.answer(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    print_step("   Xabar yuborildi", "success")

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "📝 <b>E'lon berish:</b> /start → Yangi e'lon tugmasini bosing\n"
        "📋 <b>E'lonlarim:</b> /my_ads\n"
        "🔍 <b>Qidirish:</b> /search <so'z>\n"
        "📬 <b>Xabarlar:</b> /notifications\n"
        "⚙️ <b>Kanal admini:</b> Agar kanal admini bo'lsangiz, Kanal Boshqaruvi tugmasi ko'rinadi\n"
        "👑 <b>Katta admin:</b> Agar katta admin bo'lsangiz, Katta Admin Panel tugmasi ko'rinadi\n\n"
        "📞 <b>Muammo bo'lsa:</b> @admin_username ga murojaat qiling"
    )

@dp.message(Command("search"))
async def search_command(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Qidiruv komandasi</b>\n\n"
            "Format: /search <so'z>\n\n"
            "Misol: /search iPhone\n"
            "Misol: /search Toshkent\n\n"
            "🔹 Qidiruv natijalari avtomatik ravishda ko'rsatiladi.",
            parse_mode="HTML"
        )
        return
    
    query = args[1]
    await message.answer("🔍 Qidiruv boshlandi...")
    
    result = await api_call('/search-ads', 'GET', {'q': query})
    
    if result.get('success') and result.get('ads'):
        ads = result.get('ads')[:10]
        text = f"🔍 <b>Qidiruv natijalari:</b> \"{query}\"\n\n"
        
        for ad in ads:
            text += f"🆔 #{ad.get('id')} - {ad.get('title')}\n"
            text += f"💰 {ad.get('price')} $ • 📍 {ad.get('location', 'Nomalum')}\n"
            text += f"━━━━━━━━━━━━━━━\n"
        
        kb = []
        for ad in ads[:5]:
            kb.append([InlineKeyboardButton(
                text=f"👁 #{ad.get('id')} - {ad.get('title')[:30]}",
                callback_data=f"view_ad:{ad.get('id')}"
            )])
        kb.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")])
        
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await message.answer(f"🔍 \"{query}\" bo'yicha hech qanday e'lon topilmadi.")

@dp.message(Command("notifications"))
async def notifications_command(message: Message):
    telegram_id = message.from_user.id
    
    result = await api_call(f'/notifications/{telegram_id}', 'GET')
    
    if result.get('success') and result.get('notifications'):
        notifications = result.get('notifications')[:10]
        text = "📬 <b>XABARLAR</b>\n\n"
        
        for n in notifications:
            type_emoji = {
                'approved': '✅', 'rejected': '❌', 
                'expired': '⌛️', 'reminder': '⏰', 'admin_added': '👑'
            }.get(n.get('type'), '📢')
            
            text += f"{type_emoji} {n.get('message')}\n"
            text += f"📅 {n.get('created_at', '')[:10] if n.get('created_at') else 'Nomalum'}\n"
            text += f"━━━━━━━━━━━━━━━\n"
            
            await api_call(f'/notifications/mark-read/{n.get("id")}', 'POST')
        
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("📬 Sizda yangi xabarlar yo'q.")

@dp.message(Command("my_ads"))
async def my_ads_command(message: Message):
    user_id = message.from_user.id
    page = 1
    
    await message.answer("⏳ E'lonlar yuklanmoqda...")
    
    result = await api_call('/user/ads', 'GET', {'telegram_id': user_id, 'page': page, 'per_page': 10})
    
    if result.get('success') and result.get('ads'):
        ads = result.get('ads')
        total_pages = result.get('total_pages', 1)
        
        text = "📋 <b>MENING E'LONLARIM</b>\n\n"
        for ad in ads:
            text += f"{ad.get('category_emoji', '📦')} <b>{ad.get('display_title', 'Elon')}</b>\n"
            text += f"💰 {ad.get('price', 0)} $ • 📅 {ad.get('created_date', 'Nomalum')}\n"
            text += f"📊 {ad.get('status_text', 'Nomalum')}\n"
            text += f"🆔 #{ad.get('id')}\n━━━━━━━━━━━━━━━\n"
        
        kb = []
        for ad in ads[:5]:
            kb.append([InlineKeyboardButton(
                text=f"👁 #{ad.get('id')} - {ad.get('display_title', 'Elon')[:30]}",
                callback_data=f"view_ad:{ad.get('id')}"
            )])
        
        if total_pages > 1:
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"my_ads:{page-1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"my_ads:{page+1}"))
            if nav_buttons:
                kb.append(nav_buttons)
        
        kb.append([InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}&api_url={API_URL}"))])
        kb.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")])
        
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "📭 <b>Sizda hali e'lonlar mavjud emas.</b>\n\n"
            "Yangi e'lon joylash uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}&api_url={API_URL}"))],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "my_ads")
async def my_ads_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.answer("⏳ E'lonlar yuklanmoqda...")
    
    result = await api_call('/user/ads', 'GET', {'telegram_id': user_id, 'page': 1, 'per_page': 10})
    
    if result.get('success') and result.get('ads'):
        ads = result.get('ads')
        
        text = "📋 <b>MENING E'LONLARIM</b>\n\n"
        for ad in ads:
            text += f"{ad.get('category_emoji', '📦')} <b>{ad.get('display_title', 'Elon')}</b>\n"
            text += f"💰 {ad.get('price', 0)} $ • 📅 {ad.get('created_date', 'Nomalum')}\n"
            text += f"📊 {ad.get('status_text', 'Nomalum')}\n"
            text += f"🆔 #{ad.get('id')}\n━━━━━━━━━━━━━━━\n"
        
        kb = []
        for ad in ads[:5]:
            kb.append([InlineKeyboardButton(
                text=f"👁 #{ad.get('id')} - {ad.get('display_title', 'Elon')[:30]}",
                callback_data=f"view_ad:{ad.get('id')}"
            )])
        kb.append([InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}&api_url={API_URL}"))])
        kb.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")])
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "📭 <b>Sizda hali e'lonlar mavjud emas.</b>\n\n"
            "Yangi e'lon joylash uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Yangi e'lon", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}&api_url={API_URL}"))],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("view_ad:"))
async def view_ad_callback(callback: types.CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    
    await callback.answer("⏳ Ma'lumot yuklanmoqda...")
    
    result = await api_call(f'/ad/{ad_id}', 'GET')
    
    if result.get('success'):
        ad = result.get('ad')
        
        text = f"<b>📌 E'LON #{ad.get('id')}</b>\n\n"
        text += f"📂 <b>Kategoriya:</b> {ad.get('category_name', ad.get('category'))}\n"
        text += f"💰 <b>Narx:</b> {ad.get('price')} $\n"
        text += f"📍 <b>Joylashuv:</b> {ad.get('location', 'Korsatilmagan')}\n"
        text += f"📞 <b>Aloqa:</b> {ad.get('tel1', ad.get('telegram_username', 'Yoq'))}\n"
        text += f"📊 <b>Holat:</b> {ad.get('status_text')}\n"
        text += f"📅 <b>Sana:</b> {ad.get('created_date', ad.get('created_at', 'Nomalum'))}\n"
        
        if ad.get('description'):
            text += f"\n📄 <b>Tavsif:</b>\n{ad.get('description')[:200]}..."
        
        if ad.get('media_files') and len(ad.get('media_files')) > 0:
            text += f"\n\n📸 <b>Rasmlar:</b> {len(ad.get('media_files'))} ta"
        
        kb = [
            [InlineKeyboardButton(text="🗑 E'lonni o'chirish", callback_data=f"delete_ad:{ad_id}")],
            [InlineKeyboardButton(text="↩️ Orqaga", callback_data="my_ads")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ E'lon topilmadi!")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_ad:"))
async def delete_ad_callback(callback: types.CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    await callback.answer("⏳ E'lon o'chirilmoqda...")
    
    result = await api_call(f'/ad/{ad_id}/delete', 'POST', {'user_id': user_id})
    
    if result.get('success'):
        await callback.message.edit_text(f"✅ E'lon #{ad_id} muvaffaqiyatli o'chirildi!")
    else:
        await callback.message.edit_text(f"❌ E'lon #{ad_id} o'chirishda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "search_menu")
async def search_menu_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🔍 <b>QIDIRUV</b>\n\n"
        "E'lonlarni qidirish uchun quyidagi formatlardan birini ishlating:\n\n"
        "1️⃣ <b>So'z bo'yicha:</b>\n"
        "<code>/search iPhone</code>\n\n"
        "2️⃣ <b>Joylashuv bo'yicha:</b>\n"
        "<code>/search Toshkent</code>\n\n"
        "💡 <b>Maslahat:</b> Qidiruv natijalarini yaxshilash uchun aniq so'zlardan foydalaning.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Qidirish", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "notifications_menu")
async def notifications_menu_callback(callback: types.CallbackQuery):
    await notifications_command(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "cooperation")
async def cooperation_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤝 <b>BIZ BILAN HAMKORLIK</b>\n\n"
        "📊 <b>Statistika:</b>\n"
        "• Kunlik ko'rishlar: 10,000+\n"
        "• Faol foydalanuvchilar: 5,000+\n"
        "• Muvaffaqiyatli bitimlar: 1,000+\n\n"
        "💼 <b>Hamkorlik turlari:</b>\n"
        "• Kanal reklamasi - kunlik 50,000+ ko'rish\n"
        "• Bot integratsiyasi - 24/7 avtomatik\n"
        "• Maxsus yechimlar - sizning talablaringiz bo'yicha\n\n"
        "💰 <b>Narxlar:</b>\n"
        "• Kanal reklamasi: 100,000 so'm/kun\n"
        "• Bot reklamasi: 200,000 so'm/hafta\n\n"
        "📞 <b>Bog'lanish:</b>\n"
        "Telegram: @admin_username\n"
        "Telefon: +998901234567",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📞 Admin bilan bog'lanish", url="https://t.me/admin_username")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery):
    await start_command(callback.message)
    await callback.answer()

@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        
        print_step(f"WEBAPP_DATA: user_id={user_id}, action={action}", "info")
        
        if action == "submit_ad":
            print_step(f"   E'lon ma'lumotlari qabul qilindi", "success")
            
            await state.update_data(ad_data=data)
            
            channels_result = await api_call('/channels', 'GET')
            channels = channels_result.get('channels', []) if channels_result.get('success') else []
            
            if not channels:
                await message.answer("❌ Hech qanday kanal mavjud emas!")
                return
            
            kb = []
            for channel in channels:
                category = data.get('category')
                if category == 'phone':
                    price = channel.get('phone_price', 10000)
                elif category == 'car':
                    price = channel.get('car_price', 20000)
                elif category == 'property':
                    price = channel.get('property_price', 30000)
                else:
                    price = channel.get('mixed_price', 15000)
                
                card_status = "✅" if channel.get('card_number') else "⚠️"
                kb.append([InlineKeyboardButton(
                    text=f"{card_status} {channel['channel_name']} - {int(price):,} so'm",
                    callback_data=f"select_channel:{channel['id']}:{int(price)}"
                )])
            
            kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ad")])
            
            await message.answer(
                f"✅ <b>E'lon ma'lumotlari qabul qilindi!</b>\n\n"
                f"📂 <b>Kategoriya:</b> {data.get('category')}\n"
                f"💰 <b>Narx:</b> {data.get('price')} $\n\n"
                f"📢 <b>Kanal tanlang:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
                parse_mode="HTML"
            )
            await state.set_state(AdStates.waiting_for_check)
            
        elif action == "upload_check":
            ad_id = data.get('ad_id')
            channel_id = data.get('channel_id')
            print_step(f"   Chek yuklash: ad_id={ad_id}", "info")
            await state.update_data(ad_id=ad_id, channel_id=channel_id)
            await message.answer(
                "📸 To'lov chekini rasm sifatida yuboring (jpg/png, 5MB gacha):\n\n"
                "Chekda quyidagilar ko'rinishi kerak:\n"
                "• To'lov summasi\n"
                "• Sana va vaqt\n"
                "• Karta raqamining oxirgi 4 raqami",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_check")]
                ])
            )
            await state.set_state(AdStates.waiting_for_check)
            
        elif action == "delete_ad":
            ad_id = data.get('ad_id')
            print_step(f"   E'lon o'chirish: ad_id={ad_id}", "info")
            
            result = await api_call(f'/ad/{ad_id}/delete', 'POST', {'user_id': user_id})
            
            if result.get('success'):
                await message.answer(f"✅ E'lon #{ad_id} o'chirildi.")
            else:
                await message.answer(f"❌ E'lon #{ad_id} o'chirishda xatolik: {result.get('error')}")
                
        else:
            print_step(f"   Noma'lum action: {action}", "warning")
            await message.answer("❌ Noma'lum WebApp so'rovi")
            
    except json.JSONDecodeError as e:
        print_step(f"   JSON xatosi: {e}", "error")
        await message.answer("❌ Ma'lumot formatida xatolik!")
    except Exception as e:
        print_step(f"   WebApp xatosi: {e}", "error")
        print_step(traceback.format_exc(), "debug")
        await message.answer("❌ Ma'lumotni qayta ishlashda xatolik!")

@dp.callback_query(F.data.startswith("select_channel:"), StateFilter(AdStates.waiting_for_check))
async def handle_channel_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split(":")
        channel_id = int(parts[1])
        price = int(parts[2])
        user_id = callback.from_user.id
        
        print_step(f"CHANNEL_SELECTION: user_id={user_id}, channel_id={channel_id}, price={price}", "info")
        
        state_data = await state.get_data()
        ad_data = state_data.get('ad_data')
        
        if not ad_data:
            print_step("   E'lon ma'lumotlari topilmadi", "error")
            await callback.message.edit_text("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
            await state.clear()
            await callback.answer()
            return
        
        ad_data['selected_channel'] = {
            'id': channel_id,
            'price': price
        }
        
        payment_info = await api_call(f'/payment-info/{channel_id}', 'GET')
        
        result = await api_call('/create-ad', 'POST', {
            'user_id': user_id,
            'username': callback.from_user.username,
            'first_name': callback.from_user.first_name,
            'last_name': callback.from_user.last_name,
            'data': ad_data
        })
        
        if not result.get('success'):
            print_step(f"   E'lon saqlash xatosi: {result.get('error')}", "error")
            await callback.answer("❌ E'lon saqlashda xatolik!", show_alert=True)
            return
        
        ad_id = result.get('ad_id')
        payment_amount = result.get('payment_amount', price)
        
        print_step(f"   E'lon saqlandi: ad_id={ad_id}", "success")
        await state.update_data(ad_id=ad_id, channel_id=channel_id, payment_amount=payment_amount)
        
        info = payment_info.get('payment_info', {})
        
        payment_text = "💳 <b>TO'LOV MA'LUMOTLARI</b>\n\n"
        if info.get('card_number'):
            payment_text += f"🏦 <b>Karta raqami:</b> <code>{info['card_number']}</code>\n"
            payment_text += f"👤 <b>Karta egasi:</b> {info.get('card_holder', 'Kiritilmagan')}\n"
        else:
            payment_text += "⚠️ <b>Diqqat! Karta ma'lumotlari kiritilmagan.</b>\n"
            payment_text += "Iltimos, admin bilan bog'laning.\n"
        
        payment_text += f"\n💰 <b>To'lov summasi:</b> {int(payment_amount):,} so'm\n"
        payment_text += f"📢 <b>Kanal:</b> {info.get('channel_name', 'Nomalum')}\n"
        payment_text += f"💼 <b>Admin:</b> @{info.get('admin_username', 'admin')}\n"
        payment_text += f"📅 <b>Muddati:</b> 30 kun\n\n"
        payment_text += f"💡 <b>Eslatma:</b> To'lov qilgandan so'ng chek rasmni yuklang."
        
        kb = [
            [InlineKeyboardButton(text="💳 To'lov qildim", callback_data=f"payment_done:{ad_id}:{channel_id}")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
        ]
        
        await callback.message.edit_text(
            payment_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print_step(f"Channel selection xatosi: {e}", "error")
        print_step(traceback.format_exc(), "debug")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)

@dp.callback_query(F.data.startswith("payment_done:"))
async def handle_payment_confirmation(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split(":")
        ad_id = int(parts[1])
        channel_id = int(parts[2])
        user_id = callback.from_user.id
        
        print_step(f"PAYMENT_DONE: user_id={user_id}, ad_id={ad_id}", "info")
        
        await state.update_data(ad_id=ad_id, channel_id=channel_id)
        
        webapp_url = f"{WEBAPP_URL}?user_id={user_id}&ad_id={ad_id}&channel_id={channel_id}&api_url={API_URL}"
        
        await callback.message.edit_text(
            f"✅ <b>To'lov qilganingiz tasdiqlandi!</b>\n\n"
            f"📝 <b>E'lon ID:</b> #{ad_id}\n\n"
            f"📸 <b>Endi to'lov chekini rasmga olib yuklang.</b>\n"
            f"Chekda quyidagilar ko'rinishi kerak:\n"
            f"• To'lov summasi\n"
            f"• Sana va vaqt\n"
            f"• Karta raqamining oxirgi 4 raqami\n\n"
            f"📤 <b>Chekni yuborish uchun quyidagi tugmani bosing:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Chek yuklash", web_app=WebAppInfo(url=webapp_url))],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        print_step(f"Payment confirmation xatosi: {e}", "error")
        print_step(traceback.format_exc(), "debug")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)

@dp.message(AdStates.waiting_for_check, F.photo)
async def handle_check_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        state_data = await state.get_data()
        ad_id = state_data.get('ad_id')
        
        print_step(f"CHECK_PHOTO: user_id={user_id}, ad_id={ad_id}", "info")
        
        if not ad_id:
            await message.answer("❌ E'lon ID topilmadi!")
            await state.clear()
            return
        
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        
        if file_info.file_size > 5 * 1024 * 1024:
            print_step(f"   Rasm hajmi katta: {file_info.file_size}", "warning")
            await message.answer("❌ Rasm 5MB dan kichik bo'lishi kerak!")
            return
        
        file = await bot.download_file(file_info.file_path)
        file_data = file.read()
        
        print_step(f"   Chek yuborilmoqda, hajmi: {len(file_data)} bayt", "debug")
        
        result = await api_call('/upload-check', 'POST', files={
            'check_image': (file_data, f'check_{ad_id}.jpg'),
            'ad_id': str(ad_id)
        })
        
        if result.get('success'):
            print_step(f"   Chek yuklandi: ad_id={ad_id}", "success")
            await message.answer(
                f"✅ <b>Chek qabul qilindi!</b>\n\n"
                f"📝 <b>E'lon ID:</b> #{ad_id}\n"
                f"⏳ <b>Admin tekshiruvi kutilmoqda...</b>\n\n"
                f"⏰ <b>Tasdiqlash vaqti:</b> 1-24 soat\n\n"
                f"ℹ️ Admin tasdiqlagandan so'ng e'loningiz kanalda ko'rinadi.",
                parse_mode="HTML"
            )
            await state.clear()
        else:
            print_step(f"   Chek yuklash xatosi: {result.get('error')}", "error")
            await message.answer(f"❌ Chek yuklashda xatolik: {result.get('error')}\nIltimos, qayta urinib ko'ring.")
            
    except Exception as e:
        print_step(f"   CHECK_PHOTO xatosi: {e}", "error")
        print_step(traceback.format_exc(), "debug")
        await message.answer("❌ Chek yuklashda xatolik yuz berdi!")
        await state.clear()

@dp.callback_query(F.data == "cancel_check", StateFilter(AdStates.waiting_for_check))
async def cancel_check_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ To'lov cheki yuklash bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_ad")
async def cancel_ad_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ E'lon berish bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "channel_manage")
async def channel_manage_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    stats_result = await api_call('/admin/channel-stats', 'GET', {'admin_telegram_id': user_id})
    stats = stats_result.get('stats', {}) if stats_result.get('success') else {}
    
    kb = [
        [InlineKeyboardButton(text="💳 Karta ma'lumotlari", callback_data="admin_card")],
        [InlineKeyboardButton(text="💰 Narxlarni sozlash", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⏳ Kutilayotgan e'lonlar", callback_data="admin_pending")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
    ]
    
    text = (
        f"⚙️ <b>KANAL BOSHQARUVI</b>\n\n"
        f"📢 Kanal: {channel_admin.get('channel_name')}\n"
        f"💰 Sizning foizingiz: {channel_admin.get('commission_percent')}%\n\n"
        f"📊 <b>Statistika (oxirgi 30 kun):</b>\n"
        f"• Jami e'lonlar: {stats.get('total_ads', 0)} ta\n"
        f"• Faol e'lonlar: {stats.get('active_ads', 0)} ta\n"
        f"• Kutilayotgan: {stats.get('pending_ads', 0)} ta\n"
        f"• To'lov kutilayotgan: {stats.get('waiting_payment', 0)} ta\n"
        f"• Rad etilgan: {stats.get('rejected_ads', 0)} ta\n"
        f"• Daromad: {stats.get('total_income', 0):,.0f} so'm\n\n"
        f"Quyidagi bo'limlardan birini tanlang:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_pending")
async def admin_pending_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    pending_result = await api_call('/admin/pending-ads', 'GET', {'admin_telegram_id': user_id})
    
    if not pending_result.get('success'):
        await callback.answer("❌ Ma'lumot olishda xatolik!")
        return
    
    pending_ads = pending_result.get('ads', [])
    
    if not pending_ads:
        await callback.message.edit_text(
            "⏳ <b>Kutilayotgan e'lonlar yo'q!</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = "⏳ <b>KUTILAYOTGAN E'LONLAR (To'lov qilingan)</b>\n\n"
    
    for ad in pending_ads[:10]:
        category_emoji = {'phone': '📱', 'car': '🚗', 'property': '🏠', 'mixed': '📦'}.get(ad.get('category'), '📦')
        title = ad.get('title') or ad.get('phone_model') or ad.get('car_model') or 'E\'lon'
        payment_amount = ad.get('payment_amount', 0)
        username = ad.get('username', 'nomalum')
        created_at = ad.get('created_at', '')
        ad_id = ad.get('id')
        
        text += (
            f"{category_emoji} <b>{title}</b>\n"
            f"💰 {int(payment_amount):,} so'm\n"
            f"👤 @{username}\n"
            f"📅 {created_at.split('T')[0] if created_at else 'Nomalum'}\n"
            f"🆔 #{ad_id}\n"
            f"━━━━━━━━━━━━━━━\n\n"
        )
    
    kb = []
    for ad in pending_ads[:10]:
        ad_id = ad.get('id')
        kb.append([
            InlineKeyboardButton(text=f"✅ #{ad_id} ni tasdiqlash", callback_data=f"approve_ad:{ad_id}"),
            InlineKeyboardButton(text=f"📢 #{ad_id} ni nashr qilish", callback_data=f"publish_ad:{ad_id}"),
            InlineKeyboardButton(text=f"❌ #{ad_id} ni rad etish", callback_data=f"reject_ad:{ad_id}")
        ])
    
    kb.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_pending")])
    kb.append([InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("publish_ad:"))
async def publish_ad_callback(callback: types.CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    admin_id = callback.from_user.id
    
    await callback.answer("⏳ E'lon nashr qilinmoqda...")
    
    success = await publish_ad_to_channel(ad_id, admin_id)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>E'lon #{ad_id} muvaffaqiyatli nashr qilindi!</b>\n\n"
            f"📢 E'lon kanalda ko'rinadi.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>E'lon #{ad_id} nashr qilishda xatolik!</b>\n\n"
            f"Iltimos, qayta urinib ko'ring.",
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("approve_ad:"))
async def approve_ad_callback(callback: types.CallbackQuery):
    ad_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    await callback.answer("⏳ Tasdiqlanmoqda...")
    
    result = await api_call(f'/admin/approve/{ad_id}', 'POST', {'admin_telegram_id': user_id})
    
    if result.get('success'):
        await callback.answer(f"✅ E'lon #{ad_id} tasdiqlandi!", show_alert=True)
        await admin_pending_callback(callback)
    else:
        await callback.answer("❌ E'lonni tasdiqlashda xatolik!", show_alert=True)

@dp.callback_query(F.data.startswith("reject_ad:"))
async def reject_ad_callback(callback: types.CallbackQuery, state: FSMContext):
    ad_id = int(callback.data.split(":")[1])
    
    await state.update_data(reject_ad_id=ad_id)
    await callback.message.answer(
        f"❌ E'lon #{ad_id} ni rad etish sababini yozing:\n\n"
        f"<i>Masalan: Noto'g'ri ma'lumot, rasm sifatsiz...</i>",
        parse_mode="HTML"
    )
    await state.set_state(ChannelAdminStates.waiting_for_reject_reason)
    await callback.answer()

@dp.message(ChannelAdminStates.waiting_for_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext):
    state_data = await state.get_data()
    ad_id = state_data.get('reject_ad_id')
    reason = message.text.strip()
    user_id = message.from_user.id
    
    if not ad_id:
        await message.answer("❌ Xatolik yuz berdi!")
        await state.clear()
        return
    
    result = await api_call(f'/admin/reject/{ad_id}', 'POST', {
        'admin_telegram_id': user_id,
        'reason': reason
    })
    
    if result.get('success'):
        await message.answer(f"✅ E'lon #{ad_id} rad etildi!\nSabab: {reason}")
    else:
        await message.answer("❌ E'lonni rad etishda xatolik!")
    
    await state.clear()
    await admin_pending_callback(message)

@dp.callback_query(F.data == "admin_card")
async def admin_card_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    if channel_admin.get('card_number'):
        await callback.message.edit_text(
            f"💳 <b>Joriy karta ma'lumotlari:</b>\n\n"
            f"Karta: <code>{channel_admin['card_number']}</code>\n"
            f"Egasi: {channel_admin.get('card_holder', 'Kiritilmagan')}\n\n"
            f"Yangilash uchun yangi karta raqamini yuboring:\n"
            f"<i>Format: 8600123456789012|KARTA EGASI</i>",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"💳 <b>Karta ma'lumotlari kiritilmagan!</b>\n\n"
            f"Karta raqamingizni yuboring:\n"
            f"<i>Format: 8600123456789012|Karta egasi</i>",
            parse_mode="HTML"
        )
    
    await state.set_state(ChannelAdminStates.waiting_for_card_info)
    await callback.answer()

@dp.message(ChannelAdminStates.waiting_for_card_info)
async def process_card_info(message: Message, state: FSMContext):
    user_id = message.from_user.id
    card_text = message.text.strip()
    
    if '|' in card_text:
        parts = card_text.split('|')
        card_number = parts[0].strip()
        card_holder = parts[1].strip() if len(parts) > 1 else ""
    else:
        card_number = card_text
        card_holder = ""
    
    card_number = card_number.replace(' ', '')
    if not card_number.isdigit() or len(card_number) < 8:
        await message.answer("❌ Noto'g'ri karta raqami! Iltimos, to'g'ri kiriting.")
        return
    
    result = await api_call('/admin/update-card', 'POST', {
        'telegram_id': user_id,
        'card_number': card_number,
        'card_holder': card_holder
    })
    
    if result.get('success'):
        await message.answer(
            f"✅ <b>Karta ma'lumotlari saqlandi!</b>\n\n"
            f"Karta: <code>{card_number}</code>\n"
            f"Egasi: {card_holder or 'Kiritilmagan'}",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await message.answer("❌ Karta ma'lumotlarini saqlashda xatolik!")

@dp.callback_query(F.data == "admin_prices")
async def admin_prices_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    kb = [
        [InlineKeyboardButton(text=f"📱 Telefon: {int(channel_admin.get('phone_price', 10000)):,} so'm", callback_data="price_phone")],
        [InlineKeyboardButton(text=f"🚗 Mashina: {int(channel_admin.get('car_price', 20000)):,} so'm", callback_data="price_car")],
        [InlineKeyboardButton(text=f"🏠 Ko'chmas mulk: {int(channel_admin.get('property_price', 30000)):,} so'm", callback_data="price_property")],
        [InlineKeyboardButton(text=f"📦 Aralash: {int(channel_admin.get('mixed_price', 15000)):,} so'm", callback_data="price_mixed")],
        [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
    ]
    
    await callback.message.edit_text(
        f"💰 <b>NARXLARNI SOZLASH</b>\n\n"
        f"Hozirgi narxlar:\n"
        f"📱 Telefon: {int(channel_admin.get('phone_price', 10000)):,} so'm\n"
        f"🚗 Mashina: {int(channel_admin.get('car_price', 20000)):,} so'm\n"
        f"🏠 Mulk: {int(channel_admin.get('property_price', 30000)):,} so'm\n"
        f"📦 Aralash: {int(channel_admin.get('mixed_price', 15000)):,} so'm\n\n"
        f"O'zgartirmoqchi bo'lgan narzingizni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("price_"))
async def select_price_type(callback: types.CallbackQuery, state: FSMContext):
    price_type = callback.data.split("_")[1]
    
    await state.update_data(price_type=price_type)
    
    await callback.message.edit_text(
        f"💰 <b>NARXNI O'ZGARTIRISH</b>\n\n"
        f"Yangi narxni kiriting (faqat raqam):",
        parse_mode="HTML"
    )
    await state.set_state(ChannelAdminStates.waiting_for_price_update)
    await callback.answer()

@dp.message(ChannelAdminStates.waiting_for_price_update)
async def process_new_price(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        new_price = float(message.text.replace(' ', ''))
        
        if new_price < 1000 or new_price > 1000000:
            await message.answer("❌ Narx 1,000 dan 1,000,000 so'm gacha bo'lishi kerak!")
            return
        
        state_data = await state.get_data()
        price_type = state_data.get('price_type')
        
        result = await api_call('/admin/update-price', 'POST', {
            'telegram_id': user_id,
            'price_type': price_type,
            'price': new_price
        })
        
        if result.get('success'):
            price_names = {
                'phone': 'Telefon',
                'car': 'Mashina',
                'property': "Ko'chmas mulk",
                'mixed': 'Aralash'
            }
            
            await message.answer(
                f"✅ <b>{price_names[price_type]} narxi yangilandi!</b>\n\n"
                f"Yangi narx: {int(new_price):,} so'm",
                parse_mode="HTML"
            )
            await state.clear()
        else:
            await message.answer("❌ Narxni yangilashda xatolik!")
            
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    result = await api_call('/admin/channel-stats', 'GET', {'admin_telegram_id': user_id})
    
    if result.get('success'):
        stats = result.get('stats', {})
        text = (
            f"📊 <b>KANAL STATISTIKASI</b>\n\n"
            f"📅 Oxirgi 30 kun:\n"
            f"📈 Jami e'lonlar: {stats.get('total_ads', 0)} ta\n"
            f"✅ Aktiv e'lonlar: {stats.get('active_ads', 0)} ta\n"
            f"⏳ Kutilayotgan: {stats.get('pending_ads', 0)} ta\n"
            f"💳 To'lov kutilayotgan: {stats.get('waiting_payment', 0)} ta\n"
            f"❌ Rad etilgan: {stats.get('rejected_ads', 0)} ta\n"
            f"💰 Jami daromad: {stats.get('total_income', 0):,.0f} so'm"
        )
        
        admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
        if admin_result.get('success') and admin_result.get('admin'):
            percent = admin_result.get('admin').get('commission_percent', 95)
            admin_income = stats.get('total_income', 0) * percent / 100
            text += f"\n\n💳 Sizga to'lanadigan: {admin_income:,.0f} so'm"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Statistika olishda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    kb = [
        [InlineKeyboardButton(text="📢 Kanal ma'lumotlari", callback_data="admin_channel_info")],
        [InlineKeyboardButton(text="👤 Shaxsiy ma'lumotlar", callback_data="admin_profile")],
        [InlineKeyboardButton(text="↩️ Orqaga", callback_data="channel_manage")]
    ]
    
    await callback.message.edit_text(
        f"⚙️ <b>SOZLAMALAR</b>\n\n"
        f"Bu bo'limda kanal sozlamalarini o'zgartirishingiz mumkin.\n\n"
        f"📢 Kanal: {channel_admin.get('channel_name')}\n"
        f"👤 Admin: @{channel_admin.get('admin_username', 'yoq')}\n"
        f"💳 Karta: {'Bor' if channel_admin.get('card_number') else 'Yoq'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_channel_info")
async def admin_channel_info_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    text = (
        f"📢 <b>KANAL MA'LUMOTLARI</b>\n\n"
        f"Nomi: {channel_admin.get('channel_name')}\n"
        f"ID: {channel_admin.get('channel_id')}\n"
        f"Username: @{channel_admin.get('channel_username', 'yoq')}\n"
        f"Sizning foizingiz: {channel_admin.get('commission_percent')}%\n"
        f"Kanal egasi foizi: {channel_admin.get('owner_percent')}%\n"
    )
    
    kb = [[InlineKeyboardButton(text="↩️ Orqaga", callback_data="admin_settings")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_profile")
async def admin_profile_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    admin_result = await api_call('/admin/me', 'GET', {'telegram_id': user_id})
    
    if not admin_result.get('success') or not admin_result.get('admin'):
        await callback.answer("❌ Siz kanal admini emassiz!")
        return
    
    channel_admin = admin_result.get('admin')
    
    text = (
        f"👤 <b>SHAXSIY MA'LUMOTLAR</b>\n\n"
        f"ID: {channel_admin.get('admin_telegram_id')}\n"
        f"Username: @{channel_admin.get('admin_username', 'yoq')}\n"
        f"Ism: {channel_admin.get('admin_name', 'Kiritilmagan')}\n"
        f"Karta: {channel_admin.get('card_number', 'Kiritilmagan')}\n"
        f"Karta egasi: {channel_admin.get('card_holder', 'Kiritilmagan')}\n"
    )
    
    kb = [[InlineKeyboardButton(text="↩️ Orqaga", callback_data="admin_settings")]]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== SUPER ADMIN PANEL ====================
@dp.callback_query(F.data == "superadmin_panel")
async def superadmin_panel_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    stats_result = await api_call('/admin/stats', 'GET', admin_id=user_id)
    stats = stats_result.get('stats', {}) if stats_result.get('success') else {}
    
    kb = [
        [InlineKeyboardButton(text="📊 Umumiy statistika", callback_data="super_stats")],
        [InlineKeyboardButton(text="📢 Kanallar ro'yxati", callback_data="super_channels_list")],
        [InlineKeyboardButton(text="👥 Adminlar ro'yxati", callback_data="super_admins_list")],
        [InlineKeyboardButton(text="💰 Daromad statistikasi", callback_data="super_income")],
        [InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="super_add_channel")],
        [InlineKeyboardButton(text="👤 Yangi admin qo'shish", callback_data="super_add_admin")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_main")]
    ]
    
    text = (
        f"👑 <b>KATTA ADMIN PANELI</b>\n\n"
        f"📊 <b>Qisqa statistika:</b>\n"
        f"• Foydalanuvchilar: {stats.get('total_users', 0)} ta\n"
        f"• Kanallar: {stats.get('total_channels', 0)} ta\n"
        f"• Adminlar: {stats.get('total_admins', 0)} ta\n"
        f"• Faol e'lonlar: {stats.get('active_ads', 0)} ta\n"
        f"• Kutilayotgan: {stats.get('pending_ads', 0)} ta\n"
        f"• Daromad: {stats.get('total_income', 0):,.0f} so'm\n\n"
        f"Quyidagi bo'limlardan birini tanlang:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "super_stats")
async def super_stats_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    result = await api_call('/admin/stats', 'GET', admin_id=user_id)
    
    if result.get('success'):
        stats = result.get('stats', {})
        daily_stats = result.get('daily_stats', [])
        
        text = (
            f"📊 <b>UMUMIY STATISTIKA</b>\n\n"
            f"👥 <b>Foydalanuvchilar:</b> {stats.get('total_users', 0)} ta\n\n"
            f"📢 <b>Kanallar:</b>\n"
            f"• Jami: {stats.get('total_channels', 0)} ta\n\n"
            f"👤 <b>Adminlar:</b>\n"
            f"• Jami: {stats.get('total_admins', 0)} ta\n\n"
            f"📝 <b>E'lonlar:</b>\n"
            f"• Jami: {stats.get('total_ads', 0)} ta\n"
            f"• Faol: {stats.get('active_ads', 0)} ta\n"
            f"• Kutilayotgan: {stats.get('pending_ads', 0)} ta\n"
            f"• To'lov kutilayotgan: {stats.get('waiting_payment', 0)} ta\n"
            f"• Rad etilgan: {stats.get('rejected_ads', 0)} ta\n"
            f"• Muddati tugagan: {stats.get('expired_ads', 0)} ta\n\n"
            f"💰 <b>Umumiy daromad:</b> {stats.get('total_income', 0):,.0f} so'm\n\n"
            f"📅 <b>Oxirgi 7 kunlik e'lonlar:</b>\n"
        )
        
        for day in daily_stats:
            text += f"• {day.get('date')}: {day.get('count')} ta\n"
        
        kb = [[InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Statistika olishda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "super_channels_list")
async def super_channels_list_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    result = await api_call('/admin/channels', 'GET', admin_id=user_id)
    
    if result.get('success'):
        channels = result.get('channels', [])
        
        if not channels:
            text = "📢 <b>Kanallar ro'yxati</b>\n\nHech qanday kanal topilmadi!"
        else:
            text = "📢 <b>Kanallar ro'yxati</b>\n\n"
            for ch in channels[:15]:
                status = "✅ Aktiv" if ch.get('is_active') else "❌ Noaktiv"
                admin_username = ch.get('admin_username', 'Tayinlanmagan')
                ads_count = ch.get('ads_count', 0)
                text += (
                    f"<b>{ch.get('channel_name')}</b>\n"
                    f"🆔 ID: {ch.get('channel_id')}\n"
                    f"📊 E'lonlar: {ads_count} ta\n"
                    f"👤 Admin: @{admin_username if admin_username else 'yoq'}\n"
                    f"📌 Status: {status}\n"
                    f"━━━━━━━━━━━━━━━\n"
                )
        
        kb = [
            [InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="super_add_channel")],
            [InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Kanallarni yuklashda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "super_admins_list")
async def super_admins_list_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    result = await api_call('/admin/admins', 'GET', admin_id=user_id)
    
    if result.get('success'):
        admins = result.get('admins', [])
        
        if not admins:
            text = "👥 <b>Adminlar ro'yxati</b>\n\nHech qanday admin topilmadi!"
        else:
            text = "👥 <b>Adminlar ro'yxati</b>\n\n"
            for ad in admins[:15]:
                status = "✅ Aktiv" if ad.get('is_active') else "❌ Noaktiv"
                card_status = "✅ Bor" if ad.get('card_number') else "❌ Yoq"
                text += (
                    f"<b>{ad.get('admin_name', 'Ismsiz')}</b>\n"
                    f"🆔 Telegram ID: {ad.get('admin_telegram_id')}\n"
                    f"📢 Kanal: {ad.get('channel_name')}\n"
                    f"📊 E'lonlar: {ad.get('total_ads', 0)} ta (Aktiv: {ad.get('active_ads', 0)} ta)\n"
                    f"💰 Foiz: {ad.get('commission_percent')}%\n"
                    f"💳 Karta: {card_status}\n"
                    f"📌 Status: {status}\n"
                    f"━━━━━━━━━━━━━━━\n"
                )
        
        kb = [
            [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="super_add_admin")],
            [InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Adminlarni yuklashda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "super_income")
async def super_income_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    result = await api_call('/admin/income', 'GET', admin_id=user_id)
    
    if result.get('success'):
        monthly = result.get('monthly_income', [])
        category = result.get('category_income', [])
        
        text = "💰 <b>DAROMAD STATISTIKASI</b>\n\n"
        
        text += "📅 <b>Oylik daromad:</b>\n"
        for m in monthly[:6]:
            text += f"• {m.get('month')}: {m.get('total_amount', 0):,.0f} so'm ({m.get('ads_count', 0)} ta e'lon)\n"
        
        text += "\n📂 <b>Kategoriyalar bo'yicha:</b>\n"
        cat_names = {'phone': '📱 Telefon', 'car': '🚗 Mashina', 'property': '🏠 Ko\'chmas mulk', 'mixed': '📦 Aralash'}
        for c in category:
            name = cat_names.get(c.get('category'), c.get('category'))
            text += f"• {name}: {c.get('total', 0):,.0f} so'm ({c.get('count', 0)} ta)\n"
        
        kb = [[InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]]
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("❌ Daromad statistikasini olishda xatolik!")
    
    await callback.answer()

@dp.callback_query(F.data == "super_add_channel")
async def super_add_channel_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    await callback.message.edit_text(
        "📢 <b>YANGI KANAL QO'SHISH</b>\n\n"
        "1-qadam: Kanal ID sini yuboring:\n"
        "<i>Masalan: -1001234567890</i>\n\n"
        "ℹ️ Kanal ID ni olish uchun:\n"
        "1. Kanalingizga @getidsbot ni qo'shing\n"
        "2. Kanal ID sini ko'ring\n"
        "3. Botni kanaldan o'chiring",
        parse_mode="HTML"
    )
    await state.set_state(SuperAdminStates.waiting_for_channel_id)
    await callback.answer()

@dp.message(SuperAdminStates.waiting_for_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        channel_id = int(message.text.strip())
        
        try:
            chat = await bot.get_chat(channel_id)
            channel_name = chat.title
            channel_username = chat.username
        except Exception as e:
            await message.answer(f"❌ Kanal topilmadi yoki bot kanalda admin emas!\nXato: {str(e)}")
            return
        
        await state.update_data(
            channel_id=channel_id,
            channel_name=channel_name,
            channel_username=channel_username
        )
        
        await message.answer(
            f"✅ Kanal ma'lumotlari qabul qilindi!\n\n"
            f"📢 Nomi: {channel_name}\n"
            f"🆔 ID: {channel_id}\n"
            f"📌 Username: @{channel_username if channel_username else 'yoq'}\n\n"
            f"2-qadam: Kanal tavsifini kiriting (ixtiyoriy) yoki /skip ni bosing:"
        )
        await state.set_state(SuperAdminStates.waiting_for_channel_name)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Kanal ID raqam bo'lishi kerak.\nMasalan: -1001234567890")

@dp.message(SuperAdminStates.waiting_for_channel_name)
async def process_channel_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == "/skip":
        description = ""
    else:
        description = message.text
    
    await state.update_data(description=description)
    
    await message.answer(
        "3-qadam: Kanal adminining Telegram ID sini yuboring:\n"
        "<i>Masalan: 123456789</i>\n\n"
        "ℹ️ Admin ID ni olish uchun @getidsbot ga /start yozing",
        parse_mode="HTML"
    )
    await state.set_state(SuperAdminStates.waiting_for_admin_telegram_id)

@dp.message(SuperAdminStates.waiting_for_admin_telegram_id)
async def process_admin_telegram_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        admin_id = int(message.text.strip())
        
        try:
            admin_user = await bot.get_chat(admin_id)
            admin_username = admin_user.username
            admin_name = admin_user.first_name
        except:
            admin_username = None
            admin_name = f"Admin {admin_id}"
        
        await state.update_data(
            admin_id=admin_id,
            admin_username=admin_username,
            admin_name=admin_name
        )
        
        await message.answer(
            f"✅ Admin ID qabul qilindi: {admin_id}\n\n"
            f"4-qadam: Admin uchun foizni kiriting (80-95%):",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="95"), KeyboardButton(text="90")],
                    [KeyboardButton(text="85"), KeyboardButton(text="80")],
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(SuperAdminStates.waiting_for_admin_percent)
        
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Admin ID raqam bo'lishi kerak.")

@dp.message(SuperAdminStates.waiting_for_admin_percent)
async def process_admin_percent(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        admin_percent = float(message.text.strip())
        
        if admin_percent < 80 or admin_percent > 95:
            await message.answer("❌ Foiz 80% dan 95% gacha bo'lishi kerak! Qayta kiriting:")
            return
        
        state_data = await state.get_data()
        
        channel_data = {
            "channel_id": state_data['channel_id'],
            "channel_name": state_data['channel_name'],
            "channel_username": state_data['channel_username'],
            "description": state_data.get('description', '')
        }
        
        result = await api_call('/admin/add-channel', 'POST', channel_data, admin_id=message.from_user.id)
        
        if not result.get('success'):
            await message.answer("❌ Kanal qo'shishda xatolik yuz berdi!")
            await state.clear()
            return
        
        admin_data = {
            "channel_id": state_data['channel_id'],
            "admin_telegram_id": state_data['admin_id'],
            "admin_username": state_data['admin_username'],
            "admin_name": state_data['admin_name'],
            "commission_percent": admin_percent
        }
        
        result = await api_call('/admin/add-admin', 'POST', admin_data, admin_id=message.from_user.id)
        
        if not result.get('success'):
            await message.answer("❌ Admin qo'shishda xatolik yuz berdi!")
            await state.clear()
            return
        
        await message.answer(
            f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📢 Kanal: {state_data['channel_name']}\n"
            f"🆔 ID: {state_data['channel_id']}\n"
            f"👤 Admin: {state_data['admin_name']} (ID: {state_data['admin_id']})\n"
            f"💰 Foiz: {admin_percent}%\n\n"
            f"Admin endi /start bosganda 'Kanal Boshqaruvi' tugmasini ko'radi.",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        
        try:
            await bot.send_message(
                state_data['admin_id'],
                f"🎉 <b>Tabriklaymiz! Siz kanal admini bo'ldingiz!</b>\n\n"
                f"📢 Kanal: {state_data['channel_name']}\n"
                f"💰 Sizning foizingiz: {admin_percent}%\n\n"
                f"Botdan /start bosing va 'Kanal Boshqaruvi' tugmasini bosing.\n"
                f"Bu yerda kartangizni va narxlarni sozlashingiz mumkin.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending message to new admin: {e}")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.callback_query(F.data == "super_add_admin")
async def super_add_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    result = await api_call('/admin/channels', 'GET', admin_id=user_id)
    
    if not result.get('success'):
        await callback.message.edit_text(
            "❌ Kanallarni yuklashda xatolik!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]
            ])
        )
        await callback.answer()
        return
    
    channels = result.get('channels', [])
    
    if not channels:
        await callback.message.edit_text(
            "❌ Hech qanday aktiv kanal topilmadi!\nAvval kanal qo'shing.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="super_add_channel")],
                [InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")]
            ])
        )
        await callback.answer()
        return
    
    kb = []
    for ch in channels:
        if ch.get('is_active'):
            kb.append([InlineKeyboardButton(
                text=f"📢 {ch.get('channel_name')}",
                callback_data=f"select_channel_for_admin:{ch.get('id')}"
            )])
    kb.append([InlineKeyboardButton(text="↩️ Orqaga", callback_data="superadmin_panel")])
    
    await callback.message.edit_text(
        "👤 <b>YANGI ADMIN QO'SHISH</b>\n\n"
        "Admin tayinlamoqchi bo'lgan kanalingizni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("select_channel_for_admin:"))
async def select_channel_for_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Faqat katta admin!")
        return
    
    channel_id = int(callback.data.split(":")[1])
    await state.update_data(channel_id=channel_id)
    
    await callback.message.edit_text(
        "👤 <b>YANGI ADMIN QO'SHISH</b>\n\n"
        "1-qadam: Admin Telegram ID sini yuboring:\n"
        "<i>Masalan: 123456789</i>",
        parse_mode="HTML"
    )
    await state.set_state(SuperAdminStates.waiting_for_admin_telegram_id)
    await callback.answer()

@dp.message()
async def unhandled_messages(message: Message):
    await message.answer(
        "❌ Tushunarsiz buyruq.\n\n"
        "📌 <b>Mavjud buyruqlar:</b>\n"
        "/start - Botni ishga tushirish\n"
        "/help - Yordam\n"
        "/my_ads - Mening e'lonlarim\n"
        "/new_ad - Yangi e'lon\n"
        "/search - E'lonlarni qidirish\n"
        "/notifications - Xabarlar",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )

# ==================== MAIN ====================
async def main():
    print("\n" + "═"*80)
    print(f"{Colors.GREEN}🤖 BOT ISHGA TUSHIRILMOQDA...{Colors.ENDC}")
    print("═"*80)
    
    health = await api_call('/health', 'GET')
    if health.get('status') == 'ok':
        print_step("API server ishlayapti", "success")
    else:
        print_step(f"API server ishlamayapti! Javob: {health}", "error")
        print_step("Iltimos, avval 'python api.py' ni ishga tushiring", "warning")
        return
    
    try:
        bot_info = await bot.get_me()
        print_step(f"Bot ma'lumotlari:", "info")
        print_step(f"   Nomi: {bot_info.first_name}", "debug")
        print_step(f"   Username: @{bot_info.username}", "debug")
        print_step(f"   ID: {bot_info.id}", "debug")
    except Exception as e:
        print_step(f"Bot ma'lumotlari olinmadi: {e}", "error")
        return
    
    await set_bot_commands()
    
    print("\n" + "═"*80)
    print(f"{Colors.GREEN}🚀 BOT ISHGA TUSHDI!{Colors.ENDC}")
    print("═"*80)
    print(f"\n{Colors.BOLD}📡 BOT MANZILI:{Colors.ENDC}")
    print(f"   Telegram: @{bot_info.username}")
    print(f"\n{Colors.BOLD}🌐 WEBAPP:{Colors.ENDC}")
    print(f"   URL: {WEBAPP_URL}")
    print(f"\n{Colors.BOLD}🔌 API:{Colors.ENDC}")
    print(f"   URL: {API_URL}")
    print(f"\n{Colors.BOLD}👑 ADMINLAR:{Colors.ENDC}")
    print(f"   IDlar: {ADMIN_IDS}")
    print("\n" + "═"*80)
    print(f"{Colors.GREEN}📌 YANGI FUNKSIYALAR:{Colors.ENDC}")
    print("   ✅ Kanalga e'lon yuborish")
    print("   ✅ Qidiruv (/search)")
    print("   ✅ Push-xabarlar (/notifications)")
    print("   ✅ Pagination (10 ta e'lon/sahifa)")
    print("   ✅ E'lon muddati eslatmalari")
    print("\n" + "═"*80)
    print(f"{Colors.WARNING}⏹ To'xtatish uchun: Ctrl+C{Colors.ENDC}")
    print("═"*80 + "\n")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
