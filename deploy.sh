#!/bin/bash

set -e

echo "🔄 Начало процесса деплоя бота (Ubuntu Server без GUI)..."

# Проверка прав администратора
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Требуются права администратора! Запустите с sudo."
    exit 1
fi

# Обновление системы
echo "🔄 Обновление пакетов системы..."
apt-get update
apt-get upgrade -y

# Установка базовых зависимостей
echo "📦 Установка системных зависимостей..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    unzip \
    xvfb \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation \
    libasound2 \
    libxss1 \
    libxtst6 \
    libappindicator3-1 \
    libsecret-1-0

# Установка Google Chrome Headless
if ! command -v google-chrome &> /dev/null; then
    echo "🌐 Установка Chrome Headless..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
    apt-get update
    apt-get install -y google-chrome-stable --no-install-recommends
fi

# Установка Chromedriver
if ! command -v chromedriver &> /dev/null; then
    echo "🔧 Установка chromedriver..."
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
    CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION")
    wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
    unzip chromedriver_linux64.zip
    rm chromedriver_linux64.zip
    mv chromedriver /usr/local/bin/
    chmod +x /usr/local/bin/chromedriver
fi

# Настройка виртуального дисплея
echo "🖥️  Настройка Xvfb..."
if ! pgrep -x "Xvfb" > /dev/null; then
    Xvfb :99 -screen 0 1024x768x16 &> /tmp/xvfb.log &
    export DISPLAY=:99
    echo "export DISPLAY=:99" >> /etc/profile
fi

# Переход в директорию проекта
cd "$(dirname "$0")"

# Создание виртуального окружения
if [ ! -d ".venv" ]; then
    echo "🛠️ Создание виртуального окружения..."
    python3 -m venv .venv
fi

# Остановка старого процесса
if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null; then
        echo "🛑 Остановка старого процесса с PID $OLD_PID..."
        kill $OLD_PID && echo "✅ Старый процесс остановлен."
    fi
    rm bot.pid
fi

# Установка зависимостей Python
echo "📦 Обновление зависимостей Python..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Запуск бота с headless-режимом
echo "🚀 Запуск бота в headless-режиме..."
nohup xvfb-run -a python3 -u bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Деплой успешно завершен!"
echo "📝 Логи: bot.log"
echo "🆔 PID процесса: $(cat bot.pid)"