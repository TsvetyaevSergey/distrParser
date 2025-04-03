import asyncio
import json
import os
import re
import requests
import logging
import time
from bs4 import BeautifulSoup
from packaging.version import Version
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup, User
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from config import URL, TELEGRAM_TOKEN, PRODUCT_BUTTONS, POM_MODULES, POM_BUILD_MODULES, UNIFIED_POM_URLS, MODULES_LIST, \
    RELEASES_JSON_PATH, SUBSCRIPTIONS_JSON_PATH

# Настройка логирования
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(BASE_DIR, "bot.log")
logging.basicConfig(
    filename=LOG_FILE_PATH,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

# Состояния для ConversationHandler
CHOOSE_ACTION, SELECT_MODULE, INPUT_VERSION, INPUT_DESCRIPTION, CHOOSE_VERSION_TYPE = range(5)

def get_user_info(user: User) -> str:
    """Собирает информацию о пользователе в формате: @username Имя Фамилия (id123)"""
    parts = []
    if user.username:
        parts.append(f"@{user.username}")
    if user.full_name.strip():
        parts.append(user.full_name)
    if not parts:  # Если нет ничего, используем ID
        parts.append(f"id{user.id}")
    return " ".join(parts)

def load_releases() -> list:
    try:
        with open(RELEASES_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_releases(data: list) -> None:
    # Удаляем дубликаты перед сохранением
    unique_modules = {}
    for item in data:
        module = item["module"]
        unique_modules[module] = item  # Перезаписываем дубликаты
    with open(RELEASES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(list(unique_modules.values()), f, ensure_ascii=False, indent=2)


def load_subscriptions() -> dict:
    try:
        with open(SUBSCRIPTIONS_JSON_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": []}


def save_subscriptions(data: dict) -> None:
    with open(SUBSCRIPTIONS_JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)


async def toggle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    subs = load_subscriptions()

    if user_id in subs["users"]:
        subs["users"].remove(user_id)
        text = "❌ Вы отписались от рассылки"
    else:
        subs["users"].append(user_id)
        text = "✅ Вы подписались на рассылку"

    save_subscriptions(subs)
    await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subs = load_subscriptions()
    user_id = update.effective_user.id
    sub_button = "Отписаться от рассылки" if user_id in subs["users"] else "Подписаться на рассылку"

    keyboard = [
        ["Добавить релиз модуля", "Получить"],
        [sub_button]
    ]
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSE_ACTION


async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "Получить":
        await update.message.reply_text("Выберите продукт:", reply_markup=FIRST_KEYBOARD)
        return ConversationHandler.END
    elif text == "Добавить релиз модуля":
        modules_keyboard = [MODULES_LIST[i:i + 3] for i in range(0, len(MODULES_LIST), 3)]
        await update.message.reply_text(
            "Выберите модуль:",
            reply_markup=ReplyKeyboardMarkup(modules_keyboard, resize_keyboard=True)
        )
        return SELECT_MODULE
    else:
        # Пропускаем сообщения, которые не относятся к текущему ConversationHandler
        return ConversationHandler.END  # Завершаем текущий диалог


async def select_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    module = update.message.text
    if module not in MODULES_LIST:
        await update.message.reply_text("Неверный модуль. Выберите из списка.")
        return SELECT_MODULE

    context.user_data["module"] = module
    await update.message.reply_text(
        "Введите версию модуля в формате X.Y.Z (например, 1.18.3):\n"
        "❗ Убедитесь, что версия прошла тестирование!"
    )
    return INPUT_VERSION


async def input_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    version = update.message.text.strip()
    if not re.match(r"^\d+(\.\d+){1,3}$", version):
        await update.message.reply_text("❌ Неверный формат версии! Попробуйте снова.")
        return INPUT_VERSION

    context.user_data["version"] = version
    await update.message.reply_text(
        "📝 Введите описание изменений (или нажмите /skip чтобы пропустить):"
    )
    return INPUT_DESCRIPTION


async def notify_subscribers(bot, data: dict) -> None:
    """Улучшенная рассылка с проверкой данных."""
    try:
        # Проверяем наличие обязательных полей
        required_fields = ["module", "version", "timestamp", "user"]
        for field in required_fields:
            if field not in data:
                raise KeyError(f"Отсутствует поле: {field}")

        # Формируем сообщение
        message = (
            f"🚀 Новый релиз модуля {data['module']}!\n"
            f"🔖 Версия: {data['version']}\n"
            f"⏰ Время: {data['timestamp']}\n"
            f"👤 Автор: {data['user']}\n"
        )
        if data.get("description"):
            message += f"📝 Описание: {data['description']}\n"

        # Отправляем уведомления подписчикам
        subs = load_subscriptions()
        for user_id in subs["users"]:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="Markdown"
            )

    except KeyError as e:
        logging.error(f"Ошибка в данных: {str(e)}")
    except Exception as e:
        logging.error(f"Ошибка рассылки: {str(e)}")


async def input_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        description = update.message.text
        context.user_data["description"] = description
        # Добавляем обязательные поля в контекст
        context.user_data["timestamp"] = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        context.user_data["user"] = get_user_info(update.effective_user)  # Не забываем добавить пользователя

        # Логируем данные перед рассылкой
        logging.info(f"Данные контекста: {context.user_data}")
        # Сохранение данных с обновлением существующих записей
        releases = load_releases()
        module_name = context.user_data["module"]

        # Поиск существующей записи
        existing_entry = next((item for item in releases if item["module"] == module_name), None)

        if existing_entry:
            # Обновляем существующую запись
            existing_entry.update({
                "version": context.user_data["version"],
                "description": description,
                "timestamp": (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'),
                "user": get_user_info(update.effective_user)
            })
        else:
            # Добавляем новую запись
            releases.append({
                "module": module_name,
                "version": context.user_data["version"],
                "description": description,
                "timestamp": (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S'),
                "user": get_user_info(update.effective_user)
            })

        save_releases(releases)

        # Рассылка уведомлений
        asyncio.create_task(notify_subscribers(context.bot, context.user_data))

        # Возврат в главное меню
        subs = load_subscriptions()
        user_id = update.effective_user.id
        sub_button = "Отписаться от рассылки" if user_id in subs["users"] else "Подписаться на рассылку"
        keyboard = [
            ["Добавить релиз модуля", "Получить"],
            [sub_button]
        ]
        await update.message.reply_text(
            f"✅ Версия {context.user_data['version']} успешно добавлена!",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка системы. Попробуйте позже.")
        return ConversationHandler.END

def build_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Динамическое построение главного меню."""
    subs = load_subscriptions()
    sub_button = "Отписаться от рассылки" if user_id in subs["users"] else "Подписаться на рассылку"
    return ReplyKeyboardMarkup(
        [
            ["Добавить релиз", "Получить"],
            [sub_button]
        ],
        resize_keyboard=True
    )

# 2. Исправление команды /skip
async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = ""  # Устанавливаем пустое описание
    return await input_description(update, context)


def get_pom_url(module: str, build: bool = False) -> str:
    """
    Возвращает URL для получения версии модуля.
    Ссылки для локального и сборочного pom одинаковые.
    Если build=True и имя модуля начинается с "engdb.", удаляем этот префикс для поиска URL.
    """
    if build:
        if module.startswith("engdb."):
            base = module[len("engdb."):]
            return UNIFIED_POM_URLS.get(base)
        else:
            return UNIFIED_POM_URLS.get(module)
    else:
        return UNIFIED_POM_URLS.get(module)


def build_keyboard(items: list[str], cols: int = 3) -> ReplyKeyboardMarkup:
    rows = [items[i:i + cols] for i in range(0, len(items), cols)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


FIRST_KEYBOARD = build_keyboard(list(PRODUCT_BUTTONS.keys()), cols=3)


def parse_index(url: str) -> dict[str, list[Version]]:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    versions = {}
    for link in soup.select("ul li a[href$='.tar.gz']"):
        href = link.get('href')
        match = re.match(r"^(.+)-(\d+(?:\.\d+)*)\.tar\.gz$", href)
        if match:
            name, ver = match.groups()
            versions.setdefault(name, []).append(Version(ver))
    return {name: sorted(vs) for name, vs in versions.items()}


def parse_pom_version(url: str) -> str:
    """
    Парсит версию из XML (maven-metadata.xml) через lxml.
    Пример URL: https://mvn.cstechnology.ru/releases/ru/cs/engbe/maven-metadata.xml
    """
    # Формируем корректный XML-URL
    xml_url = url.replace("#/", "").rstrip("/") + "/maven-metadata.xml"

    try:
        response = requests.get(xml_url)
        response.raise_for_status()

        # Используем lxml для парсинга XML
        soup = BeautifulSoup(response.text, "lxml-xml")  # Явно указываем парсер
        release_tag = soup.find("release")

        if release_tag and release_tag.text.strip():
            return release_tag.text.strip()

        raise ValueError(f"Тег <release> не найден в {xml_url}")

    except Exception as e:
        logging.error(f"Ошибка при парсинге {xml_url}: {str(e)}")
        raise


async def old_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    user = update.effective_user
    logging.info(f"Пользователь {user.full_name} начал работу через /start")
    await update.message.reply_text("Выберите продукт:", reply_markup=FIRST_KEYBOARD)


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    user_data = context.user_data
    logging.info(f"Пользователь выбрал: {text}")

    if 'pending_pom' in user_data:
        # Обработка выбора типа версий
        if text == "Прошедшие тестирование":
            await send_pom_version(update, user_data['pending_pom']['product'],
                                   user_data['pending_pom']['combination'], True, context)
        elif text == "Новейшие":
            await send_pom_version(update, user_data['pending_pom']['product'],
                                   user_data['pending_pom']['combination'], False, context)
        else:
            await update.message.reply_text("Неверный выбор. Используйте кнопки.")
        del user_data['pending_pom']
        return

    if 'product' not in user_data:
        if text in PRODUCT_BUTTONS:
            print(text)
            user_data['product'] = text
            second_keyboard = build_keyboard(list(PRODUCT_BUTTONS[text].keys()), cols=3)
            await update.message.reply_text(f"{text}: выберите среду:", reply_markup=second_keyboard)
    else:
        print(text + " 222")
        product = user_data.pop('product')
        combination = f"{product} {text}"
        if text in ["DEV", "STAND", "POM"]:
            await send_version(update, text, context=context, combination=combination)
        if text == "POM":
            user_data['pending_pom'] = {
                'product': product,
                'combination': combination
            }
            await update.message.reply_text(
                "Выберите тип версий:",
                reply_markup=ReplyKeyboardMarkup([["Прошедшие тестирование", "Новейшие"]], resize_keyboard=True)
            )
            return CHOOSE_VERSION_TYPE




async def send_version(update: Update, product_key: str, context: ContextTypes.DEFAULT_TYPE, combination: str = None) -> None:
    if not combination:
        combination = product_key
    logging.info(f"Запрошена комбинация: {combination}")

    # Экранируем специальные символы MarkdownV2
    safe_combination = combination.replace(".", r"\.").replace("-", r"\-")

    if product_key == "версия отсутствует":
        message = rf"*Комбинация:* {safe_combination}\nВерсия отсутствует для выбранной комбинации\."
        await update.message.reply_text(message, reply_markup=build_main_menu(update.effective_user.id), parse_mode="MarkdownV2")
        return

    try:
        parsed = parse_index(URL)
        if product_key in parsed:
            latest = parsed[product_key][-1]
            now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

            # Экранируем только для Markdown (не для кодового блока)
            distr_line = f'projectDistr="{product_key}-{latest}"'
            code_block = f"```\n{distr_line}\n```"

            # Экранируем timestamp
            safe_timestamp = now.replace("-", r"\-").replace(":", r"\:")

            message = (
                rf"*Комбинация:* {safe_combination}"
                f"{code_block}\n\n"
                rf"\(актуально на {safe_timestamp} по МСК\)"
            )
        else:
            safe_product_key = product_key.replace(".", r"\.").replace("-", r"\-")
            message = rf"*Комбинация:* {safe_combination} Продукт {safe_product_key} не найден на сервере\."

        logging.info(f"Ответ бота: {message}")
        await update.message.reply_text(message, reply_markup=build_main_menu(update.effective_user.id), parse_mode="MarkdownV2")

    except Exception as e:
        logging.exception("Ошибка при получении данных")
        error_message = f"Ошибка при получении данных: {str(e)}"
        await update.message.reply_text(error_message.replace(".", r"\."), reply_markup=build_main_menu(update.effective_user.id),
                                        parse_mode="MarkdownV2")
    finally:
        context.user_data.clear()



async def send_pom_version(update: Update, product: str, combination: str, use_tested_versions: bool, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.info(f"Запрошена комбинация POM для продукта: {product}")
    if product not in POM_MODULES:
        message = f"Комбинация: {combination}\n\nСборка POM не поддерживается для выбранного продукта."
        await update.message.reply_text(message, reply_markup=build_main_menu(update.effective_user.id))
        return

    await update.message.reply_text("Начинаю сбор информации, подождите, пожалуйста...")
    start_time = time.time()

    try:
        releases = load_releases() if use_tested_versions else []
        version_cache = {}

        # Функция для получения версии из JSON
        def get_tested_version(module_name):
            module_entries = [r for r in releases if r['module'] == module_name]
            if not module_entries:
                return None
            return max(module_entries, key=lambda x: Version(x['version']))['version']

        # Обработка локальных модулей
        local_versions = []
        for module in POM_MODULES[product]:
            base_name = module.replace("engdb.", "", 1)
            version = None

            if use_tested_versions:
                version = get_tested_version(base_name)
                if not version:
                    local_versions.append(f"<{module}.version>Версия не указана в БД</{module}.version>")
                    continue

            if not version:
                url = get_pom_url(module, build=False)
                version = parse_pom_version(url) if url else "URL не задан"

            local_versions.append(f"<{module}.version>{version}</{module}.version>")

        # Обработка сборочных модулей
        build_config = POM_BUILD_MODULES.get(product, {})
        build_lines = ["<properties>", "    <!-- CORE VERSIONS -->"]

        # Общая функция обработки модулей
        def process_modules(module_list, section):
            nonlocal build_lines
            for module in module_list:
                if module == "engdb.help.branch":
                    build_lines.append("    <engdb.help.branch>INSERT NAME</engdb.help.branch>")
                    continue

                base_name = module.replace("engdb.", "", 1)
                version = None

                if use_tested_versions:
                    version = get_tested_version(base_name)
                    if not version:
                        build_lines.append(f"    <{module}.version>Версия не указана в БД</{module}.version>")
                        continue

                if not version:
                    url = get_pom_url(module, build=True)
                    version = parse_pom_version(url) if url else "URL не задан"

                build_lines.append(f"    <{module}.version>{version}</{module}.version>")

        process_modules(build_config.get("CORE", []), "CORE")
        build_lines.append("    <!-- MODULES VERSIONS -->")
        process_modules(build_config.get("MODULES", []), "MODULES")
        build_lines.append("</properties>")

        # Форматирование сообщения
        elapsed = time.time() - start_time
        now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

        safe_combination = combination.replace(".", r"\.").replace("-", r"\-")
        safe_elapsed = f"{elapsed:.2f}".replace(".", r"\.")
        safe_now = now.replace("-", r"\-").replace(":", r"\:")

        message = (
                f"*Комбинация:* {safe_combination}\n\n"
                f"*Для локального pom:*\n```\n" + "\n".join(local_versions) + "\n```\n"
                                                                              f"_Сбор информации заняла {safe_elapsed} секунд_\n"
                                                                              f"\\(актуально на {safe_now} по МСК\\)\n\n"
                                                                              f"*Для создания сборки:*\n```\n" + "\n".join(
            build_lines) + "\n```\n"
                           f"\\(актуально на {safe_now} по МСК\\)"
        )

        await update.message.reply_text(
            message,
            reply_markup=build_main_menu(update.effective_user.id),
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        error_msg = f"Ошибка: {str(e)}".replace(".", r"\.")
        await update.message.reply_text(
            error_msg,
            reply_markup=build_main_menu(update.effective_user.id),
            parse_mode="MarkdownV2"
        )
    finally:
        context.user_data.clear()


def main() -> None:
    logging.info("Запуск бота")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            SELECT_MODULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_module)],
            INPUT_VERSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_version)],
            INPUT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_description),
                CommandHandler("skip", skip_description)
            ],
            CHOOSE_VERSION_TYPE: [
                MessageHandler(filters.Text(["Прошедшие тестирование", "Новейшие"]), handle_choice)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(MessageHandler(
        filters.Text(["Подписаться на рассылку", "Отписаться от рассылки"]),
        toggle_subscription
    ))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))

    app.run_polling()

if __name__ == '__main__':
    main()