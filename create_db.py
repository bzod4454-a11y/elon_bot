# create_db.py
# create_db.py
import sqlite3
import os

def create_database():
    db_path = r"C:\Users\ADMIN\Desktop\elon_bot\data\elon_bot.db"
    
    print(f"Creating database at: {db_path}")
    
    # Papka mavjudligini tekshirish va yaratish
    data_dir = os.path.dirname(db_path)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        print(f"✅ Created directory: {data_dir}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Users table
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
        
        # Channels table
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
        
        # Channel admins table
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Ads table
        cursor.execute('''
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Payments table
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Admin verifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER NOT NULL,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_user_id ON ads(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_channel_id ON ads(channel_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status)")
        
        conn.commit()
        print("✅ All tables created successfully!")
        
        # Verify tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\n📋 Tables in database:")
        for table in tables:
            print(f"   - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_database()
    print("\n" + "="*50)
    print("Run: python api.py")
    print("="*50)