import telebot
from telebot import types

TOKEN = '8777407228:AAFJIg2zPMKJFGwk8qzKVa2SWUBUO51qnG8'

bot = telebot.TeleBot(TOKEN)

try:
    bot.remove_webhook()
except Exception:
    pass

# Стартовая картинка с выбором языка
START_PHOTO_URL = 'https://i.ibb.co/Gfj8swsV/Untitled21.jpg'

# Картинка для меню городов (шаг 1: выбор языка)
LANG_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAOBararlqGVoGBD7wKJ6huPpS6f6-YAAuQjaxuXHbFJEu-o-AVVgLYBAAMCAAN5AAM9BA',
    'eng': None,
    'rus': None
}

# Картинка для шага выбора количества (шаг 2: после нажатия на Амбролаури / Они)
CITY_PHOTOS = {
    'geo': 'AgACAgIAAxkBAAONarasx_pBx0qle13mUv0ZopMBy58AAkkgaxvZVbBJDx5fGnJkpvABAAMCAAN5AAM9BA',
    'eng': None,
    'rus': None
}

TEXTS = {
    'geo': {
        'select_city': 'აირჩიეთ ქალაქი',
        'ambrolauri_btn': 'ამბროლაური',
        'oni_btn': 'ონი',
        'back_btn': '⬅️ უკან',
        'how_much': 'რამდენი გინდა?',
        'q05_btn': '0.5 გრ - 16 USDT (40 ლარი)',
        'q1_btn': '1 გრ - 31 USDT (80 ლარი)',
        'q2_btn': '2 გრ - 58 USDT (150 ლარი)',
        'q5_btn': '5 გრ - 135 USDT (350 ლარი)'
    },
    'eng': {
        'select_city': 'Select a location',
        'ambrolauri_btn': 'Ambrolauri',
        'oni_btn': 'Oni',
        'back_btn': '⬅️ Back',
        'how_much': 'How much do you want?',
        'q05_btn': '0.5 g - 16 USDT (40 Lari)',
        'q1_btn': '1 g - 31 USDT (80 Lari)',
        'q2_btn': '2 g - 58 USDT (150 Lari)',
        'q5_btn': '5 g - 135 USDT (350 Lari)'
    },
    'rus': {
        'select_city': 'Выберите город',
        'ambrolauri_btn': 'Амбролаури',
        'oni_btn': 'Они',
        'back_btn': '⬅️ Назад',
        'how_much': 'Сколько ты хочешь?',
        'q05_btn': '0.5 г - 16 USDT (40 Лари)',
        'q1_btn': '1 g - 31 USDT (80 Лари)',
        'q2_btn': '2 g - 58 USDT (150 Лари)',
        'q5_btn': '5 g - 135 USDT (350 Лари)'
    }
}

# Функция отправки
def safe_send(chat_id, message_id, photo_or_url, text, reply_markup):
    if photo_or_url:
        try:
            bot.delete_message(chat_id, message_id)
            bot.send_photo(chat_id, photo=photo_or_url, caption=text, reply_markup=reply_markup)
            return
        except Exception:
            pass

    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    bot.send_message(chat_id, text=text, reply_markup=reply_markup)

# /start
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("ქართული 🇬🇪", callback_data="setlang_geo"),
        types.InlineKeyboardButton("English 🇬🇧", callback_data="setlang_eng"),
        types.InlineKeyboardButton("Русский 🇷🇺", callback_data="setlang_rus")
    )
    bot.send_photo(message.chat.id, photo=START_PHOTO_URL, caption="🌍 Select language / აირჩიეთ ენა / Выберите язык", reply_markup=markup)

# Назад к выбору языка
@bot.callback_query_handler(func=lambda call: call.data == 'nav_main_start')
def nav_main_start(call):
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("ქართული", callback_data="setlang_geo"),
        types.InlineKeyboardButton("English", callback_data="setlang_eng"),
        types.InlineKeyboardButton("Русский", callback_data="setlang_rus")
    )
    safe_send(call.message.chat.id, call.message.id, START_PHOTO_URL, "🌍 Select language / აირჩიეთ ენა / Выберите язык", markup)

# Шаг 1: Выбор языка -> Меню городов
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
        types.InlineKeyboardButton(t['back_btn'], callback_data="nav_main_start")
    )

    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['select_city'], markup)

# Шаг 2: Выбор города -> Меню количества
@bot.callback_query_handler(func=lambda call: call.data.startswith('go_city_'))
def city_click(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_')
    city = parts[2]
    lang = parts[3]

    t = TEXTS[lang]
    photo_file_id = CITY_PHOTOS.get(lang)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t['q05_btn'], callback_data=f"qty_05_{city}_{lang}"),
        types.InlineKeyboardButton(t['q1_btn'], callback_data=f"qty_1_{city}_{lang}"),
        types.InlineKeyboardButton(t['q2_btn'], callback_data=f"qty_2_{city}_{lang}"),
        types.InlineKeyboardButton(t['q5_btn'], callback_data=f"qty_5_{city}_{lang}"),
        types.InlineKeyboardButton(t['back_btn'], callback_data=f"setlang_{lang}")
    )

    safe_send(call.message.chat.id, call.message.id, photo_file_id, t['how_much'], markup)

bot.infinity_polling(skip_pending=True)