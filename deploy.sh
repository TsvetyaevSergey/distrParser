#!/bin/bash
set -e

echo "🔄 Начинается деплой окружения и бота..."

# Переход в директорию скрипта (корень проекта)
cd "$(dirname "$0")"

#############################
# Часть 1. Установка окружения для Selenium (выполняется только один раз)
#############################

# Обновление списка пакетов
echo "Обновление списка пакетов..."
sudo apt update

# Установка необходимых системных пакетов (если не установлены)
echo "Установка необходимых пакетов (python3, pip, unzip, библиотеки)..."
sudo apt install -y python3 python3-pip unzip libnss3 libxss1 libayatana-appindicator3-1 libindicator7

# Установка Google Chrome (если не установлен)
if ! command -v google-chrome > /dev/null 2>&1; then
    echo "Google Chrome не найден. Устанавливаем Google Chrome..."
    wget -nc https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    sudo apt --fix-broken install -y
else
    echo "Google Chrome уже установлен: $(google-chrome --version)"
fi

# Установка chromedriver (если отсутствует)
if [ ! -f /usr/bin/chromedriver ]; then
    CHROME_VERSION="134.0.6998.165"
    echo "Chromedriver не найден. Скачиваем chromedriver для версии $CHROME_VERSION..."
    wget -nc https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip
    echo "Распаковка архива chromedriver-linux64.zip..."
    unzip -o chromedriver-linux64.zip
    # Если файл chromedriver не найден в корне, ищем его в папке chromedriver-linux64
    if [ -f chromedriver ]; then
        DRIVER_PATH="chromedriver"
    elif [ -f chromedriver-linux64/chromedriver ]; then
        DRIVER_PATH="chromedriver-linux64/chromedriver"
    else
        echo "Файл 'chromedriver' не найден после распаковки."
        exit 1
    fi
    echo "Перемещение $DRIVER_PATH в /usr/bin/ и установка прав..."
    sudo mv "$DRIVER_PATH" /usr/bin/chromedriver
    sudo chown root:root /usr/bin/chromedriver
    sudo chmod +x /usr/bin/chromedriver
else
    echo "Chromedriver уже установлен."
fi

# Установка Python-пакетов (установка повторная не повредит)
echo "Установка Python-зависимостей (selenium и webdriver-manager)..."
pip3 install selenium webdriver-manager

#############################
# Часть 2. Деплой бота
#############################

echo "🔄 Деплой бота..."

# Остановка старого процесса бота (если он запущен)
if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null; then
        echo "🛑 Остановка старого процесса с PID $OLD_PID..."
        kill $OLD_PID && echo "✅ Старый процесс остановлен."
    fi
    rm -f bot.pid
fi

# Активация виртуального окружения и установка зависимостей проекта
echo "📦 Активация виртуального окружения и установка зависимостей..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "Виртуальное окружение (.venv) не найдено. Создайте его перед деплоем."
    exit 1
fi

# Запуск бота в фоне и сохранение PID
echo "🚀 Запуск бота..."
nohup python3 bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Бот запущен! PID сохранён в bot.pid"
