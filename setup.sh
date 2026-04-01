#!/bin/bash

# E'lon Bot o'rnatish skripti

set -e

echo "🚀 E'LON BOT O'RNATISH SKRIPTI"
echo "================================"

# Python tekshirish
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 topilmadi!"
    exit 1
fi

echo "✅ Python3 topildi: $(python3 --version)"

# Pip tekshirish
if ! command -v pip3 &> /dev/null; then
    echo "❌ Pip3 topilmadi!"
    exit 1
fi

echo "✅ Pip3 topildi: $(pip3 --version)"

# Virtual environment yaratish
echo ""
echo "📦 Virtual environment yaratilmoqda..."
python3 -m venv venv
source venv/bin/activate

# Kutubxonalarni o'rnatish
echo ""
echo "📚 Kutubxonalar o'rnatilmoqda..."
pip install --upgrade pip
pip install -r requirements.txt

# Papkalarni yaratish
echo ""
echo "📁 Papkalar yaratilmoqda..."
mkdir -p data/media data/checks logs static

# .env faylini tekshirish
if [ ! -f .env ]; then
    echo ""
    echo "⚠️ .env fayli topilmadi!"
    echo "Namuna fayldan nusxa olish: cp .env.example .env"
    echo "Keyin .env faylini tahrirlang va qayta ishga tushiring."
    exit 1
fi

echo ""
echo "✅ O'rnatish tugallandi!"
echo ""
echo "🚀 Ishga tushirish:"
echo "   API server: python api.py"
echo "   Telegram bot: python bot.py"
echo "   Yoki: make run-all"
echo ""
echo "📝 .env faylini tekshirishni unutmang!"