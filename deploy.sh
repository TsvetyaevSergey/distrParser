#!/bin/bash
set -e

# Режим автоматизации для needrestart
export NEEDRESTART_MODE=a
export DEBIAN_FRONTEND=noninteractive

# Логирование всего вывода
exec > >(tee -a deploy.log) 2>&1

echo "🔄 Начало процесса деплоя ($(date))"

# Проверка прав
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Запустите скрипт с sudo!"
    exit 1
fi

# Обход проблем с needrestart
sed -i "/#\$nrconf{restart} = 'i';/s/.*/\$nrconf{restart} = 'a';/" /etc/needrestart/needrestart.conf

# Обновление системы
echo "🔄 Обновление пакетов..."
apt-get update
apt-get -y full-upgrade

# Установка зависимостей
echo "📦 Установка системных пакетов..."
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
    libgbm1 \
    libdrm2

# Установка Chrome
if ! command -v google-chrome &> /dev/null; then
    echo "🌐 Установка Chrome..."
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/googlechrome.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/googlechrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
    apt-get update
    apt-get install -y google-chrome-stable
fi

# Установка chromedriver с улучшенным логированием
install_chromedriver() {
    echo "🔧 Начало установки chromedriver..."
    echo "⚙️ Проверка доступа к Google API..."
    if ! curl -sI https://chromedriver.storage.googleapis.com >/dev/null; then
        echo "❌ Нет доступа к chromedriver.storage.googleapis.com!"
        exit 1
    fi

    CHROME_VERSION=$(google-chrome --version 2>/dev/null | awk '{print $3}')
    if [ -z "$CHROME_VERSION" ]; then
        echo "❌ Не удалось определить версию Chrome!"
        exit 1
    fi
    echo "✅ Версия Chrome: $CHROME_VERSION"

    CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$(echo $CHROME_VERSION | cut -d. -f1)")
    if [ -z "$CHROMEDRIVER_VERSION" ]; then
        echo "❌ Ошибка получения версии chromedriver!"
        exit 1
    fi
    echo "⚙️ Совместимая версия chromedriver: $CHROMEDRIVER_VERSION"

    echo "📥 Скачивание chromedriver..."
    if ! wget --tries=3 --timeout=30 -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"; then
        echo "❌ Ошибка скачивания chromedriver!"
        exit 1
    fi

    echo "📦 Распаковка архива..."
    if ! unzip -o chromedriver_linux64.zip; then
        echo "❌ Ошибка распаковки!"
        rm -f chromedriver_linux64.zip
        exit 1
    fi

    rm -f chromedriver_linux64.zip
    chmod +x chromedriver
    mv chromedriver /usr/local/bin/
    echo "✅ chromedriver установлен в /usr/local/bin/chromedriver"
}

if ! command -v chromedriver &> /dev/null; then
    install_chromedriver
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