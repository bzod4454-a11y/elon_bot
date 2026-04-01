#!/bin/bash

echo "=========================================="
echo "🚀 E'LON BOT - SERVERGA JOYLASH"
echo "=========================================="

# Virtual environment yaratish
if [ ! -d "venv" ]; then
    echo "📦 Virtual environment yaratilmoqda..."
    python3 -m venv venv
fi

# Virtual environmentni faollashtirish
source venv/bin/activate

# Paketlarni o'rnatish
echo "📦 Paketlar o'rnatilmoqda..."
pip install --upgrade pip
pip install -r requirements.txt

# Papkalarni yaratish
echo "📁 Papkalar yaratilmoqda..."
mkdir -p data data/media data/checks logs

# .env faylini tekshirish
if [ ! -f ".env" ]; then
    echo "⚠️ .env fayli topilmadi! .env.example dan nusxa olinmoqda..."
    cp .env.example .env
    echo "❌ Iltimos, .env faylini tahrirlang va kerakli ma'lumotlarni kiriting!"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ TAYYOR! Bot ishga tushirilmoqda..."
echo "=========================================="
echo ""

# API server va botni bir vaqtda ishga tushirish
python api.py &
python bot.py &

# Ctl+C bosilganda barcha jarayonlarni to'xtatish
trap "kill 0" EXIT

wait
