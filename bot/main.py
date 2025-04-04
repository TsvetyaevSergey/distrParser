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
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from config import (
    URL,
    TELEGRAM_TOKEN,
    PRODUCT_BUTTONS,
    POM_MODULES,
    POM_BUILD_MODULES,
    UNIFIED_POM_URLS,
    MODULES_LIST,
    RELEASES_JSON_PATH,
    SUBSCRIPTIONS_JSON_PATH,
)

# Настройка логирования
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(BASE_DIR, "bot.log")
logging.basicConfig(
    filename=LOG_FILE_PATH,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    encoding="utf-8",
)

# Состояния
(
    MAIN_MENU,
    ADD_RELEASE_MODULE,
    ADD_RELEASE_VERSION,
    ADD_RELEASE_DESCRIPTION,
    ADD_RELEASE_TYPE,  # Новое состояние
    GET_PROJECT,
    GET_BUILD_TYPE,
    GET_VERSION_TYPE,
) = range(8)


def get_user_info(user: User) -> str:
    parts = []
    if user.username:
        parts.append(f"@{user.username}")
    if user.full_name.strip():
        parts.append(user.full_name)
    return " ".join(parts) if parts else f"id{user.id}"


def load_releases() -> list:
    try:
        with open(RELEASES_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_releases(data: list) -> None:
    # Используем кортеж (module, version_type) как уникальный ключ
    unique_entries = {}
    for item in data:
        key = (item["module"], item["version_type"])
        unique_entries[key] = item
    with open(RELEASES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(list(unique_entries.values()), f, ensure_ascii=False, indent=2)


def load_subscriptions() -> dict:
    try:
        with open(SUBSCRIPTIONS_JSON_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": []}


def save_subscriptions(data: dict) -> None:
    with open(SUBSCRIPTIONS_JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)


def build_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    subs = load_subscriptions()
    sub_button = "Отписаться" if user_id in subs["users"] else "Подписаться"
    return ReplyKeyboardMarkup(
        [["Добавить релиз", "Получить"], [sub_button]], resize_keyboard=True
    )


def build_keyboard(items: list, cols: int = 3) -> ReplyKeyboardMarkup:
    rows = [items[i: i + cols] for i in range(0, len(items), cols)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Главное меню:", reply_markup=build_main_menu(update.effective_user.id)
    )
    return MAIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено")
    return await start(update, context)


# Блок добавления релиза
async def add_release_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = build_keyboard(MODULES_LIST)
    await update.message.reply_text("Выберите модуль:", reply_markup=keyboard)
    return ADD_RELEASE_MODULE


async def add_release_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    module = update.message.text
    if module not in MODULES_LIST:
        await update.message.reply_text("Неверный модуль. Выберите из списка.")
        return ADD_RELEASE_MODULE

    context.user_data["module"] = module
    await update.message.reply_text(
        "Введите версию в формате X.Y.Z:\n❗ Убедитесь в корректности версии!",
        reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True),
    )
    return ADD_RELEASE_VERSION


async def add_release_version(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    version = update.message.text.strip()
    if not re.match(r"^\d+(\.\d+){1,3}$", version):
        await update.message.reply_text("❌ Неверный формат! Попробуйте снова.")
        return ADD_RELEASE_VERSION

    context.user_data["version"] = version
    await update.message.reply_text(
        "Введите описание (или /skip):",
        reply_markup=ReplyKeyboardMarkup([["/skip", "/cancel"]], resize_keyboard=True),
    )
    return ADD_RELEASE_DESCRIPTION


async def add_release_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text
    keyboard = [["Допущен к установке", "Допущен к тестированию"]]
    await update.message.reply_text(
        "Выберите тип релиза:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return ADD_RELEASE_TYPE


async def add_release_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    version_type = update.message.text
    if version_type not in ["Допущен к установке", "Допущен к тестированию"]:
        await update.message.reply_text("Неверный тип. Выберите из списка.")
        return ADD_RELEASE_TYPE

    # Получаем нормализованный тип версии
    normalized_type = version_type.split()[-1].lower()  # "установке" или "тестированию"

    # Проверяем существование версии такого типа
    releases = load_releases()
    existing = next(
        (item for item in releases
         if item["module"] == context.user_data["module"]
         and item["version_type"] == normalized_type),
        None
    )

    # Обновляем или добавляем запись
    if existing:
        existing.update({
            "version": context.user_data["version"],
            "description": context.user_data.get("description", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": get_user_info(update.effective_user)
        })
    else:
        releases.append({
            "module": context.user_data["module"],
            "version": context.user_data["version"],
            "description": context.user_data.get("description", ""),
            "version_type": normalized_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": get_user_info(update.effective_user)
        })

    save_releases(releases)
    await notify_subscribers(context.bot, releases[-1])

    await update.message.reply_text(
        "✅ Релиз добавлен!",
        reply_markup=build_main_menu(update.effective_user.id)
    )
    context.user_data.clear()
    return MAIN_MENU

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = ""
    return await add_release_description(update, context)


async def notify_subscribers(bot, data: dict):
    version_type = "к установке" if data["version_type"] == "установке" else "к тестированию"
    message = (
        f"🚀 Новый релиз {data['module']} v{data['version']} ({version_type})\n"
        f"📅 {data['timestamp']}\n👤 {data['user']}\n"
    )
    if data["description"] != "/skip":
        message += f"📝 {data['description']}"

    subs = load_subscriptions()
    for user_id in subs["users"]:
        await bot.send_message(chat_id=user_id, text=message)


# Блок получения версий
async def get_version_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = build_keyboard(list(PRODUCT_BUTTONS.keys()))
    await update.message.reply_text("Выберите проект:", reply_markup=keyboard)
    return GET_PROJECT


async def get_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    project = update.message.text
    if project not in PRODUCT_BUTTONS:
        await update.message.reply_text("Неверный проект. Выберите из списка.")
        return GET_PROJECT

    context.user_data["project"] = project
    keyboard = build_keyboard(list(PRODUCT_BUTTONS[project].keys()))
    await update.message.reply_text("Выберите сборку:", reply_markup=keyboard)
    return GET_BUILD_TYPE


async def get_build_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    build_type = update.message.text
    project = context.user_data["project"]

    if build_type not in PRODUCT_BUTTONS[project]:
        await update.message.reply_text("Неверная сборка. Выберите из списка.")
        return GET_BUILD_TYPE

    if build_type == "POM":
        # В диалоге выбора сборки (GET_BUILD_TYPE) изменить клавиатуру:
        keyboard = ReplyKeyboardMarkup(
            [["Допущено к установке", "Допущено к тестированию", "Новейший релиз"]],
            resize_keyboard=True
        )
        await update.message.reply_text("Выберите тип версий:", reply_markup=keyboard)
        return GET_VERSION_TYPE

    await send_version(update, context, build_type)
    return MAIN_MENU


async def get_version_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    version_type = update.message.text
    if version_type not in ["Допущено к установке", "Допущено к тестированию", "Новейший релиз"]:
        await update.message.reply_text("Неверный тип. Выберите из списка.")
        return GET_VERSION_TYPE

    await send_pom_version(update, context, version_type)
    return MAIN_MENU


def parse_index(url: str) -> dict[str, list[Version]]:
    response = requests.get(url)
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
    xml_url = url.replace("#/", "").rstrip("/") + "/maven-metadata.xml"
    try:
        response = requests.get(xml_url)
        soup = BeautifulSoup(response.text, "lxml-xml")
        return soup.find("release").text.strip()
    except Exception as e:
        logging.error(f"Ошибка парсинга POM: {str(e)}")
        return "Ошибка получения"


async def send_version(update: Update, context: ContextTypes.DEFAULT_TYPE, build_type: str):
    project = context.user_data["project"]
    combination = f"{project} {build_type}"

    try:
        parsed = parse_index(URL)
        product = PRODUCT_BUTTONS[project][build_type]

        if product in parsed:
            latest = parsed[product][-1]
            timestamp = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

            # Экранируем специальные символы
            safe_combination = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', combination)
            safe_product = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', product)
            safe_latest = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(latest))
            safe_timestamp = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', timestamp)

            message = (
                rf"*Комбинация:* {safe_combination}"
                rf"```\nprojectDistr=\"{safe_product}-{safe_latest}\"```"
                rf"\(актуально на {safe_timestamp} по МСК\)"
            )
        else:
            safe_combination = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', combination)
            message = rf"*Комбинация:* {safe_combination}\nВерсия не найдена"

        await update.message.reply_text(
            message,
            reply_markup=build_main_menu(update.effective_user.id),
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        context.user_data.clear()

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

async def send_pom_version(update: Update, context: ContextTypes.DEFAULT_TYPE, version_type: str):
    project = context.user_data["project"]
    combination = f"{project} POM"
    use_tested_versions = version_type in ["Допущено к установке", "Допущено к тестированию"]
    is_latest = version_type == "Новейший релиз"

    def escape_md(text: str) -> str:
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))

    await update.message.reply_text("Начинаю сбор информации, подождите, пожалуйста...")
    start_time = time.time()

    try:
        # Определяем тип фильтрации
        version_filter = None
        if version_type == "Допущено к установке":
            version_filter = "установке"
        elif version_type == "Допущено к тестированию":
            version_filter = "тестированию"

        # Загрузка релизов только для разрешённых типов
        releases = []
        if use_tested_versions:
            all_releases = load_releases()
            releases = [r for r in all_releases if r.get("version_type") == version_filter]

        version_cache = {}

        # Функция для получения версии
        def get_version(module_name: str) -> str:
            if use_tested_versions:
                module_entries = [r for r in releases if r['module'] == module_name]
                if module_entries:
                    return max(module_entries, key=lambda x: Version(x['version']))['version']
            return None

        # Обработка локальных модулей
        local_versions = []
        for module in POM_MODULES[project]:
            base_name = module.replace("engdb.", "", 1)
            version = get_version(base_name)

            if not version and not use_tested_versions:
                # Парсим только для новейших версий
                url = get_pom_url(module, build=False)
                version = parse_pom_version(url) if url else "URL не задан"

            safe_module = escape_md(module)
            safe_version = escape_md(version) if version else "N/A"
            local_versions.append(f"<{safe_module}.version>{safe_version}</{safe_module}.version>")

        # Обработка сборочных модулей
        build_config = POM_BUILD_MODULES.get(project, {})
        build_lines = ["<properties>", "    <!-- CORE VERSIONS -->"]

        def process_modules(module_list):
            for module in module_list:
                if module == "engdb.help.branch":
                    build_lines.append("    <engdb.help.branch>INSERT NAME</engdb.help.branch>")
                    continue

                base_name = module.replace("engdb.", "", 1)
                version = get_version(base_name)

                if not version and not use_tested_versions:
                    url = get_pom_url(module, build=True)
                    version = parse_pom_version(url) if url else "URL не задан"

                safe_module = escape_md(module)
                safe_version = escape_md(version) if version else "N/A"
                build_lines.append(f"    <{safe_module}.version>{safe_version}</{safe_module}.version>")

        process_modules(build_config.get("CORE", []))
        build_lines.append("    <!-- MODULES VERSIONS -->")
        process_modules(build_config.get("MODULES", []))
        build_lines.append("</properties>")

        # Форматирование сообщения
        elapsed = time.time() - start_time
        now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

        safe_combination = escape_md(combination)
        safe_elapsed = escape_md(f"{elapsed:.2f} сек")
        safe_now = escape_md(now)

        message = (
            f"*Комбинация:* {safe_combination}\n\n"
            f"*Тип версий:* {escape_md(version_type)}\n\n"
            f"*Локальный pom:*\n```\n" + "\n".join(local_versions) + "\n```\n"
            f"*Сборка:*\n```\n" + "\n".join(build_lines) + "\n```\n"
            f"_Время обработки: {safe_elapsed}_\n"
            f"\\(актуально на {safe_now} по МСК\\)"
        )

        await update.message.reply_text(
            message,
            reply_markup=build_main_menu(update.effective_user.id),
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        error_msg = escape_md(f"Ошибка: {str(e)}")
        await update.message.reply_text(error_msg)
    finally:
        context.user_data.clear()


# Обработка подписки
async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    subs = load_subscriptions()

    if user_id in subs["users"]:
        subs["users"].remove(user_id)
        text = "❌ Вы отписались"
    else:
        subs["users"].append(user_id)
        text = "✅ Вы подписались"

    save_subscriptions(subs)
    await update.message.reply_text(text, reply_markup=build_main_menu(user_id))
    return MAIN_MENU


def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    add_release_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["Добавить релиз"]), add_release_start)],
        states={
            ADD_RELEASE_MODULE: [MessageHandler(filters.TEXT, add_release_module)],
            ADD_RELEASE_VERSION: [MessageHandler(filters.TEXT, add_release_version)],
            ADD_RELEASE_DESCRIPTION: [
                MessageHandler(filters.TEXT, add_release_description),
                CommandHandler("skip", skip_description)
            ],
            ADD_RELEASE_TYPE: [MessageHandler(filters.TEXT, add_release_type)]  # Новое состояние
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        map_to_parent={MAIN_MENU: MAIN_MENU},
    )

    get_version_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text(["Получить"]), get_version_start)],
        states={
            GET_PROJECT: [MessageHandler(filters.TEXT, get_project)],
            GET_BUILD_TYPE: [MessageHandler(filters.TEXT, get_build_type)],
            GET_VERSION_TYPE: [MessageHandler(filters.TEXT, get_version_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        map_to_parent={MAIN_MENU: MAIN_MENU},
    )

    main_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                add_release_conv,
                get_version_conv,
                MessageHandler(filters.Text(["Подписаться", "Отписаться"]), handle_subscription),
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(main_handler)
    application.run_polling()


if __name__ == "__main__":
    main()