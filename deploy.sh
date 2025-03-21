#!/bin/bash

echo "🔄 Деплой бота..."

# Остановим старый процесс (если надо)
pkill -f "main.py"

# Установим зависимости
echo "📦 Установка зависимостей..."
source .venv/bin/activate
pip install -r requirements.txt

# Запуск
echo "🚀 Запуск бота..."
nohup python3 bot/main.py > bot.log 2>&1 &

echo "✅ Бот запущен!"
