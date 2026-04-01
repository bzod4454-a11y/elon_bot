"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         E'LON BOT - API SERVER v2.0                          ║
║                                                                               ║
║   Yangi funksiyalar:                                                          ║
║   1. Kanalga e'lon yuborish (publish)                                         ║
║   2. Avtomatik muddat boshqaruvi                                              ║
║   3. Pagination qo'shildi                                                     ║
║   4. Media optimizatsiya (Pillow)                                             ║
║   5. Qidiruv va filtr                                                         ║
║   6. Push-xabarlar                                                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import logging
import uuid
import secrets
import time
import traceback
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from threading import Thread
import atexit
import sqlite3
from io import BytesIO

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

# Media optimizatsiya uchun
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ PIL (Pillow) o'rnatilmagan! Media optimizatsiya ishlamaydi.")
    print("   O'rnatish: pip install Pillow")

load_dotenv()

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

# ==================== KONFIGURATSIYA ====================
PORT = int(os.getenv("PORT", "5000"))
DB_PATH = os.getenv("DB_PATH", "data/elon_bot.db")
CHECKS_DIR = os.getenv("CHECKS_DIR", "data/checks")
MEDIA_DIR = os.getenv("MEDIA_DIR", "data/media")
API_KEY = os.getenv("API_KEY")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "100"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "52428800"))
MAX_PHOTOS_PER_AD = int(os.getenv("MAX_PHOTOS_PER_AD", "10"))
PAYMENT_DAYS = int(os.getenv("PAYMENT_DAYS", "30"))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if admin_ids_str:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
    except ValueError:
        pass

cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = [x.strip() for x in cors_origins_str.split(",") if x.strip()]

# Papkalarni yaratish
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_abs_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)

DB_ABSOLUTE_PATH = get_abs_path(DB_PATH)
CHECKS_ABSOLUTE_DIR = get_abs_path(CHECKS_DIR)
MEDIA_ABSOLUTE_DIR = get_abs_path(MEDIA_DIR)
LOGS_DIR = get_abs_path("logs")

for dir_path in [os.path.dirname(DB_ABSOLUTE_PATH), CHECKS_ABSOLUTE_DIR, MEDIA_ABSOLUTE_DIR, LOGS_DIR]:
    if dir_path:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'api.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['SECRET_KEY'] = JWT_SECRET_KEY or secrets.token_urlsafe(32)
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY or secrets.token_urlsafe(32)
app.config['JWT_TOKEN_LOCATION'] = ['headers']
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_ABSOLUTE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{RATE_LIMIT}/minute"],
    storage_uri="memory://"
)

# CORS
if CORS_ALLOWED_ORIGINS:
    CORS(app, origins=CORS_ALLOWED_ORIGINS, supports_credentials=True)
else:
    CORS(app, supports_credentials=True)

# Shifrlash
cipher = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None

# ==================== MODELLAR ====================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Channel(db.Model):
    __tablename__ = 'channels'
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, unique=True, nullable=False)
    channel_name = db.Column(db.String(200), nullable=False)
    channel_username = db.Column(db.String(100))
    description = db.Column(db.Text)
    is_group = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChannelAdmin(db.Model):
    __tablename__ = 'channel_admins'
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    admin_telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    admin_username = db.Column(db.String(100))
    admin_name = db.Column(db.String(200))
    card_number = db.Column(db.String(500))
    card_holder = db.Column(db.String(200))
    phone_price = db.Column(db.Float, default=10000)
    car_price = db.Column(db.Float, default=20000)
    property_price = db.Column(db.Float, default=30000)
    mixed_price = db.Column(db.Float, default=15000)
    commission_percent = db.Column(db.Float, default=95.0)
    owner_percent = db.Column(db.Float, default=5.0)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    channel = db.relationship('Channel', backref='admins')

class Ad(db.Model):
    __tablename__ = 'ads'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'))
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    tel1 = db.Column(db.String(20))
    tel2 = db.Column(db.String(20))
    telegram_username = db.Column(db.String(100))
    
    # Telefon
    phone_model = db.Column(db.String(100))
    phone_condition = db.Column(db.String(50))
    phone_color = db.Column(db.String(50))
    phone_box = db.Column(db.String(100))
    phone_exchange = db.Column(db.Integer, default=0)
    exchange_phone_model = db.Column(db.String(100))
    
    # Avtomobil
    car_model = db.Column(db.String(100))
    car_year = db.Column(db.Integer)
    car_mileage = db.Column(db.String(50))
    car_fuel_types = db.Column(db.String(200))
    car_amenities = db.Column(db.Text)
    
    # Ko'chmas mulk
    property_type = db.Column(db.String(50))
    property_custom_type = db.Column(db.String(100))
    property_area = db.Column(db.String(50))
    property_yard_area = db.Column(db.String(50))
    property_transaction = db.Column(db.String(50))
    property_amenities = db.Column(db.Text)
    
    # Aralash
    mixed_features = db.Column(db.Text)
    
    # Media
    media_count = db.Column(db.Integer, default=0)
    media_files = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(50), default='pending')
    payment_status = db.Column(db.String(50), default='pending')
    payment_amount = db.Column(db.Float)
    check_image = db.Column(db.String(200))
    channel_admin_id = db.Column(db.Integer, db.ForeignKey('channel_admins.id'))
    commission_percent = db.Column(db.Float, default=95.0)
    owner_percent = db.Column(db.Float, default=5.0)
    admin_verified = db.Column(db.Integer, default=0)
    admin_message = db.Column(db.Text)
    
    # Vaqt
    expires_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    published_message_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='ads')
    channel = db.relationship('Channel', backref='ads')
    channel_admin = db.relationship('ChannelAdmin', backref='ads')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    ad_id = db.Column(db.Integer, db.ForeignKey('ads.id'), nullable=False)
    channel_admin_id = db.Column(db.Integer, db.ForeignKey('channel_admins.id'))
    amount = db.Column(db.Float, nullable=False)
    card_number = db.Column(db.String(500))
    card_holder = db.Column(db.String(200))
    check_image = db.Column(db.String(200))
    status = db.Column(db.String(50), default='pending')
    verified_by = db.Column(db.Integer)
    verified_at = db.Column(db.String(50))
    admin_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ad = db.relationship('Ad', backref='payments')
    channel_admin = db.relationship('ChannelAdmin', backref='payments')

class AdminVerification(db.Model):
    __tablename__ = 'admin_verifications'
    id = db.Column(db.Integer, primary_key=True)
    ad_id = db.Column(db.Integer, db.ForeignKey('ads.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('channel_admins.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ad = db.relationship('Ad', backref='verifications')
    admin = db.relationship('ChannelAdmin', backref='verifications')

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_telegram_id = db.Column(db.Integer, nullable=False)
    ad_id = db.Column(db.Integer, db.ForeignKey('ads.id'))
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text)
    is_sent = db.Column(db.Integer, default=0)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== YORDAMCHI FUNKSIYALAR ====================
def encrypt_card(card_number: str) -> str:
    if not card_number or not cipher:
        return ""
    try:
        return cipher.encrypt(card_number.encode()).decode()
    except:
        return ""

def decrypt_card(encrypted_card: str) -> str:
    if not encrypted_card or not cipher:
        return ""
    try:
        return cipher.decrypt(encrypted_card.encode()).decode()
    except:
        return encrypted_card

def optimize_image(file_bytes, max_size=(1024, 1024), quality=85):
    """Rasmni optimallashtirish"""
    if not PILLOW_AVAILABLE:
        return file_bytes
    
    try:
        img = Image.open(BytesIO(file_bytes))
        
        if img.format == 'PNG' and img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
            img = background
        
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Image optimization error: {e}")
        return file_bytes

def save_media_file(file, category: str, user_id: int) -> dict:
    """Media faylni saqlash va optimallashtirish"""
    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        
        file_bytes = file.read()
        
        if file.content_type.startswith('image/'):
            file_bytes = optimize_image(file_bytes)
        
        filepath = os.path.join(MEDIA_ABSOLUTE_DIR, unique_filename)
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        
        return {
            'filename': unique_filename,
            'url': f'/api/media/{unique_filename}',
            'original_name': original_filename,
            'size': len(file_bytes),
            'mime_type': 'image/jpeg'
        }
    except Exception as e:
        logger.error(f"Error saving media file: {e}")
        return None

def save_check_image(file, ad_id: int) -> str:
    """Chek rasmni saqlash"""
    try:
        original_filename = secure_filename(file.filename)
        unique_filename = f"check_{ad_id}_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        
        file_bytes = file.read()
        
        if file.content_type.startswith('image/'):
            file_bytes = optimize_image(file_bytes, max_size=(800, 800), quality=75)
        
        filepath = os.path.join(CHECKS_ABSOLUTE_DIR, unique_filename)
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        
        return unique_filename
    except Exception as e:
        logger.error(f"Error saving check image: {e}")
        return None

def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> int:
    user = User.query.filter_by(telegram_id=telegram_id).first()
    if user:
        return user.id
    
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name or "User",
        last_name=last_name
    )
    db.session.add(user)
    db.session.commit()
    return user.id

def create_notification(user_telegram_id: int, ad_id: int, type: str, message: str):
    try:
        notification = Notification(
            user_telegram_id=user_telegram_id,
            ad_id=ad_id,
            type=type,
            message=message,
            is_sent=0
        )
        db.session.add(notification)
        db.session.commit()
        logger.info(f"Notification created for user {user_telegram_id}: {type}")
        return notification.id
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None

# ==================== DEKORATORLAR ====================
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != API_KEY:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = request.headers.get('X-Admin-ID') or request.args.get('admin_id')
        if not admin_id:
            return jsonify({'success': False, 'error': 'Admin ID required'}), 403
        try:
            if int(admin_id) not in ADMIN_IDS:
                return jsonify({'success': False, 'error': 'Admin access required'}), 403
        except:
            return jsonify({'success': False, 'error': 'Invalid admin ID'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ==================== API ENDPOINTS ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5/minute")
def auth_login():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return jsonify({'success': False, 'error': 'telegram_id required'}), 400
        
        access_token = create_access_token(identity=str(telegram_id))
        return jsonify({'success': True, 'token': access_token, 'expires_in': 86400})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
@jwt_required()
def auth_verify():
    try:
        user_id = get_jwt_identity()
        return jsonify({'success': True, 'telegram_id': int(user_id)})
    except:
        return jsonify({'success': False, 'error': 'Invalid token'}), 401

@app.route('/api/create-user', methods=['POST'])
@require_api_key
def create_user():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        username = data.get('username')
        first_name = data.get('first_name', 'User')
        last_name = data.get('last_name')
        
        if not telegram_id:
            return jsonify({'success': False, 'error': 'telegram_id required'}), 400
        
        user_id = get_or_create_user(telegram_id, username, first_name, last_name)
        return jsonify({'success': True, 'user_id': user_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/ads', methods=['GET'])
@require_api_key
def get_user_ads():
    try:
        telegram_id = request.args.get('telegram_id')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        if not telegram_id:
            return jsonify({'success': False, 'error': 'telegram_id required'}), 400
        
        user = User.query.filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': True, 'ads': [], 'count': 0, 'page': page, 'total_pages': 0})
        
        pagination = Ad.query.filter_by(user_id=user.id).order_by(Ad.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'waiting_payment': '💳 To\'lov kutilmoqda',
            'active': '✅ Faol',
            'expired': '⌛️ Muddati tugagan',
            'rejected': '❌ Rad etilgan',
            'deleted': '🗑 O\'chirilgan'
        }
        
        category_info = {
            'phone': {'emoji': '📱', 'name': 'Telefon'},
            'car': {'emoji': '🚗', 'name': 'Mashina'},
            'property': {'emoji': '🏠', 'name': 'Ko\'chmas mulk'},
            'mixed': {'emoji': '📦', 'name': 'Aralash'}
        }
        
        result = []
        for ad in pagination.items:
            ad_dict = {
                'id': ad.id,
                'category': ad.category,
                'category_emoji': category_info.get(ad.category, {}).get('emoji', '📦'),
                'category_name': category_info.get(ad.category, {}).get('name', 'E\'lon'),
                'price': ad.price,
                'created_at': ad.created_at.isoformat() if ad.created_at else None,
                'created_date': ad.created_at.strftime('%Y-%m-%d') if ad.created_at else None,
                'status': ad.status,
                'status_text': status_texts.get(ad.status, '❓ Noma\'lum'),
                'channel_name': ad.channel.channel_name if ad.channel else None,
                'title': ad.title,
                'phone_model': ad.phone_model,
                'car_model': ad.car_model,
                'property_type': ad.property_type,
                'status_class': 'status-pending'
            }
            
            if ad.status == 'active':
                ad_dict['status_class'] = 'status-published'
            elif ad.status == 'expired':
                ad_dict['status_class'] = 'status-expired'
            
            if ad_dict['category'] == 'phone' and ad.phone_model:
                ad_dict['display_title'] = ad.phone_model
            elif ad_dict['category'] == 'car' and ad.car_model:
                ad_dict['display_title'] = ad.car_model
            elif ad_dict['category'] == 'property' and ad.property_type:
                ad_dict['display_title'] = ad.property_type
            elif ad_dict['category'] == 'mixed' and ad.title:
                ad_dict['display_title'] = ad.title
            else:
                ad_dict['display_title'] = ad_dict['category_name']
            
            if ad.media_files:
                try:
                    ad_dict['media_files'] = json.loads(ad.media_files)
                except:
                    ad_dict['media_files'] = []
            else:
                ad_dict['media_files'] = []
            
            result.append(ad_dict)
        
        return jsonify({
            'success': True,
            'ads': result,
            'count': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels', methods=['GET'])
@require_api_key
def get_channels():
    try:
        channels = Channel.query.filter_by(is_active=1).all()
        result = []
        for channel in channels:
            admin = ChannelAdmin.query.filter_by(channel_id=channel.id, is_active=1).first()
            channel_dict = {
                'id': channel.id,
                'channel_id': channel.channel_id,
                'channel_name': channel.channel_name,
                'channel_username': channel.channel_username,
                'description': channel.description,
                'is_active': channel.is_active,
                'phone_price': admin.phone_price if admin else 10000,
                'car_price': admin.car_price if admin else 20000,
                'property_price': admin.property_price if admin else 30000,
                'mixed_price': admin.mixed_price if admin else 15000,
                'card_number': bool(admin and admin.card_number),
                'card_holder': admin.card_holder if admin else None,
                'admin_username': admin.admin_username if admin else None
            }
            result.append(channel_dict)
        return jsonify({'success': True, 'channels': result, 'count': len(result)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payment-info/<int:channel_id>', methods=['GET'])
@require_api_key
def get_payment_info(channel_id):
    try:
        admin = ChannelAdmin.query.filter_by(channel_id=channel_id, is_active=1).first()
        channel = Channel.query.filter_by(id=channel_id, is_active=1).first()
        
        if not channel:
            return jsonify({'success': False, 'error': 'Channel not found'}), 404
        
        admin_dict = {
            'admin_id': admin.id if admin else None,
            'channel_id': channel.id,
            'channel_name': channel.channel_name,
            'admin_username': admin.admin_username if admin else None,
            'admin_name': admin.admin_name if admin else None,
            'phone_price': admin.phone_price if admin else 10000,
            'car_price': admin.car_price if admin else 20000,
            'property_price': admin.property_price if admin else 30000,
            'mixed_price': admin.mixed_price if admin else 15000,
            'commission_percent': admin.commission_percent if admin else 95.0,
        }
        
        if admin and admin.card_number:
            try:
                card_number = decrypt_card(admin.card_number)
                admin_dict['card_number'] = card_number
                admin_dict['card_display'] = '**** **** **** ' + card_number[-4:] if len(card_number) >= 4 else card_number
                admin_dict['card_info_status'] = 'available'
            except:
                admin_dict['card_display'] = 'Karta ma\'lumoti xato'
                admin_dict['card_info_status'] = 'error'
        else:
            admin_dict['card_display'] = 'Kiritilmagan'
            admin_dict['card_info_status'] = 'missing'
            admin_dict['card_number'] = None
        
        return jsonify({'success': True, 'payment_info': admin_dict})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ad/<int:ad_id>', methods=['GET'])
@require_api_key
def get_ad_details(ad_id):
    try:
        ad = Ad.query.get(ad_id)
        if not ad:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        status_texts = {
            'pending': '⏳ Kutilmoqda',
            'waiting_payment': '💳 To\'lov kutilmoqda',
            'active': '✅ Faol',
            'expired': '⌛️ Muddati tugagan',
            'rejected': '❌ Rad etilgan',
            'deleted': '🗑 O\'chirilgan'
        }
        
        category_names = {
            'phone': 'Telefon',
            'car': 'Mashina',
            'property': "Ko'chmas mulk",
            'mixed': 'Aralash'
        }
        
        ad_dict = {
            'id': ad.id,
            'category': ad.category,
            'category_name': category_names.get(ad.category, ad.category),
            'price': ad.price,
            'location': ad.location,
            'tel1': ad.tel1,
            'telegram_username': ad.telegram_username,
            'status': ad.status,
            'status_text': status_texts.get(ad.status, '❓ Noma\'lum'),
            'status_class': 'status-pending',
            'created_at': ad.created_at.isoformat() if ad.created_at else None,
            'created_date': ad.created_at.strftime('%Y-%m-%d') if ad.created_at else None,
            'published_at': ad.published_at.isoformat() if ad.published_at else None,
            'expires_at': ad.expires_at.isoformat() if ad.expires_at else None,
            'payment_amount': ad.payment_amount,
            'description': ad.description,
            'channel_name': ad.channel.channel_name if ad.channel else None,
            'published_message_id': ad.published_message_id
        }
        
        if ad.status == 'active':
            ad_dict['status_class'] = 'status-published'
        elif ad.status == 'expired':
            ad_dict['status_class'] = 'status-expired'
        
        if ad.category == 'phone':
            ad_dict['phone_model'] = ad.phone_model
            ad_dict['phone_condition'] = ad.phone_condition
            ad_dict['display_title'] = ad.phone_model
        elif ad.category == 'car':
            ad_dict['car_model'] = ad.car_model
            ad_dict['car_year'] = ad.car_year
            ad_dict['display_title'] = ad.car_model
        elif ad.category == 'property':
            ad_dict['property_type'] = ad.property_type
            ad_dict['property_area'] = ad.property_area
            ad_dict['display_title'] = ad.property_type
        elif ad.category == 'mixed':
            ad_dict['title'] = ad.title
            ad_dict['display_title'] = ad.title
        
        if ad.media_files:
            try:
                ad_dict['media_files'] = json.loads(ad.media_files)
            except:
                ad_dict['media_files'] = []
        else:
            ad_dict['media_files'] = []
        
        return jsonify({'success': True, 'ad': ad_dict})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-ad', methods=['POST'])
@require_api_key
def create_ad():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON'}), 400
        
        telegram_id = data.get('user_id') or data.get('telegram_id')
        ad_data = data.get('data', {})
        
        if not telegram_id or not ad_data:
            return jsonify({'success': False, 'error': 'Missing required data'}), 400
        
        user = User.query.filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=data.get('username'),
                first_name=data.get('first_name', 'User'),
                last_name=data.get('last_name')
            )
            db.session.add(user)
            db.session.flush()
        
        channel_id = ad_data.get('selected_channel', {}).get('id')
        if not channel_id:
            return jsonify({'success': False, 'error': 'Channel not selected'}), 400
        
        admin = ChannelAdmin.query.filter_by(channel_id=channel_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Channel admin not found'}), 400
        
        category = ad_data.get('category')
        if category == 'phone':
            payment_amount = admin.phone_price or 10000
        elif category == 'car':
            payment_amount = admin.car_price or 20000
        elif category == 'property':
            payment_amount = admin.property_price or 30000
        else:
            payment_amount = admin.mixed_price or 15000
        
        if category == 'phone':
            title = ad_data.get('phone_model')
        elif category == 'car':
            title = ad_data.get('car_model')
        elif category == 'property':
            title = ad_data.get('property_type')
        else:
            title = ad_data.get('title')
        
        media_files_json = json.dumps(ad_data.get('media_files', []))
        
        ad = Ad(
            user_id=user.id,
            channel_id=channel_id,
            category=category,
            title=title,
            description=ad_data.get('description') or ad_data.get('extra') or '',
            price=float(ad_data.get('price', 0)),
            location=ad_data.get('location'),
            latitude=ad_data.get('latitude'),
            longitude=ad_data.get('longitude'),
            tel1=ad_data.get('tel1'),
            tel2=ad_data.get('tel2'),
            telegram_username=ad_data.get('telegram_username'),
            phone_model=ad_data.get('phone_model'),
            phone_condition=ad_data.get('condition'),
            phone_color=ad_data.get('color'),
            phone_box=ad_data.get('box'),
            phone_exchange=1 if ad_data.get('exchange') == 'ha' else 0,
            exchange_phone_model=ad_data.get('exchange_phone_model'),
            car_model=ad_data.get('car_model'),
            car_year=ad_data.get('year'),
            car_mileage=ad_data.get('mileage'),
            car_fuel_types=','.join(ad_data.get('fuel_types', [])) if isinstance(ad_data.get('fuel_types'), list) else ad_data.get('fuel_types'),
            car_amenities=json.dumps(ad_data.get('amenities', [])) if ad_data.get('amenities') else None,
            property_type=ad_data.get('property_type'),
            property_custom_type=ad_data.get('custom_type'),
            property_area=ad_data.get('area'),
            property_yard_area=ad_data.get('yard_area'),
            property_transaction=ad_data.get('transaction'),
            property_amenities=json.dumps(ad_data.get('amenities', [])) if category == 'property' else None,
            mixed_features=json.dumps(ad_data.get('features', [])) if category == 'mixed' else None,
            media_count=len(ad_data.get('media_files', [])),
            media_files=media_files_json,
            status='waiting_payment',
            payment_status='pending',
            payment_amount=payment_amount,
            channel_admin_id=admin.id,
            commission_percent=admin.commission_percent,
            owner_percent=admin.owner_percent,
            expires_at=datetime.utcnow() + timedelta(days=PAYMENT_DAYS)
        )
        
        db.session.add(ad)
        
        payment = Payment(
            ad_id=ad.id,
            channel_admin_id=admin.id,
            amount=payment_amount,
            status='pending'
        )
        db.session.add(payment)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Ad created successfully',
            'ad_id': ad.id,
            'payment_amount': payment_amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ad/<int:ad_id>/delete', methods=['POST'])
@require_api_key
def delete_ad(ad_id):
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        user = User.query.filter_by(telegram_id=user_id).first()
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        ad = Ad.query.filter_by(id=ad_id, user_id=user.id).first()
        if not ad:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        ad.status = 'deleted'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Ad deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-check', methods=['POST'])
@require_api_key
def upload_check():
    try:
        ad_id = request.form.get('ad_id')
        if not ad_id:
            return jsonify({'success': False, 'error': 'ad_id required'}), 400
        
        if 'check_image' not in request.files:
            return jsonify({'success': False, 'error': 'check_image file required'}), 400
        
        file = request.files['check_image']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not file.content_type.startswith('image/'):
            return jsonify({'success': False, 'error': 'File must be an image'}), 400
        
        unique_filename = save_check_image(file, ad_id)
        if not unique_filename:
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500
        
        ad = Ad.query.get(ad_id)
        if ad:
            ad.check_image = unique_filename
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Check uploaded successfully',
            'check_image': unique_filename,
            'url': f'/api/media/checks/{unique_filename}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-media', methods=['POST'])
@require_api_key
def upload_media():
    try:
        category = request.form.get('category', 'general')
        user_id = request.form.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if 'media' not in request.files:
            return jsonify({'success': False, 'error': 'media file required'}), 400
        
        file = request.files['media']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        saved_file = save_media_file(file, category, user_id)
        if not saved_file:
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500
        
        return jsonify({'success': True, 'file': saved_file})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/media/<filename>', methods=['GET'])
def serve_media(filename):
    try:
        if '..' in filename or filename.startswith('/'):
            abort(403)
        return send_from_directory(MEDIA_ABSOLUTE_DIR, filename)
    except:
        abort(404)

@app.route('/api/media/checks/<filename>', methods=['GET'])
def serve_check(filename):
    try:
        if '..' in filename or filename.startswith('/'):
            abort(403)
        return send_from_directory(CHECKS_ABSOLUTE_DIR, filename)
    except:
        abort(404)

@app.route('/api/publish-ad/<int:ad_id>', methods=['POST'])
@require_api_key
def publish_ad(ad_id):
    try:
        data = request.get_json() or {}
        admin_telegram_id = data.get('admin_telegram_id')
        
        if not admin_telegram_id:
            return jsonify({'success': False, 'error': 'admin_telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Admin not found'}), 403
        
        ad = Ad.query.filter_by(id=ad_id, channel_admin_id=admin.id).first()
        if not ad:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        if ad.status == 'active':
            return jsonify({'success': False, 'error': 'Ad already published'}), 400
        
        ad.status = 'active'
        ad.published_at = datetime.utcnow()
        ad.admin_verified = 1
        db.session.commit()
        
        verification = AdminVerification(
            ad_id=ad.id,
            admin_id=admin.id,
            action='publish',
            message='E\'lon kanalga nashr qilindi'
        )
        db.session.add(verification)
        db.session.commit()
        
        user = User.query.get(ad.user_id)
        if user:
            create_notification(
                user_telegram_id=user.telegram_id,
                ad_id=ad.id,
                type='approved',
                message=f"E'loningiz #{ad.id} tasdiqlandi va kanalda nashr qilindi!"
            )
        
        return jsonify({
            'success': True,
            'message': 'Ad published successfully',
            'ad_id': ad.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search-ads', methods=['GET'])
@require_api_key
def search_ads():
    try:
        query = request.args.get('q', '')
        category = request.args.get('category')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        location = request.args.get('location')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        ads_query = Ad.query.filter(Ad.status == 'active')
        
        if query:
            ads_query = ads_query.filter(
                db.or_(
                    Ad.title.ilike(f'%{query}%'),
                    Ad.description.ilike(f'%{query}%'),
                    Ad.phone_model.ilike(f'%{query}%'),
                    Ad.car_model.ilike(f'%{query}%')
                )
            )
        
        if category:
            ads_query = ads_query.filter(Ad.category == category)
        
        if min_price:
            ads_query = ads_query.filter(Ad.price >= min_price)
        
        if max_price:
            ads_query = ads_query.filter(Ad.price <= max_price)
        
        if location:
            ads_query = ads_query.filter(Ad.location.ilike(f'%{location}%'))
        
        pagination = ads_query.order_by(Ad.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = []
        for ad in pagination.items:
            title = ad.title or ad.phone_model or ad.car_model or ad.property_type or 'E\'lon'
            result.append({
                'id': ad.id,
                'category': ad.category,
                'title': title,
                'price': ad.price,
                'location': ad.location,
                'created_at': ad.created_at.isoformat() if ad.created_at else None
            })
        
        return jsonify({
            'success': True,
            'ads': result,
            'count': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications/<int:telegram_id>', methods=['GET'])
@require_api_key
def get_notifications(telegram_id):
    try:
        notifications = Notification.query.filter_by(
            user_telegram_id=telegram_id,
            is_sent=0
        ).order_by(Notification.created_at.desc()).limit(50).all()
        
        result = []
        for n in notifications:
            result.append({
                'id': n.id,
                'type': n.type,
                'message': n.message,
                'ad_id': n.ad_id,
                'created_at': n.created_at.isoformat() if n.created_at else None
            })
        
        return jsonify({'success': True, 'notifications': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notifications/mark-read/<int:notification_id>', methods=['POST'])
@require_api_key
def mark_notification_read(notification_id):
    try:
        notification = Notification.query.get(notification_id)
        if notification:
            notification.is_sent = 1
            notification.sent_at = datetime.utcnow()
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/stats', methods=['GET'])
@require_api_key
@require_admin
def admin_stats():
    try:
        from sqlalchemy import func
        
        total_users = User.query.count()
        total_channels = Channel.query.filter_by(is_active=1).count()
        total_admins = ChannelAdmin.query.filter_by(is_active=1).count()
        total_ads = Ad.query.count()
        active_ads = Ad.query.filter_by(status='active').count()
        pending_ads = Ad.query.filter_by(status='pending').count()
        waiting_payment = Ad.query.filter_by(status='waiting_payment').count()
        rejected_ads = Ad.query.filter_by(status='rejected').count()
        expired_ads = Ad.query.filter_by(status='expired').count()
        
        total_income = db.session.query(func.sum(Ad.payment_amount)).filter(
            Ad.status.in_(['active', 'expired'])
        ).scalar() or 0
        
        daily_stats = db.session.query(
            func.date(Ad.created_at).label('date'),
            func.count(Ad.id).label('count')
        ).filter(
            Ad.created_at >= func.date('now', '-7 days')
        ).group_by(func.date(Ad.created_at)).all()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'total_channels': total_channels,
                'total_admins': total_admins,
                'total_ads': total_ads,
                'active_ads': active_ads,
                'pending_ads': pending_ads,
                'waiting_payment': waiting_payment,
                'rejected_ads': rejected_ads,
                'expired_ads': expired_ads,
                'total_income': total_income,
                'active_channels': total_channels,
                'active_admins': total_admins
            },
            'daily_stats': [{'date': str(d.date), 'count': d.count} for d in daily_stats]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/channels', methods=['GET'])
@require_api_key
@require_admin
def admin_channels():
    try:
        channels = Channel.query.order_by(Channel.created_at.desc()).all()
        result = []
        for ch in channels:
            admin = ChannelAdmin.query.filter_by(channel_id=ch.id, is_active=1).first()
            ads_count = Ad.query.filter_by(channel_id=ch.id).count()
            
            ch_dict = {
                'id': ch.id,
                'channel_id': ch.channel_id,
                'channel_name': ch.channel_name,
                'channel_username': ch.channel_username,
                'is_active': ch.is_active,
                'ads_count': ads_count,
                'admin_username': admin.admin_username if admin else None,
                'admin_telegram_id': admin.admin_telegram_id if admin else None
            }
            result.append(ch_dict)
        return jsonify({'success': True, 'channels': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/add-channel', methods=['POST'])
@require_api_key
@require_admin
def add_channel():
    try:
        data = request.get_json()
        channel_id = data.get('channel_id')
        channel_name = data.get('channel_name')
        channel_username = data.get('channel_username')
        description = data.get('description', '')
        
        if not channel_id or not channel_name:
            return jsonify({'success': False, 'error': 'Channel ID and name required'}), 400
        
        channel = Channel.query.filter_by(channel_id=channel_id).first()
        if channel:
            channel.channel_name = channel_name
            channel.channel_username = channel_username
            channel.description = description
            channel.is_active = 1
        else:
            channel = Channel(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_username=channel_username,
                description=description,
                is_active=1
            )
            db.session.add(channel)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Channel added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/add-admin', methods=['POST'])
@require_api_key
@require_admin
def add_admin():
    try:
        data = request.get_json()
        channel_id = data.get('channel_id')
        admin_telegram_id = data.get('admin_telegram_id')
        admin_username = data.get('admin_username')
        admin_name = data.get('admin_name')
        commission_percent = data.get('commission_percent', 95)
        owner_percent = 100 - commission_percent
        
        if not channel_id or not admin_telegram_id:
            return jsonify({'success': False, 'error': 'Channel ID and admin ID required'}), 400
        
        channel = Channel.query.filter_by(id=channel_id).first()
        if not channel:
            return jsonify({'success': False, 'error': 'Channel not found'}), 404
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id).first()
        if admin:
            admin.channel_id = channel_id
            admin.admin_username = admin_username
            admin.admin_name = admin_name
            admin.commission_percent = commission_percent
            admin.owner_percent = owner_percent
            admin.is_active = 1
        else:
            admin = ChannelAdmin(
                channel_id=channel_id,
                admin_telegram_id=admin_telegram_id,
                admin_username=admin_username,
                admin_name=admin_name,
                commission_percent=commission_percent,
                owner_percent=owner_percent,
                is_active=1
            )
            db.session.add(admin)
        
        db.session.commit()
        
        create_notification(
            user_telegram_id=admin_telegram_id,
            ad_id=0,
            type='admin_added',
            message=f"Siz {channel.channel_name} kanaliga admin qilib tayinlandingiz!"
        )
        
        return jsonify({'success': True, 'message': 'Admin added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/admins', methods=['GET'])
@require_api_key
@require_admin
def get_admins():
    try:
        admins = ChannelAdmin.query.filter_by(is_active=1).all()
        result = []
        for admin in admins:
            channel = Channel.query.get(admin.channel_id)
            total_ads = Ad.query.filter_by(channel_admin_id=admin.id).count()
            active_ads = Ad.query.filter_by(channel_admin_id=admin.id, status='active').count()
            
            result.append({
                'id': admin.id,
                'admin_telegram_id': admin.admin_telegram_id,
                'admin_username': admin.admin_username,
                'admin_name': admin.admin_name,
                'channel_name': channel.channel_name if channel else None,
                'channel_id': admin.channel_id,
                'commission_percent': admin.commission_percent,
                'is_active': admin.is_active,
                'card_number': bool(admin.card_number),
                'total_ads': total_ads,
                'active_ads': active_ads
            })
        return jsonify({'success': True, 'admins': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/income', methods=['GET'])
@require_api_key
@require_admin
def get_income_stats():
    try:
        from sqlalchemy import func
        
        monthly_income = db.session.query(
            func.strftime('%Y-%m', Ad.created_at).label('month'),
            func.sum(Ad.payment_amount).label('total_amount'),
            func.count(Ad.id).label('ads_count')
        ).filter(
            Ad.status.in_(['active', 'expired']),
            Ad.created_at >= func.date('now', '-6 months')
        ).group_by(func.strftime('%Y-%m', Ad.created_at)).all()
        
        category_income = db.session.query(
            Ad.category,
            func.sum(Ad.payment_amount).label('total'),
            func.count(Ad.id).label('count')
        ).filter(
            Ad.status.in_(['active', 'expired'])
        ).group_by(Ad.category).all()
        
        return jsonify({
            'success': True,
            'monthly_income': [{'month': m.month, 'total_amount': m.total_amount or 0, 'ads_count': m.ads_count} for m in monthly_income],
            'category_income': [{'category': c.category, 'total': c.total or 0, 'count': c.count} for c in category_income]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/me', methods=['GET'])
@require_api_key
def get_admin_me():
    try:
        telegram_id = request.args.get('telegram_id')
        if not telegram_id:
            return jsonify({'success': False, 'error': 'telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': True, 'admin': None})
        
        channel = Channel.query.get(admin.channel_id)
        
        return jsonify({
            'success': True,
            'admin': {
                'id': admin.id,
                'channel_id': admin.channel_id,
                'channel_name': channel.channel_name if channel else None,
                'channel_username': channel.channel_username if channel else None,
                'admin_telegram_id': admin.admin_telegram_id,
                'admin_username': admin.admin_username,
                'admin_name': admin.admin_name,
                'card_number': decrypt_card(admin.card_number) if admin.card_number else None,
                'card_holder': admin.card_holder,
                'phone_price': admin.phone_price,
                'car_price': admin.car_price,
                'property_price': admin.property_price,
                'mixed_price': admin.mixed_price,
                'commission_percent': admin.commission_percent,
                'owner_percent': admin.owner_percent,
                'is_active': admin.is_active
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/update-card', methods=['POST'])
@require_api_key
def update_admin_card():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        card_number = data.get('card_number')
        card_holder = data.get('card_holder', '')
        
        if not telegram_id or not card_number:
            return jsonify({'success': False, 'error': 'telegram_id and card_number required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Admin not found'}), 404
        
        admin.card_number = encrypt_card(card_number)
        admin.card_holder = card_holder
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Card updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/update-price', methods=['POST'])
@require_api_key
def update_admin_price():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        price_type = data.get('price_type')
        price = data.get('price')
        
        if not telegram_id or not price_type or price is None:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Admin not found'}), 404
        
        if price_type == 'phone':
            admin.phone_price = float(price)
        elif price_type == 'car':
            admin.car_price = float(price)
        elif price_type == 'property':
            admin.property_price = float(price)
        elif price_type == 'mixed':
            admin.mixed_price = float(price)
        else:
            return jsonify({'success': False, 'error': 'Invalid price type'}), 400
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Price updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/pending-ads', methods=['GET'])
@require_api_key
def get_pending_ads():
    try:
        admin_telegram_id = request.args.get('admin_telegram_id')
        if not admin_telegram_id:
            return jsonify({'success': False, 'error': 'admin_telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': True, 'ads': []})
        
        ads = Ad.query.filter_by(
            channel_admin_id=admin.id,
            status='waiting_payment'
        ).order_by(Ad.created_at.desc()).all()
        
        result = []
        for ad in ads:
            user = User.query.get(ad.user_id)
            result.append({
                'id': ad.id,
                'category': ad.category,
                'title': ad.title or ad.phone_model or ad.car_model or 'E\'lon',
                'price': ad.price,
                'payment_amount': ad.payment_amount,
                'location': ad.location,
                'created_at': ad.created_at.isoformat() if ad.created_at else None,
                'username': user.username if user else None,
                'check_image': ad.check_image,
                'tel1': ad.tel1,
                'telegram_username': ad.telegram_username
            })
        
        return jsonify({'success': True, 'ads': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/approve/<int:ad_id>', methods=['POST'])
@require_api_key
def approve_ad(ad_id):
    try:
        data = request.get_json()
        admin_telegram_id = data.get('admin_telegram_id')
        
        if not admin_telegram_id:
            return jsonify({'success': False, 'error': 'admin_telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Admin not found'}), 404
        
        ad = Ad.query.filter_by(id=ad_id, channel_admin_id=admin.id).first()
        if not ad:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        ad.status = 'pending'
        ad.admin_verified = 1
        db.session.commit()
        
        verification = AdminVerification(
            ad_id=ad.id,
            admin_id=admin.id,
            action='approve',
            message='To\'lov tekshirildi, e\'lon tasdiqlandi'
        )
        db.session.add(verification)
        db.session.commit()
        
        user = User.query.get(ad.user_id)
        if user:
            create_notification(
                user_telegram_id=user.telegram_id,
                ad_id=ad.id,
                type='approved',
                message=f"E'loningiz #{ad.id} tasdiqlandi! Admin tekshiruvidan so'ng kanalda ko'rinadi."
            )
        
        return jsonify({'success': True, 'message': 'Ad approved successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/reject/<int:ad_id>', methods=['POST'])
@require_api_key
def reject_ad(ad_id):
    try:
        data = request.get_json()
        admin_telegram_id = data.get('admin_telegram_id')
        reason = data.get('reason', '')
        
        if not admin_telegram_id:
            return jsonify({'success': False, 'error': 'admin_telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': False, 'error': 'Admin not found'}), 404
        
        ad = Ad.query.filter_by(id=ad_id, channel_admin_id=admin.id).first()
        if not ad:
            return jsonify({'success': False, 'error': 'Ad not found'}), 404
        
        ad.status = 'rejected'
        ad.admin_message = reason
        ad.admin_verified = 1
        db.session.commit()
        
        verification = AdminVerification(
            ad_id=ad.id,
            admin_id=admin.id,
            action='reject',
            message=reason
        )
        db.session.add(verification)
        db.session.commit()
        
        user = User.query.get(ad.user_id)
        if user:
            create_notification(
                user_telegram_id=user.telegram_id,
                ad_id=ad.id,
                type='rejected',
                message=f"E'loningiz #{ad.id} rad etildi!\nSabab: {reason}"
            )
        
        return jsonify({'success': True, 'message': 'Ad rejected successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/channel-stats', methods=['GET'])
@require_api_key
def get_channel_stats():
    try:
        admin_telegram_id = request.args.get('admin_telegram_id')
        if not admin_telegram_id:
            return jsonify({'success': False, 'error': 'admin_telegram_id required'}), 400
        
        admin = ChannelAdmin.query.filter_by(admin_telegram_id=admin_telegram_id, is_active=1).first()
        if not admin:
            return jsonify({'success': True, 'stats': {}})
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        total_ads = Ad.query.filter_by(channel_admin_id=admin.id).count()
        active_ads = Ad.query.filter_by(channel_admin_id=admin.id, status='active').count()
        pending_ads = Ad.query.filter_by(channel_admin_id=admin.id, status='pending').count()
        waiting_payment = Ad.query.filter_by(channel_admin_id=admin.id, status='waiting_payment').count()
        rejected_ads = Ad.query.filter_by(channel_admin_id=admin.id, status='rejected').count()
        
        from sqlalchemy import func
        total_income = db.session.query(func.sum(Ad.payment_amount)).filter(
            Ad.channel_admin_id == admin.id,
            Ad.status.in_(['active', 'expired'])
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_ads': total_ads,
                'active_ads': active_ads,
                'pending_ads': pending_ads,
                'waiting_payment': waiting_payment,
                'rejected_ads': rejected_ads,
                'total_income': total_income
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== SCHEDULER ====================
def cleanup_old_media():
    try:
        cutoff_date = datetime.now() - timedelta(days=30)
        count = 0
        
        if os.path.exists(MEDIA_ABSOLUTE_DIR):
            for filename in os.listdir(MEDIA_ABSOLUTE_DIR):
                filepath = os.path.join(MEDIA_ABSOLUTE_DIR, filename)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff_date:
                        os.remove(filepath)
                        count += 1
                except:
                    pass
        
        if os.path.exists(CHECKS_ABSOLUTE_DIR):
            for filename in os.listdir(CHECKS_ABSOLUTE_DIR):
                filepath = os.path.join(CHECKS_ABSOLUTE_DIR, filename)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff_date:
                        os.remove(filepath)
                        count += 1
                except:
                    pass
        
        if count > 0:
            logger.info(f"Cleaned up {count} old media files")
    except Exception as e:
        logger.error(f"Media cleanup error: {e}")

def expire_old_ads():
    try:
        with app.app_context():
            now = datetime.utcnow()
            expired_ads = Ad.query.filter(
                Ad.status == 'active',
                Ad.expires_at < now
            ).all()
            
            for ad in expired_ads:
                ad.status = 'expired'
                logger.info(f"Expired ad #{ad.id}")
                
                user = User.query.get(ad.user_id)
                if user:
                    create_notification(
                        user_telegram_id=user.telegram_id,
                        ad_id=ad.id,
                        type='expired',
                        message=f"E'loningiz #{ad.id} muddati tugadi! Yangi e'lon joylash uchun /start ni bosing."
                    )
            
            db.session.commit()
            if len(expired_ads) > 0:
                logger.info(f"Expired {len(expired_ads)} ads")
    except Exception as e:
        logger.error(f"Expire ads error: {e}")
        db.session.rollback()

def send_reminders():
    try:
        with app.app_context():
            three_days_later = datetime.utcnow() + timedelta(days=3)
            ads = Ad.query.filter(
                Ad.status == 'active',
                Ad.expires_at <= three_days_later,
                Ad.expires_at > datetime.utcnow()
            ).all()
            
            for ad in ads:
                user = User.query.get(ad.user_id)
                if user:
                    days_left = (ad.expires_at - datetime.utcnow()).days
                    create_notification(
                        user_telegram_id=user.telegram_id,
                        ad_id=ad.id,
                        type='reminder',
                        message=f"E'loningiz #{ad.id} muddati tugashiga {days_left} kun qoldi! Yangilash uchun admin bilan bog'laning."
                    )
            
            if len(ads) > 0:
                logger.info(f"Sent {len(ads)} reminders")
    except Exception as e:
        logger.error(f"Send reminders error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_media, trigger="interval", days=1, id="cleanup_media")
scheduler.add_job(func=expire_old_ads, trigger="interval", hours=6, id="expire_ads")
scheduler.add_job(func=send_reminders, trigger="interval", hours=24, id="send_reminders")
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

# ==================== MAIN ====================
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 E'LON BOT API SERVER v2.0 ISHGA TUSHDI!")
    print("=" * 80)
    print(f"📡 Server: http://localhost:{PORT}")
    print(f"💾 Database: {DB_ABSOLUTE_PATH}")
    print(f"📁 Media: {MEDIA_ABSOLUTE_DIR}")
    print(f"📁 Checks: {CHECKS_ABSOLUTE_DIR}")
    print(f"🔑 API Key: {API_KEY[:20] if API_KEY else '❌'}..." if API_KEY else "🔑 API Key: ❌")
    print(f"👑 Admins: {ADMIN_IDS}")
    print("\n📌 YANGI FUNKSIYALAR:")
    print("   ✅ Kanalga e'lon yuborish (/api/publish-ad/<id>)")
    print("   ✅ Avtomatik muddat boshqaruvi (6 soatda bir marta)")
    print("   ✅ Pagination (20 ta e'lon/sahifa)")
    print("   ✅ Qidiruv va filtr (/api/search-ads)")
    print("   ✅ Push-xabarlar (/api/notifications)")
    print("   ✅ Media optimizatsiya (Pillow)")
    print("=" * 80)
    
    with app.app_context():
        db.create_all()
        print_step("Database tayyor", "success")
    
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
