import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

# 1. Веб-сервер для проверки работоспособности (Health Check для Render)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Запускаем сервер в отдельном фоновом потоке
threading.Thread(target=run_health_check_server, daemon=True).start()

# 2. Токен бота
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

try:
    bot.remove_webhook()
except Exception:
    pass

# === БЛОК КАРТИНОК ===
START_PHOTO_URL = 'AgACAgIAAxkBAAIBUmq_fDsajOlx-YkNyDqYbIF7QFuRAAJPGmsbQBv5SZLWUpZchATZAQADAgADeQADPQQ'

# 1️⃣ Картинки для меню выбора языка (показываются после выбора языка)
LANG_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAIBYGq_n7n4sDrzHEs1HJYxqE5O8T_vAAJUG2sbQBv5SWRdkmdjCO32AQADAgADeQADPQQ',
    'eng': 'AgACAgIAAxkBAAIBr2rA1DjaQcToRo504eUPYDv9jZsfAALhH2sbzA0JSuhWUxcNELOqAQADAgADeQADPQQ',
    'rus': 'AgACAgIAAxkBAAP1ar9gIm7E-2Ir7MFhW1jXOBmA68YAApwZaxtAG_lJs5Pvj4cqa5YBAAMCAAN5AAM9BA'
}

# 2️⃣ Картинки для городов (зависят от города и языка)
CITY_PHOTOS = {
    'amb': {
        'geo': 'AgACAgIAAxkBAAIBN2q_eL3G25yipRjnmv59C2o3u1u-AAIvGmsbQBv5SUguXSzghEIAAQEAAwIAA3kAAz0E',
        'eng': 'AgACAgIAAxkBAAIBIWq_cs2DUgLW7d_nxUJZsz6gT4VVAAMaaxtAG_lJSJZ10cAWqoIBAAMCAAN5AAM9BA',
        'rus': 'AgACAgIAAxkBAAIBFWq_cdSK_TodBOVK3xt9amHk7O6NAAL7GWsbQBv5SUUx2XJB3nfCAQADAgADeQADPQQ'
    },
    'oni': {
        'geo': 'AgACAgIAAxkBAAIBN2q_eL3G25yipRjnmv59C2o3u1u-AAIvGmsbQBv5SUguXSzghEIAAQEAAwIAA3kAAz0E',
        'eng': 'AgACAgIAAxkBAAIBIWq_cs2DUgLW7d_nxUJZsz6gT4VVAAMaaxtAG_lJSJZ10cAWqoIBAAMCAAN5AAM9BA',
        'rus': 'AgACAgIAAxkBAAIBFWq_cdSK_TodBOVK3xt9amHk7O6NAAL7GWsbQBv5SUUx2XJB3nfCAQADAgADeQADPQQ'
    }
}

# 3️⃣ Картинки для разделов «Подарок»
GIFT_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAIB4WrBx-Ka1RIDWUHRRb2tDZoiibNrAAJhG2sb_44RSigSkXTC1cvKAQADAgADeQADPQQ',
    'eng': 'AgACAgIAAxkBAAIB32rBx95PvWSAU4S4dzyXoklrHBQVAAJgG2sb_44RSjndeYhy3nr6AQADAgADeQADPQQ',
    'rus': 'AgACAgIAAxkBAAIB3WrBx9kSqxhilmFiEGASEvaTnAVRAAJfG2sb_44RSr_9z3haPjsUAQADAgADeQADPQQ'
}

CITIES = {
    'amb': {'geo': 'ამბროლაური', 'eng': 'Ambrolauri', 'rus': 'Амбролаури'},
    'oni': {'geo': 'ონი', 'eng': 'Oni', 'rus': 'Они'}
}

QUANTITIES = {
    '05': {'geo': '0.5 გრ', 'eng': '0.5 g', 'rus': '0.5 г', 'price': '16 USDT (40 GEL)'},
    '1': {'geo': '1 გრ', 'eng': '1 g', 'rus': '1 г', 'price': '31 USDT (80 GEL)'},
    '2': {'geo': '2 გრ', 'eng': '2 g', 'rus': '2 г', 'price': '58 USDT (150 GEL)'},
    '5': {'geo': '5 გრ', 'eng': '5 g', 'rus': '5 г', 'price': '135 USDT (350 GEL)'}
}

TEXTS = {
    'geo': {
        'select_city': 'აირჩიეთ ქალაქი',
        'ambrolauri_btn': 'ამბროლაური',
        'oni_btn': 'ონი',
        'gift_btn': '🎁 საჩუქარი',
        'back_btn': '⬅️ უკან',
        'how_much': 'აირჩიე რაოდენობა!',
        'q05_btn': '0.5 გრ - 16 USDT (40 GEL)',
        'q1_btn': '1 გრ - 31 USDT (80 GEL)',
        'q2_btn': '2 გრ - 58 USDT (150 GEL)',
        'q5_btn': '5 გრ - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 საჩუქრის პირობა:\n\n"
            "1. იყიდე 10 - ჯერ და მიიღე მე-11 საჩუქრად;\n"
            "2. მოიწვიე 10 მეგობარი, რომლებიც მინიმუმ ერთხელ იყიდიან და ასევე მიიღე 1 გრ საჩუქრად."
        ),
        'checkout_text': "არჩეული გაქვს ქალაქი **{city}**, რაოდენობა **{qty}**, ფასია **{price}**. გადაამოწმე! თუ ყველაფერი სწორია, დააჭირე გადახდას!",
        'pay_btn': "💳 გადახდა ({price})",
        'how_to_pay_btn': "ℹ️ როგორ გადაიხდო მარტივად"
    },
    'eng': {
        'select_city': 'Select a location',
        'ambrolauri_btn': 'Ambrolauri',
        'oni_btn': 'Oni',
        'gift_btn': '🎁 Gift',
        'back_btn': '⬅️ Back',
        'how_much': 'Select the quantity!',
        'q05_btn': '0.5 g - 16 USDT (40 GEL)',
        'q1_btn': '1 g - 31 USDT (80 GEL)',
        'q2_btn': '2 g - 58 USDT (150 GEL)',
        'q5_btn': '5 g - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 Gift Offer\n\n"
            "1. Buy 10 times and get the 11th for free as a gift;\n"
            "2. Invite 10 friends who make at least 1 purchase and get 1 g as a gift."
        ),
        'checkout_text': "You selected city **{city}**, quantity **{qty}**, price **{price}**. Double check! If everything is correct, click payment!",
        'pay_btn': "💳 Pay ({price})",
        'how_to_pay_btn': "ℹ️ How to pay easily"
    },
    'rus': {
        'select_city': 'Выберите город',
        'ambrolauri_btn': 'Амбролаури',
        'oni_btn': 'Они',
        'gift_btn': '🎁 Подарок',
        'back_btn': '⬅️ Назад',
        'how_much': 'Выбери количество!',
        'q05_btn': '0.5 г - 16 USDT (40 GEL)',
        'q1_btn': '1 г - 31 USDT (80 GEL)',
        'q2_btn': '2 г - 58 USDT (150 GEL)',
        'q5_btn': '5 г - 135 USDT (350 GEL)',
        'gift_info': (
            "🎁 Условия подарка:\n\n"
            "1. Купи 10 раз и получи 11-ый в подарок.\n"
            "2. Пригласи 10 друзей, которые хотя бы 1 раз купят и получи подарок."
        ),
        'checkout_text': "Ты выбрал город **{city}**, количество **{qty}**, цена **{price}**. Перепроверь! Если все верно, то жми оплату!",
        'pay_btn': "💳 Оплата ({price})",
        'how_to_pay_btn': "ℹ Как легко оплатить"
    }
}

def safe_send(chat_id, message_id, photo_or_url, text, reply_markup, parse_mode=None):
    if photo_or_url:
        try:
            bot.delete_message(chat_id, message_id)
            bot.send_photo(chat_id, photo=photo_or_url, caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
            return
        except Exception:
            pass
            
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    bot.send_message(chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇬🇪 ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_rus")
    )
    safe_send(message.chat.id, None, START_PHOTO_URL, "🌍 Select language / აირჩიეთ ენა / Выберите язык", markup)

@bot.callback_query_handler(func=lambda call: call.data == 'nav_main_start')
def nav_main_start(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇬🇪 ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_rus")
    )
    safe_send(call.message.chat.id, call.message.id, START_PHOTO_URL, "🌍 Select language / აირჩიეთ ენა / Выберите язык", markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def set_language(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[1]
    t = TEXTS[lang]
    photo_file_id = LANG_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['ambrolauri_btn'], callback_data=f"go_city_amb_{lang}"),
        types.InlineKeyboardButton(t['oni_btn'], callback_data=f"go_city_oni_{lang}"),
        types.InlineKeyboardButton(t['gift_btn'], callback_data=f"show_gift_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data="nav_main_start")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['select_city'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('show_gift_'))
def show_gift_info(call):
    bot.answer_callback_query(call.id)
    lang = call.data.split('_')[2]
    t = TEXTS[lang]
    gift_photo_id = GIFT_PHOTOS.get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, gift_photo_id, t['gift_info'], markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('go_city_'))
def city_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    city = parts[2]
    lang = parts[3]
    
    t = TEXTS[lang]
    photo_file_id = CITY_PHOTOS.get(city, {}).get(lang)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['q05_btn'], callback_data=f"qty_05_{city}_{lang}"),
        types.InlineKeyboardButton(t['q1_btn'], callback_data=f"qty_1_{city}_{lang}"),
        types.InlineKeyboardButton(t['q2_btn'], callback_data=f"qty_2_{city}_{lang}"),
        types.InlineKeyboardButton(t['q5_btn'], callback_data=f"qty_5_{city}_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )
    
    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['how_much'], markup)

# Выбор количества товара
@bot.callback_query_handler(func=lambda call: call.data.startswith('qty_'))
def qty_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    qty_key = parts[1]
    city_key = parts[2]
    lang = parts[3]
    
    t = TEXTS[lang]
    city_name = CITIES[city_key][lang]
    qty_info = QUANTITIES[qty_key]
    qty_name = qty_info[lang]
    price = qty_info['price']
    
    text = t['checkout_text'].format(
        city=city_name,
        qty=qty_name,
        price=price
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['pay_btn'].format(price=price), callback_data=f"pay_{qty_key}_{city_key}_{lang}"),
        types.InlineKeyboardButton(t['how_to_pay_btn'], callback_data=f"howpay_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"go_city_{city_key}_{lang}")
    )
    
    photo_file_id = CITY_PHOTOS.get(city_key, {}).get(lang)
    safe_send(call.message.chat.id, call.message.id, photo_file_id, text, markup, parse_mode='Markdown')

# Заглушка для "Как легко оплатить"
@bot.callback_query_handler(func=lambda call: call.data.startswith('howpay_'))
def how_pay_click(call):
    bot.answer_callback_query(call.id, "Инструкция появится позже", show_alert=True)

# Заглушка для "Оплата"
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def pay_click(call):
    bot.answer_callback_query(call.id, "Переход к оплате появится позже", show_alert=True)

# Обработчик сжатых фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id
    bot.send_message(message.chat.id, f"ID картинки:\n\n{file_id}")

# Обработчик документов
@bot.message_handler(content_types=['document'])
def handle_document(message):
    file_id = message.document.file_id
    bot.send_message(message.chat.id, f"ID файла:\n\n{file_id}")

# Авто-перезапуск бота при сбоях сети
while True:
    try:
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        time.sleep(5)
