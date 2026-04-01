#!/bin/bash

# Servis monitoring skripti

API_PORT=5000
BOT_PROCESS="python bot.py"
LOG_FILE="logs/monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
    echo "$1"
}

# API server tekshirish
check_api() {
    if curl -s -f -o /dev/null "http://localhost:$API_PORT/api/health"; then
        log "✅ API server ishlayapti"
        return 0
    else
        log "❌ API server ishlamayapti!"
        return 1
    fi
}

# Bot tekshirish
check_bot() {
    if pgrep -f "$BOT_PROCESS" > /dev/null; then
        log "✅ Bot ishlayapti"
        return 0
    else
        log "❌ Bot ishlamayapti!"
        return 1
    fi
}

# Disk space tekshirish
check_disk() {
    USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $USAGE -gt 90 ]; then
        log "⚠️ Disk bo'sh joy kam: ${USAGE}%"
    else
        log "✅ Disk bo'sh joy yetarli: ${USAGE}%"
    fi
}

# Database size tekshirish
check_db() {
    if [ -f "data/elon_bot.db" ]; then
        SIZE=$(du -h data/elon_bot.db | cut -f1)
        log "📊 Database hajmi: $SIZE"
    fi
}

# Asosiy tekshirish
main() {
    log "==================="
    log "Monitoring tekshiruvi"
    log "==================="
    
    check_api
    check_bot
    check_disk
    check_db
    
    echo ""
}

main