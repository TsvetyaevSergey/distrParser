#!/bin/bash

echo "🔄 Деплой бота..."

# Переход в директорию скрипта (корень проекта)
cd "$(dirname "$0")"

# Остановим старый процесс (если он был запущен ранее)
if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null; then
        echo "🛑 Остановка старого процесса с PID $OLD_PID..."
        kill $OLD_PID && echo "✅ Старый процесс остановлен."
    fi
    rm bot.pid
fi

# Активация виртуального окружения
echo "📦 Активация окружения и установка зависимостей..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Запуск бота в фоне и сохранение PID
echo "🚀 Запуск бота..."
nohup python3 bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Бот запущен! PID сохранён в bot.pid"
