#!/bin/bash

echo "🔄 Деплой бота..."

########################################
# 1. Проверка и установка Python3, pip #
########################################

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python3 не обнаружен. Устанавливаем..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
else
    echo "Python3 уже установлен."
fi

if ! command -v pip3 >/dev/null 2>&1; then
    echo "pip3 не обнаружен. Устанавливаем..."
    sudo apt-get update
    sudo apt-get install -y python3-pip
else
    echo "pip3 уже установлен."
fi

######################################
# 2. Установка зависимостей Selenium #
######################################

# Пример для Google Chrome/Chromedriver.
# Если нужно использовать Firefox, замените браузер и драйвер:
#   sudo apt-get install -y firefox-esr
#   sudo apt-get install -y firefox-geckodriver

# Проверяем, установлен ли Google Chrome
if ! command -v google-chrome >/dev/null 2>&1; then
    echo "Google Chrome не обнаружен. Устанавливаем..."
    # Для Chrome на Ubuntu/Debian может понадобиться добавить репозиторий
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      | sudo tee /etc/apt/sources.list.d/google-chrome.list
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
else
    echo "Google Chrome уже установлен."
fi

# Проверяем, установлен ли chromedriver
if ! command -v chromedriver >/dev/null 2>&1; then
    echo "ChromeDriver не обнаружен. Устанавливаем..."
    sudo apt-get update
    sudo apt-get install -y chromium-chromedriver
    # Иногда пакет chromedriver может ставиться отдельно:
    # sudo apt-get install -y chromedriver
else
    echo "ChromeDriver уже установлен."
fi

##################################
# 3. Создание/активация .venv    #
##################################

# Переход в директорию скрипта (корень проекта)
cd "$(dirname "$0")"

# Проверяем, есть ли виртуальное окружение, если нет — создаём
if [ ! -d ".venv" ]; then
    echo "Виртуальное окружение не найдено. Создаю .venv..."
    python3 -m venv .venv
fi

echo "📦 Активация окружения и установка зависимостей..."
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

####################################################
# 4. Остановка старого процесса, если он запущен   #
####################################################

if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "🛑 Остановка старого процесса с PID $OLD_PID..."
        kill $OLD_PID && echo "✅ Старый процесс остановлен."
    fi
    rm bot.pid
fi

############################
# 5. Запуск бота в фоне    #
############################

echo "🚀 Запуск бота..."
nohup python3 bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Бот запущен! PID сохранён в bot.pid"
