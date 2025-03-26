import os
import re
import requests
import logging
import time
from bs4 import BeautifulSoup
from packaging.version import Version
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


from config import URL, TELEGRAM_TOKEN, PRODUCT_BUTTONS, POM_MODULES, POM_BUILD_MODULES, UNIFIED_POM_URLS

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    user = update.effective_user
    logging.info(f"Пользователь {user.full_name} начал работу через /start")
    await update.message.reply_text("Выберите продукт:", reply_markup=FIRST_KEYBOARD)


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    user_data = context.user_data
    logging.info(f"Пользователь выбрал: {text}")
    if 'product' not in user_data:
        if text in PRODUCT_BUTTONS:
            user_data['product'] = text
            second_keyboard = build_keyboard(list(PRODUCT_BUTTONS[text].keys()), cols=3)
            await update.message.reply_text(f"{text}: выберите среду:", reply_markup=second_keyboard)
        else:
            await send_version(update, text)
        return
    product = user_data.pop('product')
    env = text
    combination = f"{product} {env}"
    if env == "POM":
        await send_pom_version(update, product, combination=combination)
        return
    product_key = PRODUCT_BUTTONS[product].get(env)
    if product_key:
        await send_version(update, product_key, combination=combination)
    else:
        await update.message.reply_text("Неверный выбор среды. Попробуйте /start.", reply_markup=FIRST_KEYBOARD)


async def send_version(update: Update, product_key: str, combination: str = None) -> None:
    if not combination:
        combination = product_key
    logging.info(f"Запрошена комбинация: {combination}")

    # Экранируем специальные символы MarkdownV2
    safe_combination = combination.replace(".", r"\.").replace("-", r"\-")

    if product_key == "версия отсутствует":
        message = rf"*Комбинация:* {safe_combination}\nВерсия отсутствует для выбранной комбинации\."
        await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD, parse_mode="MarkdownV2")
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
        await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD, parse_mode="MarkdownV2")

    except Exception as e:
        logging.exception("Ошибка при получении данных")
        error_message = f"Ошибка при получении данных: {str(e)}"
        await update.message.reply_text(error_message.replace(".", r"\."), reply_markup=FIRST_KEYBOARD,
                                        parse_mode="MarkdownV2")


async def send_pom_version(update: Update, product: str, combination: str) -> None:
    logging.info(f"Запрошена комбинация POM для продукта: {product}")
    if product not in POM_MODULES:
        message = f"Комбинация: {combination}\n\nСборка POM не поддерживается для выбранного продукта."
        await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD)
        return

    await update.message.reply_text("Начинаю сбор информации, подождите, пожалуйста...")

    start_time = time.time()
    version_cache = {}  # Кэш для хранения версий модулей

    try:
        # Обработка локальных модулей
        local_versions = []
        for module in POM_MODULES[product]:
            base_name = module.replace("engdb.", "", 1)  # Нормализуем имя
            if base_name in version_cache:
                version = version_cache[base_name]
            else:
                url = get_pom_url(module, build=False)
                version = parse_pom_version(url) if url else "URL не задан"
                version_cache[base_name] = version
            local_versions.append(f"<{module}.version>{version}</{module}.version>")

        # Обработка сборочных модулей
        build_config = POM_BUILD_MODULES.get(product, {})
        build_lines = ["<properties>", "    <!-- CORE VERSIONS -->"]

        for module in build_config.get("CORE", []):
            if module == "engdb.help.branch":
                build_lines.append("    <engdb.help.branch.version>INSERT NAME</engdb.help.branch.version>")
                continue

            base_name = module.replace("engdb.", "", 1)
            if base_name in version_cache:
                version = version_cache[base_name]
            else:
                url = get_pom_url(module, build=True)
                version = parse_pom_version(url) if url else "URL не задан"
                version_cache[base_name] = version
            build_lines.append(f"    <{module}.version>{version}</{module}.version>")

        build_lines.append("    <!-- MODULES VERSIONS -->")
        for module in build_config.get("MODULES", []):
            base_name = module.replace("engdb.", "", 1)
            if base_name in version_cache:
                version = version_cache[base_name]
            else:
                url = get_pom_url(module, build=True)
                version = parse_pom_version(url) if url else "URL не задан"
                version_cache[base_name] = version
            build_lines.append(f"    <{module}.version>{version}</{module}.version>")

        build_lines.append("</properties>")

        # Форматирование сообщения
        elapsed = time.time() - start_time
        now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

        # Экранирование специальных символов
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
            reply_markup=FIRST_KEYBOARD,
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        error_msg = f"Ошибка: {str(e)}".replace(".", r"\.")
        await update.message.reply_text(
            error_msg,
            reply_markup=FIRST_KEYBOARD,
            parse_mode="MarkdownV2"
        )


def main() -> None:
    logging.info("Запуск бота")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.run_polling()


if __name__ == '__main__':
    main()
