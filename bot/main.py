import re
import requests
import logging
from bs4 import BeautifulSoup
from packaging.version import Version
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from config import URL, TELEGRAM_TOKEN

# Настройка логирования с поддержкой кириллицы и сохранением в файл
logging.basicConfig(
    filename='../bot.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)

# Конфигурация кнопок: первый уровень -> второй уровень -> ключ продукта
PRODUCT_BUTTONS = {
    "PRV": {"DEV": "cs-eng-proryv-dev", "STAND": "cs-eng-proryv-dev-prv", "PROD": "cs-eng-proryv-proryv_prod"},
    "TMIK": {"DEV": "cs-eng-tmik-dev", "STAND": "cs-eng-tmik-stand_tmik", "PROD": "cs-eng-tmik-prod_tmik"},
    "ECPS": {"DEV": "cs-eng-ecps-dev", "STAND": "cs-eng-ecps-dev_ecps", "PROD": "cs-eng-ecps-prod-ecps"},
    "CM":   {"DEV": "cs-eng-cm-dev", "STAND": "cs-eng-dust3-dev", "PROD": "версия отсутствует"},
    "ITG":  {"DEV": "cs-eng-itg",     "STAND": "версия отсутствует", "PROD": "версия отсутствует"},
}

# Удобная функция для создания клавиатуры с N колонками
def build_keyboard(items: list[str], cols: int = 3) -> ReplyKeyboardMarkup:
    rows = [items[i:i+cols] for i in range(0, len(items), cols)]
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
    product_key = PRODUCT_BUTTONS[product].get(env)
    combination = f"{product} {env}"
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
    else:
        try:
            parsed = parse_index(URL)
            if product_key in parsed:
                latest = parsed[product_key][-1]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                message = f'Комбинация: {combination}\n\nprojectDistr="{product_key}-{latest}"\n\n(актуально на {now})'
            else:
                message = f"Комбинация: {combination}\n\nПродукт {product_key} не найден на сервере."
        except Exception as e:
            logging.exception("Ошибка при получении данных")
            message = f"Ошибка при получении данных: {e}"

    logging.info(f"Ответ бота: {message}")
    await update.message.reply_text(message, reply_markup=FIRST_KEYBOARD)

def main() -> None:
    logging.info("Запуск бота")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.run_polling()

if __name__ == '__main__':
    main()
