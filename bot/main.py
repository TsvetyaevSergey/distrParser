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

# Импорт Selenium для работы с динамически загружаемым контентом
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import URL, TELEGRAM_TOKEN

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

# Конфигурация кнопок: первый уровень -> второй уровень -> ключ продукта
PRODUCT_BUTTONS = {
    "PRV": {"DEV": "cs-eng-proryv-dev", "STAND": "cs-eng-proryv-dev-prv", "PROD": "cs-eng-proryv-proryv_prod",
            "POM": "POM"},
    "TMIK": {"DEV": "cs-eng-tmik-dev", "STAND": "cs-eng-tmik-stand_tmik", "PROD": "cs-eng-tmik-prod_tmik",
             "POM": "POM"},
    "ECPS": {"DEV": "cs-eng-ecps-dev", "STAND": "cs-eng-ecps-dev_ecps", "PROD": "cs-eng-ecps-prod-ecps", "POM": "POM"},
    "CM": {"DEV": "cs-eng-cm-dev", "STAND": "cs-eng-dust3-dev", "PROD": "версия отсутствует", "POM": "POM"},
    "ITG": {"DEV": "cs-eng-itg", "STAND": "версия отсутствует", "PROD": "версия отсутствует", "POM": "POM"},
}

# Модули, необходимые для сборки POM для каждого продукта.
POM_MODULES = {
    "PRV": ["engbe", "glo", "itg", "dms", "dpd", "cm", "ped"],
    # При необходимости можно добавить конфигурацию для других продуктов.
}

# URL для каждого модуля POM
POM_URLS = {
    "glo": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-glo",
    "itg": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-itg",
    "dms": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-dms",
    "dpd": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-dpd",
    "cm": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-cm",
    "ped": "https://mvn.cstechnology.ru/#/releases/ru/cs/cs-ped",
    "engbe": "https://mvn.cstechnology.ru/#/releases/ru/cs/engbe",
}


# Функция для создания клавиатуры с N колонками
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
    Для получения динамически загружаемого содержимого используем Selenium.
    Необходимы: установка selenium и наличие chromedriver.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        # Ожидаем появления элемента с классом "card-editor"
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "card-editor")))
        page_source = driver.page_source
    finally:
        driver.quit()
    soup = BeautifulSoup(page_source, "html.parser")
    card = soup.find("div", class_="card-editor")
    if card:
        pre = card.find("pre")
        if pre:
            text = pre.get_text()
            match = re.search(r"<version>([^<]+)</version>", text)
            if match:
                return match.group(1).strip()
    raise ValueError("Версия не найдена на странице")


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

    if product_key == "версия отсутствует":
        message = f"Комбинация: {combination}\nВерсия отсутствует для выбранной комбинации."
        await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD)
        return

    try:
        parsed = parse_index(URL)
        if product_key in parsed:
            latest = parsed[product_key][-1]
            now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
            # Экранируем кавычки и оборачиваем строку в <pre>
            distr_line = f'projectDistr="{product_key}-{latest}"'
            code_block = f"<pre>{distr_line}</pre>"
            message = (f"Комбинация: {combination}\n\n{code_block}\n\n"
                       f"(актуально на {now} по МСК)")
        else:
            message = f"Комбинация: {combination}\n\nПродукт {product_key} не найден на сервере."
    except Exception as e:
        logging.exception("Ошибка при получении данных")
        message = f"Ошибка при получении данных: {e}"

    logging.info(f"Ответ бота: {message}")
    await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD, parse_mode="HTML")



async def send_pom_version(update: Update, product: str, combination: str) -> None:
    logging.info(f"Запрошена комбинация POM для продукта: {product}")
    if product not in POM_MODULES:
        message = f"Комбинация: {combination}\n\nСборка POM не поддерживается для выбранного продукта."
        await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD)
        return

    await update.message.reply_text("Начинаю сбор информации, подождите, пожалуйста...")

    start_time = time.time()
    modules = POM_MODULES[product]
    version_lines = []
    try:
        for module in modules:
            url = POM_URLS.get(module)
            if not url:
                version = "URL не задан"
            else:
                version = parse_pom_version(url)
            # Экранируем угловые скобки
            version_line = f"&lt;{module}.version&gt;{version}&lt;/{module}.version&gt;"
            version_lines.append(version_line)

        elapsed = time.time() - start_time
        now = (datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

        # Собираем блок кода
        code_block = "<pre>" + "\n".join(version_lines) + "\n</pre>"
        message = (f"Комбинация: {combination}\n\n{code_block}\n\n"
                   f"Сбор информации заняла {elapsed:.2f} секунд\n\n"
                   f"(актуально на {now} по МСК)")
    except Exception as e:
        logging.exception("Ошибка при получении POM данных")
        message = f"Ошибка при получении данных для POM: {e}"

    logging.info(f"Ответ бота для POM: {message}")
    await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD, parse_mode="HTML")



def main() -> None:
    logging.info("Запуск бота")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.run_polling()


if __name__ == '__main__':
    main()
