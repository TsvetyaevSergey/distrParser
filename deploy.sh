#!/bin/bash
set -e

echo "🔄 Начинается деплой окружения и бота..."

# Переход в директорию скрипта (корень проекта)
cd "$(dirname "$0")"

#############################
# Часть 0. Проверка и установка Python 3.10 (3.10.12)
#############################
if ! command -v python3.10 > /dev/null 2>&1; then
    echo "Python 3.10 не найден. Добавляем репозиторий deadsnakes и устанавливаем Python 3.10 и python3.10-venv..."
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y python3.10 python3.10-venv
else
    PY_VER=$(python3.10 --version 2>&1)
    echo "Найден $PY_VER"
    # Можно добавить проверку версии, если нужно именно 3.10.12
fi

#############################
# Часть 1. Установка окружения для Selenium (устанавливается один раз)
#############################

echo "Обновление списка пакетов..."
sudo apt update

echo "Установка необходимых пакетов (python3, pip, unzip, библиотеки)..."
sudo apt install -y python3 python3-pip unzip libnss3 libxss1 libayatana-appindicator3-1 libindicator7

# Установка Google Chrome, если не установлен
if ! command -v google-chrome > /dev/null 2>&1; then
    echo "Google Chrome не найден. Устанавливаем Google Chrome..."
    wget -nc https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install -y ./google-chrome-stable_current_amd64.deb
    sudo apt --fix-broken install -y
else
    echo "Google Chrome уже установлен: $(google-chrome --version)"
fi

# Установка chromedriver, если не установлен
if [ ! -f /usr/bin/chromedriver ]; then
    CHROME_VERSION="134.0.6998.165"
    echo "Chromedriver не найден. Скачиваем chromedriver для версии $CHROME_VERSION..."
    wget -nc https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip
    echo "Распаковка архива chromedriver-linux64.zip..."
    unzip -o chromedriver-linux64.zip
    # Если файл chromedriver не найден в корневой директории, ищем его в подпапке
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

echo "Установка Python-зависимостей (selenium и webdriver-manager)..."
pip3 install selenium webdriver-manager --break-system-packages

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

# Проверка и создание виртуального окружения с использованием python3.10
if [ -d ".venv" ]; then
    if [ -f ".venv/bin/activate" ]; then
        echo "📦 Активация виртуального окружения..."
        source .venv/bin/activate
        VENV_PYTHON="python"
    else
        echo "⚠️ Файл активации (.venv/bin/activate) не найден. Используем .venv/bin/python3.10 напрямую."
        VENV_PYTHON=".venv/bin/python3.10"
    fi
else
    echo "Виртуальное окружение (.venv) не найдено. Создаем его с помощью Python 3.10..."
    python3.10 -m venv .venv
    if [ -f ".venv/bin/activate" ]; then
        echo "📦 Активация виртуального окружения..."
        source .venv/bin/activate
        VENV_PYTHON="python"
    else
        echo "⚠️ Файл активации не найден. Используем .venv/bin/python3.10 напрямую."
        VENV_PYTHON=".venv/bin/python3.10"
    fi
fi

echo "Обновление pip и установка зависимостей проекта..."
$VENV_PYTHON -m pip install --upgrade pip --break-system-packages
$VENV_PYTHON -m pip install -r requirements.txt --break-system-packages

echo "🚀 Запуск бота..."
nohup $VENV_PYTHON bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Бот запущен! PID сохранён в bot.pid"
