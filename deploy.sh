#!/bin/bash

# ==================== E'LON BOT DEPLOY SKRIPTI ====================
# Bu skript serverda bir marta ishga tushiriladi

set -e

# Ranglar
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           E'LON BOT - PRODUCTION DEPLOYMENT              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"

# ==================== KONFIGURATSIYA ====================
APP_DIR="/var/www/elonbot"
DOMAIN="your-domain.com"
EMAIL="admin@your-domain.com"

# ==================== FUNKSIYALAR ====================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ==================== 1. SYSTEM UPDATE ====================
log_info "1. Sistem yangilanmoqda..."
apt-get update && apt-get upgrade -y

# ==================== 2. DEPENDENCIES ====================
log_info "2. Kerakli paketlar o'rnatilmoqda..."
apt-get install -y \
    python3 python3-pip python3-venv \
    nginx \
    certbot python3-certbot-nginx \
    git \
    supervisor \
    sqlite3 \
    redis-server \
    fail2ban \
    ufw

# ==================== 3. APP DIRECTORY ====================
log_info "3. App papkasi yaratilmoqda..."
mkdir -p $APP_DIR
cd $APP_DIR

# ==================== 4. VIRTUAL ENVIRONMENT ====================
log_info "4. Virtual environment yaratilmoqda..."
python3 -m venv venv
source venv/bin/activate

# ==================== 5. INSTALL PYTHON PACKAGES ====================
log_info "5. Python paketlar o'rnatilmoqda..."
cat > requirements.txt << 'EOF'
Flask==2.3.3
Flask-CORS==4.0.0
Flask-Limiter==3.5.0
Flask-SQLAlchemy==3.1.1
Flask-JWT-Extended==4.5.2
cryptography==41.0.7
Pillow==10.1.0
python-dotenv==1.0.0
werkzeug==3.0.1
apscheduler==3.10.4
aiogram==3.3.0
aiohttp==3.9.1
gunicorn==21.2.0
EOF

pip install --upgrade pip
pip install -r requirements.txt

# ==================== 6. CREATE DIRECTORIES ====================
log_info "6. Papkalar yaratilmoqda..."
mkdir -p data data/media data/checks logs static

# ==================== 7. COPY FILES ====================
log_info "7. Fayllar nusxalanmoqda..."
# Bu yerda siz fayllarni serverga yuklashingiz kerak
# Masalan: scp api.py user@server:/var/www/elonbot/

# ==================== 8. SET PERMISSIONS ====================
log_info "8. Ruxsatlar berilmoqda..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR
chmod -R 775 $APP_DIR/data
chmod -R 775 $APP_DIR/logs

# ==================== 9. DATABASE INIT ====================
log_info "9. Ma'lumotlar bazasi yaratilmoqda..."
python -c "from api import db, app; app.app_context().push(); db.create_all()"

# ==================== 10. SYSTEMD SERVICES ====================
log_info "10. Systemd servislari o'rnatilmoqda..."

# API service
cat > /etc/systemd/system/elonbot-api.service << 'EOF'
[Unit]
Description=E'lon Bot API Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/elonbot
Environment="PATH=/var/www/elonbot/venv/bin"
EnvironmentFile=/var/www/elonbot/.env
ExecStart=/var/www/elonbot/venv/bin/gunicorn -c gunicorn_config.py api:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Bot service
cat > /etc/systemd/system/elonbot-bot.service << 'EOF'
[Unit]
Description=E'lon Bot Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/elonbot
Environment="PATH=/var/www/elonbot/venv/bin"
EnvironmentFile=/var/www/elonbot/.env
ExecStart=/var/www/elonbot/venv/bin/python /var/www/elonbot/bot.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable elonbot-api
systemctl enable elonbot-bot

# ==================== 11. NGINX CONFIGURATION ====================
log_info "11. Nginx konfiguratsiya qilinmoqda..."

cat > /etc/nginx/sites-available/elonbot << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL will be added by certbot
    
    client_max_body_size 50M;
    
    location / {
        root /var/www/elonbot/static;
        try_files $uri $uri/ /index.html;
        expires 1d;
    }
    
    location /api/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /api/media/ {
        proxy_pass http://127.0.0.1:5000/api/media/;
        expires 30d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/elonbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t

# ==================== 12. SSL CERTIFICATE ====================
log_info "12. SSL sertifikat olinmoqda..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL

# ==================== 13. FIREWALL ====================
log_info "13. Firewall sozlanmoqda..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ==================== 14. FAIL2BAN ====================
log_info "14. Fail2ban sozlanmoqda..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true

[sshd]
enabled = true
EOF

systemctl restart fail2ban

# ==================== 15. START SERVICES ====================
log_info "15. Servislar ishga tushirilmoqda..."
systemctl restart nginx
systemctl start elonbot-api
systemctl start elonbot-bot

# ==================== 16. MONITORING ====================
log_info "16. Monitoring sozlanmoqda..."

# Cron job for backup
cat > /etc/cron.d/elonbot-backup << 'EOF'
0 2 * * * www-data /var/www/elonbot/scripts/backup.sh >> /var/www/elonbot/logs/backup.log 2>&1
0 * * * * www-data /var/www/elonbot/scripts/monitor.sh >> /var/www/elonbot/logs/monitor.log 2>&1
EOF

# ==================== 17. STATUS CHECK ====================
log_info "17. Servis holati tekshirilmoqda..."
echo ""
systemctl status nginx --no-pager
echo ""
systemctl status elonbot-api --no-pager
echo ""
systemctl status elonbot-bot --no-pager

# ==================== COMPLETE ====================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DEPLOYMENT COMPLETED SUCCESSFULLY!           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📌 Website:${NC} https://$DOMAIN"
echo -e "${BLUE}📌 API:${NC} https://$DOMAIN/api/health"
echo -e "${BLUE}📌 Bot:${NC} https://t.me/your_bot_username"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  systemctl status elonbot-api    - Check API status"
echo "  systemctl status elonbot-bot    - Check Bot status"
echo "  journalctl -u elonbot-api -f    - View API logs"
echo "  journalctl -u elonbot-bot -f    - View Bot logs"
echo "  tail -f /var/log/nginx/elonbot_access.log - View access logs"
echo ""