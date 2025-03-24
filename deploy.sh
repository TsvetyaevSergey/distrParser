#!/bin/bash

echo "🔄 Начало процесса деплоя бота..."

# Проверка прав администратора
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  Требуются права администратора! Запустите с sudo."
    exit 1
fi

# Определение дистрибутива
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo "❌ Не удалось определить дистрибутив!"
    exit 1
fi

# Установка Python3 и pip3
if ! command -v python3 &> /dev/null; then
    echo "🐍 Установка Python3..."
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y python3 python3-pip python3-venv
            ;;
        centos|rhel|fedora)
            yum install -y python3 python3-pip
            ;;
        *)
            echo "❌ Неподдерживаемый дистрибутив: $OS"
            exit 1
            ;;
    esac
fi

# Установка системных зависимостей
echo "📦 Установка системных зависимостей..."
case $OS in
    ubuntu|debian)
        apt-get install -y wget unzip xvfb libnss3 libnspr4 \
        libgconf-2-4 libfontconfig1 libxss1 libappindicator3-1 \
        libindicator7 gdebi-core
        ;;
    centos|rhel|fedora)
        yum install -y wget unzip Xvfb nss libXScrnSaver \
        libappindicator-gtk3 liberation-fonts
        ;;
esac

# Установка Google Chrome
if ! command -v google-chrome &> /dev/null; then
    echo "🌐 Установка Chrome..."
    case $OS in
        ubuntu|debian)
            wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
            gdebi -n google-chrome-stable_current_amd64.deb
            rm google-chrome-stable_current_amd64.deb
            ;;
        centos|rhel|fedora)
            wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
            yum install -y ./google-chrome-stable_current_x86_64.rpm
            rm google-chrome-stable_current_x86_64.rpm
            ;;
    esac
fi

# Установка chromedriver
if ! command -v chromedriver &> /dev/null; then
    echo "🔧 Установка chromedriver..."
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
    CHROMEDRIVER_VERSION=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION")
    wget "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
    unzip chromedriver_linux64.zip
    rm chromedriver_linux64.zip
    mv chromedriver /usr/local/bin/
    chmod +x /usr/local/bin/chromedriver
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

# Активация окружения и установка зависимостей
echo "📦 Обновление зависимостей..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Запуск бота
echo "🚀 Запуск бота..."
nohup python3 -u bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Департамент успешно завершен!"
echo "📝 Логи будут сохраняться в bot.log"
echo "🆔 PID процесса: $(cat bot.pid)"