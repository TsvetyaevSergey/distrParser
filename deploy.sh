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
# Часть 1. Деплой бота
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
$VENV_PYTHON -m pip install --upgrade pip
$VENV_PYTHON -m pip install -r requirements.txt

echo "🚀 Запуск бота..."
nohup $VENV_PYTHON bot/main.py > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Бот запущен! PID сохранён в bot.pid"