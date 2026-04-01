#!/bin/bash

# Ma'lumotlar bazasini backup qilish skripti

BACKUP_DIR="backups"
DB_PATH="data/elon_bot.db"
DATE=$(date +"%Y%m%d_%H%M%S")

# Backup papkasini yaratish
mkdir -p $BACKUP_DIR

# Database backup
if [ -f "$DB_PATH" ]; then
    cp $DB_PATH "$BACKUP_DIR/elon_bot_$DATE.db"
    echo "✅ Database backup: $BACKUP_DIR/elon_bot_$DATE.db"
    
    # 7 kundan eski backuplarni o'chirish
    find $BACKUP_DIR -name "elon_bot_*.db" -mtime +7 -delete
    echo "🗑️ 7 kundan eski backuplar o'chirildi"
else
    echo "❌ Database topilmadi: $DB_PATH"
fi

# Media fayllarni backup
if [ -d "data/media" ]; then
    tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" data/media/
    echo "✅ Media backup: $BACKUP_DIR/media_$DATE.tar.gz"
fi

# Chek rasmlarini backup
if [ -d "data/checks" ]; then
    tar -czf "$BACKUP_DIR/checks_$DATE.tar.gz" data/checks/
    echo "✅ Checks backup: $BACKUP_DIR/checks_$DATE.tar.gz"
fi

echo ""
echo "📊 Backup statistikasi:"
du -sh $BACKUP_DIR