#!/bin/bash
set -e

echo "🔄 Начало процесса деплоя бота (Ubuntu Server без GUI)..."

# Проверка прав администратора
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Запустите скрипт с sudo!"
    exit 1
fi

# Обновление системы
echo "🔄 Обновление пакетов..."
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
    libasound2t64 \
    fonts-liberation \
    libxss1 \
    libxtst6 \
    libappindicator3-1 \
    libsecret-1-0 \
    libgbm1 \
    libdrm2

# Установка Google Chrome
if ! command -v google-chrome &> /dev/null; then
    echo "🌐 Установка Chrome..."
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/googlechrome.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
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

# Настройка Xvfb
echo "🖥️  Настройка виртуального дисплея..."
if ! pgrep -x "Xvfb" > /dev/null; then
    Xvfb :99 -screen 0 1024x768x16 &> /tmp/xvfb.log &
    echo "export DISPLAY=:99" >> /etc/profile
    source /etc/profile
fi

# Рабочая директория
cd "$(dirname "$0")"

# Виртуальное окружение
if [ ! -d ".venv" ]; then
    echo "🛠️ Создание виртуального окружения..."
    python3 -m venv .venv
fi

# Остановка предыдущего процесса
if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null; then
        echo "🛑 Остановка процесса $OLD_PID..."
        kill $OLD_PID
    fi
    rm bot.pid
fi

# Установка зависимостей
echo "📦 Установка Python-зависимостей..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Запуск бота
echo "🚀 Запуск бота..."
nohup xvfb-run -a python3 -u bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Готово! PID: $(cat bot.pid), логи: bot.log"